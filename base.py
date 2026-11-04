import sqlite3
from typing import Any

Record = dict[str, Any]


def as_record(row: sqlite3.Row | None) -> Record | None:
    return None if row is None else dict(row)


def update_row(
    conn: sqlite3.Connection,
    table: str,
    row_id: int,
    changes: Record,
    allowed: frozenset[str],
    updated_at: str,
) -> None:
    """Whitelisted dynamic UPDATE; unknown columns are rejected, never interpolated."""
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"Columns not writable: {sorted(unknown)}")
    assignments = [f"{column} = ?" for column in changes] + ["updated_at = ?"]
    conn.execute(
        f"UPDATE {table} SET {', '.join(assignments)} WHERE id = ?",
        [*changes.values(), updated_at, row_id],
    )
