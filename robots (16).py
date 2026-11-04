import sqlite3
from datetime import datetime
from urllib.robotparser import RobotFileParser

from app.core.config import Settings
from app.core.timeutil import after, to_iso
from app.core.urls import origin_of
from app.repositories.robots import RobotsRepository
from app.services.crawler.models import FetchError, Fetcher

ROBOT_TOKEN = "SearchEngineBot"
MAX_ROBOTS_BYTES = 500 * 1024
MAX_CRAWL_DELAY_S = 30.0


class RobotsPolicy:
    def __init__(self, parser: RobotFileParser | None, *, allow_all: bool) -> None:
        self._parser = parser
        self._allow_all = allow_all

    def allowed(self, url: str) -> bool:
        if self._parser is None:
            return self._allow_all
        return self._parser.can_fetch(ROBOT_TOKEN, url)

    @property
    def crawl_delay(self) -> float | None:
        if self._parser is None:
            return None
        delay = self._parser.crawl_delay(ROBOT_TOKEN)
        return None if delay is None else min(float(delay), MAX_CRAWL_DELAY_S)


def _policy_from_row(row: dict) -> RobotsPolicy:
    if row["unreachable"]:
        return RobotsPolicy(None, allow_all=False)
    if row["status_code"] is not None and 200 <= row["status_code"] < 300:
        parser = RobotFileParser()
        parser.parse(row["body"].splitlines())
        return RobotsPolicy(parser, allow_all=True)
    return RobotsPolicy(None, allow_all=True)


class RobotsService:
    """Follows RFC 9309 semantics: 2xx parsed; 4xx means no restrictions; 5xx, network errors
    and blocked destinations mean "unreachable", which disallows crawling until the short
    error TTL expires."""

    def __init__(self, conn: sqlite3.Connection, fetcher: Fetcher, settings: Settings) -> None:
        self._repo = RobotsRepository(conn)
        self._fetcher = fetcher
        self._settings = settings

    async def policy_for(self, url: str, now: datetime) -> RobotsPolicy:
        origin = origin_of(url)
        cached = self._repo.get_valid(origin, to_iso(now))
        if cached:
            return _policy_from_row(cached)
        try:
            response = await self._fetcher.fetch_raw(f"{origin}/robots.txt")
            status, body = response.status_code, response.body[:MAX_ROBOTS_BYTES]
            unreachable = status >= 500
        except FetchError:
            status, body, unreachable = None, "", True
        ttl = self._settings.robots_error_ttl_s if unreachable else self._settings.robots_ttl_s
        self._repo.put(origin, status, body, unreachable, to_iso(now), to_iso(after(now, ttl)))
        return _policy_from_row(
            {"unreachable": unreachable, "status_code": status, "body": body}
        )
