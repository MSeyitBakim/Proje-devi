from fastapi import APIRouter, Response

from app.api.deps import Conn, Paging
from app.schemas.common import Page
from app.schemas.resources import CrawlJobRead, CrawlRequest
from app.services.crawler.jobs import CrawlJobService

router = APIRouter(prefix="/crawl", tags=["crawl"])


@router.post("", response_model=CrawlJobRead, status_code=202)
def submit_crawl(body: CrawlRequest, conn: Conn, response: Response) -> dict:
    """Queue a crawl. A separate worker process (`python -m app.worker`) performs it."""
    job = CrawlJobService(conn).submit(body.url, body.max_pages, body.max_depth)
    response.headers["Location"] = f"/api/v1/crawl/jobs/{job['id']}"
    return job


@router.get("/jobs", response_model=Page[CrawlJobRead])
def list_jobs(conn: Conn, paging: Paging) -> Page[CrawlJobRead]:
    items, total = CrawlJobService(conn).list_items(paging.page, paging.limit)
    return Page[CrawlJobRead](items=items, total=total, page=paging.page, limit=paging.limit)


@router.get("/jobs/{job_id}", response_model=CrawlJobRead)
def get_job(job_id: int, conn: Conn) -> dict:
    return CrawlJobService(conn).get(job_id)
