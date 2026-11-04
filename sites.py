from fastapi import APIRouter, Query, Response

from app.api.deps import Conn, Paging
from app.schemas.common import Page
from app.schemas.resources import SiteCreate, SiteRead, SiteUpdate
from app.services.sites import SiteService

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("", response_model=Page[SiteRead])
def list_sites(conn: Conn, paging: Paging, tag_id: int | None = Query(default=None, ge=1)) -> Page[SiteRead]:
    items, total = SiteService(conn).list_items(paging.page, paging.limit, tag_id)
    return Page[SiteRead](items=items, total=total, page=paging.page, limit=paging.limit)


@router.post("", response_model=SiteRead, status_code=201)
def create_site(body: SiteCreate, conn: Conn) -> dict:
    return SiteService(conn).create(body.title, body.main_url, body.description, body.tags)


@router.get("/{site_id}", response_model=SiteRead)
def get_site(site_id: int, conn: Conn) -> dict:
    return SiteService(conn).get(site_id)


@router.patch("/{site_id}", response_model=SiteRead)
def update_site(site_id: int, body: SiteUpdate, conn: Conn) -> dict:
    return SiteService(conn).update(site_id, body.model_dump(exclude_none=True))


@router.delete("/{site_id}", status_code=204)
def delete_site(site_id: int, conn: Conn) -> Response:
    SiteService(conn).delete(site_id)
    return Response(status_code=204)
