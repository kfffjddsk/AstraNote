"""AstraNotes sync server package.

FastAPI-based HTTP server that exposes ``/auth/login``, ``/sync/push`` and
``/sync/pull`` endpoints to the desktop / CLI client.  See
``planning/requirements.md`` §R16 and ``planning/backlog.md`` Sprint 5A.

Refs: [BL B-86, B-88, B-94] [REQ R16.1, R16.2, R16.4, R16.5, R16.8, R16.10]
"""
from __future__ import annotations

from src.server.app import create_app

__all__ = ["create_app"]
