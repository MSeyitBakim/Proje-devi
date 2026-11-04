import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Query, Request

from app.core.config import Settings
from app.db.session import connect
from app.services.search.query import QueryAnalyzer


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_conn(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[sqlite3.Connection]:
    conn = connect(settings.database_path)
    try:
        yield conn
    finally:
        conn.close()


def get_analyzer(request: Request) -> QueryAnalyzer:
    return request.app.state.analyzer


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]
Config = Annotated[Settings, Depends(get_settings)]


class Pagination:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1, le=10_000)] = 1,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> None:
        self.page, self.limit = page, limit


Paging = Annotated[Pagination, Depends()]
