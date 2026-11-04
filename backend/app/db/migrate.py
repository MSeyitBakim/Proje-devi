import argparse
import sqlite3
from pathlib import Path

from app.core.config import Settings
from app.db.session import open_connection

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def apply_migrations(conn: sqlite3.Connection) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    newly_applied: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.stem in applied:
            continue
        script = (
            "BEGIN;\n"
            + path.read_text(encoding="utf-8")
            + f"\nINSERT INTO schema_migrations(version, applied_at) "
            f"VALUES ('{path.stem}', strftime('%Y-%m-%dT%H:%M:%fZ','now'));\nCOMMIT;"
        )
        try:
            conn.executescript(script)
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        newly_applied.append(path.stem)
    return newly_applied


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply database migrations")
    parser.parse_args()
    settings = Settings.from_env()
    with open_connection(settings.database_path) as conn:
        applied = apply_migrations(conn)
    print(f"Applied: {', '.join(applied) if applied else 'nothing (up to date)'}")


if __name__ == "__main__":
    main()
