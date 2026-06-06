"""Authentication and session management for AstraNotes.

Provides:
  - ``validate_username``  — enforce username rules  [BL B-60] [REQ R13.3]
  - ``AuthError``          — raised for authentication failures
  - ``RateLimitError``     — raised when account is temporarily locked  [BL B-58]
  - ``AccountStore``       — SQLAlchemy ORM-backed local account table
                             in the same ``notes.db`` as notes  [BL B-45, B-96]
  - ``SessionManager``     — JSON session-token file at ``<data-dir>/.session``
                             with 24 h expiry and owner-only permissions  [BL B-59, B-75]

Security notes:
  - Passwords stored as bcrypt hashes; never in plaintext or logs.  [REQ R13.2]
  - ``DATABASE_URL`` is never stored in configuration; for PostgreSQL backends
    (Sprint 5A) it must be read from ``os.environ`` only.  [BL B-64] [REQ R9.6]
  - Session file permissions set to owner-only (0o600) on POSIX; best-effort on
    Windows (os.chmod with POSIX bits is ignored on NTFS — use icacls if strict
    ACL control is required on Windows servers).  [BL B-75] [REQ R13.5]

Refs: [BL B-41, B-45, B-46, B-57, B-58, B-59, B-60, B-61, B-75, B-81, B-96]
      [REQ R13.1–R13.12, R14.10]
"""
from __future__ import annotations

import json
import logging
import os
import re
import stat
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
from sqlalchemy import Column, Integer, Text, UniqueConstraint, create_engine
from sqlalchemy import URL as _DbURL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Username validation  [BL B-60] [REQ R13.3]
# ---------------------------------------------------------------------------

# Use \Z (absolute end-of-string) instead of $ to prevent a trailing \n
# from bypassing the character-class constraint.  [BL B-60] [REQ R13.3]
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}\Z")


def _email_to_username(email: str) -> str:
    """Derive a valid AstraNotes username from an email address.

    Strips the domain, replaces non-alphanumeric/underscore characters with
    ``_``, trims leading/trailing underscores, and enforces the 3–32 char
    length constraint.  Used by :meth:`AccountStore.get_or_create_oauth_account`.
    """
    local = email.split("@")[0] if "@" in email else email
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", local)
    safe = safe.strip("_")[:32]
    if not safe:
        safe = "oauth_user"
    if len(safe) < 3:
        safe = f"u_{safe}"
    return safe[:32]


def validate_username(username: str) -> None:
    """Raise :class:`ValueError` if *username* fails validation rules.

    Rules: 3–32 characters, alphanumeric and underscore only, stored
    case-insensitively (``Admin`` == ``admin``).  [BL B-60] [REQ R13.3]
    """
    if not _USERNAME_RE.match(username):
        raise ValueError(
            "Username must be 3–32 characters: letters, digits, and underscore only."
        )


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class AuthError(Exception):
    """Raised when authentication fails (wrong credentials, user not found)."""


class RateLimitError(AuthError):
    """Raised when an account is temporarily locked after too many failures.

    Attributes:
        locked_until: ISO-8601 UTC timestamp when the lockout expires.
    """

    def __init__(self, message: str, locked_until: str) -> None:
        super().__init__(message)
        self.locked_until = locked_until


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model for accounts table
# ---------------------------------------------------------------------------


class _AuthBase(DeclarativeBase):
    pass


class _AccountRow(_AuthBase):
    """ORM row — maps to the ``accounts`` table in the local SQLite database.

    This table is created in the same ``notes.db`` file as ``notes`` but uses
    a separate ``DeclarativeBase`` so each store can call ``create_all()``
    independently without interfering with the other's metadata.

    Refs: [BL B-96] [REQ R13.2, R14.10]
    """

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("username", name="uq_accounts_username"),)

    account_id = Column(Text, primary_key=True)
    username = Column(Text, nullable=False)         # stored lowercase
    password_hash = Column(Text, nullable=False)    # bcrypt hash
    created_at = Column(Text, nullable=False)       # ISO-8601 UTC
    failed_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(Text, nullable=True)      # ISO-8601 UTC or NULL


# ---------------------------------------------------------------------------
# Rate-limiting constants  [BL B-58] [REQ R13.7]
# ---------------------------------------------------------------------------

_MAX_FAILED_ATTEMPTS: int = 5
_LOCKOUT_MINUTES: int = 5


# ---------------------------------------------------------------------------
# AccountStore
# ---------------------------------------------------------------------------


class AccountStore:
    """Manages the local ``accounts`` table inside ``<data-dir>/notes.db``.

    All queries go through SQLAlchemy ORM — no raw SQL.  [REQ R15.1, R15.2]
    Usernames are normalised to lowercase for case-insensitive uniqueness.
    Passwords are hashed with bcrypt; never stored or logged in plaintext.
    [REQ R13.2]

    Refs: [BL B-45, B-58, B-60, B-61, B-96] [REQ R13.1–R13.12, R14.10]
    """

    def __init__(self, data_dir: Path) -> None:
        data_dir = Path(data_dir).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / "notes.db"
        # Use URL.create() to prevent connection-URL injection from paths
        # with SQLAlchemy URL special characters.
        url = _DbURL.create("sqlite", database=str(db_path))
        self._engine = create_engine(url, echo=False)
        _AuthBase.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    # ------------------------------------------------------------------
    # Register  [BL B-45] [REQ R13.1–R13.4]
    # ------------------------------------------------------------------

    def register(self, username: str, password: str) -> str:
        """Create a new account and return the new ``account_id`` (UUID).

        Raises:
            ValueError: username fails validation, password too short, or
                        username already taken (case-insensitive).
        """
        validate_username(username)
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")

        normalized = username.lower()
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        account_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self._Session() as session:
            existing = (
                session.query(_AccountRow)
                .filter(_AccountRow.username == normalized)
                .first()
            )
            if existing is not None:
                raise ValueError(f"Username {username!r} is already taken.")

            row = _AccountRow(
                account_id=account_id,
                username=normalized,
                password_hash=password_hash,
                created_at=now,
                failed_attempts=0,
                locked_until=None,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                # Another concurrent registration sneaked in between our check
                # and insert.  The UniqueConstraint on 'username' is the
                # authoritative guard.  [REQ R13.3]
                session.rollback()
                raise ValueError(f"Username {username!r} is already taken.")

        return account_id

    # ------------------------------------------------------------------
    # OAuth account upsert  [BL B-87]
    # ------------------------------------------------------------------

    def get_or_create_oauth_account(self, email: str, oauth_sub: str) -> dict:
        """Return or create an account for a Google OAuth user.

        Uses the email's local part (sanitised) as the username.  OAuth
        accounts are registered with a random unguessable password — they
        can only be authenticated via the OAuth callback, never via the
        normal ``authenticate()`` path.

        Args:
            email: The user's verified email from Google's id_token.
            oauth_sub: The Google ``sub`` claim (stable user identifier).

        Returns:
            Account dict with at least ``account_id`` and ``username``.
        """
        import secrets as _secrets

        username = _email_to_username(email)

        existing = self.get_by_username(username)
        if existing:
            return existing

        # Username derived from email may collide with an unrelated local
        # account.  Append the first 6 chars of the Google sub to disambiguate.
        try:
            account_id = self.register(username, _secrets.token_urlsafe(32))
        except ValueError:
            # Username taken — append sub suffix and retry once.
            username = f"{username[:25]}_{oauth_sub[:6]}"
            account_id = self.register(username, _secrets.token_urlsafe(32))

        return {"account_id": account_id, "username": username}

    # ------------------------------------------------------------------
    # Lookup  [REQ R13.6]
    # ------------------------------------------------------------------

    def get_by_username(self, username: str) -> Optional[dict]:
        """Return account data dict or ``None`` if not found.

        Lookup is case-insensitive.
        """
        normalized = username.lower()
        with self._Session() as session:
            row = (
                session.query(_AccountRow)
                .filter(_AccountRow.username == normalized)
                .first()
            )
            if row is None:
                return None
            return {
                "account_id": row.account_id,
                "username": row.username,
                "password_hash": row.password_hash,
                "created_at": row.created_at,
                "failed_attempts": row.failed_attempts,
                "locked_until": row.locked_until,
            }

    # ------------------------------------------------------------------
    # Authenticate  [BL B-58] [REQ R13.6, R13.7]
    # ------------------------------------------------------------------

    def authenticate(self, username: str, password: str) -> dict:
        """Verify credentials and return account dict on success.

        Raises:
            RateLimitError: account locked due to repeated failures.
            AuthError: wrong credentials.

        Side-effects:
            - Increments ``failed_attempts`` on wrong password.
            - Locks account (sets ``locked_until``) after _MAX_FAILED_ATTEMPTS.
            - Resets ``failed_attempts`` and ``locked_until`` on success.
            - Resets counter if lockout has expired before authenticating.
        """
        normalized = username.lower()
        with self._Session() as session:
            row = (
                session.query(_AccountRow)
                .filter(_AccountRow.username == normalized)
                .first()
            )

            if row is None:
                # Do not reveal whether the username exists.
                raise AuthError("Invalid username or password.")

            now = datetime.now(timezone.utc)

            # --- Check lockout ---
            if row.locked_until is not None:
                locked_until_dt = datetime.fromisoformat(row.locked_until)
                if now < locked_until_dt:
                    raise RateLimitError(
                        f"Account locked until {row.locked_until}. "
                        f"Too many failed login attempts.",
                        row.locked_until,
                    )
                # Lockout expired — clear it before checking password.
                row.locked_until = None
                row.failed_attempts = 0
                session.commit()

            # --- Verify password ---
            if not bcrypt.checkpw(
                password.encode("utf-8"), row.password_hash.encode("utf-8")
            ):
                row.failed_attempts += 1
                if row.failed_attempts >= _MAX_FAILED_ATTEMPTS:
                    locked_until = (
                        now + timedelta(minutes=_LOCKOUT_MINUTES)
                    ).isoformat()
                    row.locked_until = locked_until
                    session.commit()
                    raise RateLimitError(
                        f"Too many failed attempts. Account locked for "
                        f"{_LOCKOUT_MINUTES} minutes.",
                        locked_until,
                    )
                session.commit()
                raise AuthError("Invalid username or password.")

            # --- Success: reset counters ---
            row.failed_attempts = 0
            row.locked_until = None
            session.commit()

            return {
                "account_id": row.account_id,
                "username": row.username,
            }

    # ------------------------------------------------------------------
    # Delete  [BL B-61, B-81] [REQ R13.12]
    # ------------------------------------------------------------------

    def delete(self, account_id: str) -> None:
        """Remove the account record from the local database.

        Does not affect notes (caller must call
        ``DatabaseStore.disassociate_account()`` separately).
        """
        with self._Session() as session:
            row = session.get(_AccountRow, account_id)
            if row is not None:
                session.delete(row)
                session.commit()


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

_SESSION_FILENAME = ".session"
_SESSION_EXPIRY_HOURS = 720  # 30 days — appropriate for an installed app


class SessionManager:
    """Manages the session token file at ``<data-dir>/.session``.

    Token file format (JSON):
        {
            "account_id": "<uuid>",
            "username":   "<str>",
            "created_at": "<ISO-8601 UTC>",
            "expires_at": "<ISO-8601 UTC>"
        }

    File permissions are set to owner-only (0o600) immediately after
    creation to comply with [BL B-75] [REQ R13.5].  On Windows the chmod
    call is best-effort (NTFS ACLs would need ``icacls``).

    An expired session file is silently removed on ``load()``.
    Expired sessions block sync/account operations but never block local
    CRUD.  [REQ R13.8]

    Refs: [BL B-59, B-75] [REQ R13.5, R13.8, R13.9]
    """

    @staticmethod
    def _path(data_dir: Path) -> Path:
        return Path(data_dir).resolve() / _SESSION_FILENAME

    @classmethod
    def create(cls, data_dir: Path, account_id: str, username: str) -> dict:
        """Write a fresh session file and return the session dict.

        The file is created with owner-only read/write permissions.
        [BL B-75] [REQ R13.5]
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=_SESSION_EXPIRY_HOURS)
        session_data = {
            "account_id": account_id,
            "username": username,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        path = cls._path(data_dir)
        path.write_text(json.dumps(session_data, indent=2), encoding="utf-8")
        # Restrict to owner read/write only.  [BL B-75]
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            logger.warning("Could not restrict session file permissions on %s.", path)
        return session_data

    @classmethod
    def load(cls, data_dir: Path) -> Optional[dict]:
        """Load and validate the session file.

        Returns the session dict if valid and not expired, or ``None`` if
        the file is absent, expired, or malformed.  An expired file is
        deleted automatically.  [BL B-59] [REQ R13.8]
        """
        path = cls._path(data_dir)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            session_data = json.loads(raw)
            expires_at = datetime.fromisoformat(session_data["expires_at"])
            if datetime.now(timezone.utc) >= expires_at:
                logger.info("Session expired; removing session file at %s.", path)
                path.unlink(missing_ok=True)
                return None
            return session_data
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            logger.warning("Could not read session file at %s; removing.", path)
            # Delete corrupt / unreadable session files so they don't generate
            # warnings on every subsequent load() call.  [BL B-59]
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

    @classmethod
    def delete(cls, data_dir: Path) -> bool:
        """Remove the session file.  Returns ``True`` if a file was removed.

        Does not raise if the file is absent.  [REQ R13.9]
        """
        path = cls._path(data_dir)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
