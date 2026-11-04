"""Rough local benchmark (stdlib only): `python scripts/bench.py [pages]`.

Indexes synthetic pages in an in-memory database, then times searches and the optional
Bloom pre-check. Numbers are machine specific; use them to compare changes, not as promises.
"""

import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.db.migrate import apply_migrations  # noqa: E402
from app.db.session import connect, transaction  # noqa: E402
from app.repositories.crawl import CrawlQueue  # noqa: E402
from app.services.bloom import SeenUrlFilter  # noqa: E402
from app.services.pages import PageService  # noqa: E402
from app.services.search.query import QueryAnalyzer  # noqa: E402
from app.services.search.service import SearchService  # noqa: E402
from app.services.sites import SiteService  # noqa: E402


def main(count: int) -> None:
    rng = random.Random(7)
    vocab = [f"word{i}" for i in range(3000)]
    conn = connect(":memory:")
    apply_migrations(conn)
    settings = Settings()
    site = SiteService(conn).create("bench", "https://bench.test", "", [])
    pages = PageService(conn, settings)
    start = time.perf_counter()
    with transaction(conn):
        for i in range(count):
            body = " ".join(rng.choices(vocab, k=300))
            pages.create(site["id"], f"https://bench.test/{i}", f"page {rng.choice(vocab)}", "", body)
    print(f"indexed {count} pages in {time.perf_counter() - start:.2f}s")

    search = SearchService(conn, settings, QueryAnalyzer(settings))
    queries = [" ".join(rng.choices(vocab, k=2)) for _ in range(200)]
    start = time.perf_counter()
    for query in queries:
        search.search(query, 1, 10)
    print(f"search: {(time.perf_counter() - start) / len(queries) * 1000:.2f} ms/query (200 queries)")

    now = datetime.now(UTC)
    for enabled in (False, True):
        queue = CrawlQueue(conn, seen=SeenUrlFilter(count * 2, 0.01, enabled))
        for i in range(count):
            queue.enqueue_url(f"https://bench.test/q/{i}", now)
        probes = [f"https://bench.test/new/{i}" for i in range(20_000)]
        start = time.perf_counter()
        for url in probes:
            queue.check_visited(url)
        label = "with bloom" if enabled else "without bloom"
        print(f"check_visited {label}: {(time.perf_counter() - start) / len(probes) * 1e6:.1f} µs/call")
        conn.execute("DELETE FROM crawl_urls")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2000)
