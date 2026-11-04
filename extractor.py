from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.core.exceptions import InvalidInputError
from app.core.urls import normalize_url
from app.services.crawler.models import ExtractedPage

_NOISE = ("script", "style", "template", "noscript", "svg", "iframe", "canvas", "head")


def _meta(soup: BeautifulSoup, **attrs: str) -> str:
    tag = soup.find("meta", attrs=attrs)
    content = tag.get("content") if tag else None
    return " ".join(str(content).split()) if content else ""


def _collapse(text: str) -> str:
    return " ".join(text.split())


def extract_page(
    html: str, page_url: str, *, max_text_chars: int = 200_000, max_links: int = 500
) -> ExtractedPage:
    """Pure function: HTML in, structured page out. Never fetches anything."""
    soup = BeautifulSoup(html, "html.parser")

    directives = {d.strip().lower() for d in _meta(soup, name="robots").split(",")}
    noindex, nofollow = "noindex" in directives, "nofollow" in directives or "none" in directives
    noindex = noindex or "none" in directives

    title = ""
    if soup.title and soup.title.string:
        title = _collapse(soup.title.string)
    title = title or _meta(soup, property="og:title")
    if not title and (h1 := soup.find("h1")):
        title = _collapse(h1.get_text(" "))

    description = _meta(soup, name="description") or _meta(soup, property="og:description")

    links: list[str] = []
    if not nofollow:
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            if len(links) >= max_links:
                break
            if "nofollow" in (anchor.get("rel") or []):
                continue
            try:
                link = normalize_url(str(anchor["href"]), base=page_url)
            except InvalidInputError:
                continue
            if link not in seen:
                seen.add(link)
                links.append(link)

    canonical = None
    tag = soup.find("link", rel="canonical", href=True)
    if tag:
        try:
            candidate = normalize_url(str(tag["href"]), base=page_url)
            if urlsplit(candidate).netloc == urlsplit(page_url).netloc:
                canonical = candidate
        except InvalidInputError:
            pass

    html_tag = soup.find("html")
    language = str(html_tag.get("lang")) if html_tag and html_tag.get("lang") else None

    for element in soup(_NOISE):
        element.decompose()
    text = _collapse(soup.get_text(" "))[:max_text_chars]
    description = description or text[:200]

    return ExtractedPage(
        url=page_url, title=title, description=description, text=text,
        discovered_links=links, canonical_url=canonical, language=language,
        noindex=noindex, nofollow=nofollow,
    )
