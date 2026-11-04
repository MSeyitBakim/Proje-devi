import math
import sqlite3

import pytest

from app.core.exceptions import ConflictError, InvalidInputError, NotFoundError
from app.db.migrate import apply_migrations
from app.db.session import transaction
from app.repositories.index import IndexRepository
from app.services.pages import PageService
from app.services.search.query import QueryAnalyzer
from app.services.search.service import SearchService, idf, length_norm, tf
from app.services.sites import SiteService
from app.services.tags import TagService


def make_search(conn, settings):
    return SearchService(conn, settings, QueryAnalyzer(settings))


def add_site(conn, domain="example.com", tags=()):
    return SiteService(conn).create(domain, f"https://{domain}", "", list(tags))


def check_stats_consistent(conn) -> None:
    index = IndexRepository(conn)
    assert dict(
        (r["term"], r["df"]) for r in conn.execute("SELECT term, df FROM term_stats")
    ) == index.recomputed_frequencies()
    assert index.doc_count() == conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]


def test_migrations_are_idempotent_and_foreign_keys_enforced(conn) -> None:
    assert apply_migrations(conn) == []
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO pages (site_id, url, created_at, updated_at) VALUES (999, 'u', 'n', 'n')"
        )


def test_transaction_rolls_back_and_nests(conn) -> None:
    with pytest.raises(RuntimeError), transaction(conn):
        conn.execute("INSERT INTO tags (title, normalized_title, created_at, updated_at) VALUES ('a','a','n','n')")
        raise RuntimeError
    assert conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0] == 0
    with transaction(conn):
        conn.execute("INSERT INTO tags (title, normalized_title, created_at, updated_at) VALUES ('a','a','n','n')")
        with pytest.raises(RuntimeError), transaction(conn):
            conn.execute("INSERT INTO tags (title, normalized_title, created_at, updated_at) VALUES ('b','b','n','n')")
            raise RuntimeError
    assert [r[0] for r in conn.execute("SELECT title FROM tags")] == ["a"]


def test_scoring_matches_documented_formula(conn, settings) -> None:
    site = add_site(conn)
    pages = PageService(conn, settings)
    first = pages.create(site["id"], "https://example.com/1", "Python guide", "", "python python tools")
    pages.create(site["id"], "https://example.com/2", "Cooking", "", "pasta recipes")
    hit = make_search(conn, settings).search("python", 1, 10).hits[0]
    assert hit.page_id == first["id"]
    n, df = 2, 1
    expected_tf = 3.0 * tf(1) + 1.0 * tf(2)
    doc_len = 2 + 3
    assert math.isclose(hit.score, idf(n, df) * expected_tf * length_norm(doc_len))
    assert first["doc_length"] == doc_len


def test_title_outranks_body_and_rarer_terms_weigh_more(conn, settings) -> None:
    site = add_site(conn)
    pages = PageService(conn, settings)
    in_body = pages.create(site["id"], "https://example.com/a", "Other", "", "rust rust rust")
    in_title = pages.create(site["id"], "https://example.com/b", "Rust", "", "something else")
    ids = [h.page_id for h in make_search(conn, settings).search("rust", 1, 10).hits]
    assert ids == [in_title["id"], in_body["id"]]
    for i in range(5):
        pages.create(site["id"], f"https://example.com/c{i}", "filler", "", "common filler words")
    rare = pages.create(site["id"], "https://example.com/r", "x", "", "common unique")
    top = make_search(conn, settings).search("common unique", 1, 1).hits[0]
    assert top.page_id == rare["id"]


def test_synonyms_and_stop_words_and_accent_folding(conn, settings) -> None:
    site = add_site(conn)
    pages = PageService(conn, settings)
    pages.create(site["id"], "https://example.com/o", "Otomobil", "", "kullanılmış otomobil")
    pages.create(site["id"], "https://example.com/c", "Çalışma", "", "çalışma saatleri")
    pages.create(site["id"], "https://example.com/p", "Programming", "", "software engineering and coding")
    search = make_search(conn, settings)
    assert search.search("araba", 1, 10).total == 1  # via synonym expansion
    assert search.search("CALISMA", 1, 10).total == 1  # accent/case folding
    assert search.search("programlama", 1, 10).total == 1  # Turkish keyword should map to programming
    assert search.search("progrmlama", 1, 10).total == 1  # typo corrected to synonym not in the index
    assert search.search("the", 1, 10).total == 0  # only stop words


def test_search_supports_substrings_and_common_typos(conn, settings) -> None:
    site = add_site(conn)
    pages = PageService(conn, settings)
    pages.create(site["id"], "https://example.com/p", "Programming", "", "python language")
    search = make_search(conn, settings)

    assert search.search("programmi", 1, 10).total == 1  # LIKE '%term%' fallback
    assert search.search("programing", 1, 10).total == 1  # one missing letter
    assert search.search("progrmming", 1, 10).total == 1  # one substituted letter
    assert search.search("unrelated", 1, 10).total == 0


def test_empty_and_oversized_queries_rejected(conn, settings) -> None:
    search = make_search(conn, settings)
    with pytest.raises(InvalidInputError):
        search.search("   ", 1, 10)
    with pytest.raises(InvalidInputError):
        search.search("x" * 500, 1, 10)


def test_pagination_is_stable_and_bounded(conn, settings) -> None:
    site = add_site(conn)
    pages = PageService(conn, settings)
    for i in range(7):
        pages.create(site["id"], f"https://example.com/p{i}", "same title", "", "same body")
    search = make_search(conn, settings)
    seen = [h.page_id for p in (1, 2, 3) for h in search.search("same", p, 3).hits]
    assert seen == sorted(seen) and len(seen) == len(set(seen)) == 7
    assert search.search("same", 4, 3).hits == []
    assert search.search("same", 1, 3).total == 7


def test_update_delete_and_cascade_keep_index_consistent(conn, settings) -> None:
    site = add_site(conn)
    other = add_site(conn, "other.org")
    pages = PageService(conn, settings)
    page = pages.create(site["id"], "https://example.com/1", "Alpha", "", "alpha beta")
    pages.create(other["id"], "https://other.org/1", "Beta", "", "beta gamma")
    search = make_search(conn, settings)
    pages.update(page["id"], {"text": "delta"})
    assert search.search("beta", 1, 10).total == 1  # stale term removed from edited page
    assert search.search("delta", 1, 10).total == 1
    check_stats_consistent(conn)
    SiteService(conn).delete(site["id"])  # cascades through pages and postings
    assert search.search("delta", 1, 10).total == 0
    check_stats_consistent(conn)
    assert IndexRepository(conn).doc_count() == 1


def test_rebuild_reproduces_identical_index(conn, settings) -> None:
    site = add_site(conn)
    pages = PageService(conn, settings)
    pages.create(site["id"], "https://example.com/1", "Alpha", "d", "alpha beta beta")
    pages.create(site["id"], "https://example.com/2", "Gamma", "", "beta")
    before = conn.execute("SELECT * FROM postings ORDER BY term, page_id").fetchall()
    stats_before = conn.execute("SELECT * FROM term_stats ORDER BY term").fetchall()
    assert pages.rebuild_index() == 2
    assert [tuple(r) for r in conn.execute("SELECT * FROM postings ORDER BY term, page_id")] == [
        tuple(r) for r in before
    ]
    assert [tuple(r) for r in conn.execute("SELECT * FROM term_stats ORDER BY term")] == [
        tuple(r) for r in stats_before
    ]


def test_page_integrity_rules(conn, settings) -> None:
    site = add_site(conn)
    pages = PageService(conn, settings)
    pages.create(site["id"], "https://example.com/1", "t", "", "x")
    with pytest.raises(ConflictError):
        pages.create(site["id"], "https://example.com/1#frag", "t", "", "x")
    with pytest.raises(InvalidInputError):
        pages.create(site["id"], "https://elsewhere.com/1", "t", "", "x")
    with pytest.raises(NotFoundError):
        pages.create(999, "https://example.com/2", "t", "", "x")


def test_sites_and_tags(conn) -> None:
    sites, tags = SiteService(conn), TagService(conn)
    a = sites.create("A", "https://A.com", "", ["Web", " web ", "Search"])
    assert a["tags"] == ["Search", "Web"] and a["main_url"] == "https://a.com/"
    with pytest.raises(ConflictError):
        sites.create("dup", "https://a.com/", "", [])
    tag = next(t for t in tags.list_items(1, 10)[0] if t["title"] == "Web")
    tags.rename(tag["id"], "Internet")
    assert sites.get(a["id"])["tags"] == ["Internet", "Search"]
    tags.delete(tag["id"])
    assert sites.get(a["id"])["tags"] == ["Search"]
    assert sites.update(a["id"], {"tags": []})["tags"] == []
    with pytest.raises(ConflictError):
        tags.create("search")
    with pytest.raises(NotFoundError):
        sites.get(12345)


def test_update_ignores_explicit_nulls(conn) -> None:
    sites = SiteService(conn)
    site = sites.create("Keep", "https://keep.example", "d", [])
    updated = sites.update(site["id"], {"title": None, "main_url": None, "description": "new"})
    assert updated["title"] == "Keep" and updated["description"] == "new"
