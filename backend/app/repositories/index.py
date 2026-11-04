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

    def matching_terms(
        self, term: str, extra_candidates: tuple[str, ...] = (), limit: int = 50
    ) -> list[str]:
        """Find an exact indexed term, substring matches, or a small typo correction set."""
        exact = self._conn.execute(
            "SELECT term FROM term_stats WHERE term = ?", (term,)
        ).fetchone()
        if exact:
            return [exact["term"]]

        if len(term) >= 3:
            partial = self._conn.execute(
                "SELECT term FROM term_stats WHERE term LIKE ? ORDER BY df DESC, term LIMIT ?",
                (f"%{term}%", limit),
            ).fetchall()
            if partial:
                return [row["term"] for row in partial]

        # LIKE alone cannot correct substitutions or transposed letters. Look up a
        # bounded set of terms sharing character n-grams, then retain close spellings.
        if len(term) < 4:
            return []
        ngram_size = 2 if len(term) <= 8 else 3
        ngrams = sorted({term[i : i + ngram_size] for i in range(len(term) - ngram_size + 1)})
        patterns = [f"%{ngram}%" for ngram in ngrams]
        clauses = " OR ".join("term LIKE ?" for _ in patterns)
        candidates = self._conn.execute(
            f"SELECT term FROM term_stats WHERE {clauses} LIMIT 500", patterns
        ).fetchall()
        max_distance = 1 if len(term) <= 11 else 2
        candidate_terms = {row["term"] for row in candidates}
        candidate_terms.update(
            candidate for candidate in extra_candidates
            if abs(len(candidate) - len(term)) <= max_distance
        )
        close = []
        for candidate in candidate_terms:
            distance = _edit_distance(term, candidate)
            if distance <= max_distance:
                close.append((distance, candidate))
        close.sort()
        return [candidate for _, candidate in close[:limit]]

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


def _edit_distance(left: str, right: str) -> int:
    """Levenshtein distance, treating one adjacent transposition as one typo."""
    if left == right:
        return 0
    if len(left) == len(right):
        mismatches = [i for i, (a, b) in enumerate(zip(left, right, strict=True)) if a != b]
        if (
            len(mismatches) == 2
            and mismatches[1] == mismatches[0] + 1
            and left[mismatches[0]] == right[mismatches[1]]
            and left[mismatches[1]] == right[mismatches[0]]
        ):
            return 1

    previous = list(range(len(right) + 1))
    for i, char_left in enumerate(left, start=1):
        current = [i]
        for j, char_right in enumerate(right, start=1):
            current.append(
                min(
                    current[j - 1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (char_left != char_right),
                )
            )
        previous = current
    return previous[-1]
