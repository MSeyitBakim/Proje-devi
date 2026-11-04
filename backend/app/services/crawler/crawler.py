import asyncio
import logging
import sqlite3
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.core.config import Settings
from app.core.timeutil import to_iso, utcnow
from app.core.urls import base_domain
from app.db.session import transaction
from app.repositories.base import Record
from app.repositories.crawl import CrawlJobRepository, CrawlQueue
from app.services.crawler.extractor import extract_page
from app.services.crawler.models import Fetcher, FetchError
from app.services.crawler.robots import RobotsService
from app.services.pages import PageService

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CrawlOutcome:
    url: str
    status: str  # done | retry | failed
    error: str | None = None
    page_id: int | None = None
    links_enqueued: int = 0


class Crawler:
    """Processes one claimed queue item end to end: robots, politeness delay, fetch, extract,
    persist + index, enqueue links, and update job bookkeeping."""

    def __init__(
        self, conn: sqlite3.Connection, settings: Settings, fetcher: Fetcher,
        robots: RobotsService, queue: CrawlQueue,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._conn, self._settings, self._fetcher = conn, settings, fetcher
        self._robots, self._queue = robots, queue
        self._jobs = CrawlJobRepository(conn)
        self._pages = PageService(conn, settings)
        self._sleep, self._clock = sleep, clock
        self._next_slot: dict[str, float] = {}
        self._host_locks: dict[str, asyncio.Lock] = {}

    async def process(self, item: Record) -> CrawlOutcome:
        url, job_id = item["url"], item["job_id"]
        if job_id is not None:
            self._start_job(job_id)
        try:
            policy = await self._robots.policy_for(url, utcnow())
            if not policy.allowed(url):
                return self._fail(item, "robots_disallowed", retry=False)
            await self._wait_turn(urlsplit(url).netloc, policy.crawl_delay)
            fetched = await self._fetcher.fetch_page(url)
        except FetchError as exc:
            return self._fail(item, exc.reason, retry=exc.retryable, status=exc.status_code)

        extracted = extract_page(
            fetched.body, fetched.url,
            max_text_chars=self._settings.max_text_chars,
            max_links=self._settings.max_links_per_page,
        )
        now = utcnow()
        page_id: int | None = None
        enqueued = 0
        with transaction(self._conn):
            if not extracted.noindex:
                page_id, _ = self._pages.save_crawled(
                    extracted.canonical_url or extracted.url, extracted.title,
                    extracted.description, extracted.text, fetched.status_code, to_iso(now),
                )
            self._queue.mark_crawled(item["id"], fetched.status_code, now)
            if job_id is not None:
                self._jobs.count_page(job_id, crawled=True)
                enqueued = self._enqueue_links(item, extracted.discovered_links)
            self._finalize(job_id)
        return CrawlOutcome(url, "done", page_id=page_id, links_enqueued=enqueued)

    def _enqueue_links(self, item: Record, links: list[str]) -> int:
        job = self._jobs.get(item["job_id"])
        if job is None or item["depth"] >= job["max_depth"]:
            return 0
        host = base_domain(item["url"])
        remaining = job["max_pages"] - self._queue.count_for_job(job["id"])
        if remaining <= 0:
            return 0
        same_host = [link for link in links if base_domain(link) == host]
        fresh = self._queue.filter_unseen(same_host)[:remaining]
        now = utcnow()
        return sum(
            self._queue.enqueue_url(link, now, job_id=job["id"], depth=item["depth"] + 1)
            for link in fresh
        )

    def _fail(self, item: Record, reason: str, *, retry: bool, status: int | None = None) -> CrawlOutcome:
        now = utcnow()
        with transaction(self._conn):
            new_status = self._queue.mark_failed(item["id"], reason, now, retry=retry, status_code=status)
            if new_status == "failed" and item["job_id"] is not None:
                self._jobs.count_page(item["job_id"], crawled=False)
            self._finalize(item["job_id"])
        log.warning("crawl_failed", extra={"url": item["url"], "reason": reason, "outcome": new_status})
        return CrawlOutcome(item["url"], "retry" if new_status == "pending" else "failed", error=reason)

    def _start_job(self, job_id: int) -> None:
        job = self._jobs.get(job_id)
        if job and job["status"] == "queued":
            self._jobs.transition(job_id, "running", utcnow())

    def _finalize(self, job_id: int | None) -> None:
        if job_id is None or self._jobs.outstanding_urls(job_id) > 0:
            return
        job = self._jobs.get(job_id)
        if job is None or job["status"] != "running":
            return
        if job["pages_crawled"] > 0:
            self._jobs.transition(job_id, "completed", utcnow())
        else:
            self._jobs.transition(job_id, "failed", utcnow(), self._jobs.last_error(job_id) or "no pages crawled")

    async def _wait_turn(self, host: str, robots_delay: float | None) -> None:
        delay = max(self._settings.crawl_host_delay_s, robots_delay or 0.0)
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = self._next_slot.get(host, 0.0) - self._clock()
            if wait > 0:
                await self._sleep(wait)
            self._next_slot[host] = self._clock() + delay
