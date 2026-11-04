import sqlite3

from app.repositories.index import IndexRepository
from app.repositories.pages import PageRepository
from app.services.indexing.text import term_counts


class Indexer:
    """Turns page fields into postings. Callers wrap calls in a transaction."""

    def __init__(self, conn: sqlite3.Connection, stop_words: frozenset[str]) -> None:
        self._pages = PageRepository(conn)
        self._index = IndexRepository(conn)
        self._conn = conn
        self._stop_words = stop_words

    def index_page(self, page_id: int, title: str, description: str, text: str, now: str) -> int:
        """(Re)index one page. Old postings are replaced, so edits never leave stale terms."""
        in_title = term_counts(title, self._stop_words)
        in_description = term_counts(description, self._stop_words)
        in_body = term_counts(text, self._stop_words)
        terms = set(in_title) | set(in_description) | set(in_body)
        self._index.replace_postings(
            page_id, ((t, in_title[t], in_description[t], in_body[t]) for t in sorted(terms))
        )
        doc_length = sum(in_title.values()) + sum(in_description.values()) + sum(in_body.values())
        self._pages.update(page_id, {"doc_length": doc_length}, now)
        return doc_length

    def rebuild(self, now: str) -> int:
        """Rebuild the whole index from stored page content. Returns the page count."""
        self._index.clear()
        rows = self._pages.iter_all().fetchall()
        for row in rows:
            self.index_page(row["id"], row["title"], row["description"], row["text"], now)
        return len(rows)
