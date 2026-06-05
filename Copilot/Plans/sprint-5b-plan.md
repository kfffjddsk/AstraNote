# Sprint 5B Implementation Plan — Desktop Sync UI + OAuth

## Context

Sprint 5A (server MVP + hardening) is fully done — 631 tests pass. Copilot started Sprint 5B and committed two scaffold files (`merge_window.py`, `sync_worker.py`) before running out of tokens. Both files are now committed. What remains is:

- **B-87**: `POST /auth/callback` OAuth PKCE endpoint on the server
- **B-89/B-90**: Sync login dialog, sync toolbar button, status indicators, and wiring `SyncWorker` + `MergeWindow` into `MainWindow`
- **Tests** in a new `tests/test_sprint5b.py`

All work respects the DoD: full suite must pass, working log required, backlog updated.

---

## Files to Modify / Create

| File | Change |
|------|--------|
| `src/server/schemas.py` | Add `OAuthCallbackRequest` schema |
| `src/server/settings.py` | Add `google_client_id`, `google_client_secret` fields + `from_env()` reads |
| `src/server/routers/auth.py` | Add `POST /auth/callback` endpoint |
| `src/core/auth.py` | Add `get_or_create_oauth_account()` to `AccountStore` |
| `src/core/sync_client.py` | Add `callback_exchange()` method |
| `src/desktop/main_window.py` | Add `SyncLoginDialog`, sync toolbar button, `_on_sync()`, conflict/merge wiring |
| `tests/test_sprint5b.py` | New — all Sprint 5B tests |

---

## Step 1 — `src/server/schemas.py`

Add `OAuthCallbackRequest` after `LoginResponse`:
- `code: str` (1–2048 chars)
- `code_verifier: str` (43–128 chars, RFC 7636)
- `redirect_uri: str` (1–512 chars)

`LoginResponse` reused as response schema.

---

## Step 2 — `src/server/settings.py`

Add to `ServerSettings`:
- `google_client_id: str = ""`
- `google_client_secret: str = ""`
- `google_token_url: str = "https://oauth2.googleapis.com/token"`

Add to `from_env()`: read `ASTRANOTES_GOOGLE_CLIENT_ID`, `ASTRANOTES_GOOGLE_CLIENT_SECRET`.

---

## Step 3 — `src/server/routers/auth.py`

Add `POST /auth/callback`:
1. Call `_exchange_oauth_code(settings, payload)` (module-level, monkeypatchable) → Google token response
2. Decode id_token middle segment (base64) → extract `sub`, `email`
3. `store.get_or_create_oauth_account(email, oauth_sub)` → account dict
4. `issue_token(settings, account_id, username)` → JWT
5. Return `LoginResponse`

Guard: if `settings.google_client_id == ""` → return 501 Not Implemented.

Errors: 400 on bad code/verifier, 400 on missing claims, 500 on unexpected.

---

## Step 4 — `src/core/auth.py`

Add `get_or_create_oauth_account(email, oauth_sub)` to `AccountStore`:
- Derive username from email local part: replace non-alphanumeric chars with `_`, enforce 3–32 chars
- `get_by_username(username)` → return if found
- Else: `register(username, secrets.token_urlsafe(32))` (OAuth accounts have unguessable password)
- Return `{"account_id": ..., "username": ...}`

Add module-level `_email_to_username(email) -> str` helper.

---

## Step 5 — `src/core/sync_client.py`

Add `SyncClient.callback_exchange(code, code_verifier, redirect_uri)`:
- `POST /auth/callback` with JSON body
- Returns parsed response dict
- Raises `SyncError` on non-2xx or network error

---

## Step 6 — `src/desktop/main_window.py`

### New: `_OAuthCallbackServer`
stdlib `HTTPServer` + `BaseHTTPRequestHandler` in a daemon thread.
Parses `GET /?code=...&state=...`, puts `{code, state}` on a `queue.Queue`, serves "You can close this tab" HTML.

### New: `SyncLoginDialog(QDialog)`
Two-tab dialog:

**Tab 1 — Local account:**
- Username + password fields → "Sign in" button
- `SyncClient.login(username, password)` → `save_cached_token(data_dir, response)` → accept

**Tab 2 — Sign in with Google (PKCE):**
- "Open Google sign-in" button
- Generates `code_verifier` (43 chars), `code_challenge` (S256)
- Binds `_OAuthCallbackServer` on `127.0.0.1:0` (random port)
- Opens auth URL in system browser via `QDesktopServices.openUrl`
- `QTimer` polls `result_queue` every 500ms
- On code received: `SyncClient.callback_exchange(code, code_verifier, redirect_uri)` → save token → accept

### `MainWindow` changes
- **`__init__`**: add `sync_url: Optional[str] = None`; `self._sync_worker = None`
- **`_build_toolbar`**: add Sync action after settings separator
- **`_build_menu_bar`**: add `Sync` menu (Sync Now / Sign In... / Sign Out)
- **`_build_status_bar`**: add `_status_sync_label` permanent widget
- **New methods**: `_on_sync`, `_on_sync_login`, `_on_sync_logout`, `_on_sync_progress`, `_on_sync_finished`, `_on_sync_failed`, `_on_conflict_detected`, `_on_merge_accepted`
- Guard: if `sync_url` empty → info dialog "Configure sync server URL in settings first"

### `AppController` change
Pass `sync_url=self.config.get("sync_url") or ""` to `MainWindow(...)`.

---

## Step 7 — `tests/test_sprint5b.py`

| Class | Count | Focus |
|-------|-------|-------|
| `TestMergeWindow` | 5 | init, `resolved_content()`, `_on_use_local`, accept/cancel |
| `TestSyncWorkerPush` | 4 | push happy path, nothing pending, `SyncError`, `AuthenticationError` |
| `TestSyncWorkerPull` | 5 | new note upserted, LWW accepted, conflict emitted, empty pull, `SyncError` |
| `TestSyncWorkerBoth` | 2 | both cycle, `finished_ok` always emitted |
| `TestOAuthCallbackEndpoint` | 6 | happy path, no client_id → 501, bad code → 400, missing claims → 400, new account, existing account |
| `TestSyncClientCallbackExchange` | 3 | happy path, non-2xx, network error |
| `TestEmailToUsername` | 4 | normal, dots/plus, short, collision |
| `TestGetOrCreateOAuthAccount` | 3 | new, existing, collision disambiguated |
| `TestMainWindowSyncUI` | 6 | sync button present, sync menu, no-token → login dialog, token cached → worker launched, conflict → MergeWindow, finished → note list refresh |

Target: ≥ 35 new tests; all 631 existing still pass; total ≥ 666.

---

## Deviation from Design Doc

Design §4.9 specifies `astranotes://callback` custom URI scheme. We use `http://127.0.0.1:<random-port>/` instead (RFC 8252 §7.3 loopback redirect):
- No OS-level URI scheme registration needed
- Fully testable without elevated permissions
- Documented as new D-xx item in `Copilot/discussion-list.md`

---

## Verification

```
pytest tests/test_sprint5b.py -v   # new tests
pytest --tb=short -q               # full suite
```
