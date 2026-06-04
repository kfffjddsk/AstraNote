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
from urllib.parse import parse_qs, urlparse

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.server.models import Base
from src.server.settings import ServerSettings


# Postgres ``sslmode`` values that Sprint 5A.2 considers "secure enough"
# for non-loopback connections.  ``require`` is the floor; ``verify-ca``
# and ``verify-full`` add certificate-chain validation on top.
_PG_SECURE_SSLMODES = frozenset({"require", "verify-ca", "verify-full"})
_PG_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", ""})


def make_engine(settings: ServerSettings) -> Engine:
    """Create a SQLAlchemy engine for *settings*.

    SQLite URLs are configured with ``check_same_thread=False`` so the
    FastAPI thread-pool can re-use a single connection across requests.
    PostgreSQL URLs (Sprint 5A.2 hardening, B-44 / B-63) gain pool tuning
    plus a ``sslmode=require`` guard for any non-loopback host.
    """
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {}
    url = settings.database_url

    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    elif url.startswith("postgresql"):
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host not in _PG_LOOPBACK_HOSTS:
            qs = parse_qs(parsed.query)
            sslmode_values = qs.get("sslmode") or [""]
            sslmode = sslmode_values[0].lower()
            if sslmode not in _PG_SECURE_SSLMODES:
                raise ValueError(
                    "Production Postgres DSN must include "
                    f"sslmode=require: {url!r}"
                )
        # B-93 connection pool tuning.  ``pool_pre_ping`` weeds out stale
        # connections after a network blip; ``pool_recycle=3600`` rotates
        # connections every hour to dodge server-side idle timeouts.
        engine_kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

    return create_engine(
        url,
        echo=False,
        future=True,
        connect_args=connect_args,
        **engine_kwargs,
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
