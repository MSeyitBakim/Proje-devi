import json
import sqlite3
from sqlite3 import IntegrityError

from app.core.exceptions import ConflictError, InvalidInputError, NotFoundError
from app.core.timeutil import to_iso, utcnow
from app.db.session import transaction
from app.repositories.base import Record
from app.repositories.sites import SiteRepository
from app.repositories.tags import TagRepository
from app.services.indexing.text import normalize_label


def clean_tag_title(title: str) -> tuple[str, str]:
    display = " ".join(title.split())
    normalized = normalize_label(display)
    if not normalized:
        raise InvalidInputError("Tag title must not be empty")
    return display, normalized


class TagService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._tags = TagRepository(conn)
        self._sites = SiteRepository(conn)

    def get_or_create(self, title: str, now: str) -> int:
        display, normalized = clean_tag_title(title)
        existing = self._tags.get_by_normalized(normalized)
        return existing["id"] if existing else self._tags.create(display, normalized, now)

    def create(self, title: str) -> Record:
        display, normalized = clean_tag_title(title)
        now = to_iso(utcnow())
        try:
            with transaction(self._conn):
                tag_id = self._tags.create(display, normalized, now)
        except IntegrityError as exc:
            raise ConflictError(f"Tag '{display}' already exists") from exc
        return self.get(tag_id)

    def get(self, tag_id: int) -> Record:
        tag = self._tags.get(tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")
        return tag

    def list_items(self, page: int, limit: int) -> tuple[list[Record], int]:
        return self._tags.list_items(limit, (page - 1) * limit)

    def rename(self, tag_id: int, title: str) -> Record:
        self.get(tag_id)
        display, normalized = clean_tag_title(title)
        now = to_iso(utcnow())
        try:
            with transaction(self._conn):
                self._tags.update(tag_id, {"title": display, "normalized_title": normalized}, now)
                for site_id in self._tags.site_ids_for_tag(tag_id):
                    self._sites.refresh_tag_list(site_id, now)
        except IntegrityError as exc:
            raise ConflictError(f"Tag '{display}' already exists") from exc
        return self.get(tag_id)

    def delete(self, tag_id: int) -> None:
        self.get(tag_id)
        now = to_iso(utcnow())
        with transaction(self._conn):
            affected = self._tags.site_ids_for_tag(tag_id)
            self._tags.delete(tag_id)
            for site_id in affected:
                self._sites.refresh_tag_list(site_id, now)


def serialize_site(site: Record) -> Record:
    return {**site, "tags": json.loads(site["tag_list"])}
