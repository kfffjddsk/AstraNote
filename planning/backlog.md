# AstraNotes — Product Backlog

Items ordered by priority. Status reflects current state.

## Sprint Zero — Done ✅

| ID | Item | User Story | Priority | Status |
|----|------|------------|----------|--------|
| B-01 | Add unencrypted note via CLI | US-1 | High | ✅ Done |
| B-02 | Add encrypted note with passphrase prompt | US-2 | High | ✅ Done |
| B-03 | Reject empty title/content on add | US-1 | High | ✅ Done |
| B-04 | Get unencrypted note by ID | US-1 | High | ✅ Done |
| B-05 | Get encrypted note with correct passphrase | US-2 | High | ✅ Done |
| B-06 | Reject wrong passphrase on get | US-2 | High | ✅ Done |
| B-07 | List notes with encrypted content hidden | US-1, US-2 | High | ✅ Done |
| B-08 | Update unencrypted note | US-1 | High | ✅ Done |
| B-09 | Update encrypted note with passphrase | US-2 | High | ✅ Done |
| B-10 | Reject wrong passphrase on update | US-2 | High | ✅ Done |
| B-11 | Delete unencrypted note | US-1 | High | ✅ Done |
| B-12 | Delete encrypted note with passphrase | US-2 | High | ✅ Done |
| B-13 | Reject wrong passphrase on delete | US-2 | High | ✅ Done |
| B-14 | Error handling for missing note IDs | US-1 | High | ✅ Done |
| ~~B-15~~ | ~~JSON persistence with save-on-mutate~~ — **replaced by B-42, B-43, B-51, B-74** (SQLite from Sprint 0 — D-10) | US-3 | High | Dropped |
| B-16 | Preserve encrypted records on no-key load | US-3 | High | ✅ Done |
| B-17 | AES-256-GCM encryption with PBKDF2 | US-2 | High | ✅ Done |
| B-18 | Plugin base class and registry | US-4 | High | ✅ Done |
| B-19 | `--data-dir` global option | US-1 | High | ⏳ Sprint 1 (CLI not yet implemented) |
| B-20 | BDD test coverage (17 scenarios) | US-1–US-4 | High | ✅ Done |
| B-21 | Unit tests for core modules (23 tests) | US-1–US-3 | High | ✅ Done |
| B-22 | Stress test for 1001 notes | US-3 | High | ✅ Done |
| B-23 | Non-zero exit codes on CLI errors | US-1 | High | ⏳ Sprint 1 (CLI not yet implemented) |
| B-42 | SQLite local store — `DatabaseStore` with `notes.db`, nullable `account_id` | US-12 | High | ✅ Done |
| B-43 | `BlobCodec` encode/encrypt pipeline; `DatabaseStore` add/get/update/delete/list | US-12, US-2 | High | ✅ Done |
| B-51 | Parameterized queries via SQLAlchemy ORM — no raw SQL | US-12, US-13 | High | ✅ Done |
| B-74 | Plaintext `title` column for fast listing (no blob parsing on list) | US-1, US-12 | High | ✅ Done |

## Backlog (Not Started)

| ID | Item | User Story | Priority |
|----|------|------------|----------|
| B-31 | Fix ID collision: use UUID or max-ID+1 | US-1 | High |
| B-32 | Passphrase confirmation prompt on encrypt | US-2 | High |
| B-33 | Fix unencrypted update/delete corrupting encrypted notes | US-2 | High |
| B-34 | Reject empty/short passphrase (min 8 chars) | US-2 | High |
| ~~B-35~~ | ~~Corrupt JSON recovery with `.bak` backup~~ — **DROPPED** (SQLite ACID replaces JSON corruption risk) `[D-10]` | US-1, US-3 | High |
| B-36 | `--data-dir` validation (must be directory, writable) | US-1 | Medium |
| B-37 | Plugin discovery and loading from `plugins/` | US-4 | Medium |
| B-38 | Plugin error isolation (try/except in hook dispatch) | US-4 | Medium |
| B-39 | File permission error handling with friendly messages | US-3 | Medium |
| B-40 | BDD + unit tests for new edge cases (B-31–B-39 scenarios) | US-1–US-4 | Medium |
| B-24 | Override policy: red warning + `CONFIRM OVERRIDE` for plugin overrides | US-5 | Medium |
| B-25 | Audit trail: JSON-per-line log with structured fields and filters | US-6 | Medium |
| B-26 | Config module: known-key whitelist with `set`/`get`/`list`/`reset` | US-7 | Medium |
| B-28 | Plugin CLI commands wired into main CLI | US-4 | Medium |
| B-29 | Substring search with `--encrypted` flag `[Sprint 3]` | US-8 | Low |
| B-30 | Export to text/JSON with `--output` and `--encrypted` `[Sprint 3]` | US-8 | Low |
| B-41 | First-login anonymous note association prompt — one-time prompt if anonymous notes exist; options: Yes / No / Ask me for each `[LOG 05-04]` | US-10 | High |
| B-42 | SQLite local store — always-on, `<data-dir>/notes.db`; `account_id` nullable FK + `synced_at` nullable timestamp on `notes` table `[LOG 05-04]` `[Sprint 0 — D-10]` | US-12 | High |
| B-43 | Sandbox binary storage: `BlobCodec` — `[4B len][JSON header][raw payload]`; `DatabaseStore` calls `encode()+encrypt()` in `add()`, `decrypt()+decode()` in `get()`/`load()` `[D-07 resolved 2026-05-11, Sprint 0 — D-10]` | US-12, US-2 | High |
| B-44 | PostgreSQL backend for sync server (`DATABASE_URL` env var, `sslmode=require`) `[LOG 05-04]` `[Sprint 5A]` | US-12 | Medium |
| B-45 | User registration and bcrypt password hashing | US-11 | Medium |
| B-46 | Login/logout session management | US-11 | Medium |
| B-47 | User isolation — scope all queries by `account_id`; anonymous notes (`account_id = NULL`) visible to all local sessions `[LOG 05-04]` | US-11 | Medium |
| ~~B-48~~ | ~~`migrate` CLI command: JSON → database migration (sandbox repackaging)~~ — **DROPPED** (no JSON storage phase; SQLite from Sprint 0) `[D-10 resolved 2026-05-12]` | US-12 | — |
| B-49 | Hybrid storage: 5 MB threshold, encrypted-only filesystem payloads | US-12 | High |
| ~~B-50~~ | ~~Mode switch with `CONFIRM MODE SWITCH` safety gate~~ — **REMOVED** (no mode-switching concept in three-layer model) `[LOG 05-04]` | — | — |
| B-51 | Parameterized queries via SQLAlchemy ORM — no raw SQL `[Sprint 0 — D-10]` | US-12, US-13 | High |
| B-52 | Input validation: reject null bytes and control characters at CLI boundary `[Sprint 1]` | US-1, US-11, US-13 | High |
| B-53 | Least-privilege PostgreSQL role (no DDL) `[Sprint 5A]` | US-12, US-13 | Medium |
| B-54 | Strip ANSI/control codes from terminal output | US-1, US-13 | Medium |
| B-55 | Path traversal prevention for --data-dir, --output, filesystem payloads | US-1, US-12, US-13 | Medium |
| B-56 | Plugin sandboxing — read-only note copies, no exec/eval, no raw DB access | US-4, US-13 | Medium |
| B-57 | Interactive auth prompts (hide_input=True) — never accept password as CLI arg | US-11 | High |
| B-58 | Auth rate limiting — 5 failures → 5-min lockout per username | US-11 | High |
| B-59 | Session token file with 24h expiry at `<data-dir>/.session` | US-11 | High |
| B-60 | Username validation — 3–32 chars, alphanumeric + underscore, case-insensitive | US-11 | Medium |
| B-61 | Account deletion: set `account_id = NULL` on all local notes; delete account record from sync server; warn user that cloud copies will be deleted `[LOG 05-04]` | US-11 | Medium |
| B-62 | Passphrase rotation via `reencrypt <note_id>` (includes filesystem payload re-encryption) | US-2 | Medium |
| B-63 | PostgreSQL `sslmode=require` enforcement `[Sprint 5A]` | US-12, US-13 | High |
| B-64 | `DATABASE_URL` env-var only — never stored in config.json | US-12, US-13 | High |
| B-65 | Alembic schema versioning for database migrations `[Sprint 1 — D-10]` | US-12 | Medium |
| B-66 | SQLite WAL mode + retry logic for concurrent access `[Sprint 1 — D-10]` | US-12 | Medium |
| B-67 | Disk-full (`ENOSPC`) error handling at JSON and DB layers `[Sprint 2]` | US-3, US-12 | Medium |
| B-68 | Filesystem payload orphan cleanup on note delete `[Sprint 2]` | US-12 | Medium |
| B-69 | Plugin allowlist in config — reject unlisted plugins | US-4 | Medium |
| ~~B-70~~ | ~~Config tampering guard — deployment_mode switch requires CONFIRM~~ — **REMOVED** (no `deployment_mode` config in three-layer model) `[LOG 05-04]` | — | — |
| B-71 | Expand audit trail scope — login/logout/register/delete-account/migrate/export | US-6 | Medium |
| ~~B-72~~ | ~~Migration: alert user about encrypted notes, prompt passphrase per note, skip on mismatch~~ — **DROPPED** (depends on B-48; no migration) `[D-10]` | US-12 | — |
| B-73 | Document passphrase memory-residency limitation | US-2 | Low |
| B-74 | Plaintext `title` and `format` columns for fast listing (no blob parsing on list) `[Sprint 0 — D-10]` | US-1, US-12 | High |
| B-75 | Session token file permissions — restrict to creator + administrator only | US-11 | High |
| B-76 | Export binary notes: write raw payload file + path reference in manifest | US-8 | Medium |
| B-77 | Flat data directory — always `<data-dir>/` layout (no per-user subdirectories on device); `files/`, `exports/`, `audit.log` at root `[LOG 05-04]` | US-12 | Medium |
| B-78 | Export file permissions + `export --cleanup` command `[Sprint 3]` | US-8 | High |
| B-79 | Alias info warning for encrypted notes `[Sprint 3]` | US-2 | Medium |
| ~~B-80~~ | ~~Migration backup auto-delete after successful verification~~ — **DROPPED** (depends on B-48; no migration) `[D-10]` | US-12 | — |
| B-81 | Per-user audit log deletion on `delete-account` | US-6, US-11 | High |
| B-83 | Unit tests for PluginBase and PluginRegistry (closes test debt from B-18) | US-4 | High |
| B-27 | GUI layer — umbrella epic (see B-84/B-85 for Sprint 4 desktop CRUD; B-89/B-90 for Sprint 5 sync-enabled desktop client) | US-9, US-14 | Low |

### Sprint 4 — Personal GUI *(Planned)*

| ID | Description | US | Priority |
|----|-------------|----|----------|
| B-84 | PySide6 desktop GUI skeleton (ADR-13 decided) — `astranotes gui` launches `QApplication`; two-pane layout (note list + sync-status dot left, editor right); toolbar; passphrase `QDialog` | US-9 | High |
| B-85 | Desktop GUI: full CRUD screens — add, view, list, edit, delete notes with passphrase dialog for encrypted notes | US-9 | High |
| B-97 | System tray icon — minimize to tray on window close; tray menu: Show/Hide, Quit; `QSystemTrayIcon` + `QMenu`; tray icon visible only while app is running | US-9 | Medium |
| B-98 | GUI passphrase security level — `security_level` config key; `high` (default): clear passphrase from memory on note close, navigate away, app minimize, or focus loss — always re-prompt; `session`: clear only on app close — prompt once per app launch | US-9 | Medium |
| B-99 | Plugin manifest validation — `load_manifests()` reads `plugin.json` from each `plugins/` subdirectory; validates required fields (`plugin_id`, `name`, `version`, `engines`, `main`) with `jsonschema`; rejects manifest containing `is_official`; rejects missing or malformed manifests with warning; validates MIME ownership (no two active plugins own same type) `[REQ R4.11, R4.12]` `[D-12]` | US-4 | High |
| B-100 | Trust-tier enforcement in `PluginRegistry.register_plugin(plugin, is_official)` — `is_official` value injected from server-verified registry record only (never from manifest); `is_official = False` → `EditorProvider` only; `is_official = True` → `EditorProvider` + `PluginBase` hooks; violation blocked at `register_plugin()` time with warning `[REQ R4.13]` `[D-12]` | US-4, US-13 | High |
| B-101 | `AppController` orchestrator + `SessionManager` session lock — `AppController` owns `ConfigStore`, `DatabaseStore`, `SessionManager`, `DesktopGUI`; `SessionManager.acquire_lock()` writes `<data-dir>/.app.lock` (JSON: `pid`, `launched_at`); alive PID → block new session with error dialog; dead PID → overwrite (stale lock); `release_lock()` on clean exit; CLI startup also checks/sets lock to enforce one-session-per-account policy `[REQ R9.7]` `[D-13]` | US-9 | High |
| B-102 | Encrypted note idle auto-lock — `SessionManager.start_idle_timer(timeout_seconds=300)`; on any user interaction reset timer; on timeout auto-close open encrypted note, clear passphrase from memory, redisplay `[Encrypted]` placeholder; fires silently `[REQ R9.8]` `[D-13]` | US-9 | Medium |
### Sprint 5 — Sync Server + Sync-Enabled Desktop Client  *(Planned)*

| ID | Description | US | Priority |
|----|-------------|----|----------|
| B-86 | Sync server skeleton (FastAPI, ADR-11) — `POST /sync/push` and `GET /sync/pull?since=<ts>` endpoints; conflict detection delegated to desktop client (compare `modified_at` vs `synced_at`); no `note_conflicts` table `[LOG 05-04]` `[D-14 decided 2026-05-14]` | US-12, US-14 | High |
| B-87 | OAuth 2.0 / Google OpenID Connect integration (authlib, ADR-12) — provider callback, JWT issuance, extensible provider registry `[LOG 05-04]` | US-11, US-14 | High |
| B-88 | JWT / bearer token validation middleware — sync endpoints require valid JWT; return HTTP 401 without token `[LOG 05-04]` | US-11, US-14 | High |
| B-89 | PySide6 sync-enabled desktop client (Sprint 5) — login dialog (Google OAuth PKCE + local login), sync button wired to push/pull, sync-status dot per note row, Settings `QDialog` (sync server URL, account) | US-14 | High |
| B-90 | CLI `sync push` / `sync pull` commands + desktop GUI sync button — upload blobs newer than `synced_at`; merge pulled notes into local SQLite `[LOG 05-04]` | US-14 | Medium |
| ~~B-91~~ | ~~Offline resilience — superseded by Layer 1 SQLite always-on (R12.1); no write queue or local web server needed~~ `[LOG 05-04]` | ~~US-14~~ | ~~Dropped~~ |
| B-92 | HTTPS/TLS enforcement for sync server — reject plain HTTP connections | US-13, US-14 | High |
| B-93 | Concurrent request handling — SQLAlchemy connection pool configuration; load test with ≥ 10 simultaneous sync users | US-12, US-14 | High |
| B-94 | Per-account data isolation at sync layer — all queries scoped by `account_id` from JWT; cross-account access test `[LOG 05-04]` | US-11, US-14 | High |
| B-95 | Sync rate limiting — 60 req/min per account; return HTTP 429 with `Retry-After` header on excess `[LOG 05-04]` | US-13, US-14 | Medium |
| B-96 | `accounts` table (local SQLite): `account_id` (UUID PK), `username`, `password_hash`, `created_at`, `failed_attempts`, `locked_until` `[LOG 05-04]` | US-11, US-12 | High |
