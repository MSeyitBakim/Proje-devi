from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import StrictModel


class TagCreate(StrictModel):
    title: str = Field(min_length=1, max_length=50)


class TagUpdate(StrictModel):
    title: str = Field(min_length=1, max_length=50)


class TagRead(BaseModel):
    id: int
    title: str
    created_at: str


class SiteCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    main_url: str = Field(min_length=1, max_length=2048)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class SiteUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    main_url: str | None = Field(default=None, min_length=1, max_length=2048)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=20)


class SiteRead(BaseModel):
    id: int
    title: str
    main_url: str
    base_domain: str
    description: str
    tags: list[str]
    created_at: str
    updated_at: str


class PageCreate(StrictModel):
    site_id: int = Field(ge=1)
    url: str = Field(min_length=1, max_length=2048)
    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=5000)
    text: str = Field(default="", max_length=200_000)


class PageUpdate(StrictModel):
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    text: str | None = Field(default=None, max_length=200_000)


class PageRead(BaseModel):
    id: int
    site_id: int
    url: str
    title: str
    description: str
    content_hash: str | None
    status_code: int | None
    doc_length: int
    crawled_at: str | None
    created_at: str
    updated_at: str


class PageDetail(PageRead):
    text: str


class CrawlRequest(StrictModel):
    url: str = Field(min_length=1, max_length=2048)
    max_pages: int = Field(default=20, ge=1, le=500)
    max_depth: int = Field(default=1, ge=0, le=5)


class CrawlJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    seed_url: str
    status: Literal["queued", "running", "completed", "failed"]
    max_pages: int
    max_depth: int
    pages_crawled: int
    pages_failed: int
    urls_pending: int
    urls_in_progress: int
    urls_done: int
    urls_failed: int
    error: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None


class SearchSite(BaseModel):
    id: int
    title: str
    base_domain: str
    tags: list[str]


class SearchResult(BaseModel):
    url: str
    title: str
    description: str
    snippet: str
    score: float
    site: SearchSite


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int
    page: int
    limit: int


class Stats(BaseModel):
    sites: int
    pages: int
    terms: int
    queue: dict[str, int]
