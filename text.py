"""Text normalization shared by indexing and query analysis.

Pipeline: NFKC -> map Turkish dotted/dotless I to "i" -> casefold -> NFD -> drop combining
marks -> NFC. The result is case- and accent-insensitive: "ÇALIŞMA", "çalışma" and "calisma"
share one token, and "ISPARTA", "Isparta" and "ısparta" do too. Trade-off: words that differ
only by those letters (e.g. "sık"/"sik") collide.

Tokens are runs of Unicode letters/digits (underscore is a separator); tokens shorter than
two characters are dropped.
"""

import re
import unicodedata
from collections import Counter

_TURKISH_I = str.maketrans({"İ": "i", "I": "i", "ı": "i"})
_TOKEN = re.compile(r"[^\W_]+")
_SPACES = re.compile(r"\s+")
MIN_TOKEN_LENGTH = 2
MAX_TOKEN_LENGTH = 64


def fold(text: str) -> str:
    decomposed = unicodedata.normalize(
        "NFD", unicodedata.normalize("NFKC", text).translate(_TURKISH_I).casefold()
    )
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped)


def normalize_label(text: str) -> str:
    """Lighter normalization for labels such as tags: keeps accents, ignores case/spacing."""
    cased = unicodedata.normalize("NFKC", text).translate(str.maketrans({"İ": "i", "I": "i"}))
    return _SPACES.sub(" ", cased.casefold()).strip()


def tokenize(text: str, stop_words: frozenset[str] = frozenset()) -> list[str]:
    tokens = _TOKEN.findall(fold(text))
    return [
        token
        for token in tokens
        if MIN_TOKEN_LENGTH <= len(token) <= MAX_TOKEN_LENGTH and token not in stop_words
    ]


def term_counts(text: str, stop_words: frozenset[str] = frozenset()) -> Counter[str]:
    return Counter(tokenize(text, stop_words))


def make_snippet(text: str, terms: set[str], max_length: int = 200) -> str:
    if not text:
        return ""
    scan_limit = 50_000
    for match in _TOKEN.finditer(text[:scan_limit]):
        if fold(match.group()) in terms:
            start = max(0, match.start() - max_length // 3)
            end = min(len(text), start + max_length)
            return _trim(text, start, end)
    return _trim(text, 0, min(len(text), max_length))


def _trim(text: str, start: int, end: int) -> str:
    if start > 0:
        space = text.find(" ", start)
        start = space + 1 if 0 <= space < end else start
    if end < len(text):
        space = text.rfind(" ", start, end)
        end = space if space > start else end
    snippet = text[start:end].strip()
    return ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")
