import json
import sqlite3

from app.repositories.base import Record, as_record, update_row

_WRITABLE = frozenset({"title", "main_url", "base_domain", "description"})


class SiteRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self, title: str, main_url: str, base_domain: str, description: str, now: str
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO sites (title, main_url, base_domain, description, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (title, main_url, base_domain, description, now, now),
        )
        return int(cursor.lastrowid or 0)

    def get(self, site_id: int) -> Record | None:
        return as_record(self._conn.execute("SELECT * FROM sites WHERE id = ?", (site_id,)).fetchone())

    def get_by_base_domain(self, domain: str) -> Record | None:
        return as_record(
            self._conn.execute("SELECT * FROM sites WHERE base_domain = ?", (domain,)).fetchone()
        )

    def list_items(self, limit: int, offset: int, tag_id: int | None = None) -> tuple[list[Record], int]:
        where, params = "", []
        if tag_id is not None:
            where = "WHERE id IN (SELECT site_id FROM site_tags WHERE tag_id = ?)"
            params = [tag_id]
        total = self._conn.execute(f"SELECT COUNT(*) FROM sites {where}", params).fetchone()[0]
        rows = self._conn.execute(
            f"SELECT * FROM sites {where} ORDER BY title COLLATE NOCASE, id LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [dict(row) for row in rows], total

    def update(self, site_id: int, changes: Record, now: str) -> None:
        update_row(self._conn, "sites", site_id, changes, _WRITABLE, now)

    def delete(self, site_id: int) -> bool:
        return self._conn.execute("DELETE FROM sites WHERE id = ?", (site_id,)).rowcount > 0

    def set_tags(self, site_id: int, tag_ids: list[int], now: str) -> None:
        self._conn.execute("DELETE FROM site_tags WHERE site_id = ?", (site_id,))
        self._conn.executemany(
            "INSERT INTO site_tags (site_id, tag_id) VALUES (?, ?)",
            [(site_id, tag_id) for tag_id in tag_ids],
        )
        self.refresh_tag_list(site_id, now)

    def refresh_tag_list(self, site_id: int, now: str) -> None:
        """tag_list is a derived cache of site_tags; it is only ever written from there."""
        titles = [
            row[0]
            for row in self._conn.execute(
                "SELECT t.title FROM site_tags st JOIN tags t ON t.id = st.tag_id "
                "WHERE st.site_id = ? ORDER BY t.normalized_title",
                (site_id,),
            )
        ]
        self._conn.execute(
            "UPDATE sites SET tag_list = ?, updated_at = ? WHERE id = ?",
            (json.dumps(titles, ensure_ascii=False), now, site_id),
        )
