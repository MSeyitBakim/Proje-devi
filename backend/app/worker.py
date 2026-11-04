"""Standalone crawl worker: `python -m app.worker [--once]`."""

import argparse
import asyncio
import logging
import signal

import httpx

from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.timeutil import utcnow
from app.db.migrate import apply_migrations
from app.db.session import connect
from app.repositories.crawl import CrawlQueue
from app.services.bloom import SeenUrlFilter
from app.services.crawler.crawler import Crawler
from app.services.crawler.fetcher import SafeFetcher
from app.services.crawler.robots import RobotsService

log = logging.getLogger("worker")


async def run_worker(settings: Settings, *, once: bool, poll_interval: float) -> None:
    conn = connect(settings.database_path)
    apply_migrations(conn)
    seen = SeenUrlFilter(settings.bloom_capacity, settings.bloom_error_rate, settings.bloom_enabled)
    queue = CrawlQueue(
        conn, max_attempts=settings.crawl_max_attempts, retry_base_s=settings.crawl_retry_base_s,
        lease_s=settings.crawl_lease_s, seen=seen,
    )
    queue.rebuild_seen_filter()
    limits = httpx.Limits(max_connections=settings.crawl_concurrency * 2)
    timeout = httpx.Timeout(settings.crawl_timeout_s)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        fetcher = SafeFetcher(client, settings)
        crawler = Crawler(conn, settings, fetcher, RobotsService(conn, fetcher, settings), queue)
        while True:
            batch = []
            while len(batch) < settings.crawl_concurrency and (item := queue.claim_next_url(utcnow())):
                batch.append(item)
            if not batch:
                if once:
                    break
                await asyncio.sleep(poll_interval)
                continue
            results = await asyncio.gather(*(crawler.process(i) for i in batch), return_exceptions=True)
            for item, result in zip(batch, results, strict=True):
                if isinstance(result, BaseException):
                    # Unexpected bug: the row stays in_progress and is reclaimed after the lease.
                    log.error("crawl_crashed", extra={"url": item["url"]}, exc_info=result)
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the crawl worker")
    parser.add_argument("--once", action="store_true", help="exit when the queue is drained")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    args = parser.parse_args()
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        asyncio.run(run_worker(settings, once=args.once, poll_interval=args.poll_interval))
    except KeyboardInterrupt:
        log.info("worker_stopped")


if __name__ == "__main__":
    main()
