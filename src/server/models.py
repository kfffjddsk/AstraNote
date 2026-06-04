"""Server-side ORM models and shared SQLAlchemy ``Base``.

The server's ``server_notes`` table always stores blobs inline (no
filesystem split) so request handling stays stateless.  Account records
live in a separate ``notes.db`` managed by
:class:`src.core.auth.AccountStore` — the server reuses that store
rather than maintaining a parallel implementation, so no
``ServerAccountRow`` is needed here.

Refs: [BL B-86, B-94] [REQ R16.1, R16.5, R16.10] design §3.1
"""
from __future__ import annotations

from sqlalchemy import Boolean, Column, Index, LargeBinary, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by all server-side ORM models."""


class ServerNoteRow(Base):
    """Server-side ``server_notes`` table.

    Every row is owned by exactly one ``account_id`` (no anonymous notes
    on the server).  ``(note_id, account_id)`` is the composite primary
    key so the same client-generated UUID can legally co-exist under two
    different accounts on the same server (per B-94 isolation tests).

    Refs: [REQ R16.1, R16.2, R16.5]
    """

    __tablename__ = "server_notes"
    __table_args__ = (
        Index("ix_server_notes_account", "account_id"),
        Index("ix_server_notes_account_modified", "account_id", "modified_at"),
    )

    note_id = Column(Text, primary_key=True)
    account_id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, nullable=False, default=False)
    encrypted_blob = Column(LargeBinary, nullable=True)
    created_at = Column(Text, nullable=False)
    modified_at = Column(Text, nullable=False)
    server_synced_at = Column(Text, nullable=False)
