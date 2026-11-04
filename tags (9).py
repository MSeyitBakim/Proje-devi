import sqlite3

from app.repositories.base import Record, as_record, update_row


class TagRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, title: str, normalized_title: str, now: str) -> int:
        cursor = self._conn.execute(
            "INSERT INTO tags (title, normalized_title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, normalized_title, now, now),
        )
        return int(cursor.lastrowid or 0)

    def get(self, tag_id: int) -> Record | None:
        return as_record(self._conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone())

    def get_by_normalized(self, normalized_title: str) -> Record | None:
        return as_record(
            self._conn.execute(
                "SELECT * FROM tags WHERE normalized_title = ?", (normalized_title,)
            ).fetchone()
        )

    def list_items(self, limit: int, offset: int) -> tuple[list[Record], int]:
        total = self._conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
        rows = self._conn.execute(
            "SELECT * FROM tags ORDER BY normalized_title, id LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [dict(row) for row in rows], total

    def update(self, tag_id: int, changes: Record, now: str) -> None:
        update_row(self._conn, "tags", tag_id, changes, frozenset({"title", "normalized_title"}), now)

    def delete(self, tag_id: int) -> bool:
        return self._conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,)).rowcount > 0

    def site_ids_for_tag(self, tag_id: int) -> list[int]:
        rows = self._conn.execute(
            "SELECT site_id FROM site_tags WHERE tag_id = ? ORDER BY site_id", (tag_id,)
        ).fetchall()
        return [row[0] for row in rows]
