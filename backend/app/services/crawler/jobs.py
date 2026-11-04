import sqlite3

from app.core.exceptions import ConflictError, NotFoundError
from app.core.netguard import check_literal_host
from app.core.timeutil import utcnow
from app.core.urls import normalize_url
from app.db.session import transaction
from app.repositories.base import Record
from app.repositories.crawl import CrawlJobRepository, CrawlQueue
from urllib.parse import urlsplit


class CrawlJobService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._jobs = CrawlJobRepository(conn)
        self._queue = CrawlQueue(conn)

    def submit(self, url: str, max_pages: int, max_depth: int) -> Record:
        seed = normalize_url(url)
        check_literal_host(urlsplit(seed).hostname or "")
        now = utcnow()
        with transaction(self._conn):
            job_id = self._jobs.create(seed, max_pages, max_depth, now)
            if not self._queue.enqueue_url(seed, now, job_id=job_id, depth=0, force=True):
                raise ConflictError("This URL is currently being crawled")
        return self.get(job_id)

    def get(self, job_id: int) -> Record:
        job = self._jobs.get(job_id)
        if job is None:
            raise NotFoundError(f"Crawl job {job_id} not found")
        return job

    def list_items(self, page: int, limit: int) -> tuple[list[Record], int]:
        return self._jobs.list_items(limit, (page - 1) * limit)
