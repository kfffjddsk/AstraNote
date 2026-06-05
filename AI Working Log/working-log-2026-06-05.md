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
