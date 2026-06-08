"""DatabaseStore — SQLite persistence layer for AstraNotes notes.

The sole local persistence layer; backed by SQLAlchemy ORM, always-on
from Sprint 0.  No raw SQL anywhere in this module.

Key design decisions:
- Every note — plain or encrypted — is stored as a Container blob in the
  single ``container`` column.  The dual content/encrypted_blob split is gone.
- Plain notes: store frames content→Container on write; unframes on read.
- Encrypted notes: blob = BlobCodec.encrypt(Container.frame(payload)); opaque
  to the store on read.  [D-07]
- Container integrity is checked at both save and load time.  A WARNING is
  logged and tolerated; an ERROR raises ContainerValidationError.  [design §5.3]
- WAL journal mode is enabled on every new connection for read-concurrency. [BL B-66]
- OperationalError "database is locked" is retried with exponential backoff. [BL B-66]
- Disk-full (ENOSPC) errors converted to DiskFullError.  [BL B-67]

Refs: [BL B-01–B-14, B-31, B-42, B-51, B-66, B-67, B-74]
      [REQ R1, R14] [US-1, US-2]
design §3.1, §4.1, §4.2, §5.2, §5.3
"""
from __future__ import annotations

import errno
import logging
import time
from pathlib import Path
from typing import Optional

from sqlalchemy import URL as _DbURL
from sqlalchemy import Boolean, Column, LargeBinary, Text, create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.core.container import (
    Container,
    ContainerValidationError,
    ValidationSeverity,
)
from src.core.note import DiskFullError, Note, _utcnow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WAL mode + locked-DB retry  [BL B-66]
# ---------------------------------------------------------------------------

_RETRY_ATTEMPTS: int = 5
_RETRY_BASE_DELAY: float = 0.05   # seconds; doubles each attempt


def _enable_wal(dbapi_conn, _connection_record) -> None:  # type: ignore[type-arg]
    """Set WAL journal mode on every new SQLite connection.  [BL B-66]"""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.close()


def _execute_with_retry(fn):
    """Retry *fn()* up to _RETRY_ATTEMPTS times on SQLite 'database is locked'.

    Uses exponential backoff starting at _RETRY_BASE_DELAY seconds.  All other
    exceptions propagate immediately.  Disk-full SQLite errors are converted to
    :class:`~src.core.note.DiskFullError`.  [BL B-66, B-67]
    """
    delay = _RETRY_BASE_DELAY
    for attempt in range(1, _RETRY_ATTEMPTS + 1):  # pragma: no branch
        try:
            return fn()
        except OperationalError as exc:
            msg = str(exc).lower()
            if "database is locked" not in msg:
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
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class _Base(DeclarativeBase):
    pass


class _NoteRow(_Base):
    """ORM row — maps to the ``notes`` table in SQLite.

    All note content lives in a single ``container`` column (Container-framed
    bytes).  The ``title`` column is a fast-listing plaintext alias.

    Refs: design §5.2 [REQ R14.3] [BL B-42, B-51, B-74]
    """

    __tablename__ = "notes"

    note_id = Column(Text, primary_key=True)
    account_id = Column(Text, nullable=True)          # NULL = anonymous/local
    title = Column(Text, nullable=False)              # plaintext alias; fast listing [B-74]
    is_encrypted = Column(Boolean, nullable=False, default=False)
    container = Column(LargeBinary, nullable=False)   # Container-framed bytes
    synced_at = Column(Text, nullable=True)
    created_at = Column(Text, nullable=False)
    modified_at = Column(Text, nullable=False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _frame_plaintext(content: str) -> bytes:
    """Wrap plaintext *content* in a Container and validate it.

    Raises :class:`~src.core.container.ContainerValidationError` (ERROR) if
    the resulting container is corrupt — which should never happen with fresh
    data but guards against future bugs.
    """
    payload = content.encode("utf-8")
    raw = Container.frame(payload, "text/plain", flags=0)
    header, payload_back = Container.unframe(raw)
    result = Container.validate(header, payload_back)
    if result.is_error:
        raise ContainerValidationError(result.severity, result.message)
    if result.is_warning:
        logger.warning("Container warning when framing plaintext: %s", result.message)
    return raw


def _unframe_plaintext(container_bytes: bytes, note_id: str) -> str:
    """Unframe a plaintext Container and return the decoded content string.

    Raises :class:`~src.core.container.ContainerValidationError` on ERROR;
    logs WARNING and continues.
    """
    try:
        header, payload = Container.unframe(container_bytes)
    except Exception as exc:
        raise ContainerValidationError(
            ValidationSeverity.ERROR,
            f"Container for note {note_id!r} could not be parsed: {exc}",
        ) from exc

    result = Container.validate(header, payload)
    if result.is_error:
        raise ContainerValidationError(result.severity, result.message)
    if result.is_warning:
        logger.warning(
            "Container warning when loading note %s: %s", note_id, result.message
        )
    return payload.decode("utf-8", errors="replace")


def _row_to_note(row: _NoteRow, *, listing_mode: bool = False) -> Note:
    """Convert an ORM row to a :class:`~src.core.note.Note`.

    For encrypted rows the container bytes are returned in ``note.blob`` —
    the caller must decrypt.  For plain rows the content is unframed inline
    unless *listing_mode* is True (list() never parses containers).  [BL B-74]
    """
    if row.is_encrypted:
        return Note(
            id=row.note_id,
            title=row.title,
            content="",
            created_at=row.created_at,
            modified_at=row.modified_at,
            encrypted=True,
            blob=row.container,
            synced_at=row.synced_at,
        )

    content = ""
    if not listing_mode and row.container:
        content = _unframe_plaintext(row.container, row.note_id)

    return Note(
        id=row.note_id,
        title=row.title,
        content=content,
        created_at=row.created_at,
        modified_at=row.modified_at,
        encrypted=False,
        blob=None,
        synced_at=row.synced_at,
    )


# ---------------------------------------------------------------------------
# DatabaseStore
# ---------------------------------------------------------------------------


class DatabaseStore:
    """Local SQLite note store backed by SQLAlchemy ORM.

    - Initialised with a ``data_dir`` path.  ``notes.db`` is created there
      on first use via ``create_all()``.
    - All mutations use explicit ACID transactions (``session.commit()``).
    - No raw SQL — all queries go through the ORM.  [REQ R15.1, R15.2]
    - ``list()`` reads only the plaintext ``title`` column and never parses
      containers.  [REQ R1.3] [BL B-74]
    - Container integrity validated at save and load time.  [design §5.3]

    Refs: [BL B-42, B-51, B-74] [REQ R14.1–R14.6] design §3.1, §4.1, §4.2
    """

    def __init__(self, data_dir: Path) -> None:
        data_dir = Path(data_dir).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        self._data_dir = data_dir
        db_path = data_dir / "notes.db"
        url = _DbURL.create("sqlite", database=str(db_path))
        self._engine = create_engine(url, echo=False)
        event.listen(self._engine, "connect", _enable_wal)
        _Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    # ------------------------------------------------------------------
    # Add
    # ------------------------------------------------------------------

    def add(self, note: Note, *, account_id: Optional[str] = None) -> str:
        """Persist *note* and return its id.

        For unencrypted notes the content is framed into a Container on write.
        For encrypted notes ``note.blob`` must already contain the encrypted
        Container bytes.  [REQ R14.6] [design §5.3]

        Raises :class:`~src.core.container.ContainerValidationError` if the
        container is structurally invalid (save-time validation).
        Raises :class:`~src.core.note.DiskFullError` if the DB is full.
        """
        if note.encrypted:
            if not note.blob:
                raise ValueError(f"Encrypted note {note.id!r} has no blob.")
            container_bytes = note.blob
        else:
            container_bytes = _frame_plaintext(note.content)

        def _do() -> str:
            with self._Session() as session:
                row = _NoteRow(
                    note_id=note.id,
                    account_id=account_id,
                    title=note.title,
                    is_encrypted=note.encrypted,
                    container=container_bytes,
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

        For encrypted notes ``note.blob`` is populated with the raw container
        bytes; the caller decrypts and unframes.  For plain notes the content
        is unframed here (load-time validation).
        """
        def _do() -> Optional[Note]:
            with self._Session() as session:
                row = session.get(_NoteRow, note_id)
                if row is None:
                    return None
                return _row_to_note(row)

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
        encrypted: Optional[bool] = None,
    ) -> Note:
        """Update a note's fields and return the refreshed Note.

        - Plain notes:      pass ``title`` and/or ``content``.
        - Encrypted notes:  pass ``blob`` (new encrypted Container bytes).
        - Decrypt to plain: pass ``content`` + ``encrypted=False``.
        - Raises :class:`KeyError` if *note_id* is not found.  [REQ R1.7]
        """
        def _do() -> Note:
            with self._Session() as session:
                row = session.get(_NoteRow, note_id)
                if row is None:
                    raise KeyError(f"Note {note_id!r} not found.")

                if title is not None:
                    row.title = title

                if encrypted is False and row.is_encrypted:
                    # Converting encrypted → plain: content must be supplied
                    if content is not None:
                        row.container = _frame_plaintext(content)
                    row.is_encrypted = False

                elif encrypted is True and not row.is_encrypted:
                    # Converting plain → encrypted: blob must be supplied.
                    # The prior plaintext container is replaced so no cleartext
                    # remains on disk.
                    if blob is not None:
                        row.container = blob
                        row.is_encrypted = True

                elif not row.is_encrypted and content is not None:
                    row.container = _frame_plaintext(content)

                elif row.is_encrypted and blob is not None:
                    row.container = blob

                row.modified_at = _utcnow()
                session.commit()
                return _row_to_note(row)

        return _execute_with_retry(_do)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, note_id: str) -> None:
        """Remove the note with *note_id*.  Raises :class:`KeyError` if not found."""
        def _do() -> None:
            with self._Session() as session:
                row = session.get(_NoteRow, note_id)
                if row is None:
                    raise KeyError(f"Note {note_id!r} not found.")
                session.delete(row)
                session.commit()

        _execute_with_retry(_do)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list(
        self, account_id: Optional[str] = None
    ) -> tuple[list[Note], list[Note]]:
        """Return ``(account_notes, local_notes)``.

        Reads only the plaintext ``title`` column; never parses containers.
        [REQ R1.3] [BL B-74] [D-11]
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
            return account_notes, local_notes

        return _execute_with_retry(_do)

    # ------------------------------------------------------------------
    # Search  [BL B-29] [REQ R10.1–R10.3]
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        account_id: Optional[str] = None,
    ) -> list[Note]:
        """Case-insensitive substring search over title and plaintext content.

        Encrypted notes: only the plaintext alias in ``title`` is searched.
        Plain notes: the container is unframed to search content text.
        [REQ R10.1, R10.3]
        """
        q_lower = query.lower()

        def _do() -> list[Note]:
            with self._Session() as session:
                rows = session.query(_NoteRow).all()
                results: list[Note] = []
                for row in rows:
                    if account_id is not None:
                        if row.account_id != account_id and row.account_id is not None:
                            continue
                    else:
                        if row.account_id is not None:
                            continue
                    if row.is_encrypted:
                        if q_lower in (row.title or "").lower():
                            note = _row_to_note(row, listing_mode=True)
                            note.blob = None
                            results.append(note)
                    else:
                        title_match = q_lower in (row.title or "").lower()
                        content_match = False
                        if not title_match and row.container:
                            try:
                                text = _unframe_plaintext(row.container, row.note_id)
                                content_match = q_lower in text.lower()
                            except ContainerValidationError:
                                pass
                        if title_match or content_match:
                            results.append(_row_to_note(row))
                return results

        return _execute_with_retry(_do)

    # ------------------------------------------------------------------
    # Account management  [BL B-61] [REQ R13.12]
    # ------------------------------------------------------------------

    def disassociate_account(self, account_id: str) -> int:
        """Set ``account_id = NULL`` on all notes belonging to *account_id``."""
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

    def associate_anonymous_notes(self, account_id: str) -> int:
        """Set ``account_id`` on all currently-anonymous notes.  [BL B-41]"""
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

    def set_note_account_id(self, note_id: str, account_id: Optional[str]) -> None:
        """Set ``account_id`` on a single note.  Raises :class:`KeyError` if not found."""
        def _do() -> None:
            with self._Session() as session:
                row = session.get(_NoteRow, note_id)
                if row is None:
                    raise KeyError(f"Note {note_id!r} not found.")
                row.account_id = account_id
                session.commit()

        _execute_with_retry(_do)

    # ------------------------------------------------------------------
    # Sync helpers  [BL B-86, B-90] [REQ R16.1, R16.2]
    # ------------------------------------------------------------------

    def list_pending_push(self, account_id: str) -> list[dict]:
        """Return note rows owned by *account_id* that need pushing.

        A note is "pending" when ``synced_at`` is NULL or older than
        ``modified_at``.  Plain-note content is unframed before returning so
        callers receive the same dict shape as before.
        [BL B-86, B-90] [REQ R16.1]
        """
        def _do() -> list[dict]:
            results: list[dict] = []
            with self._Session() as session:
                rows = (
                    session.query(_NoteRow)
                    .filter(_NoteRow.account_id == account_id)
                    .all()
                )
                for row in rows:
                    if row.synced_at is not None and row.synced_at >= row.modified_at:
                        continue
                    plain_content: Optional[str] = None
                    blob: Optional[bytes] = None
                    if row.is_encrypted:
                        blob = row.container
                    else:
                        try:
                            plain_content = _unframe_plaintext(
                                row.container, row.note_id
                            )
                        except ContainerValidationError:
                            logger.error(
                                "Skipping push for note %s: container validation error.",
                                row.note_id,
                            )
                            continue
                    results.append(
                        {
                            "id": row.note_id,
                            "title": row.title,
                            "content": plain_content,
                            "is_encrypted": bool(row.is_encrypted),
                            "blob": blob,
                            "created_at": row.created_at,
                            "modified_at": row.modified_at,
                        }
                    )
            return results

        return _execute_with_retry(_do)

    def mark_synced(self, note_id: str, synced_at: str) -> None:
        """Stamp ``synced_at`` on *note_id* (no-op if the row is gone)."""
        def _do() -> None:
            with self._Session() as session:
                row = session.get(_NoteRow, note_id)
                if row is None:
                    return
                row.synced_at = synced_at
                session.commit()

        _execute_with_retry(_do)

    def max_synced_at(self, account_id: str) -> Optional[str]:
        """Return the highest ``synced_at`` for *account_id*, or ``None``."""
        def _do() -> Optional[str]:
            with self._Session() as session:
                rows = (
                    session.query(_NoteRow.synced_at)
                    .filter(
                        _NoteRow.account_id == account_id,
                        _NoteRow.synced_at.isnot(None),
                    )
                    .all()
                )
            values = [r[0] for r in rows if r[0] is not None]
            return max(values) if values else None

        return _execute_with_retry(_do)

    def upsert_remote(
        self,
        *,
        note_id: str,
        account_id: str,
        title: str,
        content: Optional[str],
        is_encrypted: bool,
        blob: Optional[bytes],
        created_at: str,
        modified_at: str,
        synced_at: str,
    ) -> None:
        """Insert or update a note received from the sync server.

        Treats the server's payload as authoritative (last-write-wins enforced
        server-side).  [BL B-86, B-90] [REQ R16.2]
        """
        if is_encrypted:
            if not blob:
                raise ValueError(f"Remote encrypted note {note_id!r} missing blob.")
            container_bytes = blob
        else:
            container_bytes = _frame_plaintext(content or "")

        def _do() -> None:
            with self._Session() as session:
                row = session.get(_NoteRow, note_id)
                if row is None:
                    session.add(
                        _NoteRow(
                            note_id=note_id,
                            account_id=account_id,
                            title=title,
                            is_encrypted=is_encrypted,
                            container=container_bytes,
                            synced_at=synced_at,
                            created_at=created_at,
                            modified_at=modified_at,
                        )
                    )
                else:
                    row.account_id = account_id
                    row.title = title
                    row.is_encrypted = is_encrypted
                    row.container = container_bytes
                    row.synced_at = synced_at
                    row.created_at = created_at
                    row.modified_at = modified_at
                session.commit()

        _execute_with_retry(_do)
