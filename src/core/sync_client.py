"""HTTP client for the AstraNotes sync server.

Thin wrapper around :class:`httpx.Client` that knows the three endpoints
exposed by Sprint 5A.1 (``/auth/login``, ``/sync/push``, ``/sync/pull``)
plus on-disk token caching.  All non-2xx responses are surfaced as
:class:`SyncError` (or its specialised subclasses) so callers never have
to inspect raw HTTP status codes.

Refs: [BL B-86, B-88, B-90] [REQ R16.1, R16.2, R16.4, R16.8]
"""
from __future__ import annotations

import json
import logging
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

import httpx

logger = logging.getLogger(__name__)


_TOKEN_FILENAME = ".sync_token"
_DEFAULT_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SyncError(Exception):
    """Generic sync-client error.

    Attributes:
        status: HTTP status code (or 0 for non-HTTP failures).
        message: Human-readable explanation.
    """

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"[HTTP {status}] {message}" if status else message)
        self.status = status
        self.message = message


class AuthenticationError(SyncError):
    """401 — invalid credentials or expired/missing token."""


class AccountLockedError(SyncError):
    """423 — server-side account lockout."""


class ServerError(SyncError):
    """5xx — server reported an internal failure."""


# ---------------------------------------------------------------------------
# Token cache
# ---------------------------------------------------------------------------


def _token_path(data_dir: Path) -> Path:
    return Path(data_dir).resolve() / _TOKEN_FILENAME


def save_cached_token(data_dir: Path, response: Mapping[str, Any]) -> None:
    """Persist a login response to ``<data-dir>/.sync_token``.

    Restricts the file to owner read/write (best-effort on Windows NTFS).
    Refs: [REQ R16.4]
    """
    payload = {
        "access_token": response["access_token"],
        "expires_at": response["expires_at"],
        "account_id": response["account_id"],
        "username": response["username"],
    }
    path = _token_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        logger.warning("Could not restrict sync token permissions on %s.", path)


def load_cached_token(data_dir: Path) -> Optional[dict[str, Any]]:
    """Return the cached token dict, or ``None`` if absent / expired / corrupt.

    Expired files are silently deleted to keep ``<data-dir>`` clean.
    """
    path = _token_path(data_dir)
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        expires_at = datetime.fromisoformat(data["expires_at"])
        if datetime.now(timezone.utc) >= expires_at:
            logger.info("Cached sync token expired; removing %s.", path)
            path.unlink(missing_ok=True)
            return None
        return data
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        logger.warning("Corrupt sync token at %s; removing.", path)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def delete_cached_token(data_dir: Path) -> bool:
    """Delete the cached token file.  Returns True if a file was removed."""
    path = _token_path(data_dir)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def _wrap_response(response: httpx.Response) -> dict[str, Any]:
    """Convert a successful response to JSON, or raise a :class:`SyncError`."""
    if 200 <= response.status_code < 300:
        try:
            return response.json()
        except ValueError:
            raise SyncError(response.status_code, "server returned non-JSON body")
    # Non-2xx: prefer the server's ``message`` envelope when present.
    message = f"HTTP {response.status_code}"
    try:
        body = response.json()
        if isinstance(body, dict):
            message = body.get("message") or body.get("detail") or message
    except ValueError:
        pass
    if response.status_code == httpx.codes.UNAUTHORIZED:
        raise AuthenticationError(response.status_code, message)
    if response.status_code == httpx.codes.LOCKED:
        raise AccountLockedError(response.status_code, message)
    if 500 <= response.status_code < 600:
        raise ServerError(response.status_code, message)
    raise SyncError(response.status_code, message)


class SyncClient:
    """Thin HTTP wrapper for ``/auth`` and ``/sync`` endpoints.

    The client may be constructed with either a ``base_url`` (production)
    or a pre-built :class:`httpx.Client` (used by the test-suite to plug
    in :class:`fastapi.testclient.TestClient`'s ASGI transport).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        client: Optional[httpx.Client] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        if client is None:
            if not base_url:
                raise ValueError("either base_url or client must be provided")
            client = httpx.Client(base_url=base_url, timeout=timeout)
        self._client = client
        self._owns_client = client is not None and base_url is not None

    # ------------------------------------------------------------------
    # Context manager helpers
    # ------------------------------------------------------------------

    def __enter__(self) -> "SyncClient":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> dict[str, Any]:
        """Call ``POST /auth/login`` and return the parsed response body."""
        try:
            response = self._client.post(
                "/auth/login",
                json={"username": username, "password": password},
            )
        except httpx.HTTPError as exc:
            raise SyncError(0, f"network error: {exc}") from exc
        return _wrap_response(response)

    def push(self, token: str, notes: list[Mapping[str, Any]]) -> dict[str, Any]:
        """Call ``POST /sync/push`` with the bearer token and note list."""
        try:
            response = self._client.post(
                "/sync/push",
                json={"notes": list(notes)},
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            raise SyncError(0, f"network error: {exc}") from exc
        return _wrap_response(response)

    def callback_exchange(
        self, code: str, code_verifier: str, redirect_uri: str
    ) -> dict[str, Any]:
        """Call ``POST /auth/callback`` with PKCE verifier; return token response.

        Refs: [BL B-87] [REQ R13.14]
        """
        try:
            response = self._client.post(
                "/auth/callback",
                json={
                    "code": code,
                    "code_verifier": code_verifier,
                    "redirect_uri": redirect_uri,
                },
            )
        except httpx.HTTPError as exc:
            raise SyncError(0, f"network error: {exc}") from exc
        return _wrap_response(response)

    def pull(self, token: str, since: Optional[str] = None) -> dict[str, Any]:
        """Call ``GET /sync/pull?since=<since>`` with the bearer token."""
        params = {"since": since} if since else None
        try:
            response = self._client.get(
                "/sync/pull",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            raise SyncError(0, f"network error: {exc}") from exc
        return _wrap_response(response)
