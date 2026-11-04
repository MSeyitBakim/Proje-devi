import sqlite3

from app.repositories.base import Record, as_record


class RobotsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_valid(self, origin: str, now: str) -> Record | None:
        return as_record(
            self._conn.execute(
                "SELECT * FROM robots_cache WHERE origin = ? AND expires_at > ?", (origin, now)
            ).fetchone()
        )

    def put(
        self,
        origin: str,
        status_code: int | None,
        body: str,
        unreachable: bool,
        fetched_at: str,
        expires_at: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO robots_cache (origin, status_code, body, unreachable, fetched_at, expires_at)"
            " VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (origin) DO UPDATE SET status_code = excluded.status_code,"
            " body = excluded.body, unreachable = excluded.unreachable,"
            " fetched_at = excluded.fetched_at, expires_at = excluded.expires_at",
            (origin, status_code, body, int(unreachable), fetched_at, expires_at),
        )
