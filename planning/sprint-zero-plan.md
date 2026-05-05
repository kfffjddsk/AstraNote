# AstraNotes — Sprint Zero Plan

## Goal
Establish project foundation: architecture, tooling, tests, docs, agreements.

## Duration
1 sprint (1 week)

## Deliverables

### 1. Project Setup
- [x] Python project structure (`src/`, `tests/`, `plugins/`, `docs/`)
- [x] Virtual environment with pinned dependencies (`requirements.txt`)
- [x] `pytest.ini` configured with test paths and markers

### 2. Core Architecture
- [x] `Note` data model with timestamps, metadata, encryption flag
- [x] `NoteStore` for JSON-based persistence with save-on-mutate
- [x] `EncryptionEngine` (AES-256-GCM) and `KeyManager`
- [x] `PluginBase` and `PluginRegistry` for hook-based extensibility

### 3. CLI Foundation
- [x] Click-based CLI with `add`, `get`, `list`, `update`, `delete`
- [x] Global `--data-dir` option
- [x] Input validation and non-zero exit codes on errors

### 4. Testing Infrastructure
- [x] `conftest.py` with shared fixtures (runner, temp dir, cli_app)
- [x] BDD feature files for all CRUD + encryption scenarios (17 scenarios)
- [x] Unit tests for core modules (16 tests)
- [x] Bounded stress test (1001 notes)
- [x] `test_all.py` runner (unit + BDD pillars)

### 5. Documentation & Process
- [x] Working Agreement in `Copilot/`
- [x] Definition of Done in `Copilot/`
- [x] BDD testing guide in `docs/`
- [x] Test workflow in `docs/`
- [x] Git pushing rules and writing style norms

### 6. Planning Artifacts
- [x] Requirements (`planning/requirements.md`)
- [x] User stories with acceptance criteria (`planning/user-stories.md`)
- [x] Product backlog (`planning/backlog.md`)
- [x] Sprint zero plan (`planning/sprint-zero-plan.md`)

## Exit Criteria
- 33 tests pass (`pytest -v`).
- `test_all.py` green.
- Clean working tree, all pushed.
- B-01 through B-23 done.
- Agreements and planning docs committed.

## Next Sprint Candidates
*B-24, B-25, B-28 were originally flagged here. Sprint 1 was reoriented to critical bug fixes (B-31–B-40) first. B-24, B-25, B-28 are deferred to Sprint 3 after database and auth infrastructure (Sprint 2) is in place. See Sprint 3 Plan below.*

---

# Sprint 1 Plan

## Goal
Fix critical bugs, harden edge cases, integrate plugin system.

## Duration
1 sprint (1 week)

## Items
- B-31: Fix ID collision — use UUID or max-ID+1
- B-32: Passphrase confirmation prompt on encrypt
- B-33: Fix unencrypted update/delete corrupting encrypted notes
- B-34: Reject empty/short passphrase (min 8 chars)
- B-35: Corrupt JSON recovery with `.bak` backup
- B-37: Plugin discovery and loading from `plugins/`
- B-38: Plugin error isolation (try/except in hook dispatch)
- B-36: `--data-dir` validation (must be directory, writable)
- B-39: File permission error handling with friendly messages
- B-40: BDD + unit tests for new edge cases (B-31–B-39 scenarios)
- B-83: Unit tests for PluginBase and PluginRegistry *(closes test debt from B-18)*

## Exit Criteria
- No ID collision after any deletion sequence
- Passphrase confirmed on encrypt; empty/short rejected
- Unencrypted operations don't corrupt encrypted notes
- Corrupt JSON → backup + empty store + warning
- Plugins load from `plugins/`, hook errors isolated
- `--data-dir` validated; permission errors caught
- All new edge cases covered by BDD or unit tests
- All existing 33 tests still pass

---

# Sprint 2 Plan

## Goal
Introduce SQLite local store with optional account layer, database backend with sandbox binary storage, opt-in authentication, and injection prevention.  `[LOG 05-04]`

## Duration
1 sprint (1 week)

## Items
- B-41: First-login anonymous note association prompt — one-time, Yes / No / Ask me for each `[LOG 05-04]`
- B-42: SQLite local store — always-on; `account_id` nullable FK + `synced_at` nullable timestamp on `notes` table `[LOG 05-04]`
- B-43: Sandbox binary storage — length-prefixed blob (header + raw payload)
- B-44: PostgreSQL backend for sync server (`DATABASE_URL` env var, `sslmode=require`) `[LOG 05-04]`
- B-45: User registration with bcrypt password hashing
- B-46: Login/logout session management (token file, 24h expiry)
- B-47: Account isolation — scope queries by `account_id`; anonymous notes visible when logged out `[LOG 05-04]`
- B-48: `migrate` CLI command: JSON → database migration (prompt per encrypted note)
- B-49: Hybrid storage: 5 MB threshold, encrypted-only filesystem payloads
- B-51: Parameterized queries via SQLAlchemy ORM
- B-57: Interactive auth prompts (hide_input=True)
- B-58: Auth rate limiting — 5 failures → 5-min lockout
- B-59: Session token file with 24h expiry
- B-60: Username validation rules
- B-63: PostgreSQL `sslmode=require` enforcement
- B-64: `DATABASE_URL` env-var only
- B-65: Alembic schema versioning
- B-66: SQLite WAL mode + retry logic for concurrent access
- B-74: Plaintext `title` + `format` columns for fast listing
- B-75: Session token file permissions (owner only) `[LOG 05-04]`
- B-52: Input validation: reject null bytes and control characters at CLI boundary
- B-77: Flat data directory — always `<data-dir>/` layout; no per-user subdirectories `[LOG 05-04]`
- B-78: Export file permissions + `export --cleanup` command
- B-79: Alias info warning for encrypted notes
- B-80: Migration backup auto-delete after successful verification
- B-81: On `delete-account`: set `account_id = NULL` on local notes; delete server record `[LOG 05-04]`
- B-96: `accounts` table (local SQLite): `account_id` UUID PK, `username`, `password_hash`, etc. `[LOG 05-04]`

## Exit Criteria
- App starts and all CRUD operations work with no login or configuration required `[LOG 05-04]`
- SQLite always-on (WAL mode); `account_id` nullable; `synced_at` nullable on `notes` table `[LOG 05-04]`
- Sandbox binary storage: notes stored as length-prefixed blobs; encrypted notes are AES-256-GCM ciphertext; `account_id`, `note_id`, `is_encrypted`, `nonce`, `salt`, `title`, `format`, `payload_location`, `synced_at` in plaintext columns `[LOG 05-04]`
- `title` and `format` columns enable fast listing without blob parsing
- Filesystem storage only for encrypted notes >5 MB; no plaintext files on disk
- `register`/`login` available but optional; interactive prompts; bcrypt hashing verified
- Session token file permissions restricted to owner only `[LOG 05-04]`
- Auth rate limiting: 5 failed logins → 5-min lockout; session tokens expire at 24h
- Username validation enforced (3–32 chars, alphanum + underscore, case-insensitive)
- Expired session blocks sync only; local CRUD unaffected `[LOG 05-04]`
- First-login anonymous note association prompt shown once if anonymous notes exist `[LOG 05-04]`
- `migrate` command: alerts user about encrypted notes; prompts passphrase per note; skips on mismatch; JSON backed up
- All DB queries parameterized via SQLAlchemy; no raw SQL
- `DATABASE_URL` from env var only; never in config.json
- Alembic manages schema version
- Flat data directory: `<data-dir>/files/`, `exports/`, `audit.log` (no per-user subdirs) `[LOG 05-04]`
- `delete-account` sets `account_id = NULL` on local notes; warns cloud copies deleted `[LOG 05-04]`
- Export files have restricted permissions; `export --cleanup` available
- Alias info message displayed when user sets alias on encrypted note
- All existing 33 tests still pass

---

# Sprint 3 Plan

## Goal
Complete plugin system hardening, add override policy and audit trail, wire plugin CLI commands, and close remaining security backlog items from Sprint 2 scope.

## Duration
1 sprint (1 week)

## Items
- B-24: Override policy — red warning + `CONFIRM OVERRIDE` for plugin overrides (US-5)
- B-25: Audit trail — JSON-per-line log with structured fields and `audit` CLI filters (US-6)
- B-28: Plugin CLI commands wired into main CLI (US-4)
- B-26: Config module — known-key whitelist with `set`/`get`/`list`/`reset` (US-7)
- B-53: Least-privilege PostgreSQL role — no DDL in application role (US-12, US-13)
- B-54: Strip ANSI/control codes from terminal output (US-1, US-13)
- B-55: Path traversal prevention for `--data-dir`, `--output`, filesystem payloads (US-1, US-12, US-13)
- B-56: Plugin sandboxing — read-only note copies, no exec/eval, no raw DB access (US-4, US-13)
- B-62: Passphrase rotation via `reencrypt <note_id>` (US-2)
- B-69: Plugin allowlist in config — reject unlisted plugins (US-4)
- B-70: ~~Config tampering guard — deployment_mode switch requires CONFIRM (US-10)~~ — **REMOVED** (no mode-switching concept) `[LOG 05-04]`
- B-71: Expand audit trail scope — login/logout/register/delete-account/migrate/export (US-6)
- B-73: Document passphrase memory-residency limitation (US-2)
- B-76: Export binary notes — write raw payload file + path reference in manifest (US-8)

## Exit Criteria
- Override policy triggers on plugin `overrides` declaration; red warning displayed; `CONFIRM OVERRIDE` required; all attempts logged
- Audit trail writes JSON-per-line entries for all listed operations; `audit --limit`, `--operation`, `--since` filters work
- Plugin CLI commands load and appear in `--help` output; plugin errors isolated
- Config module supports all known keys; free-form keys rejected; defaults applied on missing config
- ANSI codes stripped from terminal output
- Path traversal rejected for all file path inputs
- Plugin sandboxing enforced at hook dispatch
- All existing tests still pass; new tests cover Sprint 3 behavior; new tests cover deployment modes, auth, and injection prevention

---

# Sprint 4 Plan — Personal GUI *(Planned)*

## Goal
Deliver a minimal desktop or local-web GUI for personal users that reuses the existing core modules (no logic duplication) and has a clean, task-focused design comparable to mainstream note apps.

## Duration
1 sprint (1 week)

## Decision Gate (before sprint start)
- ADR-13 decided: **PySide6 desktop app** (see `docs/design.md` ADR-13) `[LOG 05-04]`

## Items
- B-84: Personal GUI framework decision (ADR-13) + project skeleton (US-9)
- B-85: Personal GUI CRUD screens — add, view, list, edit, delete with passphrase modal (US-9)

## Exit Criteria
- GUI launches without server dependency; uses SQLite personal-mode backend via `NoteStore`
- Full CRUD works through the GUI; all operations produce identical data effects as CLI equivalents
- Passphrase dialog appears for encrypted notes; passphrase is not stored by the GUI layer
- All existing core-module tests continue to pass; at least 5 GUI-level integration tests added
- ADR-13 recorded in `docs/design.md`

---

# Sprint 5 Plan — Sync Server + Sync-Enabled Desktop Client  *(Planned)*  `[LOG 05-04]`

## Goal
Deliver optional cloud sync: a FastAPI push/pull sync server and PySide6 sync-enabled desktop client with Google OAuth login.  `[LOG 05-04]`

## Duration
2 sprints (2 weeks) — Sync Server in Sprint 5A, Desktop Sync UI + OAuth in Sprint 5B

## Decision Gates (before sprint start)
- ADR-11 decided: **FastAPI** (sync server framework) `[LOG 05-04]`
- ADR-12 decided: **authlib + Google OIDC** (OAuth/SSO provider) `[LOG 05-04]`
- ADR-13 decided: **PySide6 desktop app** (GUI for Sprint 4 + Sprint 5; sync features gated by session token) `[LOG 05-04]`

## Items — Sprint 5A (Sync Server)
- B-86: Sync server skeleton (FastAPI) — `POST /sync/push` and `GET /sync/pull?since=<ts>` endpoints; conflict table `[LOG 05-04]`
- B-88: JWT / bearer token validation middleware — sync endpoints require valid JWT; HTTP 401 otherwise (US-11, US-14)
- B-92: HTTPS/TLS enforcement — reject plain HTTP connections (US-13, US-14)
- B-93: Concurrent request handling — SQLAlchemy connection pool; load test ≥ 10 simultaneous sync users (US-12, US-14)
- B-94: Per-account data isolation at sync layer — queries scoped by `account_id`; cross-account access regression test `[LOG 05-04]`
- B-95: Rate limiting — 60 sync req/min per account; HTTP 429 with `Retry-After` on excess `[LOG 05-04]`

## Items — Sprint 5B (Desktop Sync UI + OAuth)
- B-87: OAuth 2.0 / Google OIDC integration via authlib — provider callback, JWT issuance, extensible provider registry `[LOG 05-04]`
- B-89: PySide6 sync-enabled desktop client — login dialog (Google OAuth PKCE + local login), sync button, sync-status indicators (US-14)
- B-90: `sync push` / `sync pull` CLI commands + GUI sync button — upload blobs newer than `synced_at`; merge pulled notes into local SQLite `[LOG 05-04]`
- B-91: ~~Offline resilience~~ (dropped — superseded by Layer 1 SQLite always-on; no write queue needed) `[LOG 05-04]`

## Exit Criteria
- `sync push` sends all account-associated notes newer than `synced_at` to sync server; `sync pull` fetches and merges; both update `synced_at` on success `[LOG 05-04]`
- Conflict: last-write-wins by `modified_at`; both versions in `note_conflicts` table for 30 days `[LOG 05-04]`
- Google OAuth login flow works end-to-end in the desktop app (system browser opens for consent; redirect captured on ephemeral localhost callback); JWT issued and validated by authlib `[LOG 05-04]`
- Desktop app sync button triggers push/pull when a valid session token is present
- All sync server traffic served over HTTPS; plain HTTP rejected
- All previous tests still pass; sync endpoint test coverage ≥ 80 % of routes
- ADR-11, ADR-12, ADR-13 recorded in `docs/design.md` (already done `[LOG 05-04]`)
