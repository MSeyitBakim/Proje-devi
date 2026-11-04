import json
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import InvalidInputError
from app.services.indexing.stopwords import build_stop_words
from app.services.indexing.text import fold, tokenize

_DEFAULT_SYNONYMS = Path(__file__).parents[2] / "data" / "synonyms.json"


def load_synonyms(path: str | None) -> dict[str, tuple[str, ...]]:
    """Groups are symmetric: every member expands to the other members, in file order."""
    source = Path(path) if path else _DEFAULT_SYNONYMS
    groups = json.loads(source.read_text(encoding="utf-8"))["groups"]
    mapping: dict[str, list[str]] = {}
    for group in groups:
        members = [tok for member in group for tok in [fold(member)] if tok]
        for member in members:
            bucket = mapping.setdefault(member, [])
            bucket.extend(other for other in members if other != member and other not in bucket)
    return {term: tuple(others) for term, others in mapping.items()}


@dataclass(frozen=True, slots=True)
class WeightedTerm:
    term: str
    weight: float
    expansion: bool


class QueryAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stop_words = build_stop_words(settings.extra_stop_words)
        self._synonyms = load_synonyms(settings.synonyms_file)

    @property
    def stop_words(self) -> frozenset[str]:
        return self._stop_words

    @property
    def synonym_terms(self) -> tuple[str, ...]:
        return tuple(self._synonyms)

    def synonyms_for(self, term: str) -> tuple[str, ...]:
        return tuple(
            synonym
            for synonym in self._synonyms.get(term, ())
            if " " not in synonym
        )[: self._settings.max_synonyms_per_term]

    def analyze(self, query: str) -> list[WeightedTerm]:
        """Normalize, drop stop words, then add a bounded number of configured synonyms.

        Original terms weigh 1.0, synonyms `synonym_weight`. Single-word synonyms only;
        multi-word synonym entries are ignored because the index is token based.
        """
        stripped = query.strip()
        if not stripped:
            raise InvalidInputError("Query must not be empty")
        if len(stripped) > self._settings.max_query_length:
            raise InvalidInputError(
                f"Query exceeds {self._settings.max_query_length} characters"
            )
        original = list(dict.fromkeys(tokenize(stripped, self._stop_words)))
        original = original[: self._settings.max_query_terms]
        terms = {term: WeightedTerm(term, 1.0, False) for term in original}
        for term in original:
            added = 0
            for synonym in self._synonyms.get(term, ()):
                if added >= self._settings.max_synonyms_per_term:
                    break
                if synonym in terms or " " in synonym:
                    continue
                terms[synonym] = WeightedTerm(synonym, self._settings.synonym_weight, True)
                added += 1
        return list(terms.values())
