"""ASGI middleware that enforces HTTPS-only sync server traffic.

In production deployments the AstraNotes sync server must only serve
clients over HTTPS so bearer-JWTs cannot be sniffed off the wire.  The
middleware short-circuits the request with the canonical R16.8 error
envelope when the connection is plain HTTP and not exempted.

Bypass rules (any one of these allows the request to flow through):

* ``settings.enforce_https`` is ``False`` — explicit dev opt-out via
  ``ASTRANOTES_DEV_HTTP=1`` or under the pytest harness.
* The request path is ``/healthz`` — load balancers and uptime probes
  should always be reachable.
* The ``Host`` header is ``localhost``, ``127.0.0.1`` or ``::1`` — local
  developer runs without TLS termination.
* The ASGI scope has ``scheme == "https"``.
* The ``X-Forwarded-Proto`` header (set by a reverse proxy that already
  terminated TLS) is exactly ``"https"``.

Refs: [BL B-92] [REQ R16.6, R16.8]
"""
from __future__ import annotations

import json
import logging
from typing import Awaitable, Callable, Iterable

from src.server.settings import ServerSettings

logger = logging.getLogger(__name__)

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Pre-rendered R16.8 envelope so we never allocate a JSONResponse object on
# the hot rejection path.
_REJECT_BODY = json.dumps(
    {
        "status": "error",
        "error": "bad_request",
        "message": "HTTPS is required for this endpoint",
    }
).encode("utf-8")


def _header(headers: Iterable[tuple[bytes, bytes]], name: bytes) -> str:
    """Return the first matching header value as a UTF-8 string, or ``""``."""
    target = name.lower()
    for key, value in headers:
        if key.lower() == target:
            try:
                return value.decode("latin-1")
            except UnicodeDecodeError:  # pragma: no cover - belt + braces
                return ""
    return ""


class HTTPSEnforcementMiddleware:
    """Reject plain-HTTP requests when TLS enforcement is enabled."""

    def __init__(self, app: Callable[..., Awaitable[None]], *, settings: ServerSettings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: dict, receive, send) -> None:
        # Lifespan, websocket and any non-HTTP scope passes through.
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        if not self.settings.enforce_https:
            await self.app(scope, receive, send)
            return

        # Always allow load-balancer health probes.
        if scope.get("path") == "/healthz":
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers") or []
        host_header = _header(headers, b"host")
        host_only = host_header.split(":", 1)[0].strip().lower()
        # Strip optional IPv6 brackets like ``[::1]:8000``.
        if host_only.startswith("[") and host_only.endswith("]"):
            host_only = host_only[1:-1]

        if host_only in _LOOPBACK_HOSTS:
            await self.app(scope, receive, send)
            return

        if scope.get("scheme") == "https":
            await self.app(scope, receive, send)
            return

        forwarded_proto = (
            _header(headers, b"x-forwarded-proto").split(",", 1)[0].strip().lower()
        )
        if forwarded_proto == "https":
            await self.app(scope, receive, send)
            return

        # Reject — write the R16.8 envelope directly.
        logger.info(
            "rejected plain-HTTP request to %s (host=%r)",
            scope.get("path"),
            host_header,
        )
        await send(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_REJECT_BODY)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _REJECT_BODY})
