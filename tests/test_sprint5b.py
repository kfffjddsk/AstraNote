"""Sprint 5B test suite — Desktop sync UI + Google OAuth PKCE.

Coverage:
  §1  TestMergeWindow               — conflict-resolution dialog    [BL B-86, B-89]
  §2  TestSyncWorkerPush            — SyncWorker push cycle         [BL B-89, B-90]
  §3  TestSyncWorkerPull            — SyncWorker pull cycle         [BL B-89, B-90]
  §4  TestSyncWorkerBoth            — SyncWorker both directions    [BL B-89, B-90]
  §5  TestOAuthCallbackEndpoint     — POST /auth/callback server    [BL B-87]
  §6  TestSyncClientCallbackExchange — SyncClient.callback_exchange [BL B-87]
  §7  TestEmailToUsername           — _email_to_username helper     [BL B-87]
  §8  TestGetOrCreateOAuthAccount   — AccountStore OAuth upsert     [BL B-87]
  §9  TestMainWindowSyncUI          — sync toolbar, menu, status    [BL B-89, B-90]

Target: ≥ 35 new tests.

Refs: [BL B-86, B-87, B-89, B-90] [REQ R13.14, R16.1, R16.2, R16.3]
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Qt availability guard  (mirrors test_sprint4b.py pattern)
# ---------------------------------------------------------------------------

try:
    from PySide6.QtWidgets import QApplication, QDialog
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

_qt = pytest.mark.skipif(not _QT_AVAILABLE, reason="PySide6 not available")

_app: object = None


def _ensure_app():
    global _app
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if _app is None:
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication([])
    return _app


# ---------------------------------------------------------------------------
# Server fixtures  (reused from test_sprint5a.py pattern)
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient

from src.core.auth import AccountStore
from src.core.notes import DatabaseStore, Note
from src.core.sync_client import SyncClient, SyncError, AuthenticationError
from src.server.app import create_app
from src.server.settings import ServerSettings


@pytest.fixture
def server_settings(tmp_path: Path) -> ServerSettings:
    db_path = tmp_path / "sync_server.db"
    return ServerSettings(
        database_url=f"sqlite:///{db_path.as_posix()}",
        jwt_secret="sprint5b-test-secret",
        jwt_algorithm="HS256",
        jwt_expiry_hours=24,
        data_dir=tmp_path / "server_data",
    )


@pytest.fixture
def oauth_settings(tmp_path: Path) -> ServerSettings:
    """Settings with Google OAuth enabled."""
    db_path = tmp_path / "sync_oauth.db"
    return ServerSettings(
        database_url=f"sqlite:///{db_path.as_posix()}",
        jwt_secret="sprint5b-oauth-secret",
        jwt_algorithm="HS256",
        jwt_expiry_hours=24,
        data_dir=tmp_path / "server_oauth_data",
        google_client_id="test-google-client-id",
        google_client_secret="test-google-client-secret",
    )


@pytest.fixture
def app(server_settings: ServerSettings):
    return create_app(server_settings)


@pytest.fixture
def oauth_app(oauth_settings: ServerSettings):
    return create_app(oauth_settings)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def oauth_client(oauth_app) -> Iterator[TestClient]:
    with TestClient(oauth_app) as c:
        yield c


def _make_id_token(sub: str, email: str) -> str:
    """Build a minimal (unsigned) JWT id_token for tests."""
    claims = {"sub": sub, "email": email}
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(claims).encode())
        .rstrip(b"=")
        .decode()
    )
    return f"header.{payload_b64}.sig"


# ---------------------------------------------------------------------------
# §1  TestMergeWindow  [BL B-86, B-89]
# ---------------------------------------------------------------------------


@_qt
class TestMergeWindow:
    """§1 — MergeWindow two-pane conflict dialog."""

    def _make_dlg(self, local_content="local text", remote_content="remote text",
                  title="My Note", note_id="note-001", remote_modified_at="2026-01-02T00:00:00"):
        _ensure_app()
        from src.desktop.merge_window import MergeWindow
        local = {"id": note_id, "title": title, "content": local_content}
        remote = {"content": remote_content, "modified_at": remote_modified_at}
        return MergeWindow(local_note=local, remote_note=remote)

    def test_window_title_contains_note_title(self):
        """§1.1 Window title includes the note title."""
        dlg = self._make_dlg(title="Sprint Test Note")
        assert "Sprint Test Note" in dlg.windowTitle()

    def test_resolved_content_returns_remote_pane_text(self):
        """§1.2 resolved_content() returns the right-pane (remote) text."""
        dlg = self._make_dlg(remote_content="server version")
        assert dlg.resolved_content() == "server version"

    def test_use_local_copies_local_to_right_pane(self):
        """§1.3 '← Use Local' button overwrites the right pane with local text."""
        dlg = self._make_dlg(local_content="my local edits", remote_content="server text")
        dlg._on_use_local()
        assert dlg.resolved_content() == "my local edits"

    def test_local_id_exposed(self):
        """§1.4 local_id property returns the note id from local_note."""
        dlg = self._make_dlg(note_id="test-note-xyz")
        assert dlg.local_id == "test-note-xyz"

    def test_remote_modified_at_exposed(self):
        """§1.5 remote_modified_at returns modified_at from remote_note."""
        ts = "2026-06-01T12:00:00+00:00"
        dlg = self._make_dlg(remote_modified_at=ts)
        assert dlg.remote_modified_at == ts


# ---------------------------------------------------------------------------
# §2  TestSyncWorkerPush  [BL B-89, B-90]
# ---------------------------------------------------------------------------


def _make_worker(store, client_mock, direction="push"):
    """Create a SyncWorker with a mock SyncClient."""
    _ensure_app()
    from src.desktop.sync_worker import SyncWorker
    return SyncWorker(
        client=client_mock,
        token="test-token",
        account_id="acct-001",
        store=store,
        direction=direction,
    )


def _run_and_collect(worker):
    """Call worker.run() synchronously and collect all emitted signals."""
    results: dict[str, list] = {
        "finished": [], "failed": [], "conflicts": [], "progress": []
    }
    worker.finished_ok.connect(lambda d: results["finished"].append(d))
    worker.failed.connect(lambda c, m: results["failed"].append((c, m)))
    worker.conflict_detected.connect(lambda lst: results["conflicts"].append(lst))
    worker.progress.connect(lambda m: results["progress"].append(m))
    worker.run()
    return results


@_qt
class TestSyncWorkerPush:
    """§2 — SyncWorker push cycle."""

    def test_push_marks_synced_for_accepted_notes(self, tmp_path: Path):
        """§2.1 Accepted notes are stamped with synced_at after push."""
        store = DatabaseStore(tmp_path)
        note = Note.create("Test", "body")
        note_id = store.add(note, account_id="acct-001")

        client_mock = MagicMock()
        client_mock.push.return_value = {
            "accepted": [{"id": note_id, "synced_at": "2026-06-01T00:00:00"}],
            "skipped": [],
            "server_time": "2026-06-01T00:00:00",
        }

        worker = _make_worker(store, client_mock, direction="push")
        results = _run_and_collect(worker)

        assert len(results["finished"]) == 1
        assert results["finished"][0]["pushed"] == 1
        client_mock.push.assert_called_once()

    def test_push_skips_when_nothing_pending(self, tmp_path: Path):
        """§2.2 Push emits finished_ok with pushed=0 if nothing is pending."""
        store = DatabaseStore(tmp_path)
        # No notes added
        client_mock = MagicMock()

        worker = _make_worker(store, client_mock, direction="push")
        results = _run_and_collect(worker)

        assert results["finished"][0]["pushed"] == 0
        client_mock.push.assert_not_called()

    def test_push_sync_error_emits_failed_signal(self, tmp_path: Path):
        """§2.3 A SyncError from the server emits the failed signal."""
        store = DatabaseStore(tmp_path)
        note = Note.create("Test", "body")
        store.add(note, account_id="acct-001")

        client_mock = MagicMock()
        client_mock.push.side_effect = SyncError(500, "server down")

        worker = _make_worker(store, client_mock, direction="push")
        results = _run_and_collect(worker)

        assert len(results["failed"]) == 1
        assert "server down" in results["failed"][0][1]
        assert len(results["finished"]) == 1  # finished_ok still emitted

    def test_push_auth_error_emits_failed_with_class_name(self, tmp_path: Path):
        """§2.4 AuthenticationError emits failed with class name in payload."""
        store = DatabaseStore(tmp_path)
        note = Note.create("Test", "body")
        store.add(note, account_id="acct-001")

        client_mock = MagicMock()
        client_mock.push.side_effect = AuthenticationError(401, "token expired")

        worker = _make_worker(store, client_mock, direction="push")
        results = _run_and_collect(worker)

        assert len(results["failed"]) == 1
        err_class, _msg = results["failed"][0]
        assert err_class == "AuthenticationError"


# ---------------------------------------------------------------------------
# §3  TestSyncWorkerPull  [BL B-89, B-90]
# ---------------------------------------------------------------------------


@_qt
class TestSyncWorkerPull:
    """§3 — SyncWorker pull cycle."""

    def test_pull_upserts_new_remote_note(self, tmp_path: Path):
        """§3.1 A remote note not in local DB is upserted."""
        store = DatabaseStore(tmp_path)
        now = datetime.now(timezone.utc).isoformat()
        remote_id = "remote-note-001"

        client_mock = MagicMock()
        client_mock.pull.return_value = {
            "notes": [{
                "id": remote_id,
                "title": "Remote Note",
                "content": "from server",
                "is_encrypted": False,
                "blob": None,
                "created_at": now,
                "modified_at": now,
                "synced_at": now,
            }]
        }

        worker = _make_worker(store, client_mock, direction="pull")
        results = _run_and_collect(worker)

        assert results["finished"][0]["pulled"] == 1
        assert store.get(remote_id) is not None

    def test_pull_last_write_wins_when_no_local_edits(self, tmp_path: Path):
        """§3.2 Remote update accepted when local note has no unsynced edits.

        We use upsert_remote to create the note so modified_at == synced_at
        (i.e. it was cleanly synced at old_ts with no subsequent local edits).
        """
        store = DatabaseStore(tmp_path)
        old_ts = "2026-01-01T00:00:00+00:00"
        new_ts = "2026-06-01T00:00:00+00:00"
        note_id = "note-lww-001"

        # Create note already fully synced at old_ts (no pending local edits)
        store.upsert_remote(
            note_id=note_id,
            account_id="acct-001",
            title="Original",
            content="old body",
            is_encrypted=False,
            blob=None,
            created_at=old_ts,
            modified_at=old_ts,
            synced_at=old_ts,
        )

        client_mock = MagicMock()
        client_mock.pull.return_value = {
            "notes": [{
                "id": note_id,
                "title": "Original",
                "content": "updated body",
                "is_encrypted": False,
                "blob": None,
                "created_at": old_ts,
                "modified_at": new_ts,
                "synced_at": new_ts,
            }]
        }

        worker = _make_worker(store, client_mock, direction="pull")
        results = _run_and_collect(worker)

        assert results["finished"][0]["pulled"] == 1
        refreshed = store.get(note_id)
        assert refreshed is not None
        assert refreshed.content == "updated body"

    def test_pull_conflict_detected_when_both_sides_changed(self, tmp_path: Path):
        """§3.3 conflict_detected signal emitted when local and remote both changed."""
        store = DatabaseStore(tmp_path)
        synced_ts = "2026-01-01T00:00:00+00:00"
        local_mod_ts = "2026-03-01T00:00:00+00:00"
        remote_mod_ts = "2026-06-01T00:00:00+00:00"

        note = Note.create("Conflict Note", "local edits")
        note_id = store.add(note, account_id="acct-001")
        store.mark_synced(note_id, synced_ts)
        # Simulate local edit after syncing
        store.update(note_id, title="Conflict Note", content="local edits newer")

        client_mock = MagicMock()
        client_mock.pull.return_value = {
            "notes": [{
                "id": note_id,
                "title": "Conflict Note",
                "content": "remote edits",
                "is_encrypted": False,
                "blob": None,
                "created_at": synced_ts,
                "modified_at": remote_mod_ts,
                "synced_at": remote_mod_ts,
            }]
        }

        worker = _make_worker(store, client_mock, direction="pull")
        results = _run_and_collect(worker)

        assert len(results["conflicts"]) == 1
        assert len(results["conflicts"][0]) == 1
        assert results["conflicts"][0][0]["note_id"] == note_id

    def test_pull_empty_returns_zero_pulled(self, tmp_path: Path):
        """§3.4 Empty notes list from server results in pulled=0."""
        store = DatabaseStore(tmp_path)
        client_mock = MagicMock()
        client_mock.pull.return_value = {"notes": []}

        worker = _make_worker(store, client_mock, direction="pull")
        results = _run_and_collect(worker)

        assert results["finished"][0]["pulled"] == 0

    def test_pull_sync_error_emits_failed(self, tmp_path: Path):
        """§3.5 SyncError during pull emits the failed signal."""
        store = DatabaseStore(tmp_path)
        client_mock = MagicMock()
        client_mock.pull.side_effect = SyncError(503, "service unavailable")

        worker = _make_worker(store, client_mock, direction="pull")
        results = _run_and_collect(worker)

        assert len(results["failed"]) == 1
        assert "service unavailable" in results["failed"][0][1]


# ---------------------------------------------------------------------------
# §4  TestSyncWorkerBoth  [BL B-89, B-90]
# ---------------------------------------------------------------------------


@_qt
class TestSyncWorkerBoth:
    """§4 — SyncWorker both push+pull direction."""

    def test_both_runs_push_then_pull(self, tmp_path: Path):
        """§4.1 'both' direction calls push when pending notes exist, then pull."""
        store = DatabaseStore(tmp_path)
        # Add a note so push has something to send
        note = Note.create("Sync Me", "body to push")
        store.add(note, account_id="acct-001")

        client_mock = MagicMock()
        client_mock.push.return_value = {"accepted": [], "skipped": [], "server_time": ""}
        client_mock.pull.return_value = {"notes": []}

        worker = _make_worker(store, client_mock, direction="both")
        results = _run_and_collect(worker)

        assert len(results["finished"]) == 1
        client_mock.push.assert_called_once()
        client_mock.pull.assert_called_once()

    def test_both_emits_finished_ok_even_after_push_error(self, tmp_path: Path):
        """§4.2 finished_ok is always emitted even when push raises SyncError."""
        store = DatabaseStore(tmp_path)
        note = Note.create("Push fail", "body")
        store.add(note, account_id="acct-001")

        client_mock = MagicMock()
        client_mock.push.side_effect = SyncError(500, "push fail")

        worker = _make_worker(store, client_mock, direction="both")
        results = _run_and_collect(worker)

        assert len(results["finished"]) == 1
        assert len(results["failed"]) == 1


# ---------------------------------------------------------------------------
# §5  TestOAuthCallbackEndpoint  [BL B-87]
# ---------------------------------------------------------------------------

import src.server.routers.auth as _auth_mod


@pytest.fixture
def fake_exchange_fn():
    """Monkeypatchable stand-in for _exchange_oauth_code."""
    def _exchange(settings: Any, payload: Any) -> dict:
        return {"id_token": _make_id_token("google-sub-001", "user@example.com")}
    return _exchange


class TestOAuthCallbackEndpoint:
    """§5 — POST /auth/callback server endpoint."""

    def test_callback_without_client_id_returns_501(self, client: TestClient):
        """§5.1 501 when GOOGLE_CLIENT_ID is not configured."""
        r = client.post("/auth/callback", json={
            "code": "some-code",
            "code_verifier": "a" * 43,
            "redirect_uri": "http://127.0.0.1:9999/",
        })
        assert r.status_code == 501

    def test_callback_happy_path_returns_token(
        self, monkeypatch, oauth_client: TestClient, fake_exchange_fn
    ):
        """§5.2 Valid exchange returns a LoginResponse with access_token."""
        monkeypatch.setattr(_auth_mod, "_exchange_oauth_code", fake_exchange_fn)
        r = oauth_client.post("/auth/callback", json={
            "code": "google-auth-code",
            "code_verifier": "b" * 43,
            "redirect_uri": "http://127.0.0.1:9999/",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["username"]

    def test_callback_creates_account_from_email(
        self, monkeypatch, oauth_app, oauth_client: TestClient, fake_exchange_fn
    ):
        """§5.3 A new account is created for the Google email on first sign-in."""
        monkeypatch.setattr(_auth_mod, "_exchange_oauth_code", fake_exchange_fn)
        r = oauth_client.post("/auth/callback", json={
            "code": "gc-1",
            "code_verifier": "c" * 43,
            "redirect_uri": "http://127.0.0.1:9999/",
        })
        assert r.status_code == 200
        username = r.json()["username"]
        store: AccountStore = oauth_app.state.account_store
        assert store.get_by_username(username) is not None

    def test_callback_reuses_existing_account(
        self, monkeypatch, oauth_client: TestClient, fake_exchange_fn
    ):
        """§5.4 A second sign-in with the same email reuses the same account."""
        monkeypatch.setattr(_auth_mod, "_exchange_oauth_code", fake_exchange_fn)
        payload = {
            "code": "gc-reuse",
            "code_verifier": "d" * 43,
            "redirect_uri": "http://127.0.0.1:9999/",
        }
        r1 = oauth_client.post("/auth/callback", json=payload)
        r2 = oauth_client.post("/auth/callback", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["account_id"] == r2.json()["account_id"]

    def test_callback_bad_exchange_returns_400(
        self, monkeypatch, oauth_client: TestClient
    ):
        """§5.5 Bad code → exchange raises → 400 returned."""
        from fastapi import HTTPException
        def bad_exchange(settings, payload):
            raise HTTPException(status_code=400, detail="invalid_grant")
        monkeypatch.setattr(_auth_mod, "_exchange_oauth_code", bad_exchange)
        r = oauth_client.post("/auth/callback", json={
            "code": "bad",
            "code_verifier": "e" * 43,
            "redirect_uri": "http://127.0.0.1:9999/",
        })
        assert r.status_code == 400

    def test_callback_missing_id_token_returns_400(
        self, monkeypatch, oauth_client: TestClient
    ):
        """§5.6 Exchange response missing id_token returns 400."""
        monkeypatch.setattr(
            _auth_mod, "_exchange_oauth_code",
            lambda s, p: {"access_token": "only-access"},
        )
        r = oauth_client.post("/auth/callback", json={
            "code": "no-id-token",
            "code_verifier": "f" * 43,
            "redirect_uri": "http://127.0.0.1:9999/",
        })
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# §6  TestSyncClientCallbackExchange  [BL B-87]
# ---------------------------------------------------------------------------


class TestSyncClientCallbackExchange:
    """§6 — SyncClient.callback_exchange() method."""

    def test_callback_exchange_happy_path(
        self, monkeypatch, oauth_app, fake_exchange_fn
    ):
        """§6.1 Returns a dict with access_token on success."""
        monkeypatch.setattr(_auth_mod, "_exchange_oauth_code", fake_exchange_fn)
        # TestClient extends httpx.Client — pass it directly to SyncClient
        with TestClient(oauth_app) as tc:
            sc = SyncClient(client=tc)
            result = sc.callback_exchange(
                code="code-x",
                code_verifier="g" * 43,
                redirect_uri="http://127.0.0.1:9000/",
            )
        assert "access_token" in result

    def test_callback_exchange_non_2xx_raises_sync_error(
        self, monkeypatch, oauth_app
    ):
        """§6.2 A 400 from /auth/callback raises SyncError."""
        from fastapi import HTTPException

        def bad_exchange(settings, payload):
            raise HTTPException(status_code=400, detail="bad code")

        monkeypatch.setattr(_auth_mod, "_exchange_oauth_code", bad_exchange)
        with TestClient(oauth_app) as tc:
            sc = SyncClient(client=tc)
            with pytest.raises(SyncError):
                sc.callback_exchange(
                    code="bad",
                    code_verifier="h" * 43,
                    redirect_uri="http://127.0.0.1:9000/",
                )

    def test_callback_exchange_network_error_raises_sync_error(self):
        """§6.3 Network error during exchange raises SyncError."""
        import httpx

        class _FailTransport(httpx.BaseTransport):
            def handle_request(self, request):
                raise httpx.ConnectError("refused")

        http_client = httpx.Client(transport=_FailTransport(), base_url="http://badhost/")
        sc = SyncClient(client=http_client)
        with pytest.raises(SyncError):
            sc.callback_exchange(
                code="c",
                code_verifier="i" * 43,
                redirect_uri="http://127.0.0.1:9999/",
            )


# ---------------------------------------------------------------------------
# §7  TestEmailToUsername  [BL B-87]
# ---------------------------------------------------------------------------


class TestEmailToUsername:
    """§7 — _email_to_username helper."""

    def setup_method(self):
        from src.core.auth import _email_to_username
        self.fn = _email_to_username

    def test_normal_email_strips_domain(self):
        """§7.1 Plain email returns the local part."""
        assert self.fn("alice@example.com") == "alice"

    def test_dots_replaced_with_underscores(self):
        """§7.2 Dots in local part become underscores."""
        result = self.fn("john.doe@example.com")
        assert "." not in result
        assert result == "john_doe"

    def test_short_local_part_padded(self):
        """§7.3 A local part shorter than 3 chars is padded with u_ prefix."""
        result = self.fn("ab@example.com")
        assert len(result) >= 3

    def test_no_at_sign_uses_whole_string(self):
        """§7.4 Input without @ is treated as a username directly."""
        result = self.fn("plainstring")
        assert result == "plainstring"


# ---------------------------------------------------------------------------
# §8  TestGetOrCreateOAuthAccount  [BL B-87]
# ---------------------------------------------------------------------------


class TestGetOrCreateOAuthAccount:
    """§8 — AccountStore.get_or_create_oauth_account()."""

    def test_new_account_created_from_email(self, tmp_path: Path):
        """§8.1 A new account is created for a fresh email."""
        store = AccountStore(tmp_path)
        result = store.get_or_create_oauth_account(
            email="newuser@example.com", oauth_sub="sub-abc"
        )
        assert result["account_id"]
        assert result["username"] == "newuser"

    def test_existing_account_returned_on_second_call(self, tmp_path: Path):
        """§8.2 Calling twice with the same email returns the same account."""
        store = AccountStore(tmp_path)
        r1 = store.get_or_create_oauth_account(email="repeat@example.com", oauth_sub="s1")
        r2 = store.get_or_create_oauth_account(email="repeat@example.com", oauth_sub="s1")
        assert r1["account_id"] == r2["account_id"]

    def test_oauth_account_username_matches_email_local_part(self, tmp_path: Path):
        """§8.3 The derived username uses the email local part (sanitised)."""
        store = AccountStore(tmp_path)
        result = store.get_or_create_oauth_account(
            email="some.user@corp.example.com", oauth_sub="sub-qrs"
        )
        # Dots replaced with underscores; domain stripped
        assert "some_user" in result["username"]
        assert result["account_id"]


# ---------------------------------------------------------------------------
# §9  TestMainWindowSyncUI  [BL B-89, B-90]
# ---------------------------------------------------------------------------


def _make_window_with_sync(tmp_path: Path, sync_url: str = "http://localhost:8000"):
    """Create a test MainWindow with sync_url wired."""
    _ensure_app()
    from src.core.config import ConfigStore
    from src.core.plugin_base import PluginRegistry
    from src.desktop.main_window import MainWindow
    store = DatabaseStore(tmp_path)
    config = ConfigStore(config_path=tmp_path / "config.json")
    registry = PluginRegistry()
    return MainWindow(
        store=store, config=config, registry=registry,
        data_dir=tmp_path, sync_url=sync_url
    ), store, config


@_qt
class TestMainWindowSyncUI:
    """§9 — MainWindow sync toolbar, menu, and status label."""

    def test_sync_now_action_exists_in_window(self, tmp_path: Path):
        """§9.1 MainWindow has _action_sync_now after construction."""
        win, _, _ = _make_window_with_sync(tmp_path)
        assert hasattr(win, "_action_sync_now")

    def test_sync_now_action_shortcut_is_ctrl_shift_s(self, tmp_path: Path):
        """§9.2 Sync Now shortcut is Ctrl+Shift+S."""
        win, _, _ = _make_window_with_sync(tmp_path)
        assert "Ctrl+Shift+S" in win._action_sync_now.shortcut().toString()

    def test_sync_signin_and_signout_actions_exist(self, tmp_path: Path):
        """§9.3 Sign In and Sign Out actions are both present."""
        win, _, _ = _make_window_with_sync(tmp_path)
        assert hasattr(win, "_action_sync_signin")
        assert hasattr(win, "_action_sync_signout")

    def test_status_sync_label_starts_as_not_signed_in(self, tmp_path: Path):
        """§9.4 Sync status label shows 'Not signed in' on startup."""
        win, _, _ = _make_window_with_sync(tmp_path)
        assert "Not signed in" in win._status_sync_label.text()

    def test_on_sync_shows_info_when_no_url_configured(self, tmp_path: Path):
        """§9.5 _on_sync() shows info dialog when sync_url is empty."""
        win, _, _ = _make_window_with_sync(tmp_path, sync_url="")
        with patch("src.desktop.main_window.QMessageBox.information") as mock_info:
            win._on_sync()
            mock_info.assert_called_once()

    def test_on_sync_logout_clears_status_to_not_signed_in(self, tmp_path: Path):
        """§9.6 _on_sync_logout() resets status label to 'Not signed in'."""
        win, _, _ = _make_window_with_sync(tmp_path)
        win._status_sync_label.setText("⬤ Synced")
        win._on_sync_logout()
        assert "Not signed in" in win._status_sync_label.text()
