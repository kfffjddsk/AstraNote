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
- B-24: Override policy (US-5)
- B-25: Audit trail (US-6)
- B-28: Plugin CLI commands (US-4)

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
- B-40: BDD + unit tests for new edge cases

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
Introduce deployment modes, database backend with sandbox binary storage, server-mode authentication, and injection prevention.

## Duration
1 sprint (1 week)

## Items
- B-41: Deployment mode selection (personal vs server) first-launch prompt
- B-42: SQLite backend for personal mode (WAL mode enabled)
- B-43: Sandbox binary storage — length-prefixed blob (header + raw payload)
- B-44: PostgreSQL backend for server mode
- B-45: User registration with bcrypt password hashing
- B-46: Login/logout session management (token file, 24h expiry)
- B-47: User isolation — scope all queries by user_id
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
- B-75: Session token file permissions (creator + admin only)
- B-52: Input validation: reject null bytes and control characters at CLI boundary
- B-77: Per-user data directories with hashed user IDs (server mode)
- B-78: Export file permissions + `export --cleanup` command
- B-79: Alias info warning for encrypted notes
- B-80: Migration backup auto-delete after successful verification
- B-81: Per-user audit log deletion on `delete-account`

## Exit Criteria
- First launch prompts for deployment mode; choice persisted in config
- Personal mode uses SQLite (WAL mode); server mode uses PostgreSQL (`sslmode=require`)
- Sandbox binary storage: notes stored as length-prefixed blobs `[header_length][JSON header][raw payload]`; encrypted notes are AES-256-GCM ciphertext; only `note_id`, `user_id`, `is_encrypted`, `nonce`, `salt`, `title`, `format`, `payload_location` in plaintext columns
- `title` and `format` columns enable fast listing without blob parsing
- Filesystem storage only for encrypted notes >5 MB; no plaintext files on disk
- Server mode: register/login/logout with interactive prompts; bcrypt hashing verified
- Session token file permissions restricted to creator + administrator
- Auth rate limiting: 5 failed logins → 5-min lockout; session tokens expire at 24h
- Username validation enforced (3–32 chars, alphanum + underscore, case-insensitive)
- All queries scoped by user_id in server mode; cross-user access impossible
- `migrate` command: alerts user about encrypted notes; prompts passphrase per note; skips on mismatch; JSON backed up
- All DB queries parameterized via SQLAlchemy; no raw SQL
- `DATABASE_URL` from env var only; never in config.json
- Alembic manages schema version
- Server mode: per-user data directories (`<data-dir>/users/<hashed_uid>/`) with audit log, files, and exports isolation
- `delete-account` purges entire per-user directory (audit logs, payloads, exports)
- Export files have restricted permissions; `export --cleanup` available
- Alias info message displayed when user sets alias on encrypted note
- `migrate` command: after successful migration, prompt to delete backup; auto-deleted if confirmed
- All existing tests still pass; new tests cover deployment modes, auth, and injection prevention
