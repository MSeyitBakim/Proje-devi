"""Requires fastapi + httpx (TestClient)."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path, conn):  # `conn` fixture migrates the same database file
    settings = Settings(database_path=str(tmp_path / "test.db"), cors_origins=("http://localhost:5173",))
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_site_url_search_flow(client: TestClient) -> None:
    site = client.post("/api/v1/sites", json={
        "title": "Docs", "main_url": "https://docs.example.com", "tags": ["Reference"],
    })
    assert site.status_code == 201 and site.json()["base_domain"] == "docs.example.com"
    page = client.post("/api/v1/urls", json={
        "site_id": site.json()["id"], "url": "https://docs.example.com/intro",
        "title": "Introduction", "text": "Learn about inverted indexes",
    })
    assert page.status_code == 201
    result = client.get("/api/v1/search", params={"q": "inverted"}).json()
    assert result["total"] == 1 and result["results"][0]["site"]["tags"] == ["Reference"]
    assert client.get("/api/v1/stats").json()["pages"] == 1
    assert client.delete(f"/api/v1/sites/{site.json()['id']}").status_code == 204
    assert client.get("/api/v1/search", params={"q": "inverted"}).json()["total"] == 0


def test_error_envelope_and_validation(client: TestClient) -> None:
    missing = client.get("/api/v1/sites/999")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
    bad = client.post("/api/v1/sites", json={"title": "", "main_url": "ftp://x"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] in {"validation_error", "invalid_input"}
    assert client.post("/api/v1/sites", json={"title": "t", "main_url": "https://a.com", "x": 1}).status_code == 422
    assert client.get("/api/v1/search", params={"q": ""}).status_code == 422
    assert client.get("/api/v1/search", params={"q": "a", "limit": 1000}).status_code == 422


def test_conflicts_and_crawl_submission(client: TestClient) -> None:
    body = {"title": "A", "main_url": "https://a.example"}
    assert client.post("/api/v1/sites", json=body).status_code == 201
    assert client.post("/api/v1/sites", json=body).status_code == 409
    job = client.post("/api/v1/crawl", json={"url": "https://a.example", "max_pages": 5, "max_depth": 1})
    assert job.status_code == 202 and job.json()["status"] == "queued"
    assert client.get(f"/api/v1/crawl/jobs/{job.json()['id']}").json()["urls_pending"] == 1
    blocked = client.post("/api/v1/crawl", json={"url": "http://127.0.0.1/"})
    assert blocked.status_code == 422 and blocked.json()["error"]["code"] == "blocked_destination"


def test_cors_only_for_configured_origin(client: TestClient) -> None:
    ok = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    other = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in other.headers


def test_patch_with_null_fields_does_not_break_site(client: TestClient) -> None:
    site = client.post("/api/v1/sites", json={"title": "A", "main_url": "https://n.example"}).json()
    response = client.patch(f"/api/v1/sites/{site['id']}", json={"title": None, "description": "x"})
    assert response.status_code == 200 and response.json()["title"] == "A"
