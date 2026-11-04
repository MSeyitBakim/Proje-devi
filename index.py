import sqlite3
from collections.abc import Iterable


class IndexRepository:
    """Inverted index storage. Document frequencies are maintained by SQLite triggers."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def replace_postings(
        self, page_id: int, rows: Iterable[tuple[str, int, int, int]]
    ) -> None:
        """rows: (term, tf_title, tf_description, tf_body)."""
        self._conn.execute("DELETE FROM postings WHERE page_id = ?", (page_id,))
        self._conn.executemany(
            "INSERT INTO postings (term, page_id, tf_title, tf_description, tf_body)"
            " VALUES (?, ?, ?, ?, ?)",
            [(term, page_id, a, b, c) for term, a, b, c in rows],
        )

    def clear(self) -> None:
        self._conn.execute("DELETE FROM postings")

    def doc_count(self) -> int:
        return int(self._conn.execute("SELECT doc_count FROM corpus_stats WHERE id = 1").fetchone()[0])

    def term_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM term_stats").fetchone()[0])

    def document_frequencies(self, terms: list[str]) -> dict[str, int]:
        if not terms:
            return {}
        marks = ",".join("?" * len(terms))
        rows = self._conn.execute(
            f"SELECT term, df FROM term_stats WHERE term IN ({marks})", terms
        ).fetchall()
        return {row["term"]: row["df"] for row in rows}

    def postings_for(self, terms: list[str]) -> list[sqlite3.Row]:
        if not terms:
            return []
        marks = ",".join("?" * len(terms))
        return self._conn.execute(
            "SELECT po.term, po.page_id, po.tf_title, po.tf_description, po.tf_body,"
            " pg.doc_length FROM postings po JOIN pages pg ON pg.id = po.page_id"
            f" WHERE po.term IN ({marks})",
            terms,
        ).fetchall()

    def recomputed_frequencies(self) -> dict[str, int]:
        """Ground truth used by consistency checks and tests."""
        rows = self._conn.execute("SELECT term, COUNT(*) AS df FROM postings GROUP BY term")
        return {row["term"]: row["df"] for row in rows}
