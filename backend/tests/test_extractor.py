from app.services.crawler.extractor import extract_page

HTML = """<!doctype html><html lang="tr"><head><title> Merhaba  Dünya </title>
<meta name="description" content="Açıklama  metni"><link rel="canonical" href="/canon">
<style>.x{}</style><script>var a=1</script></head><body><nav>Menu</nav><h1>Başlık</h1>
<p>Gövde <b>metin</b></p><a href="/a#top">A</a><a href="/a">A again</a>
<a href="https://other.com/x">O</a><a href="mailto:a@b.c">M</a><a href="javascript:x()">J</a>
<a href="ftp://x/y">F</a><script>alert(1)</script></body></html>"""


def test_extracts_fields_and_links():
    page = extract_page(HTML, "https://ex.com/p")
    assert page.title == "Merhaba Dünya"
    assert page.description == "Açıklama metni"
    assert page.canonical_url == "https://ex.com/canon"
    assert page.language == "tr"
    assert "alert" not in page.text and "var a" not in page.text and ".x{}" not in page.text
    assert "Gövde metin" in page.text
    assert page.discovered_links == ["https://ex.com/a", "https://other.com/x"]


def test_cross_host_canonical_ignored():
    html = '<html><head><link rel="canonical" href="https://evil.com/"></head></html>'
    assert extract_page(html, "https://ex.com/").canonical_url is None


def test_fallbacks_and_meta_robots():
    html = '<meta name="robots" content="noindex, nofollow"><h1>Only H1</h1><a href="/x">x</a>'
    page = extract_page(html, "https://ex.com/")
    assert page.title == "Only H1" and page.noindex and page.nofollow
    assert page.discovered_links == []
    assert page.description == "Only H1 x"


def test_limits_and_garbage():
    page = extract_page("<p>" + "word " * 1000, "https://ex.com/", max_text_chars=50)
    assert len(page.text) == 50
    assert extract_page("", "https://ex.com/").text == ""
    assert extract_page("<<<>>><a href", "https://ex.com/").discovered_links == []
    links = "".join(f'<a href="/{i}">x</a>' for i in range(20))
    assert len(extract_page(links, "https://ex.com/", max_links=5).discovered_links) == 5
