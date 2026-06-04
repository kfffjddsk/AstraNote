"""FastAPI application factory.

Builds a fully-configured app that ties together :class:`ServerSettings`,
the SQLAlchemy engine + session factory, and the auth + sync routers.
The factory pattern lets the test-suite spin up isolated apps backed by
temporary SQLite files without leaking state between tests.

Refs: [BL B-86, B-88, B-94] [REQ R16.1, R16.2, R16.4, R16.5, R16.8, R16.10]
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.auth import AccountStore
from src.server.db import init_db, make_engine, make_session_factory
from src.server.routers import auth as auth_router_module
from src.server.routers import sync as sync_router_module
from src.server.settings import ServerSettings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error envelope (R16.8)
# ---------------------------------------------------------------------------


_ERROR_CODE_BY_STATUS: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "validation_error",
    status.HTTP_423_LOCKED: "locked",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
}


def _envelope(*, error: str, message: str) -> dict[str, str]:
    """Return the canonical R16.8 JSON error envelope body."""
    return {"status": "error", "error": error, "message": message}


async def _http_exception_handler(
    _request: Request, exc: HTTPException
) -> JSONResponse:
    code = _ERROR_CODE_BY_STATUS.get(exc.status_code, "error")
    body = _envelope(error=code, message=str(exc.detail) if exc.detail else code)
    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        headers=exc.headers,
    )


async def _validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Pydantic produces a list of granular errors; we keep the most useful
    # snippet in the message field and let the client read the raw 422 body
    # via ``exc.errors()`` if it needs the detailed report.
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", ()))
    message = (
        f"{where}: {first.get('msg', 'validation error')}"
        if where
        else first.get("msg", "validation error")
    )
    body = _envelope(error="validation_error", message=message)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=body,
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_app(settings: Optional[ServerSettings] = None) -> FastAPI:
    """Build and return a fully-wired FastAPI application.

    The server's :class:`ServerSettings`, ``AccountStore`` and SQLAlchemy
    session factory are stashed on ``app.state`` so request-scoped
    dependencies (``current_account``, sync routers) can pull them via
    ``request.app.state``.
    """
    if settings is None:
        settings = ServerSettings.from_env()

    settings.data_dir.mkdir(parents=True, exist_ok=True)

    engine = make_engine(settings)
    init_db(engine)
    session_factory = make_session_factory(engine)
    account_store = AccountStore(settings.data_dir)

    app = FastAPI(
        title="AstraNotes Sync Server",
        version="5A.1",
        description=(
            "MVP cloud-sync server: JWT-authenticated push/pull for "
            "AstraNotes desktop and CLI clients."
        ),
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.account_store = account_store

    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)

    app.include_router(auth_router_module.router)
    app.include_router(sync_router_module.router)

    @app.get("/healthz", include_in_schema=False)
    def _healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
