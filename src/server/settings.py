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

    def __post_init__(self) -> None:
        # Always store a resolved Path so downstream code never has to guess.
        self.data_dir = Path(self.data_dir).resolve()

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

        return cls(
            database_url=database_url,
            jwt_secret=secret,
            jwt_algorithm="HS256",
            jwt_expiry_hours=expiry_hours,
            data_dir=data_dir,
        )
