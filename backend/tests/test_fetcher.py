"""Requires httpx. Uses httpx.MockTransport, so no network access is needed."""

import httpx
import pytest

from app.core.config import Settings
from app.services.crawler.fetcher import SafeFetcher
from app.services.crawler.models import FetchError

PUBLIC = ["93.184.216.34"]


async def resolver(host: str) -> list[str]:
    return ["10.0.0.5"] if host == "internal.example" else PUBLIC


def fetcher_for(handler, **overrides) -> tuple[SafeFetcher, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(**{"crawl_max_bytes": 1024, "crawl_max_redirects": 2, **overrides})
    return SafeFetcher(client, settings, resolver), client


def html_response(body: str = "<title>ok</title>", **kwargs) -> httpx.Response:
    return httpx.Response(200, text=body, headers={"content-type": "text/html; charset=utf-8"}, **kwargs)


@pytest.mark.anyio
async def test_fetches_html() -> None:
    fetcher, client = fetcher_for(lambda request: html_response())
    async with client:
        page = await fetcher.fetch_page("https://ok.example/")
    assert page.status_code == 200 and "ok" in page.body and page.content_type == "text/html"


@pytest.mark.anyio
async def test_follows_redirects_and_limits_them() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(301, headers={"location": "/final"})
        if request.url.path == "/loop":
            return httpx.Response(302, headers={"location": "/loop"})
        return html_response()

    fetcher, client = fetcher_for(handler)
    async with client:
        assert (await fetcher.fetch_page("https://ok.example/start")).url == "https://ok.example/final"
        with pytest.raises(FetchError) as exc:
            await fetcher.fetch_page("https://ok.example/loop")
    assert exc.value.reason == "too_many_redirects" and not exc.value.retryable


@pytest.mark.anyio
async def test_redirect_to_private_host_is_blocked() -> None:
    handler = lambda request: httpx.Response(302, headers={"location": "http://internal.example/secret"})  # noqa: E731
    fetcher, client = fetcher_for(handler)
    async with client:
        with pytest.raises(FetchError) as exc:
            await fetcher.fetch_page("https://ok.example/")
    assert exc.value.reason == "blocked_destination"


@pytest.mark.anyio
async def test_literal_private_ip_blocked_without_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be made")

    fetcher, client = fetcher_for(handler)
    async with client:
        with pytest.raises(FetchError) as exc:
            await fetcher.fetch_page("http://169.254.169.254/latest/meta-data")
    assert exc.value.reason == "blocked_destination"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "reason", "retryable"),
    [
        (httpx.Response(404, text="x"), "http_404", False),
        (httpx.Response(503, text="x"), "http_503", True),
        (httpx.Response(429, text="x"), "http_429", True),
        (httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"}),
         "unsupported_content_type", False),
        (html_response("x" * 5000), "response_too_large", False),
    ],
)
async def test_error_classification(response, reason, retryable) -> None:
    fetcher, client = fetcher_for(lambda request: response)
    async with client:
        with pytest.raises(FetchError) as exc:
            await fetcher.fetch_page("https://ok.example/")
    assert exc.value.reason == reason and exc.value.retryable is retryable


@pytest.mark.anyio
async def test_timeout_and_network_errors_are_retryable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    for handler, reason in ((timeout, "timeout"), (refused, "network_error")):
        fetcher, client = fetcher_for(handler)
        async with client:
            with pytest.raises(FetchError) as exc:
                await fetcher.fetch_page("https://ok.example/")
        assert exc.value.reason == reason and exc.value.retryable


@pytest.mark.anyio
async def test_fetch_raw_returns_non_2xx_for_robots() -> None:
    fetcher, client = fetcher_for(lambda request: httpx.Response(404, text="nope"))
    async with client:
        page = await fetcher.fetch_raw("https://ok.example/robots.txt")
    assert page.status_code == 404
