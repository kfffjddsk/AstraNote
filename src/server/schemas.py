"""Pydantic v2 request / response schemas for the sync server.

Encrypted blobs travel as base64-encoded strings so the JSON envelope stays
plain ASCII regardless of transport.  All field constraints live here so
the routers stay focused on business logic.

Refs: [BL B-86] [REQ R16.1, R16.2, R16.8]
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """``POST /auth/login`` body."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    """``POST /auth/login`` success body."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
    expires_at: str          # ISO-8601 UTC
    account_id: str
    username: str


class NotePayload(BaseModel):
    """A single note as it travels over the wire.

    The server never trusts the ``account_id`` field on inbound payloads —
    it always overrides with the JWT subject (R16.5 / B-94).  The field is
    accepted but ignored on push.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=512)
    content: Optional[str] = None
    is_encrypted: bool = False
    encrypted_blob_b64: Optional[str] = None
    created_at: str           # ISO-8601 UTC
    modified_at: str          # ISO-8601 UTC
    # Accepted for forward compatibility but silently overwritten server-side.
    account_id: Optional[str] = None


class PushRequest(BaseModel):
    """``POST /sync/push`` body."""

    model_config = ConfigDict(extra="forbid")

    notes: list[NotePayload] = Field(default_factory=list)


class PushResponse(BaseModel):
    """``POST /sync/push`` success body."""

    model_config = ConfigDict(extra="forbid")

    accepted: int
    skipped: int
    server_time: str          # ISO-8601 UTC


class PullResponse(BaseModel):
    """``GET /sync/pull`` success body."""

    model_config = ConfigDict(extra="forbid")

    notes: list[NotePayload]
    server_time: str          # ISO-8601 UTC


class ErrorResponse(BaseModel):
    """Common JSON error envelope per R16.8."""

    model_config = ConfigDict(extra="forbid")

    status: str = "error"
    error: str
    message: str
