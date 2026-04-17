# AstraNotes — Product Backlog

Items ordered by priority. Status reflects current state.

## Done

| ID | Item | User Story | Status |
|----|------|------------|--------|
| B-01 | Add unencrypted note via CLI | US-1 | Done |
| B-02 | Add encrypted note with passphrase prompt | US-2 | Done |
| B-03 | Reject empty title/content on add | US-1 | Done |
| B-04 | Get unencrypted note by ID | US-1 | Done |
| B-05 | Get encrypted note with correct passphrase | US-2 | Done |
| B-06 | Reject wrong passphrase on get | US-2 | Done |
| B-07 | List notes with encrypted content hidden | US-1, US-2 | Done |
| B-08 | Update unencrypted note | US-1 | Done |
| B-09 | Update encrypted note with passphrase | US-2 | Done |
| B-10 | Reject wrong passphrase on update | US-2 | Done |
| B-11 | Delete unencrypted note | US-1 | Done |
| B-12 | Delete encrypted note with passphrase | US-2 | Done |
| B-13 | Reject wrong passphrase on delete | US-2 | Done |
| B-14 | Error handling for missing note IDs | US-1 | Done |
| B-15 | JSON persistence with save-on-mutate | US-3 | Done |
| B-16 | Preserve encrypted records on no-key load | US-3 | Done |
| B-17 | AES-256-GCM encryption with PBKDF2 | US-2 | Done |
| B-18 | Plugin base class and registry | US-4 | Done |
| B-19 | `--data-dir` global option | US-1 | Done |
| B-20 | BDD test coverage (17 scenarios) | US-1–US-4 | Done |
| B-21 | Unit tests for core modules (16 tests) | US-1–US-3 | Done |
| B-22 | Stress test for 1001 notes | US-3 | Done |
| B-23 | Non-zero exit codes on CLI errors | US-1 | Done |

## Backlog (Not Started)

| ID | Item | User Story | Priority |
|----|------|------------|----------|
| B-31 | Fix ID collision: use UUID or max-ID+1 | US-1 | High |
| B-32 | Passphrase confirmation prompt on encrypt | US-2 | High |
| B-33 | Fix unencrypted update/delete corrupting encrypted notes | US-2 | High |
| B-34 | Reject empty/short passphrase (min 8 chars) | US-2 | High |
| B-35 | Corrupt JSON recovery with `.bak` backup | US-1, US-3 | High |
| B-36 | `--data-dir` validation (must be directory, writable) | US-1 | Medium |
| B-37 | Plugin discovery and loading from `plugins/` | US-4 | Medium |
| B-38 | Plugin error isolation (try/except in hook dispatch) | US-4 | Medium |
| B-39 | File permission error handling with friendly messages | US-3 | Medium |
| B-40 | BDD + unit tests for new edge cases | US-1–US-3 | Medium |
| B-24 | Override policy: red warning + `CONFIRM OVERRIDE` for plugin overrides | US-5 | Medium |
| B-25 | Audit trail: JSON-per-line log with structured fields and filters | US-6 | Medium |
| B-26 | Config module: known-key whitelist with `set`/`get`/`list`/`reset` | US-7 | Medium |
| B-28 | Plugin CLI commands wired into main CLI | US-4 | Medium |
| B-29 | Substring search with `--encrypted` flag | US-8 | Low |
| B-30 | Export to text/JSON with `--output` and `--encrypted` | US-8 | Low |
| B-41 | Deployment mode selection (personal vs server) first-launch prompt | US-10 | High |
| B-42 | SQLite backend for personal mode | US-12 | High |
| B-43 | Sandbox binary storage: length-prefixed blob (header + raw payload) | US-12, US-2 | High |
| B-44 | PostgreSQL backend for server mode | US-12 | Medium |
| B-45 | User registration and bcrypt password hashing | US-11 | Medium |
| B-46 | Login/logout session management | US-11 | Medium |
| B-47 | User isolation — scope all queries by user_id | US-11 | Medium |
| B-48 | `migrate` CLI command: JSON → database migration (sandbox repackaging) | US-12 | Medium |
| B-49 | Hybrid storage: 5 MB threshold, encrypted-only filesystem payloads | US-12 | High |
| B-50 | Mode switch with `CONFIRM MODE SWITCH` safety gate | US-10 | Low |
| B-51 | Parameterized queries via SQLAlchemy ORM — no raw SQL | US-12 | High |
| B-52 | Input validation: reject null bytes and control characters at CLI boundary | US-1, US-11 | High |
| B-53 | Least-privilege PostgreSQL role (no DDL) | US-12 | Medium |
| B-54 | Strip ANSI/control codes from terminal output | US-1 | Medium |
| B-55 | Path traversal prevention for --data-dir, --output, filesystem payloads | US-1, US-12 | Medium |
| B-56 | Plugin sandboxing — read-only note copies, no exec/eval, no raw DB access | US-4 | Medium |
| B-57 | Interactive auth prompts (hide_input=True) — never accept password as CLI arg | US-11 | High |
| B-58 | Auth rate limiting — 5 failures → 5-min lockout per username | US-11 | High |
| B-59 | Session token file with 24h expiry at `<data-dir>/.session` | US-11 | High |
| B-60 | Username validation — 3–32 chars, alphanumeric + underscore, case-insensitive | US-11 | Medium |
| B-61 | Account deletion with full per-user directory purge (notes, payloads, audit logs, exports) | US-11 | Medium |
| B-62 | Passphrase rotation via `reencrypt <note_id>` (includes filesystem payload re-encryption) | US-2 | Medium |
| B-63 | PostgreSQL `sslmode=require` enforcement | US-12 | High |
| B-64 | `DATABASE_URL` env-var only — never stored in config.json | US-12 | High |
| B-65 | Alembic schema versioning for database migrations | US-12 | Medium |
| B-66 | SQLite WAL mode + retry logic for concurrent access | US-12 | Medium |
| B-67 | Disk-full (`ENOSPC`) error handling at JSON and DB layers | US-3, US-12 | Medium |
| B-68 | Filesystem payload orphan cleanup on note delete | US-12 | Medium |
| B-69 | Plugin allowlist in config — reject unlisted plugins | US-4 | Medium |
| B-70 | Config tampering guard — deployment_mode switch requires CONFIRM | US-10 | Medium |
| B-71 | Expand audit trail scope — login/logout/register/delete-account/migrate/export | US-6 | Medium |
| B-72 | Migration: alert user about encrypted notes, prompt passphrase per note, skip on mismatch | US-12 | Medium |
| B-73 | Document passphrase memory-residency limitation | US-2 | Low |
| B-74 | Plaintext `title` and `format` columns for fast listing (no blob parsing on list) | US-1, US-12 | High |
| B-75 | Session token file permissions — restrict to creator + administrator only | US-11 | High |
| B-76 | Export binary notes: write raw payload file + path reference in manifest | US-8 | Medium |
| B-77 | Per-user data directories with hashed user IDs (server mode) | US-11, US-12 | High |
| B-78 | Export file permissions + `export --cleanup` command | US-8 | High |
| B-79 | Alias info warning for encrypted notes | US-2 | Medium |
| B-80 | Migration backup auto-delete after successful verification | US-12 | Medium |
| B-81 | Per-user audit log deletion on `delete-account` | US-6, US-11 | High |
| B-27 | GUI layer (deferred epic) | US-9 | Low |
