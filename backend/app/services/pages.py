import hashlib
import sqlite3
from sqlite3 import IntegrityError

from app.core.config import Settings
from app.core.exceptions import ConflictError, InvalidInputError, NotFoundError
from app.core.timeutil import to_iso, utcnow
from app.core.urls import base_domain, normalize_url, origin_of
from app.db.session import transaction
from app.repositories.base import Record
from app.repositories.pages import PageRepository
from app.repositories.sites import SiteRepository
from app.services.indexing.indexer import Indexer
from app.services.indexing.stopwords import build_stop_words


def content_hash(title: str, description: str, text: str) -> str:
    digest = hashlib.sha256()
    for part in (title, description, text):
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


class PageService:
    def __init__(self, conn: sqlite3.Connection, settings: Settings) -> None:
        self._conn = conn
        self._pages = PageRepository(conn)
        self._sites = SiteRepository(conn)
        self._indexer = Indexer(conn, build_stop_words(settings.extra_stop_words))

    def create(self, site_id: int, url: str, title: str, description: str, text: str) -> Record:
        canonical = normalize_url(url)
        site = self._sites.get(site_id)
        if site is None:
            raise NotFoundError(f"Site {site_id} not found")
        if base_domain(canonical) != site["base_domain"]:
            raise InvalidInputError(f"URL host does not match site domain '{site['base_domain']}'")
        now = to_iso(utcnow())
        try:
            with transaction(self._conn):
                page_id = self._pages.create(
                    site_id, canonical, title, description, text,
                    content_hash(title, description, text), None, None, now,
                )
                self._indexer.index_page(page_id, title, description, text, now)
        except IntegrityError as exc:
            raise ConflictError("A page with this URL already exists") from exc
        return self.get(page_id)

    def get(self, page_id: int) -> Record:
        page = self._pages.get(page_id)
        if page is None:
            raise NotFoundError(f"URL {page_id} not found")
        return page

    def list_items(self, page: int, limit: int, site_id: int | None = None) -> tuple[list[Record], int]:
        return self._pages.list_items(limit, (page - 1) * limit, site_id)

    def update(self, page_id: int, changes: Record) -> Record:
        current = self.get(page_id)
        merged = {k: changes.get(k, current[k]) for k in ("title", "description", "text")}
        now = to_iso(utcnow())
        with transaction(self._conn):
            self._pages.update(
                page_id, {**merged, "content_hash": content_hash(**merged)}, now
            )
            self._indexer.index_page(page_id, merged["title"], merged["description"], merged["text"], now)
        return self.get(page_id)

    def delete(self, page_id: int) -> None:
        self.get(page_id)
        with transaction(self._conn):
            self._pages.delete(page_id)

    def save_crawled(
        self, url: str, title: str, description: str, text: str, status_code: int, crawled_at: str
    ) -> tuple[int, bool]:
        """Upsert a crawled page, creating its site on first contact. Returns (page_id, reindexed).

        Unchanged content only refreshes crawl metadata; changed content replaces the postings.
        """
        digest = content_hash(title, description, text)
        now = to_iso(utcnow())
        with transaction(self._conn):
            domain = base_domain(url)
            site = self._sites.get_by_base_domain(domain)
            site_id = (
                site["id"]
                if site
                else self._sites.create(title or domain, origin_of(url) + "/", domain, "", now)
            )
            existing = self._pages.get_by_url(url)
            if existing and existing["content_hash"] == digest:
                self._pages.update(
                    existing["id"], {"status_code": status_code, "crawled_at": crawled_at}, now
                )
                return existing["id"], False
            if existing:
                page_id = existing["id"]
                self._pages.update(
                    page_id,
                    {"title": title, "description": description, "text": text,
                     "content_hash": digest, "status_code": status_code, "crawled_at": crawled_at},
                    now,
                )
            else:
                page_id = self._pages.create(
                    site_id, url, title, description, text, digest, status_code, crawled_at, now
                )
            self._indexer.index_page(page_id, title, description, text, now)
            return page_id, True

    def rebuild_index(self) -> int:
        with transaction(self._conn):
            return self._indexer.rebuild(to_iso(utcnow()))
