from fastapi import APIRouter

from app.api.deps import Conn
from app.repositories.crawl import CrawlQueue
from app.repositories.index import IndexRepository
from app.schemas.resources import Stats

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(conn: Conn) -> dict[str, str]:
    conn.execute("SELECT 1")
    return {"status": "ok"}


@router.get("/stats", response_model=Stats)
def stats(conn: Conn) -> Stats:
    index = IndexRepository(conn)
    return Stats(
        sites=conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0],
        pages=index.doc_count(),
        terms=index.term_count(),
        queue=CrawlQueue(conn).status_counts(),
    )
