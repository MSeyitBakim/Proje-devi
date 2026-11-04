from dataclasses import dataclass, field
from typing import Protocol


class FetchError(Exception):
    """A fetch that failed. `retryable` decides whether the queue schedules another attempt."""

    def __init__(self, reason: str, *, retryable: bool, status_code: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class FetchedPage:
    url: str
    status_code: int
    content_type: str
    body: str


class Fetcher(Protocol):
    async def fetch_page(self, url: str) -> FetchedPage: ...

    async def fetch_raw(self, url: str) -> FetchedPage: ...


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    url: str
    title: str
    description: str
    text: str
    discovered_links: list[str] = field(default_factory=list)
    canonical_url: str | None = None
    language: str | None = None
    noindex: bool = False
    nofollow: bool = False
