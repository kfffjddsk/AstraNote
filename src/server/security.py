"""JWT issuance and verification for the sync server.

Uses ``joserfc`` for HS256 sign / verify.

Refs: [BL B-88, B-94] [REQ R16.4, R16.5]
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from joserfc import jwt as _jwt
from joserfc.errors import BadSignatureError, DecodeError, ExpiredTokenError, JoseError
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry as _ClaimsRegistry

_CLAIMS_REGISTRY = _ClaimsRegistry(exp={"essential": True})

from src.server.settings import ServerSettings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TokenError(Exception):
    """Base error for JWT-related problems."""


class TokenInvalid(TokenError):
    """Token is malformed, has a bad signature, or fails claim validation."""


class TokenExpired(TokenError):
    """Token's ``exp`` claim is in the past."""


# ---------------------------------------------------------------------------
# Claims dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AccountClaims:
    """Decoded JWT claims for an authenticated request.

    The router code never reads the raw token; it depends on
    :func:`current_account` which produces this object.
    """

    account_id: str
    username: str
    issued_at: int
    expires_at: int


# ---------------------------------------------------------------------------
# Issue / verify
# ---------------------------------------------------------------------------


def issue_token(
    settings: ServerSettings,
    *,
    account_id: str,
    username: str,
    issued_at: Optional[datetime] = None,
) -> tuple[str, datetime]:
    """Sign a JWT for *account_id* / *username*.

    Returns ``(token, expires_at)`` so the caller can include the absolute
    expiry in its response body.
    """
    now = issued_at or datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.jwt_expiry_hours)
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    payload = {
        "sub": account_id,
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    key = OctKey.import_key(settings.jwt_secret.encode())
    token = _jwt.encode(header, payload, key)
    return token, expires_at


def verify_token(settings: ServerSettings, token: str) -> AccountClaims:
    """Decode + validate *token* and return :class:`AccountClaims`.

    Raises :class:`TokenExpired` if the ``exp`` claim is past, otherwise
    :class:`TokenInvalid` for any other failure (bad signature, malformed,
    missing claim).
    """
    key = OctKey.import_key(settings.jwt_secret.encode())
    try:
        result = _jwt.decode(token, key)
        _CLAIMS_REGISTRY.validate(result.claims)
    except ExpiredTokenError as exc:
        raise TokenExpired("token has expired") from exc
    except (BadSignatureError, DecodeError) as exc:
        raise TokenInvalid("invalid token signature") from exc
    except JoseError as exc:
        raise TokenInvalid(f"invalid token: {exc}") from exc

    claims = result.claims
    sub = claims.get("sub")
    username = claims.get("username")
    iat = claims.get("iat")
    exp = claims.get("exp")
    if not isinstance(sub, str) or not sub:
        raise TokenInvalid("missing 'sub' claim")
    if not isinstance(username, str) or not username:
        raise TokenInvalid("missing 'username' claim")
    if not isinstance(iat, int) or not isinstance(exp, int):
        raise TokenInvalid("malformed 'iat' / 'exp' claim")

    return AccountClaims(
        account_id=sub, username=username, issued_at=iat, expires_at=exp
    )


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def _settings_from_request(request: Request) -> ServerSettings:
    """Pull the :class:`ServerSettings` instance attached to ``app.state``."""
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, ServerSettings):
        # This is a server-side configuration error, not a user error.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="server misconfigured: missing settings",
        )
    return settings


def _unauthorized(message: str) -> HTTPException:
    """Build a uniform 401 response with a ``WWW-Authenticate`` header."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_account(request: Request) -> AccountClaims:
    """FastAPI dependency that extracts and validates the bearer token.

    Returns the decoded :class:`AccountClaims`.  Any failure surfaces as
    HTTP 401 with the JSON error envelope produced by
    :func:`src.server.app.create_app`'s exception handlers.
    """
    settings = _settings_from_request(request)
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth:
        raise _unauthorized("missing Authorization header")
    parts = auth.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise _unauthorized("malformed Authorization header")
    token = parts[1]
    try:
        return verify_token(settings, token)
    except TokenExpired:
        raise _unauthorized("token has expired") from None
    except TokenInvalid as exc:
        raise _unauthorized(str(exc)) from None


# Re-export Depends for convenient ``Depends(current_account)`` usage in
# routers without forcing every router to import ``fastapi.Depends`` again.
CurrentAccount = Depends(current_account)
