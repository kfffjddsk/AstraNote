"""SQLAlchemy engine / session factory bound to :class:`ServerSettings`.

A single engine is created per :class:`ServerSettings` instance and reused
across requests via FastAPI's dependency-injection system.  ``init_db()``
runs ``Base.metadata.create_all`` so the MVP can boot without Alembic; a
proper Alembic migration set for the server schema is a follow-up
(tracked under Sprint 5A.2).

Refs: [REQ R16.1, R16.10]
"""
from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.server.models import Base
from src.server.settings import ServerSettings


def make_engine(settings: ServerSettings) -> Engine:
    """Create a SQLAlchemy engine for *settings*.

    SQLite URLs are configured with ``check_same_thread=False`` so the
    FastAPI thread-pool can re-use a single connection across requests; for
    other URLs the SQLAlchemy default behaviour is used.
    """
    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        settings.database_url, echo=False, future=True, connect_args=connect_args
    )


def init_db(engine: Engine) -> None:
    """Create all server-side tables on the bound engine.

    Idempotent — safe to call on every server startup.  In production the
    server will eventually be moved to Alembic migrations (5A.2).
    """
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a configured :class:`sessionmaker` for the given engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def session_dependency(
    session_factory: sessionmaker[Session],
) -> "object":
    """Build a FastAPI dependency that yields a SQLAlchemy session.

    The factory is captured by closure so the resulting callable can be
    used as a normal ``Depends(...)`` target without referencing module
    globals — important for the test fixture that builds an isolated
    application instance per test.
    """

    def _provide_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    return _provide_session
