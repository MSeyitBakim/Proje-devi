from datetime import timedelta

import pytest

from app.core.timeutil import utcnow

from app.repositories.crawl import CrawlJobRepository, CrawlQueue
from app.services.crawler.crawler import Crawler
from app.services.crawler.extractor import extract_page
from app.services.crawler.jobs import CrawlJobService
from app.services.crawler.models import FetchedPage, FetchError
from app.services.crawler.robots import RobotsService
from app.services.search.query import QueryAnalyzer
from app.services.search.service import SearchService


def html(title: str, body: str, links: tuple[str, ...] = ()) -> str:
    anchors = "".join(f'<a href="{href}">x</a>' for href in links)
    return f"<html><head><title>{title}</title></head><body><p>{body}</p>{anchors}</body></html>"


class FakeFetcher:
    def __init__(self, pages: dict[str, str | FetchError], robots: str | None = None) -> None:
        self.pages, self.robots, self.calls = pages, robots, []

    async def fetch_raw(self, url: str) -> FetchedPage:
        if url.endswith("/robots.txt"):
            if self.robots is None:
                return FetchedPage(url, 404, "text/plain", "")
            return FetchedPage(url, 200, "text/plain", self.robots)
        raise AssertionError(url)

    async def fetch_page(self, url: str) -> FetchedPage:
        self.calls.append(url)
        result = self.pages.get(url, FetchError("http_404", retryable=False, status_code=404))
        if isinstance(result, FetchError):
            raise result
        return FetchedPage(url, 200, "text/html", result)


def build(conn, settings, fetcher):
    queue = CrawlQueue(conn, max_attempts=2, retry_base_s=10)
    crawler = Crawler(conn, settings, fetcher, RobotsService(conn, fetcher, settings), queue)
    return crawler, queue


async def drain(crawler, queue, offset: float = 0) -> list:
    outcomes = []
    while (item := queue.claim_next_url(utcnow() + timedelta(seconds=offset))):
        outcomes.append(await crawler.process(item))
    return outcomes


@pytest.mark.anyio
async def test_crawl_indexes_pages_follows_same_host_links_and_completes_job(conn, settings) -> None:
    fetcher = FakeFetcher({
        "https://site.test/": html("Home", "welcome astronomy", ("/a", "https://other.test/x", "/b")),
        "https://site.test/a": html("Telescopes", "refractor telescope guide"),
        "https://site.test/b": html("Orbits", "elliptical orbit maths", ("/a",)),
    })
    crawler, queue = build(conn, settings, fetcher)
    job = CrawlJobService(conn).submit("https://site.test", max_pages=10, max_depth=2)
    outcomes = await drain(crawler, queue)
    assert [o.status for o in outcomes] == ["done"] * 3
    assert "https://other.test/x" not in fetcher.calls  # cross-host links are not followed
    finished = CrawlJobRepository(conn).get(job["id"])
    assert finished["status"] == "completed" and finished["pages_crawled"] == 3
    search = SearchService(conn, settings, QueryAnalyzer(settings))
    assert search.search("telescope", 1, 5).hits[0].url == "https://site.test/a"
    assert conn.execute("SELECT base_domain FROM sites").fetchone()[0] == "site.test"


@pytest.mark.anyio
async def test_limits_depth_and_page_cap(conn, settings) -> None:
    pages = {"https://s.test/": html("Home", "x1", ("/1", "/2", "/3"))}
    pages |= {f"https://s.test/{i}": html(f"P{i}", "deep", ("/deeper",)) for i in (1, 2, 3)}
    fetcher = FakeFetcher(pages)
    crawler, queue = build(conn, settings, fetcher)
    job = CrawlJobService(conn).submit("https://s.test/", max_pages=3, max_depth=5)
    await drain(crawler, queue)
    assert CrawlJobRepository(conn).get(job["id"])["pages_crawled"] <= 3
    assert queue.count_for_job(job["id"]) == 3


@pytest.mark.anyio
async def test_robots_disallow_is_respected_and_permanent(conn, settings) -> None:
    fetcher = FakeFetcher({"https://r.test/": html("Home", "x")}, robots="User-agent: *\nDisallow: /\n")
    crawler, queue = build(conn, settings, fetcher)
    job = CrawlJobService(conn).submit("https://r.test/", 5, 1)
    outcomes = await drain(crawler, queue)
    assert outcomes[0].status == "failed" and outcomes[0].error == "robots_disallowed"
    assert fetcher.calls == []
    assert CrawlJobRepository(conn).get(job["id"])["status"] == "failed"


@pytest.mark.anyio
async def test_retryable_error_is_rescheduled_then_fails(conn, settings) -> None:
    fetcher = FakeFetcher({"https://t.test/": FetchError("timeout", retryable=True)})
    crawler, queue = build(conn, settings, fetcher)
    job = CrawlJobService(conn).submit("https://t.test/", 5, 0)
    first = await drain(crawler, queue)
    assert first[0].status == "retry"
    assert CrawlJobRepository(conn).get(job["id"])["status"] == "running"
    second = await drain(crawler, queue, 30)
    assert second[0].status == "failed"
    done = CrawlJobRepository(conn).get(job["id"])
    assert done["status"] == "failed" and done["pages_failed"] == 1 and done["error"] == "timeout"


@pytest.mark.anyio
async def test_recrawl_with_unchanged_content_does_not_reindex(conn, settings) -> None:
    fetcher = FakeFetcher({"https://u.test/": html("Same", "stable content")})
    crawler, queue = build(conn, settings, fetcher)
    service = CrawlJobService(conn)
    service.submit("https://u.test/", 1, 0)
    await drain(crawler, queue)
    before = conn.execute("SELECT updated_at FROM pages").fetchone()[0]
    count = conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
    service.submit("https://u.test/", 1, 0)
    await drain(crawler, queue)
    assert conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0] == count
    assert conn.execute("SELECT updated_at FROM pages").fetchone()[0] >= before


@pytest.mark.anyio
async def test_robots_responses_are_cached(conn, settings) -> None:
    class Counting(FakeFetcher):
        robots_fetches = 0

        async def fetch_raw(self, url: str) -> FetchedPage:
            Counting.robots_fetches += 1
            return await super().fetch_raw(url)

    fetcher = Counting({"https://c.test/": html("H", "x", ("/a",)), "https://c.test/a": html("A", "y")})
    crawler, queue = build(conn, settings, fetcher)
    CrawlJobService(conn).submit("https://c.test/", 5, 1)
    await drain(crawler, queue)
    assert Counting.robots_fetches == 1


@pytest.mark.anyio
async def test_unreachable_robots_blocks_crawling(conn, settings) -> None:
    class Down(FakeFetcher):
        async def fetch_raw(self, url: str) -> FetchedPage:
            raise FetchError("timeout", retryable=True)

    fetcher = Down({"https://d.test/": html("H", "x")})
    crawler, queue = build(conn, settings, fetcher)
    CrawlJobService(conn).submit("https://d.test/", 5, 0)
    assert (await drain(crawler, queue))[0].error == "robots_disallowed"


def test_extractor_handles_malformed_html_and_directives() -> None:
    page = extract_page("<title>Broken<p>text <a href=/x>l</a><div", "https://e.test/")
    assert "text" in page.text
    noindex = extract_page(
        '<meta name="robots" content="noindex, nofollow"><a href="/x">l</a>', "https://e.test/"
    )
    assert noindex.noindex and noindex.nofollow and noindex.discovered_links == []
    empty = extract_page("", "https://e.test/")
    assert empty.title == "" and empty.text == ""
    page = extract_page(
        '<head><link rel=canonical href="https://evil.test/x"></head><a href="javascript:x()">j</a>',
        "https://e.test/",
    )
    assert page.canonical_url is None and page.discovered_links == []


def test_submit_rejects_private_seed(conn) -> None:
    from app.core.exceptions import BlockedDestinationError
    with pytest.raises(BlockedDestinationError):
        CrawlJobService(conn).submit("http://127.0.0.1:8000/", 5, 1)
