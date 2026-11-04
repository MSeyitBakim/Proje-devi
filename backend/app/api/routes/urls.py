from fastapi import APIRouter, Query, Response

from app.api.deps import Conn, Config, Paging
from app.schemas.common import Page
from app.schemas.resources import PageCreate, PageDetail, PageRead, PageUpdate
from app.services.pages import PageService

router = APIRouter(prefix="/urls", tags=["urls"])


@router.get("", response_model=Page[PageRead])
def list_urls(
    conn: Conn, settings: Config, paging: Paging, site_id: int | None = Query(default=None, ge=1)
) -> Page[PageRead]:
    items, total = PageService(conn, settings).list_items(paging.page, paging.limit, site_id)
    return Page[PageRead](items=items, total=total, page=paging.page, limit=paging.limit)


@router.post("", response_model=PageDetail, status_code=201)
def create_url(body: PageCreate, conn: Conn, settings: Config) -> dict:
    return PageService(conn, settings).create(
        body.site_id, body.url, body.title, body.description, body.text
    )


@router.get("/{page_id}", response_model=PageDetail)
def get_url(page_id: int, conn: Conn, settings: Config) -> dict:
    return PageService(conn, settings).get(page_id)


@router.patch("/{page_id}", response_model=PageDetail)
def update_url(page_id: int, body: PageUpdate, conn: Conn, settings: Config) -> dict:
    return PageService(conn, settings).update(page_id, body.model_dump(exclude_unset=True, exclude_none=True))


@router.delete("/{page_id}", status_code=204)
def delete_url(page_id: int, conn: Conn, settings: Config) -> Response:
    PageService(conn, settings).delete(page_id)
    return Response(status_code=204)
