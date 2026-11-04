from app.services.indexing.stopwords import build_stop_words
from app.services.indexing.text import fold, make_snippet, normalize_label, tokenize


def test_turkish_folding():
    assert tokenize("İSTANBUL Isparta ısparta ÇALIŞMA şeker ĞÜÖ") == [
        "istanbul", "isparta", "isparta", "calisma", "seker", "guo"]


def test_single_character_tokens_are_dropped():
    assert tokenize("a, b2 c_d x-y 3d") == ["b2", "3d"]


def test_underscore_and_punctuation_split():
    assert tokenize("foo_bar-baz.qux") == ["foo", "bar", "baz", "qux"]


def test_stop_words_are_folded():
    stops = build_stop_words()
    assert tokenize("The ve İçin araba", stops) == ["araba"]


def test_fold_handles_sharp_s_and_nfkc():
    assert fold("Straße ﬁ") == "strasse fi"


def test_label_normalization_keeps_accents():
    assert normalize_label("  Çay   İçmek ") == "çay içmek"


def test_snippet_centres_on_match():
    text = "lorem " * 40 + "target word here " + "ipsum " * 40
    snippet = make_snippet(text, {"target"}, 80)
    assert "target" in snippet and snippet.startswith("…") and snippet.endswith("…")
    assert len(snippet) <= 90


def test_snippet_fallback_and_empty():
    assert make_snippet("", {"x"}) == ""
    assert make_snippet("short text", {"nomatch"}) == "short text"
