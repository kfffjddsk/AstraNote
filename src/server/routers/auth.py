"""Auth routers: ``POST /auth/login`` and ``POST /auth/callback``.

``/auth/login`` — validates credentials and returns a 24-hour JWT.
``/auth/callback`` — Sprint 5B PKCE OAuth callback; exchanges a Google
authorization code for an id_token, upserts the account, and issues a JWT.

Refs: [BL B-86, B-87, B-88] [REQ R13.14, R16.4]
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from src.core.auth import (
    AccountStore,
    AuthError,
    RateLimitError,
)
from src.server.schemas import LoginRequest, LoginResponse, OAuthCallbackRequest
from src.server.security import issue_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Internal helpers for OAuth PKCE exchange  [BL B-87]
# ---------------------------------------------------------------------------


def _exchange_oauth_code(
    settings: Any, payload: OAuthCallbackRequest
) -> dict[str, Any]:
    """Exchange an authorization code with Google's token endpoint.

    Extracted as a module-level function so tests can monkeypatch it without
    touching the endpoint handler.  Raises ``HTTPException(400)`` on any
    non-2xx response from Google.
    """
    try:
        resp = httpx.post(
            settings.google_token_url,
            data={
                "grant_type": "authorization_code",
                "code": payload.code,
                "code_verifier": payload.code_verifier,
                "redirect_uri": payload.redirect_uri,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Google token exchange network error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth token exchange failed: network error",
        ) from exc

    if not resp.is_success:
        logger.warning(
            "Google token exchange returned %d: %s", resp.status_code, resp.text[:200]
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth token exchange failed: invalid code or verifier",
        )
    return resp.json()


def _decode_id_token_claims(id_token: str) -> dict[str, Any]:
    """Decode the payload segment of a JWT id_token without verifying signature.

    The server trusts Google's TLS for transport security and does not
    re-verify the JWT signature here (acceptable for a course-project
    implementation; production would use JWKS verification).
    """
    try:
        parts = id_token.split(".")
        if len(parts) < 2:
            raise ValueError("malformed id_token")
        # Add padding so base64.urlsafe_b64decode works
        payload_b64 = parts[1] + "=="
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not decode id_token: {exc}",
        ) from exc


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "invalid credentials"},
        status.HTTP_423_LOCKED: {"description": "account locked"},
    },
)
def login(payload: LoginRequest, request: Request) -> LoginResponse:
    """Validate credentials and issue a 24-hour JWT.

    The error message is intentionally identical for ``unknown user`` and
    ``wrong password`` to avoid username-enumeration attacks.
    """
    settings = request.app.state.settings
    store: AccountStore = request.app.state.account_store
    try:
        account = store.authenticate(payload.username, payload.password)
    except RateLimitError as exc:
        # 423 Locked carries enough information for the client to retry.
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=str(exc),
        ) from exc
    except AuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    token, expires_at = issue_token(
        settings,
        account_id=account["account_id"],
        username=account["username"],
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at.isoformat(),
        account_id=account["account_id"],
        username=account["username"],
    )


@router.post(
    "/callback",
    response_model=LoginResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "bad code or verifier"},
        status.HTTP_501_NOT_IMPLEMENTED: {"description": "OAuth not configured"},
    },
)
def oauth_callback(payload: OAuthCallbackRequest, request: Request) -> LoginResponse:
    """Exchange a Google PKCE authorization code for an AstraNotes JWT.

    Requires ``ASTRANOTES_GOOGLE_CLIENT_ID`` and
    ``ASTRANOTES_GOOGLE_CLIENT_SECRET`` to be set on the server.  Returns
    501 when OAuth credentials are not configured so clients can detect
    the feature is disabled without crashing.

    Refs: [BL B-87] [REQ R13.14]
    """
    settings = request.app.state.settings
    store: AccountStore = request.app.state.account_store

    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured on this server",
        )

    # Exchange code → token response (monkeypatchable in tests)
    token_response = _exchange_oauth_code(settings, payload)

    id_token = token_response.get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return an id_token",
        )

    claims = _decode_id_token_claims(id_token)
    google_sub = claims.get("sub")
    email = claims.get("email")
    if not google_sub or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="id_token missing required claims (sub, email)",
        )

    account = store.get_or_create_oauth_account(email=email, oauth_sub=google_sub)

    token, expires_at = issue_token(
        settings,
        account_id=account["account_id"],
        username=account["username"],
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at.isoformat(),
        account_id=account["account_id"],
        username=account["username"],
    )
