"""Sync-server runtime settings.

The server is configured exclusively via environment variables and explicit
constructor overrides (used by tests).  ``ASTRANOTES_JWT_SECRET`` is the only
truly required variable in production; ``DATABASE_URL`` defaults to a local
SQLite file so the MVP works out of the box.

Refs: [BL B-86, B-88] [REQ R16.4, R16.10]
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Deterministic secret used only when running under pytest.  This keeps unit
# tests hermetic without forcing every test fixture to set an env variable
# and without leaking a usable secret into production builds.
_TEST_JWT_SECRET = "test-secret-do-not-use-in-prod"  # noqa: S105 - test-only

_DEFAULT_DATABASE_URL = "sqlite:///./astranotes_sync.db"
_DEFAULT_DATA_DIR = Path("./astranotes_server_data").resolve()


def _running_under_pytest() -> bool:
    """Return ``True`` when the process is executing a pytest test.

    The check is deliberately permissive: either the standard
    ``PYTEST_CURRENT_TEST`` variable is set (during a test) or the parent
    framework loader is on ``sys.argv[0]`` — both indicate test context.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    # Fallback: ``sys.argv[0]`` ends with ``pytest`` when invoked via
    # ``python -m pytest``.  Avoid importing sys at module top-level so this
    # function remains a single self-contained probe.
    import sys

    argv0 = (sys.argv[0] if sys.argv else "").lower()
    return argv0.endswith("pytest") or "pytest" in argv0


@dataclass
class ServerSettings:
    """Server-side configuration values.

    Construct with ``ServerSettings.from_env()`` for production, or instantiate
    directly in tests with explicit keyword arguments.

    Refs: [REQ R16.4, R16.10]
    """

    database_url: str = _DEFAULT_DATABASE_URL
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    data_dir: Path = field(default_factory=lambda: _DEFAULT_DATA_DIR)
    # Sprint 5A.2 hardening fields.  ``enforce_https`` defaults to ``None`` so
    # ``__post_init__`` can resolve it to ``False`` under pytest and ``True``
    # in production without breaking any 5A.1 fixture that constructs
    # ``ServerSettings(...)`` directly.  Refs: [BL B-92, B-93, B-95]
    enforce_https: Optional[bool] = None
    rate_limit_per_minute: int = 60
    db_pool_size: int = 10
    db_max_overflow: int = 20

    def __post_init__(self) -> None:
        # Always store a resolved Path so downstream code never has to guess.
        self.data_dir = Path(self.data_dir).resolve()
        if self.enforce_https is None:
            # Pytest runs talk to ``http://testserver`` via ``TestClient``; we
            # must not reject those out of the box.  Production gets the safe
            # default of HTTPS-required.
            self.enforce_https = not _running_under_pytest()

    @classmethod
    def from_env(cls) -> "ServerSettings":
        """Build a :class:`ServerSettings` from environment variables.

        Raises :class:`RuntimeError` if ``ASTRANOTES_JWT_SECRET`` is unset
        outside of a pytest run.
        """
        secret = os.environ.get("ASTRANOTES_JWT_SECRET", "")
        if not secret:
            if _running_under_pytest():
                logger.info(
                    "ASTRANOTES_JWT_SECRET not set; using deterministic "
                    "pytest secret."
                )
                secret = _TEST_JWT_SECRET
            else:
                raise RuntimeError(
                    "ASTRANOTES_JWT_SECRET environment variable is required "
                    "to start the AstraNotes sync server."
                )

        database_url = os.environ.get(
            "ASTRANOTES_SYNC_DATABASE_URL", _DEFAULT_DATABASE_URL
        )
        data_dir_raw: Optional[str] = os.environ.get("ASTRANOTES_SYNC_DATA_DIR")
        data_dir = Path(data_dir_raw).resolve() if data_dir_raw else _DEFAULT_DATA_DIR

        expiry_raw = os.environ.get("ASTRANOTES_JWT_EXPIRY_HOURS", "24")
        try:
            expiry_hours = int(expiry_raw)
        except ValueError:
            logger.warning(
                "Invalid ASTRANOTES_JWT_EXPIRY_HOURS=%r; falling back to 24.",
                expiry_raw,
            )
            expiry_hours = 24

        # Sprint 5A.2 hardening env vars.  ``ASTRANOTES_DEV_HTTP=1`` is the
        # canonical opt-out for HTTPS enforcement (developer loopback runs).
        # Pytest also disables it so the existing test suite stays green.
        dev_http_raw = os.environ.get("ASTRANOTES_DEV_HTTP", "").strip().lower()
        if dev_http_raw in ("1", "true", "yes"):
            enforce_https = False
        elif _running_under_pytest():
            enforce_https = False
        else:
            enforce_https = True

        rate_limit_raw = os.environ.get("ASTRANOTES_RATE_LIMIT_PER_MIN", "60")
        try:
            rate_limit_per_minute = int(rate_limit_raw)
        except ValueError:
            logger.warning(
                "Invalid ASTRANOTES_RATE_LIMIT_PER_MIN=%r; falling back to 60.",
                rate_limit_raw,
            )
            rate_limit_per_minute = 60

        pool_size_raw = os.environ.get("ASTRANOTES_DB_POOL_SIZE", "10")
        try:
            db_pool_size = int(pool_size_raw)
        except ValueError:
            logger.warning(
                "Invalid ASTRANOTES_DB_POOL_SIZE=%r; falling back to 10.",
                pool_size_raw,
            )
            db_pool_size = 10

        max_overflow_raw = os.environ.get("ASTRANOTES_DB_MAX_OVERFLOW", "20")
        try:
            db_max_overflow = int(max_overflow_raw)
        except ValueError:
            logger.warning(
                "Invalid ASTRANOTES_DB_MAX_OVERFLOW=%r; falling back to 20.",
                max_overflow_raw,
            )
            db_max_overflow = 20

        return cls(
            database_url=database_url,
            jwt_secret=secret,
            jwt_algorithm="HS256",
            jwt_expiry_hours=expiry_hours,
            data_dir=data_dir,
            enforce_https=enforce_https,
            rate_limit_per_minute=rate_limit_per_minute,
            db_pool_size=db_pool_size,
            db_max_overflow=db_max_overflow,
        )
