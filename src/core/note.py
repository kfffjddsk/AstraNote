"""Note dataclass — in-memory model for a single AstraNotes note.

Deliberately free of SQLAlchemy / persistence concerns; those live in
:mod:`src.core.store`.

Refs: [BL B-01–B-14] [REQ R1, R14] [US-1, US-2] design §3.1, D-07
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timezone
from typing import Optional


@dataclasses.dataclass
class Attachment:
    """An in-memory attachment belonging to a Note.

    ``data`` holds the raw bytes as packed by the responsible plugin.
    The plugin is identified by ``mime_type``; the store wraps the bytes in
    a :class:`~src.core.container.Container` before persisting.

    Attachment persistence is a future-sprint feature; this stub lets the
    Note model carry the field without breaking existing code.
    """

    id: str
    filename: str
    mime_type: str
    data: bytes


def _utcnow() -> str:
    """Return the current UTC instant as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class DiskFullError(OSError):
    """Raised when a write fails because the filesystem is full.

    Covers both SQLite ENOSPC writes and direct filesystem payload writes.
    [BL B-67] [REQ R3.8, R14.12]
    """


@dataclasses.dataclass
class Note:
    """In-memory representation of a single note.

    Field semantics (D-07):
    - Unencrypted: ``encrypted=False``, ``blob=None``.
      ``title`` and ``content`` are authoritative.
    - Encrypted, no key (listing / raw get): ``encrypted=True``, ``blob=<bytes>``.
      ``title`` holds the stored alias (or ``"[Encrypted Note]"``); ``content``
      is ``""`` — the caller must call BlobCodec.decrypt() to populate it.
    - Encrypted, key present: same as above but the caller decodes ``blob`` and
      sets ``content`` in memory; this object is then returned to the end-user.

    Refs: design §3.1, D-07
    """

    id: str
    title: str
    content: str
    created_at: str           # ISO-8601 UTC
    modified_at: str          # ISO-8601 UTC
    encrypted: bool
    blob: Optional[bytes] = None
    # blob semantics (D-07):
    #   Unencrypted note  → None (store holds the container internally)
    #   Encrypted note    → BlobCodec.encrypt(Container.frame(payload)) bytes
    synced_at: Optional[str] = None    # last server sync stamp; None = never synced
    attachments: list = dataclasses.field(default_factory=list)  # list[Attachment]

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        title: str,
        content: str,
        *,
        encrypted: bool = False,
        blob: Optional[bytes] = None,
    ) -> "Note":
        """Return a new Note with a UUID id and UTC timestamps.

        Validates that title is non-empty and, for unencrypted notes, that
        content is non-empty.  [REQ R1.6]
        """
        if not title or not title.strip():
            raise ValueError("Note title must not be empty or whitespace.")
        if "\x00" in title:
            raise ValueError("Note title must not contain null bytes.")
        if not encrypted:
            if not content or not content.strip():
                raise ValueError("Note content must not be empty or whitespace.")
            if "\x00" in content:
                raise ValueError("Note content must not contain null bytes.")
        now = _utcnow()
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            content=content,
            created_at=now,
            modified_at=now,
            encrypted=encrypted,
            blob=blob,
        )

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def update(
        self,
        title: Optional[str] = None,
        content: Optional[str] = None,
    ) -> None:
        """Update mutable fields and refresh ``modified_at``.  [REQ R1.4]"""
        if title is None and content is None:
            return
        if title is not None:
            if "\x00" in title:
                raise ValueError("Note title must not contain null bytes.")
            self.title = title
        if content is not None:
            if "\x00" in content:
                raise ValueError("Note content must not contain null bytes.")
            self.content = content
        self.modified_at = _utcnow()
