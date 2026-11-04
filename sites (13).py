import sqlite3
from sqlite3 import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError
from app.core.timeutil import to_iso, utcnow
from app.core.urls import base_domain, normalize_url
from app.db.session import transaction
from app.repositories.base import Record
from app.repositories.sites import SiteRepository
from app.services.tags import TagService, serialize_site


class SiteService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._sites = SiteRepository(conn)
        self._tags = TagService(conn)

    def create(self, title: str, main_url: str, description: str, tags: list[str]) -> Record:
        url = normalize_url(main_url)
        now = to_iso(utcnow())
        try:
            with transaction(self._conn):
                site_id = self._sites.create(title, url, base_domain(url), description, now)
                self._apply_tags(site_id, tags, now)
        except IntegrityError as exc:
            raise ConflictError("A site with this URL or domain already exists") from exc
        return self.get(site_id)

    def get(self, site_id: int) -> Record:
        site = self._sites.get(site_id)
        if site is None:
            raise NotFoundError(f"Site {site_id} not found")
        return serialize_site(site)

    def list_items(self, page: int, limit: int, tag_id: int | None = None) -> tuple[list[Record], int]:
        rows, total = self._sites.list_items(limit, (page - 1) * limit, tag_id)
        return [serialize_site(row) for row in rows], total

    def update(self, site_id: int, changes: Record) -> Record:
        self.get(site_id)
        changes = {k: v for k, v in changes.items() if v is not None}
        fields = {k: v for k, v in changes.items() if k in {"title", "description"}}
        if "main_url" in changes:
            url = normalize_url(changes["main_url"])
            fields["main_url"], fields["base_domain"] = url, base_domain(url)
        now = to_iso(utcnow())
        try:
            with transaction(self._conn):
                if fields:
                    self._sites.update(site_id, fields, now)
                if "tags" in changes:
                    self._apply_tags(site_id, changes["tags"], now)
        except IntegrityError as exc:
            raise ConflictError("A site with this URL or domain already exists") from exc
        return self.get(site_id)

    def delete(self, site_id: int) -> None:
        """Cascades to the site's pages; their postings and statistics are cleaned by triggers."""
        self.get(site_id)
        with transaction(self._conn):
            self._sites.delete(site_id)

    def _apply_tags(self, site_id: int, titles: list[str], now: str) -> None:
        tag_ids = list(dict.fromkeys(self._tags.get_or_create(title, now) for title in titles))
        self._sites.set_tags(site_id, tag_ids, now)
