"""Uvicorn entry point for the sync server.

Run ``python -m src.server.main`` (or ``uvicorn src.server.main:app``) to
start the server in development.  Production deployment is handled in
Sprint 5A.2.

Refs: [BL B-86] [REQ R16.10]
"""
from __future__ import annotations

import logging
import os

from src.server.app import create_app
from src.server.settings import ServerSettings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Module-level ``app`` instance for ``uvicorn src.server.main:app`` imports.
# Constructed lazily inside ``__main__`` so ``import src.server.main`` from a
# test process does not blow up when ``ASTRANOTES_JWT_SECRET`` is unset.
app = None


def _make_app() -> "object":
    """Build the FastAPI app from environment-derived settings."""
    settings = ServerSettings.from_env()
    return create_app(settings)


if __name__ == "__main__":  # pragma: no cover - exercised manually
    import uvicorn

    app = _make_app()
    host = os.environ.get("ASTRANOTES_SYNC_HOST", "127.0.0.1")
    port = int(os.environ.get("ASTRANOTES_SYNC_PORT", "8765"))
    uvicorn.run(app, host=host, port=port)
