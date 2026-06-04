"""``POST /auth/login`` router.

Validates credentials against the existing :class:`src.core.auth.AccountStore`
on the server's ``data_dir`` and returns a freshly-issued JWT.  This MVP
endpoint deliberately accepts username + password directly; OAuth / OIDC
flows are deferred to Sprint 5B.

Refs: [BL B-86, B-88] [REQ R16.4]
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from src.core.auth import (
    AccountStore,
    AuthError,
    RateLimitError,
)
from src.server.schemas import LoginRequest, LoginResponse
from src.server.security import issue_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


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
