import json
import math
import sqlite3
from dataclasses import dataclass, field

from app.core.config import Settings
from app.repositories.index import IndexRepository
from app.repositories.pages import PageRepository
from app.services.indexing.text import make_snippet
from app.services.search.query import QueryAnalyzer


@dataclass(frozen=True, slots=True)
class SearchHit:
    page_id: int
    url: str
    title: str
    description: str
    snippet: str
    score: float
    site_id: int
    site_title: str
    base_domain: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SearchPage:
    hits: list[SearchHit]
    total: int
    page: int
    limit: int


def idf(doc_count: int, document_frequency: int) -> float:
    """Smoothed IDF: ln((N + 1) / (df + 1)) + 1. Always >= 1, defined for df = 0 and N = 0."""
    return math.log((doc_count + 1) / (document_frequency + 1)) + 1.0


def tf(count: int) -> float:
    """Sublinear term frequency: 1 + ln(count) for count > 0, else 0."""
    return 1.0 + math.log(count) if count > 0 else 0.0


def length_norm(doc_length: int) -> float:
    """Gentle length normalization: 1 / (1 + ln(1 + length))."""
    return 1.0 / (1.0 + math.log(1 + doc_length))


class SearchService:
    """score(d, q) = length_norm(d) * sum_t qw(t) * idf(t) * (w_title*tf(c_title) +
    w_desc*tf(c_desc) + w_body*tf(c_body)). Documents matching any term are candidates;
    ties break on ascending page id."""

    def __init__(self, conn: sqlite3.Connection, settings: Settings, analyzer: QueryAnalyzer) -> None:
        self._index = IndexRepository(conn)
        self._pages = PageRepository(conn)
        self._settings = settings
        self._analyzer = analyzer

    def search(self, query: str, page: int, limit: int) -> SearchPage:
        weighted = self._analyzer.analyze(query)
        weights = {item.term: item.weight for item in weighted}
        scores = self._score(weights)
        ranked = sorted(scores.items(), key=lambda pair: (-round(pair[1], 9), pair[0]))
        start = (page - 1) * limit
        window = ranked[start : start + limit]
        pages = self._pages.with_site([page_id for page_id, _ in window])
        hits = []
        term_set = set(weights)
        for page_id, score in window:
            row = pages[page_id]
            hits.append(
                SearchHit(
                    page_id=page_id,
                    url=row["url"],
                    title=row["title"],
                    description=row["description"],
                    snippet=make_snippet(row["text"], term_set) or row["description"],
                    score=score,
                    site_id=row["site_id"],
                    site_title=row["site_title"],
                    base_domain=row["base_domain"],
                    tags=json.loads(row["tag_list"]),
                )
            )
        return SearchPage(hits=hits, total=len(ranked), page=page, limit=limit)

    def _score(self, weights: dict[str, float]) -> dict[int, float]:
        if not weights:
            return {}
        terms = sorted(weights)
        doc_count = self._index.doc_count()
        dfs = self._index.document_frequencies(terms)
        s = self._settings
        scores: dict[int, float] = {}
        for row in self._index.postings_for(terms):
            term = row["term"]
            field_tf = (
                s.weight_title * tf(row["tf_title"])
                + s.weight_description * tf(row["tf_description"])
                + s.weight_body * tf(row["tf_body"])
            )
            contribution = weights[term] * idf(doc_count, dfs[term]) * field_tf
            page_id = row["page_id"]
            scores[page_id] = scores.get(page_id, 0.0) + contribution * length_norm(row["doc_length"])
        return scores
