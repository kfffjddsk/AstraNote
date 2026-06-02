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
| B-16 | Preserve encrypted records on no-key load | US-3 | High | ✅ Done |
| B-17 | AES-256-GCM encryption with PBKDF2 | US-2 | High | ✅ Done |
| B-18 | Plugin base class and registry | US-4 | High | ✅ Done |
| B-20 | BDD test coverage (17 scenarios) | US-1–US-4 | High | ✅ Done |
| B-21 | Unit tests for core modules (23 tests) | US-1–US-3 | High | ✅ Done |
| B-22 | Stress test for 1001 notes | US-3 | High | ✅ Done |
| B-42 | SQLite local store — `DatabaseStore` with `notes.db`, nullable `account_id` | US-12 | High | ✅ Done |
| B-43 | `BlobCodec` encode/encrypt pipeline; `DatabaseStore` add/get/update/delete/list | US-12, US-2 | High | ✅ Done |
| B-51 | Parameterized queries via SQLAlchemy ORM — no raw SQL | US-12, US-13 | High | ✅ Done |
| B-74 | Plaintext `title` column for fast listing (no blob parsing on list) | US-1, US-12 | High | ✅ Done |
| B-31 | UUID-based note IDs — `uuid4()` in `Note.create()` (no ID collision) | US-1 | High | ✅ Done (Sprint 0) |
| B-33 | Co-existence invariant: unencrypted ops do not corrupt encrypted notes | US-2 | High | ✅ Done (Sprint 0) |
| B-34 | Passphrase min-length enforcement (8 chars) in `KeyManager` | US-2 | High | ✅ Done (Sprint 0) |
| B-38 | Plugin error isolation — try/except per handler in `PluginRegistry.call_hook()` | US-4 | Medium | ✅ Done (Sprint 0) |

---

## Sprint 1 — Done ✅

> **Goal:** Wire Click CLI, fix remaining edge cases, and harden plugin integration. Items B-19 and B-23 were Sprint 0 scope, deferred because CLI was not implemented in Sprint 0. Completed May 2026 — 140 tests, 99% branch coverage on core modules.

| ID | Item | User Story | Priority | Status |
|----|------|------------|----------|--------|
| B-19 | `--data-dir` global option *(deferred from Sprint 0)* | US-1 | High | ✅ Done |
| B-23 | Non-zero exit codes on CLI errors *(deferred from Sprint 0)* | US-1 | High | ✅ Done |
| B-32 | Passphrase confirmation prompt on encrypt | US-2 | High | ✅ Done |
| B-36 | `--data-dir` validation (must be directory, writable) | US-1 | Medium | ✅ Done |
| B-37 | Plugin discovery and loading from `plugins/` | US-4 | Medium | ✅ Done |
| B-39 | File permission error handling with friendly messages | US-3 | Medium | ✅ Done |
| B-40 | BDD + unit tests for new edge cases (B-32, B-36, B-37, B-39, B-52 scenarios) | US-1–US-4 | Medium | ✅ Done |
| B-52 | Input validation: reject null bytes and control characters at CLI boundary | US-1, US-11, US-13 | High | ✅ Done |
| B-65 | Alembic schema versioning for database migrations `[D-10]` | US-12 | Medium | ✅ Done |
| B-66 | SQLite WAL mode + retry logic for concurrent access `[D-10]` | US-12 | Medium | ✅ Done |
| B-83 | Unit tests for PluginBase and PluginRegistry (closes test debt from B-18) | US-4 | High | ✅ Done |

---

## Sprint 2 — Done ✅

> **Goal:** Opt-in account layer, session management, and auth hardening. Completed May 2026 — 246 tests total (106 new Sprint 2 tests + 3 bug-regression tests + 8 branch-coverage tests), 1 skipped (POSIX permission test, Windows-only skip). 100% branch coverage on all core modules.

| ID | Item | User Story | Priority | Status |
|----|------|------------|----------|--------|
| B-41 | First-login anonymous note association prompt `[LOG 05-04]` | US-10 | High | ✅ Done |
| B-45 | User registration and bcrypt password hashing | US-11 | Medium | ✅ Done |
| B-46 | Login/logout session management | US-11 | Medium | ✅ Done |
| B-47 | User isolation — scope queries by `account_id` `[LOG 05-04]` | US-11 | Medium | ✅ Done |
| B-49 | Hybrid storage: 5 MB threshold, encrypted-only filesystem payloads | US-12 | High | ✅ Done |
| B-57 | Interactive auth prompts (hide_input=True) — never accept password as CLI arg | US-11 | High | ✅ Done |
| B-58 | Auth rate limiting — 5 failures → 5-min lockout per username | US-11 | High | ✅ Done |
| B-59 | Session token file with 24h expiry at `<data-dir>/.session` | US-11 | High | ✅ Done |
| B-60 | Username validation — 3–32 chars, alphanumeric + underscore, case-insensitive | US-11 | Medium | ✅ Done |
| B-61 | Account deletion: set `account_id = NULL` on local notes; delete server record; warn user `[LOG 05-04]` | US-11 | Medium | ✅ Done |
| B-64 | `DATABASE_URL` env-var only — never stored in config.json | US-12, US-13 | High | ✅ Done |
| B-67 | Disk-full (`ENOSPC`) error handling at DB and filesystem layers | US-3, US-12 | Medium | ✅ Done |
| B-68 | Filesystem payload orphan cleanup on note delete | US-12 | Medium | ✅ Done |
| B-75 | Session token file permissions — restrict to creator + administrator only | US-11 | High | ✅ Done |
| B-77 | Flat data directory — always `<data-dir>/` layout `[LOG 05-04]` | US-12 | Medium | ✅ Done |
| B-81 | Per-user audit log deletion on `delete-account` | US-6, US-11 | High | ✅ Done |
| B-96 | `accounts` table (local SQLite): `account_id` UUID PK, `username`, `password_hash`, `failed_attempts`, `locked_until` `[LOG 05-04]` | US-11, US-12 | High | ✅ Done |

---

## Sprint 3 — ✅ Done

> **Goal:** Plugin hardening, audit trail, config module, search, and export. Completed May 2026 — 396 tests passing (397 collected, 1 skipped). BDD: 30 scenarios across 8 feature files. Key design refinement: `DatabaseStore.search()` never exposes encrypted blobs; `--encrypted` flag prompts passphrase **per note** (each note may have a different passphrase).

| ID | Item | User Story | Priority | Status |
|----|------|------------|----------|--------|
| B-24 | Override policy: red warning + `CONFIRM OVERRIDE` for plugin overrides | US-5 | Medium | ✅ Done |
| B-25 | Audit trail: JSON-per-line log with structured fields and filters | US-6 | Medium | ✅ Done |
| B-26 | Config module: known-key whitelist with `set`/`get`/`list`/`reset` | US-7 | Medium | ✅ Done |
| B-28 | Plugin CLI commands wired into main CLI | US-4 | Medium | ✅ Done |
| B-29 | Substring search with `--encrypted` flag | US-8 | Low | ✅ Done |
| B-30 | Export to text/JSON with `--output` and `--encrypted` | US-8 | Low | ✅ Done |
| B-54 | Strip ANSI/control codes from terminal output | US-1, US-13 | Medium | ✅ Done |
| B-55 | Path traversal prevention for `--data-dir`, `--output`, filesystem payloads | US-1, US-12, US-13 | Medium | ✅ Done |
| B-56 | Plugin sandboxing — read-only note copies, no exec/eval, no raw DB access | US-4, US-13 | Medium | ✅ Done |
| B-62 | Passphrase rotation via `reencrypt <note_id>` | US-2 | Medium | ✅ Done |
| B-69 | Plugin allowlist in config — reject unlisted plugins | US-4 | Medium | ✅ Done |
| B-71 | Expand audit trail scope — login/logout/register/delete-account/export | US-6 | Medium | ✅ Done |
| B-73 | Document passphrase memory-residency limitation | US-2 | Low | ✅ Done |
| B-76 | Export binary notes: write raw payload file + path reference in manifest | US-8 | Medium | ✅ Done |
| B-78 | Export file permissions + `export --cleanup` command | US-8 | High | ✅ Done |
| B-79 | Alias info warning for encrypted notes | US-2 | Medium | ✅ Done |

---

## Sprint 4 — Personal GUI *(Planned)*

> **Goal:** PySide6 desktop GUI for personal use (ADR-13). See [Sprint 4 Plan](sprint-zero-plan.md).

| ID | Description | US | Priority |
|----|-------------|----|----------|
| B-27 | GUI layer — umbrella epic (B-84/B-85 Sprint 4 CRUD; B-89/B-90 Sprint 5 sync) | US-9, US-14 | Low |
| B-84 | PySide6 desktop GUI skeleton — `astranotes gui` → `AppController` → `QApplication`; two-pane layout; passphrase `QDialog` `[ADR-13]` `[D-13]` | US-9 | High |
| B-85 | Desktop GUI: full CRUD screens with passphrase dialog for encrypted notes | US-9 | High |
| B-97 | System tray icon — minimize to tray; `QSystemTrayIcon` + `QMenu` (Show/Hide, Quit) | US-9 | Medium |
| B-98 | GUI passphrase security level — `security_level` config key; `high` (default) / `session` modes | US-9 | Medium |
| B-99 | Plugin manifest validation — `load_manifests()`; validates required fields; rejects `is_official` in manifest `[REQ R4.11, R4.12]` `[D-12]` | US-4 | High |
| B-100 | Trust-tier enforcement in `PluginRegistry.register_plugin()` — `is_official` server-injected only `[REQ R4.13]` `[D-12]` | US-4, US-13 | High |
| B-101 | `AppController` + `SessionManager` PID lock file — session exclusivity; stale lock overwritten `[REQ R9.7]` `[D-13]` | US-9 | High |
| B-102 | Encrypted note idle auto-lock — 5-min `QTimer`; clears passphrase on timeout `[REQ R9.8]` `[D-13]` | US-9 | Medium |

---

## Sprint 5A — Sync Server *(Planned)*

> **Goal:** FastAPI push/pull sync server with PostgreSQL backend (ADR-11). See [Sprint 5 Plan](sprint-zero-plan.md).

| ID | Description | US | Priority |
|----|-------------|----|----------|
| B-44 | PostgreSQL backend for sync server (`DATABASE_URL` env var) `[LOG 05-04]` | US-12 | Medium |
| B-53 | Least-privilege PostgreSQL role (no DDL) | US-12, US-13 | Medium |
| B-63 | PostgreSQL `sslmode=require` enforcement | US-12, US-13 | High |
| B-86 | Sync server skeleton (FastAPI) — `POST /sync/push` and `GET /sync/pull?since=<ts>`; conflict detection on client `[LOG 05-04]` `[D-14]` | US-12, US-14 | High |
| B-88 | JWT / bearer token validation middleware — HTTP 401 without valid token `[LOG 05-04]` | US-11, US-14 | High |
| B-92 | HTTPS/TLS enforcement — reject plain HTTP connections | US-13, US-14 | High |
| B-93 | Concurrent request handling — SQLAlchemy connection pool; load test ≥ 10 users | US-12, US-14 | High |
| B-94 | Per-account data isolation at sync layer — queries scoped by `account_id` from JWT `[LOG 05-04]` | US-11, US-14 | High |
| B-95 | Sync rate limiting — 60 req/min per account; HTTP 429 with `Retry-After` `[LOG 05-04]` | US-13, US-14 | Medium |

---

## Sprint 5B — Desktop Sync UI + OAuth *(Planned)*

> **Goal:** Sync-enabled PySide6 client with Google OAuth login (ADR-12). See [Sprint 5 Plan](sprint-zero-plan.md).

| ID | Description | US | Priority |
|----|-------------|----|----------|
| B-87 | OAuth 2.0 / Google OIDC integration (authlib) — provider callback, JWT issuance `[LOG 05-04]` | US-11, US-14 | High |
| B-89 | PySide6 sync-enabled desktop client — login dialog (Google OAuth PKCE + local login), sync button `[LOG 05-04]` | US-14 | High |
| B-90 | CLI `sync push` / `sync pull` + GUI sync button; updates `synced_at` on success `[LOG 05-04]` | US-14 | Medium |
| ~~B-91~~ | ~~Offline resilience — write queue + local web server~~ — **DROPPED** (superseded by Layer 1 SQLite always-on) `[LOG 05-04]` | — | — |
