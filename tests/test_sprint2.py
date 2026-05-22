"""Sprint 2 unit and CLI integration tests for AstraNotes.

Coverage:
  §1  AccountStore — registration, username validation, duplicate detection
                     [BL B-45, B-60, B-96]
  §2  Authentication and rate limiting  [BL B-58]
  §3  SessionManager — create, load, expiry, permissions, delete  [BL B-59, B-75]
  §4  Hybrid storage — small notes inline, large encrypted notes on filesystem
                       [BL B-49] [REQ R14.8]
  §5  ENOSPC / disk-full error handling  [BL B-67]
  §6  DatabaseStore account_id — add with account, list scoping,
                                  disassociate_account, associate_anonymous_notes,
                                  set_note_account_id  [BL B-47]
  §7  CLI ``register`` command  [BL B-45, B-57, B-60]
  §8  CLI ``login`` and ``logout``  [BL B-46, B-57, B-58, B-59]
  §9  CLI ``delete-account``  [BL B-61, B-81]
  §10 CLI ``list`` — two-section output when logged in  [BL B-47]
  §11 CLI ``add`` — associates with active account  [BL B-47]
  §12 First-login anonymous note association prompt  [BL B-41]
  §13 DATABASE_URL never stored (architectural invariant)  [BL B-64]
  §14 Flat data directory layout  [BL B-77]
  §15 Alembic Sprint 2 migration  [BL B-65]
  §16 Backward compatibility — all existing CRUD tests still pass implicitly
  §17 Auth bug regressions (trailing newline, IntegrityError, corrupt session)
  §18 Branch-coverage gap tests — previously-uncovered execution paths

Refs: [BL B-41, B-45, B-46, B-47, B-49, B-57, B-58, B-59, B-60, B-61, B-64,
       B-65, B-67, B-68, B-75, B-77, B-81, B-96]
"""
from __future__ import annotations

import errno
import json
import os
import stat
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli import cli
from src.core.auth import (
    AccountStore,
    AuthError,
    RateLimitError,
    SessionManager,
    validate_username,
)
from src.core.blob_codec import BlobCodec
from src.core.notes import (
    DatabaseStore,
    DiskFullError,
    Note,
    _FILESYSTEM_THRESHOLD_BYTES,
)
from src.core.security import KeyManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_PASSPHRASE = "TestPass1!"
_TEST_ITERATIONS = 1_000     # keep tests fast

_RUNNER = CliRunner()


def _make_encrypted_blob(content: str, passphrase: str = _TEST_PASSPHRASE) -> bytes:
    km = KeyManager(passphrase, iterations=_TEST_ITERATIONS)
    engine = km.get_engine()
    header = {"title": "enc", "format": "text/plain"}
    raw = BlobCodec.encode(header, content.encode("utf-8"))
    return BlobCodec.encrypt(raw, engine)


def _make_large_encrypted_blob(size_mb: float = 6) -> bytes:
    """Return an encrypted blob that exceeds the 5 MiB threshold."""
    payload = b"X" * int(size_mb * 1024 * 1024)
    km = KeyManager(_TEST_PASSPHRASE, iterations=_TEST_ITERATIONS)
    engine = km.get_engine()
    header = {"title": "big", "format": "application/octet-stream"}
    raw = BlobCodec.encode(header, payload)
    return BlobCodec.encrypt(raw, engine)


# ===========================================================================
# §1  AccountStore — registration
# ===========================================================================


class TestAccountStoreRegistration:
    """[BL B-45, B-60, B-96]"""

    def test_register_returns_uuid(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        account_id = store.register("alice", "password1")
        assert len(account_id) == 36  # UUID format

    def test_register_password_hash_not_plaintext(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("bob", "hunter2!!")
        account = store.get_by_username("bob")
        assert account is not None
        assert "hunter2!!" not in account["password_hash"]
        assert account["password_hash"].startswith("$2b$")  # bcrypt marker

    def test_register_normalises_username_to_lowercase(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("Charlie", "password1")
        account = store.get_by_username("charlie")
        assert account is not None
        assert account["username"] == "charlie"

    def test_register_duplicate_username_raises(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("dana", "password1")
        with pytest.raises(ValueError, match="already taken"):
            store.register("dana", "password2")

    def test_register_duplicate_case_insensitive(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("eve", "password1")
        with pytest.raises(ValueError, match="already taken"):
            store.register("EVE", "password2")

    def test_register_invalid_username_too_short(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        with pytest.raises(ValueError, match="3"):
            store.register("ab", "password1")

    def test_register_invalid_username_too_long(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        with pytest.raises(ValueError, match="32"):
            store.register("a" * 33, "password1")

    def test_register_invalid_username_bad_chars(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        with pytest.raises(ValueError):
            store.register("bad-name!", "password1")

    def test_register_short_password_raises(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        with pytest.raises(ValueError, match="8"):
            store.register("frank", "short")

    def test_get_by_username_not_found_returns_none(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        assert store.get_by_username("nobody") is None

    def test_get_by_username_case_insensitive(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("Grace", "password1")
        assert store.get_by_username("GRACE") is not None


# ===========================================================================
# §2  Authentication and rate limiting
# ===========================================================================


class TestAuthentication:
    """[BL B-58] [REQ R13.6, R13.7]"""

    def test_authenticate_correct_credentials(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("hank", "goodpass1")
        result = store.authenticate("hank", "goodpass1")
        assert result["username"] == "hank"
        assert "account_id" in result

    def test_authenticate_wrong_password_raises(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("iris", "correctpass")
        with pytest.raises(AuthError):
            store.authenticate("iris", "wrongpass")

    def test_authenticate_unknown_user_raises(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        with pytest.raises(AuthError):
            store.authenticate("phantom", "anything")

    def test_authenticate_increments_failed_attempts(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("jack", "password1")
        for _ in range(2):
            try:
                store.authenticate("jack", "wrongpass")
            except AuthError:
                pass
        account = store.get_by_username("jack")
        assert account is not None
        assert account["failed_attempts"] == 2

    def test_authenticate_locks_after_five_failures(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("karen", "password1")
        for _ in range(5):
            try:
                store.authenticate("karen", "wrongpass")
            except (AuthError, RateLimitError):
                pass
        with pytest.raises(RateLimitError) as exc_info:
            store.authenticate("karen", "password1")  # even correct creds fail
        assert exc_info.value.locked_until is not None

    def test_authenticate_rate_limit_error_has_locked_until(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("leo", "password1")
        for _ in range(5):
            try:
                store.authenticate("leo", "wrong")
            except (AuthError, RateLimitError):
                pass
        with pytest.raises(RateLimitError) as exc_info:
            store.authenticate("leo", "wrong")
        assert exc_info.value.locked_until is not None

    def test_authenticate_resets_counter_on_success(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("mia", "password1")
        # Two failures
        for _ in range(2):
            try:
                store.authenticate("mia", "wrong")
            except AuthError:
                pass
        # Then success
        store.authenticate("mia", "password1")
        account = store.get_by_username("mia")
        assert account is not None
        assert account["failed_attempts"] == 0

    def test_authenticate_expired_lockout_allows_login(self, tmp_path: Path) -> None:
        store = AccountStore(tmp_path)
        store.register("ned", "password1")
        # Manually set a lockout time in the past
        account = store.get_by_username("ned")
        assert account is not None
        with store._Session() as session:
            from src.core.auth import _AccountRow
            row = session.get(_AccountRow, account["account_id"])
            assert row is not None
            past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
            row.locked_until = past
            row.failed_attempts = 5
            session.commit()
        # Login should now succeed
        result = store.authenticate("ned", "password1")
        assert result["username"] == "ned"


# ===========================================================================
# §3  SessionManager
# ===========================================================================


class TestSessionManager:
    """[BL B-59, B-75] [REQ R13.5, R13.8, R13.9]"""

    def test_create_writes_session_file(self, tmp_path: Path) -> None:
        SessionManager.create(tmp_path, "uuid-001", "alice")
        session_file = tmp_path / ".session"
        assert session_file.exists()

    def test_create_returns_valid_session_dict(self, tmp_path: Path) -> None:
        session = SessionManager.create(tmp_path, "uuid-001", "alice")
        assert session["account_id"] == "uuid-001"
        assert session["username"] == "alice"
        assert "expires_at" in session
        assert "created_at" in session

    def test_load_returns_session_when_valid(self, tmp_path: Path) -> None:
        SessionManager.create(tmp_path, "uuid-002", "bob")
        loaded = SessionManager.load(tmp_path)
        assert loaded is not None
        assert loaded["account_id"] == "uuid-002"

    def test_load_returns_none_when_no_file(self, tmp_path: Path) -> None:
        assert SessionManager.load(tmp_path) is None

    def test_load_returns_none_and_deletes_expired_session(self, tmp_path: Path) -> None:
        # Manually write an expired session
        past = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        expired = {
            "account_id": "uuid-003",
            "username": "carol",
            "created_at": past,
            "expires_at": past,
        }
        session_file = tmp_path / ".session"
        session_file.write_text(json.dumps(expired), encoding="utf-8")
        result = SessionManager.load(tmp_path)
        assert result is None
        assert not session_file.exists()

    def test_load_returns_none_for_corrupted_file(self, tmp_path: Path) -> None:
        (tmp_path / ".session").write_text("not json!!!", encoding="utf-8")
        assert SessionManager.load(tmp_path) is None

    def test_delete_removes_session_file(self, tmp_path: Path) -> None:
        SessionManager.create(tmp_path, "uuid-004", "dave")
        removed = SessionManager.delete(tmp_path)
        assert removed is True
        assert not (tmp_path / ".session").exists()

    def test_delete_returns_false_when_no_file(self, tmp_path: Path) -> None:
        assert SessionManager.delete(tmp_path) is False

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions only")
    def test_session_file_permissions_owner_only(self, tmp_path: Path) -> None:
        """Session file must be readable/writable only by owner.  [BL B-75]"""
        SessionManager.create(tmp_path, "uuid-005", "eve")
        session_file = tmp_path / ".session"
        mode = session_file.stat().st_mode
        # Other and group bits must be clear
        assert not (mode & stat.S_IRGRP), "Group read should be disabled"
        assert not (mode & stat.S_IWGRP), "Group write should be disabled"
        assert not (mode & stat.S_IROTH), "Other read should be disabled"
        assert not (mode & stat.S_IWOTH), "Other write should be disabled"


# ===========================================================================
# §4  Hybrid storage
# ===========================================================================


class TestHybridStorage:
    """[BL B-49] [REQ R14.8]"""

    def test_small_encrypted_note_stored_inline(self, tmp_path: Path) -> None:
        store = DatabaseStore(tmp_path)
        blob = _make_encrypted_blob("small content")
        assert len(blob) < _FILESYSTEM_THRESHOLD_BYTES
        note = Note.create("[Encrypted Note]", "", encrypted=True, blob=blob)
        store.add(note)
        # Filesystem payload directory should be empty
        files_dir = tmp_path / "files"
        assert list(files_dir.iterdir()) == []

    def test_large_encrypted_note_stored_on_filesystem(self, tmp_path: Path) -> None:
        store = DatabaseStore(tmp_path)
        blob = _make_large_encrypted_blob(6)  # 6 MiB
        assert len(blob) > _FILESYSTEM_THRESHOLD_BYTES
        note = Note.create("[Encrypted Note]", "", encrypted=True, blob=blob)
        store.add(note)
        # File should exist under files/
        payload_file = tmp_path / "files" / f"{note.id}.bin"
        assert payload_file.exists()
        assert payload_file.read_bytes() == blob

    def test_large_encrypted_note_db_row_has_filesystem_location(
        self, tmp_path: Path
    ) -> None:
        store = DatabaseStore(tmp_path)
        blob = _make_large_encrypted_blob(6)
        note = Note.create("[Encrypted Note]", "", encrypted=True, blob=blob)
        store.add(note)
        # Check DB row directly
        from src.core.notes import _NoteRow
        with store._Session() as session:
            row = session.get(_NoteRow, note.id)
            assert row is not None
            assert row.payload_location == "filesystem"
            assert row.encrypted_blob is None  # payload is on disk, not in DB

    def test_get_filesystem_note_loads_blob_from_file(self, tmp_path: Path) -> None:
        store = DatabaseStore(tmp_path)
        blob = _make_large_encrypted_blob(6)
        note = Note.create("[Encrypted Note]", "", encrypted=True, blob=blob)
        store.add(note)
        retrieved = store.get(note.id)
        assert retrieved is not None
        assert retrieved.blob == blob

    def test_delete_filesystem_note_removes_payload_file(self, tmp_path: Path) -> None:
        """Orphan cleanup on delete.  [BL B-68]"""
        store = DatabaseStore(tmp_path)
        blob = _make_large_encrypted_blob(6)
        note = Note.create("[Encrypted Note]", "", encrypted=True, blob=blob)
        store.add(note)
        payload_file = tmp_path / "files" / f"{note.id}.bin"
        assert payload_file.exists()
        store.delete(note.id)
        assert not payload_file.exists()

    def test_delete_inline_note_no_filesystem_side_effects(
        self, tmp_path: Path
    ) -> None:
        store = DatabaseStore(tmp_path)
        blob = _make_encrypted_blob("small")
        note = Note.create("[Encrypted Note]", "", encrypted=True, blob=blob)
        store.add(note)
        store.delete(note.id)  # must not raise even though there's no file

    def test_large_unencrypted_note_always_stored_inline(
        self, tmp_path: Path
    ) -> None:
        """No plaintext files ever written to disk.  [REQ R14.8]"""
        store = DatabaseStore(tmp_path)
        big_content = "A" * (6 * 1024 * 1024)  # 6 MiB
        note = Note.create("Big Plain Note", big_content)
        store.add(note)
        files_dir = tmp_path / "files"
        assert list(files_dir.iterdir()) == []

    def test_files_directory_created_on_init(self, tmp_path: Path) -> None:
        """files/ directory must exist after DatabaseStore init.  [BL B-77]"""
        DatabaseStore(tmp_path)
        assert (tmp_path / "files").is_dir()


# ===========================================================================
# §5  ENOSPC / disk-full error handling
# ===========================================================================


class TestEnospcHandling:
    """[BL B-67] [REQ R3.8, R14.12]"""

    def test_enospc_on_filesystem_payload_write_raises_disk_full_error(
        self, tmp_path: Path
    ) -> None:
        store = DatabaseStore(tmp_path)
        blob = _make_large_encrypted_blob(6)
        note = Note.create("[Encrypted Note]", "", encrypted=True, blob=blob)

        enospc = OSError(errno.ENOSPC, "No space left on device")
        with patch.object(Path, "write_bytes", side_effect=enospc):
            with pytest.raises(DiskFullError):
                store.add(note)

    def test_disk_full_error_is_oserror_subclass(self) -> None:
        err = DiskFullError(errno.ENOSPC, "full")
        assert isinstance(err, OSError)


# ===========================================================================
# §6  DatabaseStore account_id
# ===========================================================================


class TestDatabaseStoreAccountId:
    """[BL B-47] [REQ R1.3]"""

    def test_add_with_account_id_stores_it(self, tmp_path: Path) -> None:
        store = DatabaseStore(tmp_path)
        note = Note.create("Account Note", "content")
        store.add(note, account_id="acc-001")
        from src.core.notes import _NoteRow
        with store._Session() as session:
            row = session.get(_NoteRow, note.id)
            assert row is not None
            assert row.account_id == "acc-001"

    def test_add_without_account_id_stores_null(self, tmp_path: Path) -> None:
        store = DatabaseStore(tmp_path)
        note = Note.create("Local Note", "content")
        store.add(note)
        from src.core.notes import _NoteRow
        with store._Session() as session:
            row = session.get(_NoteRow, note.id)
            assert row is not None
            assert row.account_id is None

    def test_list_account_notes_scoped_by_account_id(self, tmp_path: Path) -> None:
        store = DatabaseStore(tmp_path)
        n_local = Note.create("Local", "local content")
        n_acc = Note.create("Account", "account content")
        store.add(n_local)
        store.add(n_acc, account_id="acc-001")

        account_notes, local_notes = store.list(account_id="acc-001")
        account_ids = {n.id for n in account_notes}
        local_ids = {n.id for n in local_notes}
        assert n_acc.id in account_ids
        assert n_local.id in local_ids
        assert n_acc.id not in local_ids
        assert n_local.id not in account_ids

    def test_list_logged_out_returns_only_anonymous_notes(
        self, tmp_path: Path
    ) -> None:
        store = DatabaseStore(tmp_path)
        n_local = Note.create("Local", "content")
        n_acc = Note.create("Account", "content")
        store.add(n_local)
        store.add(n_acc, account_id="acc-001")

        account_notes, local_notes = store.list(account_id=None)
        assert account_notes == []
        local_ids = {n.id for n in local_notes}
        assert n_local.id in local_ids
        assert n_acc.id not in local_ids  # account note not shown when logged out

    def test_list_other_account_notes_not_shown(self, tmp_path: Path) -> None:
        store = DatabaseStore(tmp_path)
        n_a = Note.create("A", "content")
        n_b = Note.create("B", "content")
        store.add(n_a, account_id="acc-001")
        store.add(n_b, account_id="acc-002")

        account_notes, local_notes = store.list(account_id="acc-001")
        account_ids = {n.id for n in account_notes}
        local_ids = {n.id for n in local_notes}
        assert n_a.id in account_ids
        assert n_b.id not in account_ids
        assert n_b.id not in local_ids  # other account note hidden

    def test_disassociate_account_sets_null(self, tmp_path: Path) -> None:
        store = DatabaseStore(tmp_path)
        note = Note.create("Note", "content")
        store.add(note, account_id="acc-001")
        count = store.disassociate_account("acc-001")
        assert count == 1
        from src.core.notes import _NoteRow
        with store._Session() as session:
            row = session.get(_NoteRow, note.id)
            assert row is not None
            assert row.account_id is None

    def test_associate_anonymous_notes(self, tmp_path: Path) -> None:
        store = DatabaseStore(tmp_path)
        n1 = Note.create("N1", "c1")
        n2 = Note.create("N2", "c2")
        store.add(n1)
        store.add(n2)
        count = store.associate_anonymous_notes("acc-001")
        assert count == 2
        from src.core.notes import _NoteRow
        with store._Session() as session:
            for nid in [n1.id, n2.id]:
                row = session.get(_NoteRow, nid)
                assert row is not None
                assert row.account_id == "acc-001"

    def test_associate_anonymous_notes_skips_existing_account_notes(
        self, tmp_path: Path
    ) -> None:
        store = DatabaseStore(tmp_path)
        n_local = Note.create("Local", "c")
        n_acc = Note.create("Account", "c")
        store.add(n_local)
        store.add(n_acc, account_id="acc-002")
        count = store.associate_anonymous_notes("acc-001")
        assert count == 1  # only the anonymous note was updated
        from src.core.notes import _NoteRow
        with store._Session() as session:
            row = session.get(_NoteRow, n_acc.id)
            assert row is not None
            assert row.account_id == "acc-002"  # unchanged

    def test_set_note_account_id(self, tmp_path: Path) -> None:
        store = DatabaseStore(tmp_path)
        note = Note.create("N", "c")
        store.add(note)
        store.set_note_account_id(note.id, "acc-001")
        from src.core.notes import _NoteRow
        with store._Session() as session:
            row = session.get(_NoteRow, note.id)
            assert row is not None
            assert row.account_id == "acc-001"

    def test_set_note_account_id_not_found_raises(self, tmp_path: Path) -> None:
        store = DatabaseStore(tmp_path)
        with pytest.raises(KeyError):
            store.set_note_account_id("nonexistent", "acc-001")


# ===========================================================================
# §7  CLI register command
# ===========================================================================


class TestCliRegister:
    """[BL B-45, B-57, B-60]"""

    def test_register_creates_account(self, tmp_path: Path) -> None:
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "register"],
            input="alice\nPassword1!\nPassword1!\n",
        )
        assert result.exit_code == 0, result.output
        assert "alice" in result.output

    def test_register_invalid_username_exits_nonzero(self, tmp_path: Path) -> None:
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "register"],
            input="ab\nPassword1!\nPassword1!\n",  # too short
        )
        assert result.exit_code != 0

    def test_register_short_password_exits_nonzero(self, tmp_path: Path) -> None:
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "register"],
            input="validuser\nshort\nshort\n",
        )
        assert result.exit_code != 0

    def test_register_duplicate_username_exits_nonzero(self, tmp_path: Path) -> None:
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "register"],
            input="bob\nPassword1!\nPassword1!\n",
        )
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "register"],
            input="bob\nPassword1!\nPassword1!\n",
        )
        assert result.exit_code != 0
        assert "taken" in result.output.lower()


# ===========================================================================
# §8  CLI login and logout
# ===========================================================================


class TestCliLoginLogout:
    """[BL B-46, B-57, B-58, B-59]"""

    def _register_user(
        self, tmp_path: Path, username: str = "carol", password: str = "Password1!"
    ) -> None:
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "register"],
            input=f"{username}\n{password}\n{password}\n",
        )

    def test_login_creates_session_file(self, tmp_path: Path) -> None:
        self._register_user(tmp_path)
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="carol\nPassword1!\nno\n",  # "no" answers the first-login prompt
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".session").exists()

    def test_login_session_contains_correct_username(self, tmp_path: Path) -> None:
        self._register_user(tmp_path)
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="carol\nPassword1!\nno\n",
        )
        session = SessionManager.load(tmp_path)
        assert session is not None
        assert session["username"] == "carol"

    def test_login_wrong_password_exits_nonzero(self, tmp_path: Path) -> None:
        self._register_user(tmp_path)
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="carol\nWrongPass!\n",
        )
        assert result.exit_code != 0

    def test_login_wrong_password_no_session_file(self, tmp_path: Path) -> None:
        self._register_user(tmp_path)
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="carol\nWrongPass!\n",
        )
        assert not (tmp_path / ".session").exists()

    def test_login_rate_limit_after_five_failures(self, tmp_path: Path) -> None:
        self._register_user(tmp_path)
        for _ in range(5):
            _RUNNER.invoke(
                cli,
                ["--data-dir", str(tmp_path), "login"],
                input="carol\nWrongPass!\n",
            )
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="carol\nPassword1!\n",
        )
        assert result.exit_code != 0
        assert "locked" in result.output.lower()

    def test_logout_removes_session_file(self, tmp_path: Path) -> None:
        self._register_user(tmp_path)
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="carol\nPassword1!\nno\n",
        )
        result = _RUNNER.invoke(
            cli, ["--data-dir", str(tmp_path), "logout"]
        )
        assert result.exit_code == 0
        assert not (tmp_path / ".session").exists()

    def test_logout_when_not_logged_in_exits_zero(self, tmp_path: Path) -> None:
        result = _RUNNER.invoke(
            cli, ["--data-dir", str(tmp_path), "logout"]
        )
        assert result.exit_code == 0
        assert "no active session" in result.output.lower()


# ===========================================================================
# §9  CLI delete-account
# ===========================================================================


class TestCliDeleteAccount:
    """[BL B-61, B-81] [REQ R13.12]"""

    def _setup(self, tmp_path: Path) -> None:
        """Register + login a user."""
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "register"],
            input="dan\nPassword1!\nPassword1!\n",
        )
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="dan\nPassword1!\nno\n",
        )

    def test_delete_account_requires_login(self, tmp_path: Path) -> None:
        result = _RUNNER.invoke(
            cli, ["--data-dir", str(tmp_path), "delete-account"]
        )
        assert result.exit_code != 0
        assert "not logged in" in result.output.lower()

    def test_delete_account_wrong_confirmation_aborts(
        self, tmp_path: Path
    ) -> None:
        self._setup(tmp_path)
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "delete-account"],
            input="Password1!\nWRONG PHRASE\n",
        )
        assert result.exit_code != 0
        # Account must still exist
        store = AccountStore(tmp_path)
        assert store.get_by_username("dan") is not None

    def test_delete_account_dissociates_notes(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        session_data = SessionManager.load(tmp_path)
        assert session_data is not None
        account_id = session_data["account_id"]

        # Add a note while logged in (will be associated with account)
        note_store = DatabaseStore(tmp_path)
        note = Note.create("Dan's Note", "secret")
        note_store.add(note, account_id=account_id)

        # Delete account
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "delete-account"],
            input="Password1!\nCONFIRM DELETE ACCOUNT\n",
        )
        assert result.exit_code == 0, result.output

        # Note still exists but is now anonymous
        from src.core.notes import _NoteRow
        with note_store._Session() as session:
            row = session.get(_NoteRow, note.id)
            assert row is not None
            assert row.account_id is None

    def test_delete_account_removes_session_file(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "delete-account"],
            input="Password1!\nCONFIRM DELETE ACCOUNT\n",
        )
        assert not (tmp_path / ".session").exists()

    def test_delete_account_removes_account_record(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "delete-account"],
            input="Password1!\nCONFIRM DELETE ACCOUNT\n",
        )
        store = AccountStore(tmp_path)
        assert store.get_by_username("dan") is None

    def test_delete_account_removes_audit_log(self, tmp_path: Path) -> None:
        self._setup(tmp_path)
        audit_log = tmp_path / "audit.log"
        audit_log.write_text('{"operation":"test"}\n', encoding="utf-8")
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "delete-account"],
            input="Password1!\nCONFIRM DELETE ACCOUNT\n",
        )
        assert not audit_log.exists()


# ===========================================================================
# §10  CLI list — two-section output when logged in
# ===========================================================================


class TestCliListWithAccount:
    """[BL B-47] [REQ R1.3]"""

    def _register_login(self, tmp_path: Path) -> None:
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "register"],
            input="ellen\nPassword1!\nPassword1!\n",
        )
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="ellen\nPassword1!\nno\n",
        )

    def test_list_logged_out_flat_format(self, tmp_path: Path) -> None:
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "MyNote", "--content", "hi"],
        )
        result = _RUNNER.invoke(cli, ["--data-dir", str(tmp_path), "list"])
        assert result.exit_code == 0
        assert "MyNote" in result.output
        assert "Your Notes" not in result.output

    def test_list_logged_in_shows_sections(self, tmp_path: Path) -> None:
        self._register_login(tmp_path)
        # Add a note (will be associated with account because logged in)
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "AccountNote", "--content", "hi"],
        )
        result = _RUNNER.invoke(cli, ["--data-dir", str(tmp_path), "list"])
        assert result.exit_code == 0
        assert "Your Notes" in result.output
        assert "AccountNote" in result.output

    def test_list_logged_in_local_notes_section_shown(self, tmp_path: Path) -> None:
        # Add anonymous note first (before login)
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "AnonNote", "--content", "hi"],
        )
        self._register_login(tmp_path)
        result = _RUNNER.invoke(cli, ["--data-dir", str(tmp_path), "list"])
        assert result.exit_code == 0
        assert "Local Open Notes" in result.output
        assert "AnonNote" in result.output

    def test_list_shows_no_notes_found_when_empty(self, tmp_path: Path) -> None:
        result = _RUNNER.invoke(cli, ["--data-dir", str(tmp_path), "list"])
        assert result.exit_code == 0
        assert "no notes found" in result.output.lower()


# ===========================================================================
# §11  CLI add — associates with active account
# ===========================================================================


class TestCliAddWithAccount:
    """[BL B-47]"""

    def _register_login(self, tmp_path: Path) -> str:
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "register"],
            input="frank\nPassword1!\nPassword1!\n",
        )
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="frank\nPassword1!\nno\n",
        )
        session = SessionManager.load(tmp_path)
        assert session is not None
        return session["account_id"]

    def test_add_while_logged_in_sets_account_id(self, tmp_path: Path) -> None:
        account_id = self._register_login(tmp_path)
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "WorkNote", "--content", "stuff"],
        )
        assert result.exit_code == 0, result.output
        note_id = result.output.strip()

        from src.core.notes import _NoteRow
        store = DatabaseStore(tmp_path)
        with store._Session() as session:
            row = session.get(_NoteRow, note_id)
            assert row is not None
            assert row.account_id == account_id

    def test_add_while_logged_out_creates_anonymous_note(
        self, tmp_path: Path
    ) -> None:
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "LocalNote", "--content", "hi"],
        )
        assert result.exit_code == 0
        note_id = result.output.strip()

        from src.core.notes import _NoteRow
        store = DatabaseStore(tmp_path)
        with store._Session() as session:
            row = session.get(_NoteRow, note_id)
            assert row is not None
            assert row.account_id is None


# ===========================================================================
# §12  First-login anonymous note association prompt
# ===========================================================================


class TestFirstLoginPrompt:
    """[BL B-41] [REQ R12.3]"""

    def _setup_user_and_anon_notes(self, tmp_path: Path, n: int = 2) -> None:
        """Register a user and add n anonymous notes before logging in."""
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "register"],
            input="grace\nPassword1!\nPassword1!\n",
        )
        for i in range(n):
            _RUNNER.invoke(
                cli,
                ["--data-dir", str(tmp_path), "add",
                 "--title", f"Note{i}", "--content", "content"],
            )

    def test_prompt_shown_when_anon_notes_exist(self, tmp_path: Path) -> None:
        self._setup_user_and_anon_notes(tmp_path, n=2)
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="grace\nPassword1!\nno\n",
        )
        assert result.exit_code == 0
        assert "local note" in result.output.lower()

    def test_prompt_yes_associates_all_anon_notes(self, tmp_path: Path) -> None:
        self._setup_user_and_anon_notes(tmp_path, n=2)
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="grace\nPassword1!\nyes\n",
        )
        session = SessionManager.load(tmp_path)
        assert session is not None
        account_id = session["account_id"]

        store = DatabaseStore(tmp_path)
        account_notes, local_notes = store.list(account_id=account_id)
        assert len(account_notes) == 2
        assert len(local_notes) == 0

    def test_prompt_no_leaves_notes_anonymous(self, tmp_path: Path) -> None:
        self._setup_user_and_anon_notes(tmp_path, n=2)
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="grace\nPassword1!\nno\n",
        )
        session = SessionManager.load(tmp_path)
        assert session is not None
        account_id = session["account_id"]

        store = DatabaseStore(tmp_path)
        account_notes, local_notes = store.list(account_id=account_id)
        assert len(account_notes) == 0
        assert len(local_notes) == 2  # still anonymous

    def test_prompt_ask_associates_selected_notes(self, tmp_path: Path) -> None:
        self._setup_user_and_anon_notes(tmp_path, n=2)
        # "ask" mode: say "y" for first note, "n" for second
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="grace\nPassword1!\nask\ny\nn\n",
        )
        assert result.exit_code == 0, result.output
        session = SessionManager.load(tmp_path)
        assert session is not None
        account_id = session["account_id"]

        store = DatabaseStore(tmp_path)
        account_notes, local_notes = store.list(account_id=account_id)
        assert len(account_notes) == 1
        assert len(local_notes) == 1

    def test_prompt_not_shown_when_no_anon_notes(self, tmp_path: Path) -> None:
        """If no anonymous notes exist, the prompt should not appear."""
        _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "register"],
            input="henry\nPassword1!\nPassword1!\n",
        )
        result = _RUNNER.invoke(
            cli,
            ["--data-dir", str(tmp_path), "login"],
            input="henry\nPassword1!\n",
        )
        assert result.exit_code == 0
        assert "local note" not in result.output.lower()


# ===========================================================================
# §13  DATABASE_URL architectural invariant
# ===========================================================================


class TestDatabaseUrlEnvVarOnly:
    """[BL B-64] [REQ R9.6]"""

    @staticmethod
    def _code_lines_with_keyword(source: str, keyword: str):
        """Return non-comment, non-docstring lines that contain *keyword*."""
        results = []
        in_docstring = False
        for line in source.splitlines():
            stripped = line.strip()
            # Toggle docstring state on triple-quote markers
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            if stripped.startswith("#"):
                continue
            if keyword in line:
                results.append(line)
        return results

    def test_cli_does_not_read_database_url_from_config(self) -> None:
        """No code in cli.py may read DATABASE_URL from a dict/file."""
        import src.cli as cli_module
        import inspect
        source = inspect.getsource(cli_module)
        bad_lines = self._code_lines_with_keyword(source, "DATABASE_URL")
        for line in bad_lines:
            assert "os.environ" in line or "getenv" in line, (
                f"DATABASE_URL accessed outside os.environ in cli.py: {line!r}"
            )

    def test_auth_module_does_not_read_database_url_from_config(self) -> None:
        """No code in auth.py may read DATABASE_URL from a dict/file."""
        import src.core.auth as auth_module
        import inspect
        source = inspect.getsource(auth_module)
        bad_lines = self._code_lines_with_keyword(source, "DATABASE_URL")
        for line in bad_lines:
            assert "os.environ" in line or "getenv" in line, (
                f"DATABASE_URL accessed outside os.environ in auth.py: {line!r}"
            )


# ===========================================================================
# §14  Flat data directory layout
# ===========================================================================


class TestFlatDataDirectoryLayout:
    """[BL B-77] [REQ R14.13]"""

    def test_notes_db_at_root_of_data_dir(self, tmp_path: Path) -> None:
        DatabaseStore(tmp_path)
        assert (tmp_path / "notes.db").is_file()

    def test_files_dir_at_root_of_data_dir(self, tmp_path: Path) -> None:
        DatabaseStore(tmp_path)
        assert (tmp_path / "files").is_dir()

    def test_no_per_user_subdirectory_created(self, tmp_path: Path) -> None:
        """Flat layout: no per-user subdirectories on the local device."""
        store = DatabaseStore(tmp_path)
        blob = _make_large_encrypted_blob(6)
        note = Note.create("[Encrypted Note]", "", encrypted=True, blob=blob)
        store.add(note, account_id="acc-001")

        # Confirm file is in flat files/ not in users/<id>/files/
        expected_path = tmp_path / "files" / f"{note.id}.bin"
        assert expected_path.exists()
        # No per-user directory
        assert not (tmp_path / "users").exists()

    def test_session_file_at_root_of_data_dir(self, tmp_path: Path) -> None:
        SessionManager.create(tmp_path, "uuid-x", "user")
        assert (tmp_path / ".session").is_file()


# ===========================================================================
# §15  Alembic Sprint 2 migration
# ===========================================================================


class TestAlembicSprint2Migration:
    """[BL B-65]"""

    def test_migration_file_exists(self) -> None:
        migration_file = Path(
            "alembic/versions/3b7c9f2d8a1e_sprint_two_accounts.py"
        )
        assert migration_file.exists()

    def test_migration_has_correct_down_revision(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sprint2_migration",
            "alembic/versions/3b7c9f2d8a1e_sprint_two_accounts.py",
        )
        assert spec is not None, "Failed to load migration module spec"
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None, "Failed to load migration module loader"
        spec.loader.exec_module(module)
        assert module.down_revision == "e2f2634ce4f7"
        assert module.revision == "3b7c9f2d8a1e"

    def test_accounts_table_created_by_account_store_init(
        self, tmp_path: Path
    ) -> None:
        """AccountStore.create_all() must create the accounts table in SQLite."""
        AccountStore(tmp_path)
        import sqlalchemy as sa
        from sqlalchemy import URL as _U, create_engine, inspect as _inspect
        url = _U.create("sqlite", database=str(tmp_path / "notes.db"))
        engine = create_engine(url)
        inspector = _inspect(engine)
        assert "accounts" in inspector.get_table_names()


# ===========================================================================
# §16  validate_username unit tests
# ===========================================================================


class TestValidateUsername:
    """[BL B-60] [REQ R13.3]"""

    @pytest.mark.parametrize("name", ["abc", "user123", "my_name", "A" * 32])
    def test_valid_usernames_pass(self, name: str) -> None:
        validate_username(name)  # must not raise

    @pytest.mark.parametrize("name", ["ab", "a" * 33, "bad-name", "bad name", ""])
    def test_invalid_usernames_raise(self, name: str) -> None:
        with pytest.raises(ValueError):
            validate_username(name)

    def test_trailing_newline_rejected(self) -> None:
        """Regression: $ anchor allows trailing \\n; \\Z must be used instead."""
        with pytest.raises(ValueError):
            validate_username("alice\n")

    def test_embedded_newline_rejected(self) -> None:
        with pytest.raises(ValueError):
            validate_username("ali\nce")


# ===========================================================================
# §17  Auth bug regressions
# ===========================================================================


class TestAuthBugRegressions:
    """Regression tests for the three auth bugs fixed post-Sprint 2."""

    def test_register_username_with_trailing_newline_raises(
        self, tmp_path: Path
    ) -> None:
        """Bug fix: validate_username must reject 'alice\\n' (trailing newline)."""
        store = AccountStore(tmp_path)
        with pytest.raises(ValueError):
            store.register("alice\n", "Password1!")

    def test_register_duplicate_via_integrity_error(
        self, tmp_path: Path
    ) -> None:
        """Bug fix: IntegrityError from DB unique constraint → ValueError."""
        from unittest.mock import patch, MagicMock
        from sqlalchemy.exc import IntegrityError as SAIntegrityError
        store = AccountStore(tmp_path)
        store.register("alice", "Password1!")

        # Simulate race: the manual-check query returns None (no existing row),
        # but the subsequent insert hits the unique constraint.
        original_query = store._Session

        class _FakeSession:
            """Context manager that lets the query return None but commit raises."""
            def __init__(self):
                self._real = original_query()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                try:
                    self._real.close()
                except Exception:
                    pass
            def query(self, *a, **kw):
                class _Q:
                    def filter(self, *a, **kw): return self
                    def first(self): return None   # pretend no duplicate found
                return _Q()
            def add(self, row): pass
            def commit(self):
                raise SAIntegrityError("UNIQUE constraint failed", None, None)
            def rollback(self): pass
            def get(self, *a, **kw): return None

        with patch.object(store, "_Session", side_effect=lambda: _FakeSession()):
            with pytest.raises(ValueError, match="already taken"):
                store.register("alice", "Password1!")

    def test_load_deletes_corrupt_session_file(self, tmp_path: Path) -> None:
        """Bug fix: corrupt session file must be removed, not silently ignored."""
        session_file = tmp_path / ".session"
        session_file.write_text("{{invalid json{{", encoding="utf-8")
        result = SessionManager.load(tmp_path)
        assert result is None
        assert not session_file.exists(), "Corrupt session file should be deleted"


# ===========================================================================
# §18  Branch-coverage gap tests
# ===========================================================================


class TestBranchCoverageGaps:
    """Targeted tests for previously-uncovered execution paths.

    Each test maps to a specific missing branch from the coverage report:
      auth.py  : 314->exit, 373-374, 403-404
      notes.py : 103, 326, 372-373, 453-454
    The unreachable for-loop exit branch in _execute_with_retry
    (notes.py:95->exit) is suppressed with # pragma: no branch in source.
    """

    # ------------------------------------------------------------------
    # auth.py:314->exit — AccountStore.delete() row is None (noop branch)
    # ------------------------------------------------------------------

    def test_delete_nonexistent_account_is_noop(self, tmp_path: Path) -> None:
        """delete() with an unknown account_id silently does nothing."""
        store = AccountStore(tmp_path)
        store.delete("00000000-0000-0000-0000-000000000000")  # must not raise
        assert store.get_by_username("nobody") is None

    # ------------------------------------------------------------------
    # auth.py:373-374 — SessionManager.create() os.chmod raises OSError
    # ------------------------------------------------------------------

    def test_create_session_succeeds_when_chmod_raises(
        self, tmp_path: Path
    ) -> None:
        """Session file is written even when os.chmod() raises (best-effort)."""
        with patch("src.core.auth.os.chmod", side_effect=OSError("permission denied")):
            session = SessionManager.create(tmp_path, "uuid-z", "testuser")
        assert (tmp_path / ".session").exists()
        assert session["account_id"] == "uuid-z"

    # ------------------------------------------------------------------
    # auth.py:403-404 — SessionManager.load() corrupt-cleanup unlink raises OSError
    # ------------------------------------------------------------------

    def test_load_corrupt_session_returns_none_when_unlink_fails(
        self, tmp_path: Path
    ) -> None:
        """load() returns None even if the corrupt file cannot be unlinked."""
        session_file = tmp_path / ".session"
        session_file.write_text("{bad json", encoding="utf-8")
        with patch.object(Path, "unlink", side_effect=OSError("read-only fs")):
            result = SessionManager.load(tmp_path)
        assert result is None

    # ------------------------------------------------------------------
    # notes.py:103 — DiskFullError from SQLite "disk i/o error" OperationalError
    # ------------------------------------------------------------------

    def test_sqlite_disk_io_error_raises_disk_full_error(self) -> None:
        """_execute_with_retry converts 'disk I/O error' OperationalError to DiskFullError."""
        from sqlalchemy.exc import OperationalError as SAOp
        from src.core.notes import _execute_with_retry

        def _bad():
            raise SAOp("disk I/O error", params=None, orig=None)

        with pytest.raises(DiskFullError):
            _execute_with_retry(_bad)

    def test_sqlite_disk_full_msg_raises_disk_full_error(self) -> None:
        """_execute_with_retry converts 'disk full' OperationalError to DiskFullError."""
        from sqlalchemy.exc import OperationalError as SAOp
        from src.core.notes import _execute_with_retry

        def _bad():
            raise SAOp("disk full", params=None, orig=None)

        with pytest.raises(DiskFullError):
            _execute_with_retry(_bad)

    # ------------------------------------------------------------------
    # notes.py:326 — non-ENOSPC OSError on write_bytes is re-raised unchanged
    # ------------------------------------------------------------------

    def test_add_large_encrypted_non_enospc_oserror_propagates(
        self, tmp_path: Path
    ) -> None:
        """An OSError that is NOT ENOSPC on write_bytes is re-raised, not
        wrapped in DiskFullError."""
        import errno as _errno
        store = DatabaseStore(tmp_path)
        blob = _make_large_encrypted_blob(6)
        note = Note.create("[Encrypted Note]", "", encrypted=True, blob=blob)

        with patch.object(Path, "write_bytes",
                          side_effect=OSError(_errno.EIO, "I/O error")):
            with pytest.raises(OSError) as exc_info:
                store.add(note)
        assert not isinstance(exc_info.value, DiskFullError)

    # ------------------------------------------------------------------
    # notes.py:372-373 — get() when filesystem payload file is missing
    # ------------------------------------------------------------------

    def test_get_filesystem_note_missing_payload_returns_note_with_none_blob(
        self, tmp_path: Path
    ) -> None:
        """If the payload file is gone, get() returns the Note with blob=None."""
        store = DatabaseStore(tmp_path)
        blob = _make_large_encrypted_blob(6)
        note = Note.create("[Encrypted Note]", "", encrypted=True, blob=blob)
        store.add(note)
        (tmp_path / "files" / f"{note.id}.bin").unlink()

        retrieved = store.get(note.id)
        assert retrieved is not None
        assert retrieved.blob is None  # missing file → blob stays None

    # ------------------------------------------------------------------
    # notes.py:453-454 — delete() when payload file is already gone
    # ------------------------------------------------------------------

    def test_delete_filesystem_note_tolerates_already_removed_payload(
        self, tmp_path: Path
    ) -> None:
        """delete() must not raise if the payload file was already removed.
        [BL B-68] — idempotent clean-up."""
        store = DatabaseStore(tmp_path)
        blob = _make_large_encrypted_blob(6)
        note = Note.create("[Encrypted Note]", "", encrypted=True, blob=blob)
        store.add(note)
        (tmp_path / "files" / f"{note.id}.bin").unlink()

        store.delete(note.id)  # must not raise FileNotFoundError
        assert store.get(note.id) is None
