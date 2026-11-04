import pytest

from app.services.bloom import BloomFilter, SeenUrlFilter
from app.services.indexing.stopwords import build_stop_words
from app.services.indexing.text import fold, make_snippet, normalize_label, tokenize


def test_turkish_folding() -> None:
    assert fold("ISPARTA") == fold("Isparta") == fold("ısparta") == "isparta"
    assert fold("İstanbul ÇALIŞMA") == "istanbul calisma"
    assert fold("Straße") == "strasse"


def test_tokenize_filters_short_and_stop_words() -> None:
    stops = build_stop_words()
    assert tokenize("The quick-brown fox, a 5 and Öğrenci_bankası!", stops) == [
        "quick", "brown", "fox", "ogrenci", "bankasi",
    ]


def test_normalize_label_keeps_accents() -> None:
    assert normalize_label("  Web   SEARCH ") == "web search"
    assert normalize_label("Çay") != normalize_label("Cay")


def test_snippet_centers_on_match_and_handles_empty() -> None:
    text = "lorem " * 40 + "needle here " + "ipsum " * 40
    snippet = make_snippet(text, {"needle"}, 80)
    assert "needle" in snippet
    assert snippet.startswith("…")
    assert make_snippet("", {"x"}) == ""
    assert make_snippet("short text", {"zzz"}) == "short text"


def test_bloom_no_false_negatives_and_bounded_false_positives() -> None:
    bloom = BloomFilter(capacity=2000, error_rate=0.01)
    added = [f"https://example.com/page/{i}" for i in range(2000)]
    for url in added:
        bloom.add(url)
    assert all(url in bloom for url in added)
    false_positives = sum(f"https://other.org/{i}" in bloom for i in range(5000))
    assert false_positives / 5000 < 0.03
    assert bloom.estimated_false_positive_rate() < 0.02


@pytest.mark.parametrize(("capacity", "rate"), [(0, 0.01), (10, 0.0), (10, 1.0), (10, 1.5)])
def test_bloom_validates_arguments(capacity: int, rate: float) -> None:
    with pytest.raises(ValueError):
        BloomFilter(capacity, rate)


def test_seen_filter_disabled_or_saturated_never_reports_absent() -> None:
    assert not SeenUrlFilter(enabled=False).definitely_absent("x")
    seen = SeenUrlFilter(capacity=3, error_rate=0.01, enabled=True)
    assert seen.definitely_absent("a")
    seen.rebuild(["a", "b", "c", "d"])  # more than capacity -> saturated -> unusable
    assert not seen.definitely_absent("zzz")
