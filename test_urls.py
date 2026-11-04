import pytest

from app.core.exceptions import InvalidInputError
from app.core.urls import base_domain, normalize_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HTTP://Example.COM:80/a", "http://example.com/a"),
        ("https://example.com:443", "https://example.com/"),
        ("https://example.com:8443/x", "https://example.com:8443/x"),
        ("https://example.com/a/./b/../c#frag", "https://example.com/a/c"),
        ("https://example.com/a/b/..", "https://example.com/a/"),
        ("https://example.com/%7euser/%2fx", "https://example.com/~user/%2Fx"),
        ("https://example.com/a b?q=1 2", "https://example.com/a%20b?q=1%202"),
        ("https://example.com/?b=2&a=1", "https://example.com/?b=2&a=1"),
        ("https://www.example.com/", "https://www.example.com/"),
        ("https://Bücher.example/", "https://xn--bcher-kva.example/"),
        ("https://example.com./x", "https://example.com/x"),
        ("https://[2001:DB8::1]:8080/", "https://[2001:db8::1]:8080/"),
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


def test_normalize_is_idempotent() -> None:
    once = normalize_url("HTTP://Ex.com/a/../b c?x=%7e")
    assert normalize_url(once) == once


def test_relative_resolution() -> None:
    assert normalize_url("../x?y=1#z", base="https://a.com/p/q/r") == "https://a.com/p/x?y=1"


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "ftp://example.com", "javascript:alert(1)", "mailto:a@b.c", "https://",
     "https://user:pw@example.com/", "https://ex%41mple.com/", "https://example.com:99999/",
     "https://" + "a" * 2100 + ".com", "//example.com"],
)
def test_rejects_invalid(bad: str) -> None:
    with pytest.raises(InvalidInputError):
        normalize_url(bad)


def test_base_domain_keeps_www() -> None:
    assert base_domain("https://WWW.Example.com:8080/x") == "www.example.com"
