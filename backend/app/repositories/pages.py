import sqlite3

from app.repositories.base import Record, as_record, update_row

_WRITABLE = frozenset(
    {"title", "description", "text", "content_hash", "status_code", "doc_length", "crawled_at"}
)


class PageRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self,
        site_id: int,
        url: str,
        title: str,
        description: str,
        text: str,
        content_hash: str | None,
        status_code: int | None,
        crawled_at: str | None,
        now: str,
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO pages (site_id, url, title, description, text, content_hash, status_code,"
            " crawled_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (site_id, url, title, description, text, content_hash, status_code, crawled_at, now, now),
        )
        return int(cursor.lastrowid or 0)

    def get(self, page_id: int) -> Record | None:
        return as_record(self._conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone())

    def get_by_url(self, url: str) -> Record | None:
        return as_record(self._conn.execute("SELECT * FROM pages WHERE url = ?", (url,)).fetchone())

    def list_items(
        self, limit: int, offset: int, site_id: int | None = None
    ) -> tuple[list[Record], int]:
        where, params = "", []
        if site_id is not None:
            where, params = "WHERE site_id = ?", [site_id]
        total = self._conn.execute(f"SELECT COUNT(*) FROM pages {where}", params).fetchone()[0]
        rows = self._conn.execute(
            "SELECT id, site_id, url, title, description, content_hash, status_code, doc_length,"
            f" crawled_at, created_at, updated_at FROM pages {where} ORDER BY id LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [dict(row) for row in rows], total

    def update(self, page_id: int, changes: Record, now: str) -> None:
        update_row(self._conn, "pages", page_id, changes, _WRITABLE, now)

    def delete(self, page_id: int) -> bool:
        return self._conn.execute("DELETE FROM pages WHERE id = ?", (page_id,)).rowcount > 0

    def iter_all(self) -> sqlite3.Cursor:
        return self._conn.execute("SELECT id, title, description, text FROM pages ORDER BY id")

    def with_site(self, page_ids: list[int]) -> dict[int, Record]:
        if not page_ids:
            return {}
        marks = ",".join("?" * len(page_ids))
        rows = self._conn.execute(
            "SELECT p.id, p.url, p.title, p.description, p.text, s.id AS site_id,"
            " s.title AS site_title, s.base_domain, s.tag_list FROM pages p"
            f" JOIN sites s ON s.id = p.site_id WHERE p.id IN ({marks})",
            page_ids,
        ).fetchall()
        return {row["id"]: dict(row) for row in rows}
