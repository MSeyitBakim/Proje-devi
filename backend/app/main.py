import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import crawl, health, search, sites, tags, urls
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.db.migrate import apply_migrations
from app.db.session import open_connection
from app.services.search.query import QueryAnalyzer

log = logging.getLogger("app")


def _error(status: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    body: dict = {"code": code, "message": message}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.auto_migrate:
            with open_connection(settings.database_path) as conn:
                apply_migrations(conn)
        yield

    app = FastAPI(title="Search Engine API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.analyzer = QueryAnalyzer(settings)
    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return _error(422, "validation_error", "Request validation failed", details)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_error", extra={"path": request.url.path}, exc_info=exc)
        return _error(500, "internal_error", "Internal server error")

    for module in (search, sites, urls, tags, crawl, health):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()  # uvicorn app.main:app
