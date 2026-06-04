"""Sprint 5A.1 — sync server MVP tests.

Covers:
* App factory + /healthz smoke
* POST /auth/login: success, bad password, unknown user, locked, validation
* JWT middleware: missing / malformed / bogus / expired / valid bearer tokens
* POST /sync/push: auth, multi-upsert, last-write-wins, spoof prevention
* GET /sync/pull: auth, full list, since watermark, empty inbox
* B-94 cross-account isolation
* SyncClient + token cache round-trip
* CLI sync push / pull / logout against a TestClient-backed httpx transport
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

import httpx
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from src.cli import cli as cli_app
from src.core import sync_client as sync_client_mod
from src.core.auth import AccountStore
from src.core.notes import DatabaseStore
from src.core.sync_client import (
    AccountLockedError,
    AuthenticationError,
    SyncClient,
    SyncError,
    delete_cached_token,
    load_cached_token,
    save_cached_token,
)
from src.server.app import create_app
from src.server.routers.sync import _utcnow_iso
from src.server.security import (
    AccountClaims,
    TokenExpired,
    TokenInvalid,
    issue_token,
    verify_token,
)
from src.server.settings import ServerSettings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server_settings(tmp_path: Path) -> ServerSettings:
    """Per-test ServerSettings backed by a temp directory + isolated SQLite."""
    db_path = tmp_path / "sync_server.db"
    return ServerSettings(
        database_url=f"sqlite:///{db_path.as_posix()}",
        jwt_secret="unit-test-secret",
        jwt_algorithm="HS256",
        jwt_expiry_hours=24,
        data_dir=tmp_path / "server_data",
    )


@pytest.fixture
def app(server_settings: ServerSettings):
    """Fresh FastAPI app per test (isolated SQLite + AccountStore)."""
    return create_app(server_settings)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    """FastAPI TestClient bound to the per-test app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def alice_credentials(app) -> tuple[str, str, str]:
    """Register a default user 'alice' / 'CorrectHorse9!' and return triple."""
    store: AccountStore = app.state.account_store
    aid = store.register("alice", "CorrectHorse9!")
    return ("alice", "CorrectHorse9!", aid)


@pytest.fixture
def bob_credentials(app) -> tuple[str, str, str]:
    store: AccountStore = app.state.account_store
    aid = store.register("bob", "TrombonePencil9!")
    return ("bob", "TrombonePencil9!", aid)


@pytest.fixture
def alice_token(client: TestClient, alice_credentials) -> str:
    username, password, _aid = alice_credentials
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def bob_token(client: TestClient, bob_credentials) -> str:
    username, password, _aid = bob_credentials
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _note_payload(
    *,
    note_id: str,
    title: str,
    content: Optional[str] = "hello",
    is_encrypted: bool = False,
    blob: Optional[bytes] = None,
    created_at: Optional[str] = None,
    modified_at: Optional[str] = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": note_id,
        "title": title,
        "content": content,
        "is_encrypted": is_encrypted,
        "encrypted_blob_b64": (
            base64.b64encode(blob).decode("ascii") if blob else None
        ),
        "created_at": created_at or now,
        "modified_at": modified_at or now,
    }


# ---------------------------------------------------------------------------
# App factory + /healthz smoke
# ---------------------------------------------------------------------------


class TestAppFactory:
    def test_create_app_returns_fastapi(self, app) -> None:
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)

    def test_healthz_returns_ok(self, client: TestClient) -> None:
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_state_carries_settings_and_factory(self, app) -> None:
        assert hasattr(app.state, "settings")
        assert hasattr(app.state, "session_factory")
        assert hasattr(app.state, "account_store")


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


class TestAuthLogin:
    def test_login_success_returns_token(
        self, client: TestClient, alice_credentials
    ) -> None:
        u, p, aid = alice_credentials
        r = client.post("/auth/login", json={"username": u, "password": p})
        assert r.status_code == 200
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["account_id"] == aid
        assert body["username"] == u
        assert body["access_token"]

    def test_login_bad_password_returns_401(
        self, client: TestClient, alice_credentials
    ) -> None:
        u, _p, _ = alice_credentials
        r = client.post(
            "/auth/login", json={"username": u, "password": "WrongPass1!"}
        )
        assert r.status_code == 401
        body = r.json()
        assert body["status"] == "error"
        assert body["error"] == "unauthorized"

    def test_login_unknown_user_returns_401_same_message(
        self, client: TestClient, alice_credentials
    ) -> None:
        # Don't even need alice; the parametrized fixture just sets up the store.
        _ = alice_credentials
        r = client.post(
            "/auth/login", json={"username": "ghost", "password": "Whatever1!"}
        )
        assert r.status_code == 401
        # Same envelope code so attackers cannot distinguish from bad password.
        assert r.json()["error"] == "unauthorized"

    def test_login_validation_error_returns_envelope(
        self, client: TestClient
    ) -> None:
        r = client.post("/auth/login", json={"username": ""})
        assert r.status_code == 422
        body = r.json()
        assert body["status"] == "error"
        assert body["error"] == "validation_error"

    def test_login_locked_account_returns_423(
        self, app, client: TestClient, alice_credentials
    ) -> None:
        u, _p, _ = alice_credentials
        # Trigger lockout by repeated bad attempts.  AccountStore default policy
        # is 5 failures -> 15-minute lockout (see src/core/auth.py).
        for _ in range(6):
            client.post(
                "/auth/login", json={"username": u, "password": "WrongPass1!"}
            )
        r = client.post(
            "/auth/login", json={"username": u, "password": "WrongPass1!"}
        )
        assert r.status_code == 423
        assert r.json()["error"] == "locked"


# ---------------------------------------------------------------------------
# JWT middleware
# ---------------------------------------------------------------------------


class TestJwtMiddleware:
    def test_missing_authorization_header_returns_401(
        self, client: TestClient
    ) -> None:
        r = client.get("/sync/pull")
        assert r.status_code == 401
        assert r.json()["error"] == "unauthorized"

    def test_malformed_authorization_header_returns_401(
        self, client: TestClient
    ) -> None:
        r = client.get("/sync/pull", headers={"Authorization": "NotBearer xyz"})
        assert r.status_code == 401

    def test_bearer_with_garbage_token_returns_401(
        self, client: TestClient
    ) -> None:
        r = client.get("/sync/pull", headers={"Authorization": "Bearer garbage"})
        assert r.status_code == 401

    def test_expired_token_returns_401(
        self, app, client: TestClient, alice_credentials
    ) -> None:
        _, _, aid = alice_credentials
        settings: ServerSettings = app.state.settings
        # Manually craft a token with iat/exp in the past.
        past = datetime.now(timezone.utc) - timedelta(hours=settings.jwt_expiry_hours + 2)
        token, _exp = issue_token(
            settings,
            account_id=aid,
            username="alice",
            issued_at=past,
        )
        r = client.get(
            "/sync/pull", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 401

    def test_valid_token_passes_to_pull(
        self, client: TestClient, alice_token: str
    ) -> None:
        r = client.get(
            "/sync/pull", headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert r.status_code == 200
        assert r.json()["notes"] == []

    def test_verify_token_roundtrip(
        self, server_settings, alice_credentials
    ) -> None:
        _, _, aid = alice_credentials
        token, _exp = issue_token(
            server_settings, account_id=aid, username="alice"
        )
        claims: AccountClaims = verify_token(server_settings, token)
        assert claims.account_id == aid
        assert claims.username == "alice"

    def test_verify_token_expired_raises(self, server_settings) -> None:
        past = datetime.now(timezone.utc) - timedelta(hours=48)
        token, _exp = issue_token(
            server_settings, account_id="abc", username="x", issued_at=past
        )
        with pytest.raises(TokenExpired):
            verify_token(server_settings, token)

    def test_verify_token_bad_signature_raises(self, server_settings) -> None:
        token, _exp = issue_token(
            server_settings, account_id="abc", username="x"
        )
        # Tamper with the secret.
        bad = ServerSettings(
            database_url=server_settings.database_url,
            jwt_secret="different-secret",
            jwt_algorithm="HS256",
            jwt_expiry_hours=24,
            data_dir=server_settings.data_dir,
        )
        with pytest.raises(TokenInvalid):
            verify_token(bad, token)


# ---------------------------------------------------------------------------
# POST /sync/push
# ---------------------------------------------------------------------------


class TestSyncPush:
    def test_push_unauthenticated_returns_401(self, client: TestClient) -> None:
        r = client.post("/sync/push", json={"notes": []})
        assert r.status_code == 401

    def test_push_two_notes_accepts_both(
        self, client: TestClient, alice_token: str
    ) -> None:
        notes = [
            _note_payload(note_id="n1", title="One"),
            _note_payload(note_id="n2", title="Two"),
        ]
        r = client.post(
            "/sync/push",
            json={"notes": notes},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["accepted"] == 2
        assert body["skipped"] == 0
        assert body["server_time"]

    def test_push_empty_list_returns_zero_counts(
        self, client: TestClient, alice_token: str
    ) -> None:
        r = client.post(
            "/sync/push",
            json={"notes": []},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert r.status_code == 200
        assert r.json()["accepted"] == 0

    def test_push_overwrites_when_modified_at_newer(
        self, client: TestClient, alice_token: str
    ) -> None:
        old = _note_payload(
            note_id="n1",
            title="Old",
            modified_at="2026-01-01T00:00:00+00:00",
        )
        client.post(
            "/sync/push",
            json={"notes": [old]},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        new = _note_payload(
            note_id="n1",
            title="New",
            modified_at="2026-06-01T00:00:00+00:00",
        )
        r = client.post(
            "/sync/push",
            json={"notes": [new]},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert r.json()["accepted"] == 1
        assert r.json()["skipped"] == 0

        # Confirm via pull
        pulled = client.get(
            "/sync/pull", headers={"Authorization": f"Bearer {alice_token}"}
        ).json()["notes"]
        assert pulled[0]["title"] == "New"

    def test_push_skips_when_modified_at_older(
        self, client: TestClient, alice_token: str
    ) -> None:
        new = _note_payload(
            note_id="n1",
            title="New",
            modified_at="2026-06-01T00:00:00+00:00",
        )
        client.post(
            "/sync/push",
            json={"notes": [new]},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        old = _note_payload(
            note_id="n1",
            title="Old",
            modified_at="2026-01-01T00:00:00+00:00",
        )
        r = client.post(
            "/sync/push",
            json={"notes": [old]},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        body = r.json()
        assert body["accepted"] == 0
        assert body["skipped"] == 1
        # And the old title is NOT what pull returns.
        pulled = client.get(
            "/sync/pull", headers={"Authorization": f"Bearer {alice_token}"}
        ).json()["notes"]
        assert pulled[0]["title"] == "New"

    def test_push_overrides_spoofed_account_id(
        self, client: TestClient, alice_token: str, bob_credentials
    ) -> None:
        _, _, bob_id = bob_credentials
        spoof = _note_payload(note_id="evil", title="Pwned")
        spoof["account_id"] = bob_id  # alice tries to write under bob's id
        r = client.post(
            "/sync/push",
            json={"notes": [spoof]},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert r.status_code == 200
        # Confirm the row landed under alice, not bob.
        a_pull = client.get(
            "/sync/pull", headers={"Authorization": f"Bearer {alice_token}"}
        ).json()["notes"]
        assert any(n["id"] == "evil" for n in a_pull)

    def test_push_with_encrypted_blob_roundtrips(
        self, client: TestClient, alice_token: str
    ) -> None:
        blob = b"\x00\x01\x02encrypted-bytes\xff"
        note = _note_payload(
            note_id="enc1", title="Sealed", is_encrypted=True, blob=blob
        )
        r = client.post(
            "/sync/push",
            json={"notes": [note]},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert r.json()["accepted"] == 1
        pulled = client.get(
            "/sync/pull", headers={"Authorization": f"Bearer {alice_token}"}
        ).json()["notes"]
        assert pulled[0]["is_encrypted"] is True
        decoded = base64.b64decode(pulled[0]["encrypted_blob_b64"])
        assert decoded == blob


# ---------------------------------------------------------------------------
# GET /sync/pull
# ---------------------------------------------------------------------------


class TestSyncPull:
    def test_pull_unauthenticated_returns_401(self, client: TestClient) -> None:
        r = client.get("/sync/pull")
        assert r.status_code == 401

    def test_pull_empty_returns_empty_list(
        self, client: TestClient, alice_token: str
    ) -> None:
        r = client.get(
            "/sync/pull", headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["notes"] == []
        assert body["server_time"]

    def test_pull_since_filters_older_notes(
        self, client: TestClient, alice_token: str
    ) -> None:
        old_ts = "2026-01-01T00:00:00+00:00"
        new_ts = "2026-06-01T00:00:00+00:00"
        client.post(
            "/sync/push",
            json={
                "notes": [
                    _note_payload(note_id="old", title="Old", modified_at=old_ts),
                    _note_payload(note_id="new", title="New", modified_at=new_ts),
                ]
            },
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        r = client.get(
            "/sync/pull",
            params={"since": "2026-03-01T00:00:00+00:00"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        ids = [n["id"] for n in r.json()["notes"]]
        assert ids == ["new"]

    def test_pull_since_zero_returns_everything(
        self, client: TestClient, alice_token: str
    ) -> None:
        client.post(
            "/sync/push",
            json={
                "notes": [
                    _note_payload(note_id="a", title="A"),
                    _note_payload(note_id="b", title="B"),
                ]
            },
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        r = client.get(
            "/sync/pull",
            params={"since": "0"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert len(r.json()["notes"]) == 2


# ---------------------------------------------------------------------------
# B-94 Cross-account isolation (R16.5)
# ---------------------------------------------------------------------------


class TestAccountIsolation:
    def test_alice_cannot_see_bob_notes(
        self, client: TestClient, alice_token: str, bob_token: str
    ) -> None:
        # Bob writes 2 notes
        client.post(
            "/sync/push",
            json={
                "notes": [
                    _note_payload(note_id="bob-1", title="Bob One"),
                    _note_payload(note_id="bob-2", title="Bob Two"),
                ]
            },
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        # Alice pulls
        r = client.get(
            "/sync/pull", headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert r.json()["notes"] == []

    def test_same_note_id_isolated_between_accounts(
        self, client: TestClient, alice_token: str, bob_token: str
    ) -> None:
        client.post(
            "/sync/push",
            json={"notes": [_note_payload(note_id="shared", title="Alice's")]},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        client.post(
            "/sync/push",
            json={"notes": [_note_payload(note_id="shared", title="Bob's")]},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        a = client.get(
            "/sync/pull", headers={"Authorization": f"Bearer {alice_token}"}
        ).json()["notes"]
        b = client.get(
            "/sync/pull", headers={"Authorization": f"Bearer {bob_token}"}
        ).json()["notes"]
        assert len(a) == 1 and a[0]["title"] == "Alice's"
        assert len(b) == 1 and b[0]["title"] == "Bob's"

    def test_pull_response_account_id_matches_token(
        self, client: TestClient, alice_token: str, alice_credentials
    ) -> None:
        _, _, aid = alice_credentials
        client.post(
            "/sync/push",
            json={"notes": [_note_payload(note_id="n", title="N")]},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        notes = client.get(
            "/sync/pull", headers={"Authorization": f"Bearer {alice_token}"}
        ).json()["notes"]
        assert notes[0]["account_id"] == aid


# ---------------------------------------------------------------------------
# SyncClient + token cache
# ---------------------------------------------------------------------------


class TestSyncClient:
    def _client_with_app(self, app) -> SyncClient:
        # TestClient itself is a sync httpx-compatible client, so we feed it
        # straight into SyncClient.  ASGITransport is async-only in httpx 0.28.
        sc = SyncClient(client=TestClient(app))
        sc._owns_client = False  # the caller manages the TestClient lifecycle
        return sc

    def test_login_returns_response_dict(self, app, alice_credentials) -> None:
        u, p, _ = alice_credentials
        sc = self._client_with_app(app)
        try:
            response = sc.login(u, p)
            assert response["token_type"] == "bearer"
            assert response["access_token"]
        finally:
            sc.close()

    def test_login_bad_password_raises_authentication_error(
        self, app, alice_credentials
    ) -> None:
        u, _p, _ = alice_credentials
        sc = self._client_with_app(app)
        try:
            with pytest.raises(AuthenticationError):
                sc.login(u, "WrongPass1!")
        finally:
            sc.close()

    def test_token_cache_roundtrip(self, tmp_path: Path) -> None:
        future = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat()
        save_cached_token(
            tmp_path,
            {
                "access_token": "tok",
                "expires_at": future,
                "account_id": "aid",
                "username": "alice",
            },
        )
        loaded = load_cached_token(tmp_path)
        assert loaded is not None
        assert loaded["access_token"] == "tok"
        assert loaded["username"] == "alice"

    def test_load_expired_token_returns_none(self, tmp_path: Path) -> None:
        past = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()
        save_cached_token(
            tmp_path,
            {
                "access_token": "tok",
                "expires_at": past,
                "account_id": "aid",
                "username": "alice",
            },
        )
        assert load_cached_token(tmp_path) is None
        # File should have been auto-deleted.
        assert not (tmp_path / ".sync_token").exists()

    def test_load_corrupt_token_returns_none(self, tmp_path: Path) -> None:
        path = tmp_path / ".sync_token"
        path.write_text("not json", encoding="utf-8")
        assert load_cached_token(tmp_path) is None
        assert not path.exists()

    def test_delete_cached_token_when_absent(self, tmp_path: Path) -> None:
        assert delete_cached_token(tmp_path) is False

    def test_push_pull_via_sync_client(self, app, alice_credentials) -> None:
        u, p, _ = alice_credentials
        sc = self._client_with_app(app)
        try:
            login = sc.login(u, p)
            token = login["access_token"]
            push_resp = sc.push(
                token,
                [
                    {
                        "id": "n1",
                        "title": "T",
                        "content": "c",
                        "is_encrypted": False,
                        "encrypted_blob_b64": None,
                        "created_at": _utcnow_iso(),
                        "modified_at": _utcnow_iso(),
                    }
                ],
            )
            assert push_resp["accepted"] == 1
            pull_resp = sc.pull(token)
            assert len(pull_resp["notes"]) == 1
        finally:
            sc.close()


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def _make_cli_sync_client_factory(app):
    """Return a SyncClient subclass that proxies every call to *app* via TestClient."""

    class _AsgiSyncClient(SyncClient):
        def __init__(self, base_url=None, *, client=None, timeout=30.0) -> None:
            super().__init__(client=TestClient(app))
            # TestClient cleans itself up; nothing for SyncClient.close() to do.
            self._owns_client = False

    return _AsgiSyncClient


class TestCliSync:
    def test_sync_logout_when_absent(self, tmp_path: Path) -> None:
        runner = CliRunner()
        r = runner.invoke(
            cli_app,
            ["--data-dir", str(tmp_path), "sync", "logout"],
            catch_exceptions=False,
        )
        assert r.exit_code == 0
        assert "No cached sync token" in r.output

    def test_sync_push_without_token_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Configure a sync_server_url so we get past _resolve_server_url.
        from src.core.config import ConfigStore
        config = ConfigStore()
        config.set("sync_server_url", "http://localhost:9999")

        runner = CliRunner()
        r = runner.invoke(
            cli_app,
            ["--data-dir", str(tmp_path), "sync", "push"],
            catch_exceptions=False,
        )
        assert r.exit_code == 1
        assert "no valid sync token" in r.output.lower()

    def test_sync_login_push_pull_flow(
        self,
        tmp_path: Path,
        app,
        alice_credentials,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        u, p, aid = alice_credentials
        client_dir = tmp_path / "client"
        client_dir.mkdir()

        # Patch SyncClient inside the cli's lazy-imported module so it talks to TestClient.
        AsgiSyncClient = _make_cli_sync_client_factory(app)
        monkeypatch.setattr(sync_client_mod, "SyncClient", AsgiSyncClient)

        runner = CliRunner()

        # 1) sync login (with --server-url override, prompts for u/p)
        r = runner.invoke(
            cli_app,
            [
                "--data-dir",
                str(client_dir),
                "sync",
                "login",
                "--server-url",
                "http://testserver",
            ],
            input=f"{u}\n{p}\n",
            catch_exceptions=False,
        )
        assert r.exit_code == 0, r.output
        assert "Logged in to sync server" in r.output
        assert (client_dir / ".sync_token").exists()

        # 2) Add a local note tagged with this account so push has work to do.
        store = DatabaseStore(client_dir)
        from src.core.notes import Note
        note = Note.create(title="Local", content="hello")
        nid = store.add(note, account_id=aid)

        # 3) sync push
        r = runner.invoke(
            cli_app,
            [
                "--data-dir",
                str(client_dir),
                "sync",
                "push",
                "--server-url",
                "http://testserver",
            ],
            catch_exceptions=False,
        )
        assert r.exit_code == 0, r.output
        assert "Pushed 1 notes" in r.output

        # 4) Delete the local note then sync pull --full to get it back.
        store.delete(nid)
        r = runner.invoke(
            cli_app,
            [
                "--data-dir",
                str(client_dir),
                "sync",
                "pull",
                "--server-url",
                "http://testserver",
                "--full",
            ],
            catch_exceptions=False,
        )
        assert r.exit_code == 0, r.output
        assert "Pulled 1 notes" in r.output
        # Confirm the note is back locally.
        recovered = store.get(nid)
        assert recovered is not None
        assert recovered.title == "Local"

        # 5) sync logout removes the token file.
        r = runner.invoke(
            cli_app,
            ["--data-dir", str(client_dir), "sync", "logout"],
            catch_exceptions=False,
        )
        assert r.exit_code == 0
        assert "Sync token cleared" in r.output
        assert not (client_dir / ".sync_token").exists()
