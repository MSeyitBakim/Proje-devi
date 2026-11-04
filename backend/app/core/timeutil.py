from datetime import UTC, datetime, timedelta

_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_iso(moment: datetime) -> str:
    """Fixed-width UTC timestamps sort lexicographically, which SQLite comparisons rely on."""
    return moment.astimezone(UTC).strftime(_FORMAT)


def after(moment: datetime, seconds: float) -> datetime:
    return moment + timedelta(seconds=seconds)
