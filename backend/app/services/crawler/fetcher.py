import httpx

from app.core.config import Settings
from app.core.exceptions import BlockedDestinationError, InvalidInputError
from app.core.netguard import Resolver, assert_public_destination, resolve_host
from app.core.urls import normalize_url
from app.services.crawler.models import FetchedPage, FetchError

_REDIRECTS = {301, 302, 303, 307, 308}
_HTML_TYPES = {"text/html", "application/xhtml+xml"}


class SafeFetcher:
    """HTTP fetching with SSRF checks on every hop, manual redirects, and a hard byte limit."""

    def __init__(
        self, client: httpx.AsyncClient, settings: Settings, resolver: Resolver = resolve_host
    ) -> None:
        self._client = client
        self._settings = settings
        self._resolver = resolver

    async def fetch_raw(self, url: str) -> FetchedPage:
        """Any status and content type; raises FetchError only for transport-level problems."""
        current = url
        for _ in range(self._settings.crawl_max_redirects + 1):
            await self._check(current)
            try:
                async with self._client.stream(
                    "GET", current, follow_redirects=False,
                    headers={"User-Agent": self._settings.user_agent, "Accept": "text/html,*/*;q=0.5"},
                ) as response:
                    location = response.headers.get("location")
                    if response.status_code in _REDIRECTS and location:
                        try:
                            current = normalize_url(location, base=current)
                        except InvalidInputError as exc:
                            raise FetchError("invalid_redirect", retryable=False) from exc
                        continue
                    return await self._read(response, current)
            except httpx.TimeoutException as exc:
                raise FetchError("timeout", retryable=True) from exc
            except httpx.HTTPError as exc:
                raise FetchError("network_error", retryable=True) from exc
        raise FetchError("too_many_redirects", retryable=False)

    async def fetch_page(self, url: str) -> FetchedPage:
        page = await self.fetch_raw(url)
        status = page.status_code
        if status >= 400 or status < 200 or status >= 300:
            retryable = status in {408, 425, 429} or status >= 500
            raise FetchError(f"http_{status}", retryable=retryable, status_code=status)
        if page.content_type not in _HTML_TYPES:
            raise FetchError("unsupported_content_type", retryable=False, status_code=status)
        return page

    async def _check(self, url: str) -> None:
        host = httpx.URL(url).host
        try:
            await assert_public_destination(
                host, resolver=self._resolver, allow_private=self._settings.crawl_allow_private_hosts
            )
        except BlockedDestinationError as exc:
            raise FetchError("blocked_destination", retryable=False) from exc
        except OSError as exc:
            raise FetchError("dns_error", retryable=True) from exc

    async def _read(self, response: httpx.Response, url: str) -> FetchedPage:
        limit = self._settings.crawl_max_bytes
        declared = response.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > limit:
            raise FetchError("response_too_large", retryable=False)
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > limit:
                raise FetchError("response_too_large", retryable=False)
            chunks.append(chunk)
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        try:
            body = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        except LookupError:
            body = b"".join(chunks).decode("utf-8", errors="replace")
        return FetchedPage(url=url, status_code=response.status_code, content_type=content_type, body=body)
