"""Sprint 5A.2 — server hardening tests.

Covers:
* HTTPS enforcement middleware (B-92): rejection, dev opt-out, loopback
  always-allowed, ``X-Forwarded-Proto`` proxy header, ``/healthz`` bypass.
* Per-account sliding-window rate limiter (B-95) at the unit level and
  end-to-end through ``/sync/push`` + ``/sync/pull``.
* Postgres DSN validation (B-63): localhost ok, remote without
  ``sslmode`` rejected, remote with ``sslmode=require`` ok.
* Concurrent push/pull with 10 accounts in parallel threads (B-93).
* ``ServerSettings`` hardening defaults (B-92, B-93, B-95).
"""
from __future__ import annotations

import base64
import concurrent.futures
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

import pytest
from fastapi.testclient import TestClient

from src.server.app import create_app
from src.server.db import make_engine
from src.server.rate_limit import AccountRateLimiter, RateLimitExceeded
from src.server.settings import ServerSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_settings(
    tmp_path: Path,
    *,
    enforce_https: bool = False,
    rate_limit_per_minute: int = 60,
    suffix: str = "",
) -> ServerSettings:
    """Per-test settings backed by an isolated SQLite file + data dir."""
    db_name = f"sync_server{suffix}.db"
    data_dir = tmp_path / f"server_data{suffix}"
    return ServerSettings(
        database_url=f"sqlite:///{(tmp_path / db_name).as_posix()}",
        jwt_secret="unit-test-secret",
        jwt_algorithm="HS256",
        jwt_expiry_hours=24,
        data_dir=data_dir,
        enforce_https=enforce_https,
        rate_limit_per_minute=rate_limit_per_minute,
    )


def _client(
    tmp_path: Path,
    *,
    enforce_https: bool = False,
    rate_limit_per_minute: int = 60,
    base_url: str = "http://testserver",
    suffix: str = "",
) -> TestClient:
    """FastAPI ``TestClient`` whose base URL drives the ASGI scope/host."""
    settings = _build_settings(
        tmp_path,
        enforce_https=enforce_https,
        rate_limit_per_minute=rate_limit_per_minute,
        suffix=suffix,
    )
    app = create_app(settings)
    return TestClient(app, base_url=base_url)


def _register_and_login(
    client: TestClient, username: str, password: str = "CorrectHorse9!"
) -> str:
    """Register an account via ``AccountStore`` and obtain a bearer token."""
    store = client.app.state.account_store
    store.register(username, password)
    r = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _note_payload(note_id: str = "n1", title: str = "T") -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": note_id,
        "title": title,
        "content": "hello",
        "is_encrypted": False,
        "encrypted_blob_b64": None,
        "created_at": now,
        "modified_at": now,
    }


# ---------------------------------------------------------------------------
# 1. HTTPS enforcement (B-92)
# ---------------------------------------------------------------------------


class TestHttpsEnforcement:
    def test_http_request_rejected_when_enforce_https_true(
        self, tmp_path: Path
    ) -> None:
        with _client(
            tmp_path, enforce_https=True, base_url="http://testserver"
        ) as c:
            r = c.get("/sync/pull")
            assert r.status_code == 400
            body = r.json()
            assert body["status"] == "error"
            assert body["error"] == "bad_request"
            assert "HTTPS" in body["message"]

    def test_http_allowed_when_enforce_https_false(self, tmp_path: Path) -> None:
        with _client(tmp_path, enforce_https=False) as c:
            # No token, but the middleware doesn't fire so we hit 401 from
            # the JWT dependency — proving HTTP traffic was allowed through.
            r = c.get("/sync/pull")
            assert r.status_code == 401

    def test_loopback_always_allowed(self, tmp_path: Path) -> None:
        with _client(
            tmp_path, enforce_https=True, base_url="http://localhost"
        ) as c:
            r = c.get("/healthz")
            assert r.status_code == 200
            # And the loopback exemption applies to non-healthz too: an
            # unauthenticated /sync/pull still returns 401, not 400.
            r2 = c.get("/sync/pull")
            assert r2.status_code == 401

    def test_x_forwarded_proto_https_accepted(self, tmp_path: Path) -> None:
        with _client(
            tmp_path, enforce_https=True, base_url="http://testserver"
        ) as c:
            r = c.get("/sync/pull", headers={"X-Forwarded-Proto": "https"})
            # No bearer token, but the HTTPS check passed — 401 not 400.
            assert r.status_code == 401

    def test_healthz_bypasses_https_check(self, tmp_path: Path) -> None:
        with _client(
            tmp_path, enforce_https=True, base_url="http://testserver"
        ) as c:
            r = c.get("/healthz")
            assert r.status_code == 200
            assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# 2. Rate limiting end-to-end (B-95)
# ---------------------------------------------------------------------------


class TestRateLimit:
    def test_under_limit_passes(self, tmp_path: Path) -> None:
        with _client(tmp_path, rate_limit_per_minute=10) as c:
            token = _register_and_login(c, "alice")
            for _ in range(5):
                r = c.get(
                    "/sync/pull",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert r.status_code == 200

    def test_over_limit_returns_429(self, tmp_path: Path) -> None:
        with _client(tmp_path, rate_limit_per_minute=10) as c:
            token = _register_and_login(c, "alice")
            statuses = []
            for _ in range(11):
                r = c.get(
                    "/sync/pull",
                    headers={"Authorization": f"Bearer {token}"},
                )
                statuses.append(r.status_code)
            assert statuses[:10] == [200] * 10
            assert statuses[10] == 429
            # Last response carries the Retry-After header.
            last = c.get(
                "/sync/pull",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert last.status_code == 429
            assert last.headers.get("Retry-After")
            assert int(last.headers["Retry-After"]) >= 1

    def test_429_envelope_shape(self, tmp_path: Path) -> None:
        with _client(tmp_path, rate_limit_per_minute=1) as c:
            token = _register_and_login(c, "alice")
            assert (
                c.get(
                    "/sync/pull",
                    headers={"Authorization": f"Bearer {token}"},
                ).status_code
                == 200
            )
            r = c.get(
                "/sync/pull", headers={"Authorization": f"Bearer {token}"}
            )
            assert r.status_code == 429
            body = r.json()
            assert body["status"] == "error"
            assert body["error"] == "rate_limited"
            assert "message" in body
            # ``retry_after`` lives in the header per RFC 6585.
            assert int(r.headers["Retry-After"]) >= 1

    def test_per_account_isolation(self, tmp_path: Path) -> None:
        with _client(tmp_path, rate_limit_per_minute=2) as c:
            alice = _register_and_login(c, "alice")
            bob = _register_and_login(c, "bob", "TrombonePencil9!")
            # alice exhausts her budget.
            for _ in range(2):
                assert (
                    c.get(
                        "/sync/pull",
                        headers={"Authorization": f"Bearer {alice}"},
                    ).status_code
                    == 200
                )
            r_alice = c.get(
                "/sync/pull", headers={"Authorization": f"Bearer {alice}"}
            )
            assert r_alice.status_code == 429
            # bob's bucket is untouched.
            r_bob = c.get(
                "/sync/pull", headers={"Authorization": f"Bearer {bob}"}
            )
            assert r_bob.status_code == 200

    def test_login_not_rate_limited(self, tmp_path: Path) -> None:
        # rate_limit_per_minute=1 would block on the *second* login call if
        # /auth/login shared the sync limiter.  Five logins must all succeed.
        with _client(tmp_path, rate_limit_per_minute=1) as c:
            store = c.app.state.account_store
            store.register("alice", "CorrectHorse9!")
            statuses = []
            for _ in range(5):
                r = c.post(
                    "/auth/login",
                    json={"username": "alice", "password": "CorrectHorse9!"},
                )
                statuses.append(r.status_code)
            assert all(s == 200 for s in statuses)


# ---------------------------------------------------------------------------
# 3. Rate limiter unit tests
# ---------------------------------------------------------------------------


class TestRateLimiterUnit:
    def test_allows_under_limit(self) -> None:
        limiter = AccountRateLimiter(per_minute=5)
        for _ in range(5):
            limiter.check("alice")  # no exception

    def test_raises_at_limit(self) -> None:
        limiter = AccountRateLimiter(per_minute=3)
        limiter.check("alice")
        limiter.check("alice")
        limiter.check("alice")
        with pytest.raises(RateLimitExceeded) as info:
            limiter.check("alice")
        assert info.value.retry_after_seconds >= 1
        assert info.value.retry_after_seconds <= 60

    def test_window_slides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin time.time used inside the rate_limit module.
        import src.server.rate_limit as rate_limit_mod

        now = [1_000_000.0]
        monkeypatch.setattr(rate_limit_mod.time, "time", lambda: now[0])

        limiter = AccountRateLimiter(per_minute=2)
        limiter.check("alice")
        limiter.check("alice")
        with pytest.raises(RateLimitExceeded):
            limiter.check("alice")

        # Advance the clock past the 60-second window — old entries expire
        # and the limiter accepts again.
        now[0] += 61.0
        limiter.check("alice")  # no exception

    def test_thread_safety(self) -> None:
        per_minute = 50
        limiter = AccountRateLimiter(per_minute=per_minute)
        successes = 0
        failures = 0
        lock = threading.Lock()

        def worker() -> None:
            nonlocal successes, failures
            local_succ = 0
            local_fail = 0
            for _ in range(10):
                try:
                    limiter.check("alice")
                    local_succ += 1
                except RateLimitExceeded:
                    local_fail += 1
            with lock:
                successes += local_succ
                failures += local_fail

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 20 threads * 10 calls = 200 attempts; exactly ``per_minute``
        # may succeed within the 60-second window.
        assert successes + failures == 200
        assert successes == min(200, per_minute)


# ---------------------------------------------------------------------------
# 4. Postgres DSN validation (B-63)
# ---------------------------------------------------------------------------


def _safe_make_engine(url: str, *, pool_size: int = 10, max_overflow: int = 20):
    """Call make_engine without requiring the psycopg2 driver."""
    settings = ServerSettings(
        database_url=url,
        jwt_secret="x",
        db_pool_size=pool_size,
        db_max_overflow=max_overflow,
    )
    return make_engine(settings)


class TestPostgresDsnValidation:
    def test_localhost_pg_no_sslmode_ok(self) -> None:
        try:
            _safe_make_engine("postgresql://u:p@localhost/db")
        except ValueError:
            pytest.fail("localhost Postgres without sslmode should be accepted")
        except (ImportError, ModuleNotFoundError):
            # psycopg2 not installed in this venv — that's fine.  We only
            # care that our pre-flight ValueError did not fire.
            pass
        except Exception as exc:  # pragma: no cover - driver-specific
            # Other SQLAlchemy/dialect errors are acceptable.
            assert "Production Postgres DSN" not in str(exc)

    def test_remote_pg_without_sslmode_raises(self) -> None:
        with pytest.raises(ValueError, match="sslmode=require"):
            _safe_make_engine("postgresql://u:p@db.example.com/astranotes")

    def test_remote_pg_with_sslmode_require_ok(self) -> None:
        url = "postgresql://u:p@db.example.com/astranotes?sslmode=require"
        try:
            _safe_make_engine(url)
        except ValueError as exc:
            pytest.fail(
                f"sslmode=require should satisfy validation; got {exc!r}"
            )
        except (ImportError, ModuleNotFoundError):
            pass
        except Exception as exc:  # pragma: no cover - driver-specific
            assert "Production Postgres DSN" not in str(exc)


# ---------------------------------------------------------------------------
# 5. Concurrent sync (B-93)
# ---------------------------------------------------------------------------


class TestConcurrentSync:
    def test_ten_concurrent_users_push_pull(self, tmp_path: Path) -> None:
        # High limit so the limiter never kicks in for this load test.
        settings = _build_settings(
            tmp_path,
            enforce_https=False,
            rate_limit_per_minute=1000,
        )
        app = create_app(settings)
        # Pre-register all accounts on the main thread to keep AccountStore
        # registration deterministic; concurrent ops happen on login + sync.
        store = app.state.account_store
        users = [(f"user{i:02d}", "CorrectHorse9!") for i in range(10)]
        for username, password in users:
            store.register(username, password)

        results: list[dict[str, Any]] = []
        results_lock = threading.Lock()

        def worker(username: str, password: str) -> None:
            with TestClient(app) as c:
                login = c.post(
                    "/auth/login",
                    json={"username": username, "password": password},
                )
                assert login.status_code == 200, login.text
                token = login.json()["access_token"]

                note_id = f"note-{username}"
                push = c.post(
                    "/sync/push",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "notes": [_note_payload(note_id, f"{username}-title")]
                    },
                )
                assert push.status_code == 200, push.text
                pull = c.get(
                    "/sync/pull",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert pull.status_code == 200, pull.text
                with results_lock:
                    results.append(
                        {
                            "username": username,
                            "note_ids": [n["id"] for n in pull.json()["notes"]],
                            "account_ids": [
                                n["account_id"] for n in pull.json()["notes"]
                            ],
                        }
                    )

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = [
                ex.submit(worker, u, p) for u, p in users
            ]
            for f in futures:
                f.result()

        assert len(results) == 10
        # Each user sees exactly their own note — account isolation holds.
        for r in results:
            assert r["note_ids"] == [f"note-{r['username']}"]
            assert len(set(r["account_ids"])) == 1


# ---------------------------------------------------------------------------
# 6. Settings hardening defaults
# ---------------------------------------------------------------------------


class TestSettingsHardening:
    def test_enforce_https_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Under pytest the default is False (we're literally in pytest now).
        assert ServerSettings().enforce_https is False

        # In production (mock out the pytest detector) it flips to True.
        import src.server.settings as settings_mod

        monkeypatch.setattr(
            settings_mod, "_running_under_pytest", lambda: False
        )
        assert ServerSettings().enforce_https is True

    def test_dev_http_env_flips_enforce_https(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.server.settings as settings_mod

        monkeypatch.setattr(
            settings_mod, "_running_under_pytest", lambda: False
        )
        monkeypatch.setenv("ASTRANOTES_JWT_SECRET", "x")
        monkeypatch.setenv("ASTRANOTES_DEV_HTTP", "1")
        s = ServerSettings.from_env()
        assert s.enforce_https is False

    def test_rate_limit_env_parsed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASTRANOTES_JWT_SECRET", "x")
        monkeypatch.setenv("ASTRANOTES_RATE_LIMIT_PER_MIN", "42")
        s = ServerSettings.from_env()
        assert s.rate_limit_per_minute == 42

    def test_pool_field_defaults(self) -> None:
        s = ServerSettings()
        assert s.db_pool_size == 10
        assert s.db_max_overflow == 20
        assert s.rate_limit_per_minute == 60
