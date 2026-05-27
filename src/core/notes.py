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
- WAL journal mode is enabled on every new connection for read-concurrency. [BL B-66]
- OperationalError "database is locked" is retried with exponential backoff. [BL B-66]
- Hybrid storage: encrypted notes >5 MB are written to <data-dir>/files/ on the
  filesystem; DB stores payload_location='filesystem'. [BL B-49] [REQ R14.8]
- Disk-full (ENOSPC) errors caught at both DB and filesystem layers. [BL B-67]
- Filesystem payloads cleaned up on note delete. [BL B-68]

Refs: [BL B-01-B-14, B-31, B-42, B-49, B-51, B-66, B-67, B-68, B-74]
      [REQ R1, R14] [US-1, US-2]
design §3.1, §4.1, §4.2, §5.2
"""
from __future__ import annotations

import dataclasses
import errno
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import URL as _DbURL
from sqlalchemy import Boolean, Column, LargeBinary, Text, create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hybrid storage threshold  [BL B-49] [REQ R14.8]
# ---------------------------------------------------------------------------

# Encrypted notes with blobs larger than this are stored on the filesystem
# rather than inline in the database.  Unencrypted notes are always inline
# (no plaintext files on disk).  [REQ R14.8]
_FILESYSTEM_THRESHOLD_BYTES: int = 5 * 1024 * 1024   # 5 MiB
_PAYLOAD_DIR = "files"                               # flat under data_dir [BL B-77]


# ---------------------------------------------------------------------------
# Disk-full error  [BL B-67] [REQ R3.8]
# ---------------------------------------------------------------------------


class DiskFullError(OSError):
    """Raised when a write operation fails because the filesystem is full.

    Covers both SQLite ENOSPC writes and direct filesystem payload writes.
    [BL B-67] [REQ R3.8, R14.12]
    """


# ---------------------------------------------------------------------------
# WAL mode + locked-DB retry  [BL B-66]
# ---------------------------------------------------------------------------

_RETRY_ATTEMPTS: int = 5
_RETRY_BASE_DELAY: float = 0.05   # seconds; doubles each attempt


def _enable_wal(dbapi_conn, _connection_record) -> None:  # type: ignore[type-arg]
    """Set WAL journal mode on every new SQLite connection.

    WAL provides better read-concurrency and is resilient to reader/writer
    contention in single-writer scenarios.  [BL B-66]
    """
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.close()


def _execute_with_retry(fn):
    """Retry *fn()* up to _RETRY_ATTEMPTS times on SQLite 'database is locked'.

    Uses exponential backoff starting at _RETRY_BASE_DELAY seconds.  All other
    exceptions propagate immediately.  [BL B-66]

    Disk-full SQLite errors (OperationalError: 'disk I/O error' or 'no space')
    are converted to :class:`DiskFullError`.  [BL B-67]
    """
    delay = _RETRY_BASE_DELAY
    for attempt in range(1, _RETRY_ATTEMPTS + 1):  # pragma: no branch
        try:
            return fn()
        except OperationalError as exc:
            msg = str(exc).lower()
            if "database is locked" not in msg:
                # Detect SQLite disk-full condition and re-raise as DiskFullError.
                if "disk i/o error" in msg or "no space" in msg or "disk full" in msg:
                    raise DiskFullError(
                        errno.ENOSPC,
                        "Database write failed: no space left on device.",
                    ) from exc
                raise
            if attempt == _RETRY_ATTEMPTS:
                raise
            logger.warning(
                "SQLite database is locked (attempt %d/%d); retrying in %.2fs.",
                attempt, _RETRY_ATTEMPTS, delay,
            )
            time.sleep(delay)
            delay *= 2


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
        self._data_dir = data_dir                   # used by hybrid-storage methods
        # Create the flat filesystem-payload directory.  [BL B-77] [REQ R14.13]
        (data_dir / _PAYLOAD_DIR).mkdir(exist_ok=True)
        db_path = data_dir / "notes.db"
        # Use URL.create() instead of f-string to prevent connection-URL injection
        # from paths that contain SQLAlchemy URL special characters.
        url = _DbURL.create("sqlite", database=str(db_path))
        self._engine = create_engine(url, echo=False)
        # Enable WAL mode on every new connection.  [BL B-66]
        event.listen(self._engine, "connect", _enable_wal)
        _Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    # ------------------------------------------------------------------
    # Add
    # ------------------------------------------------------------------

    def add(self, note: Note, *, account_id: Optional[str] = None) -> str:
        """Persist *note* and return its id.

        For encrypted notes, ``note.blob`` is stored in ``encrypted_blob`` and
        ``content`` is left NULL.  For unencrypted notes, ``note.content`` is
        stored in the ``content`` column.  [REQ R14.6]

        Encrypted notes whose blob exceeds ``_FILESYSTEM_THRESHOLD_BYTES`` (5 MiB)
        are written to ``<data-dir>/files/<note_id>.bin`` and the DB row records
        ``payload_location = 'filesystem'``.  Unencrypted notes are always inline;
        no plaintext files are written to disk.  [BL B-49] [REQ R14.8]

        Raises :class:`DiskFullError` if the filesystem or database is full.
        [BL B-67] [REQ R3.8]

        Args:
            note:       Note to persist.
            account_id: Associate with this account UUID (``None`` = anonymous).
        """
        payload_location = "inline"
        blob_for_db: Optional[bytes] = note.blob if note.encrypted else None

        # --- Hybrid storage: write large encrypted blobs to filesystem ---
        if note.encrypted and note.blob and len(note.blob) > _FILESYSTEM_THRESHOLD_BYTES:
            payload_location = "filesystem"
            file_path = self._data_dir / _PAYLOAD_DIR / f"{note.id}.bin"
            try:
                file_path.write_bytes(note.blob)
            except OSError as exc:
                if getattr(exc, "errno", None) == errno.ENOSPC:
                    raise DiskFullError(
                        errno.ENOSPC,
                        f"Cannot write payload for note {note.id!r}: no space left on device.",
                    ) from exc
                raise
            blob_for_db = None  # payload is on disk; DB only stores location marker

        def _do() -> str:
            with self._Session() as session:
                row = _NoteRow(
                    note_id=note.id,
                    account_id=account_id,
                    title=note.title,
                    content=note.content if not note.encrypted else None,
                    encrypted_blob=blob_for_db,
                    is_encrypted=note.encrypted,
                    payload_location=payload_location,
                    created_at=note.created_at,
                    modified_at=note.modified_at,
                )
                session.add(row)
                session.commit()
            return note.id

        return _execute_with_retry(_do)

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    def get(self, note_id: str) -> Optional[Note]:
        """Return the Note with *note_id*, or ``None`` if not found.

        For encrypted notes the returned Note has ``content=""`` and ``blob``
        populated — the caller decrypts the blob with BlobCodec if it has a key.
        For notes with ``payload_location='filesystem'`` the blob is loaded from
        ``<data-dir>/files/<note_id>.bin`` before returning.  [BL B-49]
        [BL B-74] [D-07] [D-11]
        """
        def _do() -> Optional[Note]:
            with self._Session() as session:
                row = session.get(_NoteRow, note_id)
                if row is None:
                    return None
                note = _row_to_note(row)
                # Load filesystem payload if the blob lives outside the DB.
                if row.is_encrypted and row.payload_location == "filesystem":
                    file_path = self._data_dir / _PAYLOAD_DIR / f"{note_id}.bin"
                    try:
                        note.blob = file_path.read_bytes()
                    except FileNotFoundError:
                        logger.error(
                            "Filesystem payload missing for note %s at %s.",
                            note_id, file_path,
                        )
                        # blob remains None; caller must handle gracefully
                return note

        return _execute_with_retry(_do)

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
        def _do() -> Note:
            with self._Session() as session:
                row = session.get(_NoteRow, note_id)
                if row is None:
                    raise KeyError(f"Note {note_id!r} not found.")
                if title is not None:
                    row.title = title
                if not row.is_encrypted and content is not None:
                    row.content = content
                if row.is_encrypted and blob is not None:
                    if row.payload_location == "filesystem":
                        # Write re-encrypted payload back to the filesystem file;
                        # the DB ``encrypted_blob`` column stays NULL.  [BL B-62]
                        file_path = self._data_dir / _PAYLOAD_DIR / f"{note_id}.bin"
                        try:
                            file_path.write_bytes(blob)
                        except OSError as exc:
                            if getattr(exc, "errno", None) == errno.ENOSPC:
                                raise DiskFullError(
                                    errno.ENOSPC,
                                    f"Cannot write re-encrypted payload for {note_id!r}:"
                                    " no space left on device.",
                                ) from exc
                            raise
                    else:
                        row.encrypted_blob = blob
                row.modified_at = _utcnow()
                session.commit()
                # Access attributes while session is still open (auto-refresh after commit).
                return _row_to_note(row)

        return _execute_with_retry(_do)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, note_id: str) -> None:
        """Remove the note with *note_id*.

        Raises :class:`KeyError` if not found.  Other notes — including
        co-stored encrypted ones — are never affected.  [REQ R2.12] [BL B-33]

        If the note has ``payload_location='filesystem'``, the corresponding
        file under ``<data-dir>/files/`` is deleted after the DB row is removed.
        Missing files are silently ignored (idempotent clean-up).  [BL B-68]
        """
        payload_location: Optional[str] = None

        def _do() -> None:
            nonlocal payload_location
            with self._Session() as session:
                row = session.get(_NoteRow, note_id)
                if row is None:
                    raise KeyError(f"Note {note_id!r} not found.")
                payload_location = row.payload_location
                session.delete(row)
                session.commit()

        _execute_with_retry(_do)

        # Clean up orphaned filesystem payload after DB row is gone.  [BL B-68]
        if payload_location == "filesystem":
            file_path = self._data_dir / _PAYLOAD_DIR / f"{note_id}.bin"
            try:
                file_path.unlink()
            except FileNotFoundError:
                pass

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list(
        self, account_id: Optional[str] = None
    ) -> tuple[list[Note], list[Note]]:
        """Return ``(account_notes, local_notes)``.

        - ``account_notes``: notes whose ``account_id`` matches the argument.
          Empty when ``account_id`` is ``None`` (no active session).
        - ``local_notes``: notes with ``account_id IS NULL`` (anonymous).
        - Notes belonging to *other* accounts are never returned.  [REQ R1.3]

        Reads only the plaintext ``title`` / ``format`` columns; never parses
        blobs.  [REQ R1.3] [BL B-74] [D-11]
        """
        def _do() -> tuple[list[Note], list[Note]]:
            with self._Session() as session:
                rows = session.query(_NoteRow).all()
                account_notes: list[Note] = []
                local_notes: list[Note] = []
                for row in rows:
                    note = _row_to_note(row, listing_mode=True)
                    if account_id is not None and row.account_id == account_id:
                        account_notes.append(note)
                    elif row.account_id is None:
                        local_notes.append(note)
                    # else: belongs to a different account — omit
            return account_notes, local_notes

        return _execute_with_retry(_do)

    # ------------------------------------------------------------------
    # search  [BL B-29] [REQ R10.1–R10.3]
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        account_id: Optional[str] = None,
    ) -> list[Note]:
        """Case-insensitive substring search over title and plaintext content.

        Search semantics:
        - Non-encrypted notes: match checked against ``title`` AND ``content``.
        - Encrypted notes: ONLY the plaintext alias stored in ``title`` is
          searched.  Content and blob are NEVER read or exposed by this method.
          If the alias matches, the note is returned with ``blob=None`` so the
          caller can display it without a passphrase.  [REQ R10.1]
        - For content-level searching of encrypted notes the caller must decrypt
          independently (e.g. CLI ``--encrypted`` flag) and re-run the match.
          [REQ R10.3]
        - Account scoping follows the same rules as :meth:`list`:
          ``account_id=None`` → only anonymous notes; non-None → account notes
          and anonymous notes.

        Refs: [BL B-29] [REQ R10.1–R10.3]
        """
        q_lower = query.lower()

        def _do() -> list[Note]:
            with self._Session() as session:
                rows = session.query(_NoteRow).all()
                results: list[Note] = []
                for row in rows:
                    # Account scoping (mirrors list() logic).
                    if account_id is not None:
                        if row.account_id != account_id and row.account_id is not None:
                            continue
                    else:
                        if row.account_id is not None:
                            continue

                    if row.is_encrypted:
                        # Only search the plaintext alias — never read or expose blob.
                        if q_lower in (row.title or "").lower():
                            note = _row_to_note(row, listing_mode=True)
                            note.blob = None  # alias match never exposes blob
                            results.append(note)
                    else:
                        title_match = q_lower in (row.title or "").lower()
                        content_match = q_lower in (row.content or "").lower()
                        if title_match or content_match:
                            results.append(_row_to_note(row))

                return results

        return _execute_with_retry(_do)

    # ------------------------------------------------------------------
    # disassociate_account  [BL B-61] [REQ R13.12]
    # ------------------------------------------------------------------

    def disassociate_account(self, account_id: str) -> int:
        """Set ``account_id = NULL`` on all notes belonging to *account_id*.

        Called during ``delete-account`` to detach notes from the account
        while keeping them on the device.  Returns the count of rows updated.
        [BL B-61] [REQ R13.12]
        """
        def _do() -> int:
            with self._Session() as session:
                rows = (
                    session.query(_NoteRow)
                    .filter(_NoteRow.account_id == account_id)
                    .all()
                )
                for row in rows:
                    row.account_id = None
                session.commit()
                return len(rows)

        return _execute_with_retry(_do)

    # ------------------------------------------------------------------
    # associate_anonymous_notes  [BL B-41] [REQ R12.3]
    # ------------------------------------------------------------------

    def associate_anonymous_notes(self, account_id: str) -> int:
        """Set ``account_id`` on all currently-anonymous notes (``account_id IS NULL``).

        Called after the first-login prompt when the user answers ``yes``.
        Returns the count of rows updated.  [BL B-41] [REQ R12.3]
        """
        def _do() -> int:
            with self._Session() as session:
                rows = (
                    session.query(_NoteRow)
                    .filter(_NoteRow.account_id.is_(None))
                    .all()
                )
                for row in rows:
                    row.account_id = account_id
                session.commit()
                return len(rows)

        return _execute_with_retry(_do)

    # ------------------------------------------------------------------
    # set_note_account_id  [BL B-41] [REQ R12.3]
    # ------------------------------------------------------------------

    def set_note_account_id(self, note_id: str, account_id: Optional[str]) -> None:
        """Set ``account_id`` on a single note by *note_id*.

        Used during the per-note first-login association prompt (``ask`` choice).
        Raises :class:`KeyError` if *note_id* is not found.  [BL B-41]
        """
        def _do() -> None:
            with self._Session() as session:
                row = session.get(_NoteRow, note_id)
                if row is None:
                    raise KeyError(f"Note {note_id!r} not found.")
                row.account_id = account_id
                session.commit()

        _execute_with_retry(_do)


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
