"""Note dataclass and DatabaseStore for AstraNotes.

DatabaseStore is the sole local persistence layer — SQLite via SQLAlchemy ORM,
always-on from Sprint 0.  No raw SQL anywhere in this module.

Key design decisions:
- Note.blob is authoritative for encrypted notes; title/content are ephemeral
  in-memory views populated by the caller after decryption. [D-07]
- Unencrypted notes store content in a plaintext ``content`` column for Sprint 0.
  Encrypted notes store the AES-GCM ciphertext in ``encrypted_blob``.
- list() returns (account_notes, local_notes) per R1.3 / D-11.
- Input validation (empty title/content) is enforced in Note.create(). [REQ R1.6]

Refs: [BL B-01–B-14, B-31, B-42, B-51, B-74] [REQ R1, R14] [US-1, US-2]
design §3.1, §4.1, §4.2, §5.2
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import URL as _DbURL
from sqlalchemy import Boolean, Column, LargeBinary, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    """Return the current UTC instant as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Note dataclass
# ---------------------------------------------------------------------------


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
    blob: Optional[bytes] = None  # AES-256-GCM ciphertext; None for unencrypted

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
        """Update mutable fields and refresh ``modified_at``.  No-op if both
        arguments are ``None``.  [REQ R1.4]
        """
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


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class _Base(DeclarativeBase):
    pass


class _NoteRow(_Base):
    """ORM row — maps to the ``notes`` table in SQLite.

    Refs: design §5.2 [REQ R14.3] [BL B-42, B-51, B-74] [LOG 05-04]
    """

    __tablename__ = "notes"

    note_id = Column(Text, primary_key=True)
    account_id = Column(Text, nullable=True)          # NULL = anonymous/local
    title = Column(Text, nullable=False)              # plaintext alias; fast listing [B-74]
    content = Column(Text, nullable=True)             # plaintext content (unencrypted notes)
    format = Column(Text, nullable=False, default="text/plain")
    encrypted_blob = Column(LargeBinary, nullable=True)  # AES-GCM ciphertext
    nonce = Column(LargeBinary, nullable=True)        # reserved; embedded in blob for now
    salt = Column(LargeBinary, nullable=True)         # reserved; embedded in blob for now
    is_encrypted = Column(Boolean, nullable=False, default=False)
    payload_location = Column(Text, nullable=False, default="inline")
    synced_at = Column(Text, nullable=True)
    created_at = Column(Text, nullable=False)
    modified_at = Column(Text, nullable=False)


# ---------------------------------------------------------------------------
# DatabaseStore
# ---------------------------------------------------------------------------


class DatabaseStore:
    """Local SQLite note store backed by SQLAlchemy ORM.

    - Initialised with a ``data_dir`` path.  ``notes.db`` is created there
      on first use via ``create_all()``.
    - All mutations use explicit ACID transactions (``session.commit()``).
    - No raw SQL — all queries go through the ORM.  [REQ R15.1, R15.2]
    - ``list()`` reads only the plaintext ``title``/``format`` columns and
      never parses blobs.  [REQ R1.3] [BL B-74]

    Refs: [BL B-42, B-51, B-74] [REQ R14.1–R14.6] design §3.1, §4.1, §4.2
    """

    def __init__(self, data_dir: Path) -> None:
        # resolve() canonicalises the path (eliminates `..` traversal components)
        # before we create directories or embed the path in a connection URL.
        data_dir = Path(data_dir).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / "notes.db"
        # Use URL.create() instead of f-string to prevent connection-URL injection
        # from paths that contain SQLAlchemy URL special characters.
        url = _DbURL.create("sqlite", database=str(db_path))
        self._engine = create_engine(url, echo=False)
        _Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    # ------------------------------------------------------------------
    # Add
    # ------------------------------------------------------------------

    def add(self, note: Note) -> str:
        """Persist *note* and return its id.

        For encrypted notes, ``note.blob`` is stored in ``encrypted_blob`` and
        ``content`` is left NULL.  For unencrypted notes, ``note.content`` is
        stored in the ``content`` column.  [REQ R14.6]
        """
        with self._Session() as session:
            row = _NoteRow(
                note_id=note.id,
                account_id=None,
                title=note.title,
                content=note.content if not note.encrypted else None,
                encrypted_blob=note.blob if note.encrypted else None,
                is_encrypted=note.encrypted,
                created_at=note.created_at,
                modified_at=note.modified_at,
            )
            session.add(row)
            session.commit()
        return note.id

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    def get(self, note_id: str) -> Optional[Note]:
        """Return the Note with *note_id*, or ``None`` if not found.

        For encrypted notes the returned Note has ``content=""`` and ``blob``
        populated — the caller decrypts the blob with BlobCodec if it has a key.
        [BL B-74] [D-07] [D-11]
        """
        with self._Session() as session:
            row = session.get(_NoteRow, note_id)
            if row is None:
                return None
            return _row_to_note(row)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(
        self,
        note_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        blob: Optional[bytes] = None,
    ) -> Note:
        """Update a note's fields and return the refreshed Note.

        - For unencrypted notes: pass ``title`` and/or ``content``.
        - For encrypted notes: pass ``blob`` to replace the ciphertext (e.g.
          after re-encryption).  Title alias updates are always accepted.
        - Updating an unencrypted note never touches an encrypted note's blob,
          satisfying the co-existence invariant.  [REQ R2.12] [BL B-33]
        - Raises :class:`KeyError` if *note_id* is not found.  [REQ R1.7]
        """
        with self._Session() as session:
            row = session.get(_NoteRow, note_id)
            if row is None:
                raise KeyError(f"Note {note_id!r} not found.")
            if title is not None:
                row.title = title
            if not row.is_encrypted and content is not None:
                row.content = content
            if row.is_encrypted and blob is not None:
                row.encrypted_blob = blob
            row.modified_at = _utcnow()
            session.commit()
            # Access attributes while session is still open (auto-refresh after commit).
            return _row_to_note(row)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, note_id: str) -> None:
        """Remove the note with *note_id*.

        Raises :class:`KeyError` if not found.  Other notes — including
        co-stored encrypted ones — are never affected.  [REQ R2.12] [BL B-33]
        """
        with self._Session() as session:
            row = session.get(_NoteRow, note_id)
            if row is None:
                raise KeyError(f"Note {note_id!r} not found.")
            session.delete(row)
            session.commit()

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list(
        self, account_id: Optional[str] = None
    ) -> tuple[list[Note], list[Note]]:
        """Return ``(account_notes, local_notes)``.

        - ``account_notes``: notes whose ``account_id`` matches the argument.
          Empty when ``account_id`` is ``None`` (no active session).
        - ``local_notes``: anonymous notes (``account_id IS NULL``).

        Reads only the plaintext ``title`` / ``format`` columns; never parses
        blobs.  [REQ R1.3] [BL B-74] [D-11]
        """
        with self._Session() as session:
            rows = session.query(_NoteRow).all()
            account_notes: list[Note] = []
            local_notes: list[Note] = []
            for row in rows:
                note = _row_to_note(row, listing_mode=True)
                if account_id and row.account_id == account_id:
                    account_notes.append(note)
                else:
                    local_notes.append(note)
        return account_notes, local_notes


# ---------------------------------------------------------------------------
# Internal helper (module-level to avoid duplication)
# ---------------------------------------------------------------------------


def _row_to_note(row: _NoteRow, *, listing_mode: bool = False) -> Note:
    """Convert an ORM row to a :class:`Note`.

    In *listing_mode* the ``content`` field is always ``""`` (no blob parsing,
    no content column read).  For encrypted notes, ``title`` is the stored
    alias (default ``"[Encrypted Note]"``), ``content`` is ``""``, and
    ``blob`` carries the raw ciphertext.  [BL B-74] [D-07]
    """
    if row.is_encrypted:
        return Note(
            id=row.note_id,
            title=row.title,          # stored alias or "[Encrypted Note]"
            content="",               # authoritative data is in blob
            created_at=row.created_at,
            modified_at=row.modified_at,
            encrypted=True,
            blob=row.encrypted_blob,
        )
    return Note(
        id=row.note_id,
        title=row.title,
        content="" if listing_mode else (row.content or ""),
        created_at=row.created_at,
        modified_at=row.modified_at,
        encrypted=False,
        blob=None,
    )
