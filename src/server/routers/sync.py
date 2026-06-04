"""``/sync/push`` and ``/sync/pull`` endpoints.

Both endpoints are gated by the bearer-JWT dependency
:func:`src.server.security.current_account`.  Every server-side query is
scoped by ``claims.account_id`` so cross-account access is impossible
(R16.5 / B-94).  Conflict policy is last-write-wins on ``modified_at``.

Refs: [BL B-86, B-94] [REQ R16.1, R16.2, R16.5]
"""
from __future__ import annotations

import base64
import binascii
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.server.models import ServerNoteRow
from src.server.rate_limit import AccountRateLimiter, RateLimitExceeded
from src.server.schemas import (
    NotePayload,
    PullResponse,
    PushRequest,
    PushResponse,
)
from src.server.security import AccountClaims, current_account

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


# ---------------------------------------------------------------------------
# Rate limiting (B-95 / R16.7)
# ---------------------------------------------------------------------------


def _rate_limit_check(
    request: Request,
    claims: AccountClaims = Depends(current_account),
) -> AccountClaims:
    """Per-account sliding-window check; raises 429 with ``Retry-After``.

    Reads the shared :class:`AccountRateLimiter` off ``app.state``.  When
    no limiter is attached (e.g. an embedded test harness) the dependency
    becomes a no-op so unit tests remain deterministic.
    """
    limiter: Optional[AccountRateLimiter] = getattr(
        request.app.state, "rate_limiter", None
    )
    if limiter is None:
        return claims
    try:
        limiter.check(claims.account_id)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"rate limit exceeded; retry after "
                f"{exc.retry_after_seconds}s"
            ),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from None
    return claims


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    """Return the current UTC instant as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _decode_blob(b64_text: Optional[str]) -> Optional[bytes]:
    """Decode a base64-encoded blob; raise 400 on malformed input."""
    if b64_text is None:
        return None
    try:
        return base64.b64decode(b64_text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"malformed encrypted_blob_b64: {exc}",
        ) from None


def _encode_blob(blob: Optional[bytes]) -> Optional[str]:
    """Encode bytes as base64 ASCII for the wire."""
    if blob is None:
        return None
    return base64.b64encode(bytes(blob)).decode("ascii")


def _row_to_payload(row: ServerNoteRow) -> NotePayload:
    """Convert an ORM row into the JSON-serialisable payload model."""
    return NotePayload(
        id=row.note_id,
        title=row.title,
        content=row.content,
        is_encrypted=bool(row.is_encrypted),
        encrypted_blob_b64=_encode_blob(row.encrypted_blob),
        created_at=row.created_at,
        modified_at=row.modified_at,
        account_id=row.account_id,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/push", response_model=PushResponse)
def push(
    body: PushRequest,
    request: Request,
    claims: AccountClaims = Depends(_rate_limit_check),
) -> PushResponse:
    """Upsert each note from *body* under the authenticated account.

    Last-write-wins by ``modified_at``.  The server always overrides
    ``account_id`` with the JWT subject — clients cannot spoof ownership
    (B-94).
    """
    factory = request.app.state.session_factory
    session: Session = factory()
    accepted = 0
    skipped = 0
    server_time = _utcnow_iso()
    try:
        for note in body.notes:
            blob = _decode_blob(note.encrypted_blob_b64)
            existing = (
                session.query(ServerNoteRow)
                .filter(
                    ServerNoteRow.account_id == claims.account_id,
                    ServerNoteRow.note_id == note.id,
                )
                .one_or_none()
            )
            if existing is None:
                session.add(
                    ServerNoteRow(
                        note_id=note.id,
                        account_id=claims.account_id,
                        title=note.title,
                        content=note.content,
                        is_encrypted=bool(note.is_encrypted),
                        encrypted_blob=blob,
                        created_at=note.created_at,
                        modified_at=note.modified_at,
                        server_synced_at=server_time,
                    )
                )
                accepted += 1
                continue
            # Existing row: compare modified_at (LWW).  Equality counts as
            # "newer" so retries with identical timestamps still succeed.
            if note.modified_at >= existing.modified_at:
                existing.title = note.title
                existing.content = note.content
                existing.is_encrypted = bool(note.is_encrypted)
                existing.encrypted_blob = blob
                # Preserve the original created_at; only mutate modified.
                existing.modified_at = note.modified_at
                existing.server_synced_at = server_time
                accepted += 1
            else:
                skipped += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return PushResponse(accepted=accepted, skipped=skipped, server_time=server_time)


@router.get("/pull", response_model=PullResponse)
def pull(
    request: Request,
    since: Optional[str] = Query(default=None, description="ISO-8601 watermark"),
    claims: AccountClaims = Depends(_rate_limit_check),
) -> PullResponse:
    """Return all notes for the authenticated account modified after *since*.

    ``since`` may be omitted, ``"0"``, or empty — all of which mean "send
    everything".  Otherwise it is treated as an ISO-8601 timestamp string
    and compared lexicographically (which is correct for ISO-8601 with a
    consistent timezone, the only format the client emits).
    """
    factory = request.app.state.session_factory
    session: Session = factory()
    server_time = _utcnow_iso()
    try:
        query = session.query(ServerNoteRow).filter(
            ServerNoteRow.account_id == claims.account_id
        )
        if since and since != "0":
            query = query.filter(ServerNoteRow.modified_at > since)
        rows = query.order_by(ServerNoteRow.modified_at.asc()).all()
        payloads = [_row_to_payload(row) for row in rows]
    finally:
        session.close()
    return PullResponse(notes=payloads, server_time=server_time)
