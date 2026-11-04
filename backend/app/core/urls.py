"""Canonical URL policy.

Normalization is deliberately non-destructive:
- scheme and host are lowercased; IDN hosts become punycode; a trailing host dot is removed
- default ports (80/443) are dropped; credentials are rejected
- the fragment is removed; dot segments are resolved; an empty path becomes "/"
- percent-escapes are upper-cased and unreserved characters are decoded
- the query string is preserved verbatim (no sorting, no parameter stripping)
- "www." is NOT stripped: www.example.com and example.com are different hosts
"""

import ipaddress
import re
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from app.core.exceptions import InvalidInputError

MAX_URL_LENGTH = 2048
_DEFAULT_PORTS = {"http": 80, "https": 443}
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_HOST_CHARS = re.compile(r"[a-z0-9_.-]+")
_PERCENT = re.compile(r"%([0-9A-Fa-f]{2})")
_PATH_SAFE = "/%:@!$&'()*+,;=" + "-._~"
_QUERY_SAFE = "/%:@!$&'()*+,;=?" + "-._~"


def _normalize_percent(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        char = chr(int(match.group(1), 16))
        return char if char in _UNRESERVED else "%" + match.group(1).upper()

    return _PERCENT.sub(replace, value)


def _remove_dot_segments(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    segments = path.split("/")[1:]
    stack: list[str] = []
    for index, segment in enumerate(segments):
        is_last = index == len(segments) - 1
        if segment == ".":
            if is_last:
                stack.append("")
        elif segment == "..":
            if stack:
                stack.pop()
            if is_last:
                stack.append("")
        else:
            stack.append(segment)
    return "/" + "/".join(stack)


def _ascii_host(host: str) -> str:
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        ascii_host = host.lower().rstrip(".").encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise InvalidInputError("URL host is not a valid hostname") from exc
    if not _HOST_CHARS.fullmatch(ascii_host):
        raise InvalidInputError("URL host contains invalid characters")
    return ascii_host


def normalize_url(raw: str, *, base: str | None = None) -> str:
    candidate = raw.strip()
    if base is not None:
        candidate = urljoin(base, candidate)
    if not candidate:
        raise InvalidInputError("URL must not be empty")
    if len(candidate) > MAX_URL_LENGTH:
        raise InvalidInputError(f"URL exceeds {MAX_URL_LENGTH} characters")
    try:
        parts = urlsplit(candidate)
        port = parts.port
        hostname = parts.hostname
    except ValueError as exc:
        raise InvalidInputError("URL is malformed") from exc

    scheme = parts.scheme.lower()
    if scheme not in _DEFAULT_PORTS:
        raise InvalidInputError("Only http and https URLs are supported")
    if parts.username is not None or parts.password is not None:
        raise InvalidInputError("URLs with embedded credentials are not allowed")
    if not hostname:
        raise InvalidInputError("URL must include a host")

    host = _ascii_host(hostname)
    netloc = f"[{host}]" if ":" in host else host
    if port is not None and port != _DEFAULT_PORTS[scheme]:
        netloc = f"{netloc}:{port}"

    path = quote(_normalize_percent(_remove_dot_segments(parts.path)), safe=_PATH_SAFE)
    query = quote(parts.query, safe=_QUERY_SAFE)
    return urlunsplit((scheme, netloc, path, query, ""))


def base_domain(url: str) -> str:
    """Normalized hostname used to group pages under a site (no Public Suffix List)."""
    hostname = urlsplit(url).hostname
    if not hostname:
        raise InvalidInputError("URL must include a host")
    return _ascii_host(hostname)


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"
