from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import Conn, Config, get_analyzer
from app.schemas.resources import SearchResponse, SearchResult, SearchSite
from app.services.search.query import QueryAnalyzer
from app.services.search.service import SearchService

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(
    conn: Conn,
    settings: Config,
    analyzer: Annotated[QueryAnalyzer, Depends(get_analyzer)],
    q: Annotated[str, Query(min_length=1, max_length=500, description="Search query")],
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SearchResponse:
    result = SearchService(conn, settings, analyzer).search(q, page, limit)
    return SearchResponse(
        query=q, total=result.total, page=result.page, limit=result.limit,
        results=[
            SearchResult(
                url=h.url, title=h.title, description=h.description, snippet=h.snippet,
                score=h.score,
                site=SearchSite(id=h.site_id, title=h.site_title, base_domain=h.base_domain, tags=h.tags),
            )
            for h in result.hits
        ],
    )
