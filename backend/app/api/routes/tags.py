from fastapi import APIRouter, Response

from app.api.deps import Conn, Paging
from app.schemas.common import Page
from app.schemas.resources import TagCreate, TagRead, TagUpdate
from app.services.tags import TagService

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=Page[TagRead])
def list_tags(conn: Conn, paging: Paging) -> Page[TagRead]:
    items, total = TagService(conn).list_items(paging.page, paging.limit)
    return Page[TagRead](items=items, total=total, page=paging.page, limit=paging.limit)


@router.post("", response_model=TagRead, status_code=201)
def create_tag(body: TagCreate, conn: Conn) -> dict:
    return TagService(conn).create(body.title)


@router.patch("/{tag_id}", response_model=TagRead)
def rename_tag(tag_id: int, body: TagUpdate, conn: Conn) -> dict:
    return TagService(conn).rename(tag_id, body.title)


@router.delete("/{tag_id}", status_code=204)
def delete_tag(tag_id: int, conn: Conn) -> Response:
    TagService(conn).delete(tag_id)
    return Response(status_code=204)
