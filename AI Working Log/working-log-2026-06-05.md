# AI Working Log — 2026-06-05

## Session Summary

**AI Partner:** Claude (claude-sonnet-4-6)
**Sprint:** 5B — Desktop Sync UI + Google OAuth PKCE
**Outcome:** Sprint 5B fully delivered. 669 tests passing (38 new), 1 skipped.

---

## What Was Delivered (Backlog B-87, B-89, B-90)

| ID | Item | Notes |
|----|------|-------|
| B-87 | `POST /auth/callback` — Google OAuth PKCE server endpoint | `OAuthCallbackRequest` schema; `_exchange_oauth_code()` (monkeypatchable); `_decode_id_token_claims()`; endpoint in `src/server/routers/auth.py`. Returns 501 when `ASTRANOTES_GOOGLE_CLIENT_ID` unset so clients can detect gracefully. |
| B-87 | `AccountStore.get_or_create_oauth_account()` | Derives username from email local part via `_email_to_username()`. Registers with unguessable random password — OAuth accounts can never be authenticated via username/password path. |
| B-87 | `SyncClient.callback_exchange()` | `POST /auth/callback` call; wraps errors as `SyncError`. |
| B-87 | `ServerSettings` OAuth fields | `google_client_id`, `google_client_secret`, `google_token_url`; read from env vars `ASTRANOTES_GOOGLE_CLIENT_ID` / `ASTRANOTES_GOOGLE_CLIENT_SECRET` in `from_env()`. |
| B-89 | `_OAuthCallbackServer` | Stdlib `HTTPServer` on `127.0.0.1:0` in a daemon thread. Captures `GET /?code=…&state=…` and puts result on a `queue.Queue`. Follows RFC 8252 §7.3 loopback redirect (no custom URI scheme / registry write needed). |
| B-89 | `SyncLoginDialog(QDialog)` | Two-tab dialog: Local account (username + password) and Sign in with Google (PKCE). Generates `code_verifier` + S256 `code_challenge`, opens browser via `QDesktopServices.openUrl`, polls `_OAuthCallbackServer` every 500 ms via `QTimer`. Saves token via `save_cached_token` on success. |
| B-89 | Sync toolbar button | `_action_sync_now` added to `_build_toolbar` after Delete separator. |
| B-89 | Sync menu | `&Sync` menu in menu bar: Sync Now (Ctrl+Shift+S), separator, Sign In…, Sign Out. |
| B-89 | Sync status label | `_status_sync_label = QLabel("⬤ Not synced")` added as first permanent widget in status bar. |
| B-90 | `MainWindow` sync wiring | `_on_sync()`, `_on_sync_login()`, `_on_sync_logout()`, `_on_sync_progress()`, `_on_sync_finished()`, `_on_sync_failed()`, `_on_conflict_detected()`, `_on_merge_accepted()`. `AppController` passes `sync_url=config.get("sync_server_url")`. |
| B-90 | `Note.synced_at` field | Added `synced_at: Optional[str] = None` to `Note` dataclass; `_row_to_note()` now populates it from the DB row. Fixes a latent bug in `SyncWorker._do_pull()` where `getattr(local, "synced_at", "")` always returned `""`, making all pulls land in conflict mode instead of last-write-wins. |

---

## Files Touched

### Modified
- `src/core/notes.py` — `Note.synced_at` field + `_row_to_note()` update
- `src/core/auth.py` — `_email_to_username()` + `AccountStore.get_or_create_oauth_account()` (already committed in prior session)
- `src/core/sync_client.py` — `callback_exchange()` (already committed in prior session)
- `src/server/schemas.py` — `OAuthCallbackRequest` (already committed)
- `src/server/settings.py` — `google_client_id`, `google_client_secret` fields (already committed)
- `src/server/routers/auth.py` — `POST /auth/callback` endpoint (already committed)
- `src/desktop/main_window.py` — `_OAuthCallbackServer`, `SyncLoginDialog`, sync toolbar/menu/status, `_on_sync*` methods, `sync_url` param
- `src/desktop/app_controller.py` — passes `sync_url=config.get("sync_server_url")` to `MainWindow`

### New
- `src/desktop/sync_worker.py` — `SyncWorker(QThread)` (committed in prior session)
- `src/desktop/merge_window.py` — `MergeWindow(QDialog)` (committed in prior session)
- `tests/test_sprint5b.py` — 38 new tests across 9 classes
- `Copilot/Plans/sprint-5b-plan.md` — implementation plan

---

## Test Results

```
669 passed, 1 skipped  (38 new in test_sprint5b.py)
```

Previous baseline: 631 tests (Sprint 5A.2).

---

## Deviations from Design Doc

| ID | Decision | Reason |
|----|----------|--------|
| D-xx | Loopback redirect (`http://127.0.0.1:<port>/`) instead of `astranotes://callback` custom URI scheme | No OS registration needed; RFC 8252 §7.3 compliant; fully testable without install-time setup. Documented in `Copilot/discussion-list.md`. |

---

## Discussion Items

- `authlib.jose` deprecation warning (should migrate to `joserfc` before 2.0). Logged as a follow-up.
- `Note.synced_at` field addition is a minor model expansion that is backward-compatible (default `None`). All 631 prior tests continue to pass.

---

## Tech Debt Resolution — 2026-06-05 (same session, continuation)

### What Was Fixed

| TD | Item | Files Changed |
|----|------|--------------|
| TD-01 | `authlib.jose` → `joserfc` | `src/server/security.py` |
| TD-02 | Auto-sync interval not wired | `src/desktop/main_window.py`, `src/desktop/app_controller.py` |
| TD-03 | Rate limiter in-process only | `src/server/rate_limit.py`, `src/server/settings.py`, `src/server/app.py`, `src/server/routers/sync.py` |
| TD-04 | Server Alembic migrations missing | `alembic_server.ini`, `alembic_server/env.py`, `alembic_server/script.py.mako`, `alembic_server/versions/0001_server_notes_initial.py` |
| TD-05 | No desktop account registration | `Copilot/Plans/gui-account-registration.md` (design doc only) |

### TD-01 Detail: authlib → joserfc

Replaced the `warnings.catch_warnings()` suppression block and all `authlib.jose` imports with `joserfc`:

- `from joserfc import jwt as _jwt`
- `from joserfc.jwk import OctKey`
- `from joserfc.errors import BadSignatureError, DecodeError, ExpiredTokenError, JoseError`

`issue_token`: creates `OctKey.import_key(settings.jwt_secret.encode())`, calls `_jwt.encode(header, payload, key)` → returns `str` directly (no `bytes.decode()` needed).

`verify_token`: `_jwt.decode(token, key)` → `Token`; `token.validate()` → raises `ExpiredTokenError` on stale; `token.claims` → `dict` for claim extraction.

Exception hierarchy unchanged; all existing token tests pass.

### TD-02 Detail: Auto-sync interval

- `MainWindow.__init__` gains `sync_auto_interval: int = 0` param; stored as `self._sync_auto_interval`.
- New `start_auto_sync_timer()` method: creates `QTimer` firing `_on_sync()` every `interval * 60 * 1000` ms when `interval > 0` and `sync_url` is set.
- `_on_sync_logout()` stops the timer.
- `AppController.run()` reads `sync_auto_interval` from `ConfigStore`, passes to `MainWindow`, calls `window.start_auto_sync_timer()` after `start_idle_timer()`.
- No changes to `config.py` — the key was already there with default `0` and non-negative validation.

### TD-03 Detail: Redis rate limiter

Added to `src/server/rate_limit.py`:

- `_REDIS_AVAILABLE` flag (conditional `import redis`).
- `RedisRateLimiter`: sorted-set per account (`astranotes:rl:<account_id>`); prune → count → reject or zadd in two pipelined round-trips; sets key TTL for automatic cleanup.
- `make_rate_limiter(per_minute, redis_url)` factory: tries Redis (with PING probe), falls back to `AccountRateLimiter` on any failure and logs a warning.

`ServerSettings` gains `redis_url: str = ""` field (env var `ASTRANOTES_REDIS_URL`).

`app.py` changed from `AccountRateLimiter(settings.rate_limit_per_minute)` → `make_rate_limiter(settings.rate_limit_per_minute, settings.redis_url)`.

`sync.py` router import cleaned up (no longer imports `AccountRateLimiter` by name).

### TD-04 Detail: Server Alembic migrations

`alembic_server/` mirrors the client-side `alembic/` structure but targets `src.server.models.Base`:

- `alembic_server.ini` — separate ini file; `ASTRANOTES_SERVER_DB_URL` overrides the URL.
- `alembic_server/env.py` — standard online/offline setup with `render_as_batch=True` for SQLite ALTER support.
- `alembic_server/versions/0001_server_notes_initial.py` — creates `server_notes` table and both indexes; has a working `downgrade()`.

The server's `init_db(create_all=True)` path is kept intact for development/testing. Alembic is for production PostgreSQL deployments.

### TD-05 Detail: GUI design doc

`Copilot/Plans/gui-account-registration.md` documents:
- Proposed "Create account" third tab in `SyncLoginDialog`.
- Username chip with dropdown in the status bar.
- Dedicated Sync page in `SettingsDialog`.
- Full dialog flow diagram.
- Open design questions for user review.

Implementation not started — document created for redesign discussion.

### Test Results

All tests still passing after TD-01 through TD-04 changes.
