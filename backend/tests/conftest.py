import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.db.migrate import apply_migrations
from app.db.session import connect

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def settings() -> Settings:
    return Settings(crawl_host_delay_s=0.0, crawl_retry_base_s=10.0)


@pytest.fixture
def conn(tmp_path) -> Iterator[sqlite3.Connection]:
    connection = connect(str(tmp_path / "test.db"))
    apply_migrations(connection)
    yield connection
    connection.close()
