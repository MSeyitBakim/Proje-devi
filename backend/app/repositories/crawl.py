import sqlite3
from collections.abc import Iterator
from datetime import datetime

from app.core.exceptions import InvalidStateError
from app.core.timeutil import after, to_iso
from app.repositories.base import Record, as_record
from app.services.bloom import SeenUrlFilter

_JOB_TRANSITIONS = {
    "queued": {"running", "failed"},
    "running": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


class CrawlQueue:
    """SQLite-backed persistent URL frontier. The database is the only authoritative state."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        max_attempts: int = 3,
        retry_base_s: float = 60.0,
        lease_s: float = 300.0,
        seen: SeenUrlFilter | None = None,
    ) -> None:
        self._conn = conn
        self._max_attempts = max_attempts
        self._retry_base_s = retry_base_s
        self._lease_s = lease_s
        self._seen = seen or SeenUrlFilter()

    def enqueue_url(
        self, url: str, now: datetime, *, job_id: int | None = None, depth: int = 0,
        force: bool = False,
    ) -> bool:
        """Insert a URL. Returns True when a new row was created (or force reset one)."""
        stamp = to_iso(now)
        cursor = self._conn.execute(
            "INSERT OR IGNORE INTO crawl_urls (url, job_id, depth, next_attempt_at, created_at,"
            " updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (url, job_id, depth, stamp, stamp, stamp),
        )
        self._seen.add(url)
        if cursor.rowcount:
            return True
        if not force:
            return False
        existing = self._conn.execute(
            "SELECT status FROM crawl_urls WHERE url = ?", (url,)
        ).fetchone()
        if existing["status"] == "in_progress":
            return False
        self._conn.execute(
            "UPDATE crawl_urls SET status = 'pending', job_id = ?, depth = ?, attempts = 0,"
            " last_error = NULL, next_attempt_at = ?, claimed_at = NULL, updated_at = ?"
            " WHERE url = ?",
            (job_id, depth, stamp, stamp, url),
        )
        return True

    def check_visited(self, url: str) -> bool:
        if self._seen.definitely_absent(url):
            return False
        return self._conn.execute("SELECT 1 FROM crawl_urls WHERE url = ?", (url,)).fetchone() is not None

    def filter_unseen(self, urls: list[str]) -> list[str]:
        return [url for url in urls if not self.check_visited(url)]

    def claim_next_url(self, now: datetime) -> Record | None:
        """Atomically claim the oldest eligible row (pending and due, or a stale lease)."""
        stamp, stale = to_iso(now), to_iso(after(now, -self._lease_s))
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT id FROM crawl_urls WHERE (status = 'pending' AND next_attempt_at <= ?)"
                " OR (status = 'in_progress' AND claimed_at <= ?)"
                " ORDER BY next_attempt_at, id LIMIT 1",
                (stamp, stale),
            ).fetchone()
            if row is None:
                self._conn.execute("COMMIT")
                return None
            self._conn.execute(
                "UPDATE crawl_urls SET status = 'in_progress', claimed_at = ?, updated_at = ?"
                " WHERE id = ?",
                (stamp, stamp, row["id"]),
            )
            claimed = self._conn.execute(
                "SELECT * FROM crawl_urls WHERE id = ?", (row["id"],)
            ).fetchone()
            self._conn.execute("COMMIT")
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        return dict(claimed)

    def mark_crawled(self, item_id: int, status_code: int | None, now: datetime) -> None:
        stamp = to_iso(now)
        self._conn.execute(
            "UPDATE crawl_urls SET status = 'done', last_status_code = ?, last_error = NULL,"
            " claimed_at = NULL, updated_at = ? WHERE id = ?",
            (status_code, stamp, item_id),
        )

    def mark_failed(
        self, item_id: int, error: str, now: datetime, *, retry: bool,
        status_code: int | None = None,
    ) -> str:
        """Record a failure. Returns the new status: 'pending' (will retry) or 'failed'."""
        row = self._conn.execute("SELECT attempts FROM crawl_urls WHERE id = ?", (item_id,)).fetchone()
        attempts = row["attempts"] + 1
        stamp = to_iso(now)
        if retry and attempts < self._max_attempts:
            delay = self._retry_base_s * 2 ** (attempts - 1)
            self._conn.execute(
                "UPDATE crawl_urls SET status = 'pending', attempts = ?, last_error = ?,"
                " last_status_code = ?, next_attempt_at = ?, claimed_at = NULL, updated_at = ?"
                " WHERE id = ?",
                (attempts, error, status_code, to_iso(after(now, delay)), stamp, item_id),
            )
            return "pending"
        self._conn.execute(
            "UPDATE crawl_urls SET status = 'failed', attempts = ?, last_error = ?,"
            " last_status_code = ?, claimed_at = NULL, updated_at = ? WHERE id = ?",
            (attempts, error, status_code, stamp, item_id),
        )
        return "failed"

    def get_retryable_urls(self, now: datetime, limit: int = 100) -> list[Record]:
        rows = self._conn.execute(
            "SELECT * FROM crawl_urls WHERE status = 'pending' AND attempts > 0"
            " AND next_attempt_at <= ? ORDER BY next_attempt_at, id LIMIT ?",
            (to_iso(now), limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def count_for_job(self, job_id: int) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM crawl_urls WHERE job_id = ?", (job_id,)
            ).fetchone()[0]
        )

    def iter_urls(self) -> Iterator[str]:
        for row in self._conn.execute("SELECT url FROM crawl_urls"):
            yield row[0]

    def rebuild_seen_filter(self) -> None:
        self._seen.rebuild(self.iter_urls())

    def status_counts(self) -> dict[str, int]:
        rows = self._conn.execute("SELECT status, COUNT(*) AS n FROM crawl_urls GROUP BY status")
        counts = {"pending": 0, "in_progress": 0, "done": 0, "failed": 0}
        counts.update({row["status"]: row["n"] for row in rows})
        return counts


class CrawlJobRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, seed_url: str, max_pages: int, max_depth: int, now: datetime) -> int:
        cursor = self._conn.execute(
            "INSERT INTO crawl_jobs (seed_url, status, max_pages, max_depth, created_at)"
            " VALUES (?, 'queued', ?, ?, ?)",
            (seed_url, max_pages, max_depth, to_iso(now)),
        )
        return int(cursor.lastrowid or 0)

    def get(self, job_id: int) -> Record | None:
        row = self._conn.execute(
            "SELECT j.*,"
            " (SELECT COUNT(*) FROM crawl_urls u WHERE u.job_id = j.id AND u.status = 'pending') AS urls_pending,"
            " (SELECT COUNT(*) FROM crawl_urls u WHERE u.job_id = j.id AND u.status = 'in_progress') AS urls_in_progress,"
            " (SELECT COUNT(*) FROM crawl_urls u WHERE u.job_id = j.id AND u.status = 'done') AS urls_done,"
            " (SELECT COUNT(*) FROM crawl_urls u WHERE u.job_id = j.id AND u.status = 'failed') AS urls_failed"
            " FROM crawl_jobs j WHERE j.id = ?",
            (job_id,),
        ).fetchone()
        return as_record(row)

    def list_items(self, limit: int, offset: int) -> tuple[list[Record], int]:
        total = self._conn.execute("SELECT COUNT(*) FROM crawl_jobs").fetchone()[0]
        ids = [
            row[0]
            for row in self._conn.execute(
                "SELECT id FROM crawl_jobs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            )
        ]
        return [job for job_id in ids if (job := self.get(job_id))], total

    def transition(self, job_id: int, new_status: str, now: datetime, error: str | None = None) -> None:
        row = self._conn.execute("SELECT status FROM crawl_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise InvalidStateError(f"Crawl job {job_id} does not exist")
        if new_status not in _JOB_TRANSITIONS[row["status"]]:
            raise InvalidStateError(f"Cannot move crawl job from {row['status']} to {new_status}")
        stamp = to_iso(now)
        if new_status == "running":
            self._conn.execute(
                "UPDATE crawl_jobs SET status = 'running', started_at = ? WHERE id = ?", (stamp, job_id)
            )
        else:
            self._conn.execute(
                "UPDATE crawl_jobs SET status = ?, error = ?, finished_at = ? WHERE id = ?",
                (new_status, error, stamp, job_id),
            )

    def count_page(self, job_id: int, *, crawled: bool) -> None:
        column = "pages_crawled" if crawled else "pages_failed"
        self._conn.execute(f"UPDATE crawl_jobs SET {column} = {column} + 1 WHERE id = ?", (job_id,))

    def outstanding_urls(self, job_id: int) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM crawl_urls WHERE job_id = ? AND status IN ('pending','in_progress')",
                (job_id,),
            ).fetchone()[0]
        )

    def last_error(self, job_id: int) -> str | None:
        row = self._conn.execute(
            "SELECT last_error FROM crawl_urls WHERE job_id = ? AND last_error IS NOT NULL"
            " ORDER BY updated_at DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        return None if row is None else row[0]
