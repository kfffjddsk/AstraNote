# Working Log — 2026-04-15

## Summary
Deployment architecture design, database backend planning, sandbox binary storage model, injection prevention, full planning review and hardening pass.

## Key Decisions

### Deployment Modes (US-10)
- Two modes: **Personal** (single-user, SQLite, no login) and **Server** (multi-user, PostgreSQL, login required).
- Mode selected on first launch; stored in config under `deployment_mode`.
- Mode switch requires typed `CONFIRM MODE SWITCH` with data migration warning.

### Database Backend (US-12)
- Personal mode: SQLite at `<data-dir>/notes.db` with WAL mode + retry logic.
- Server mode: PostgreSQL via `DATABASE_URL` env var only (never in config to prevent credential leakage). Connection requires `sslmode=require`.
- Schema: `notes` table (`note_id`, `user_id`, `encrypted_blob`, `nonce`, `salt`, `is_encrypted`), `users` table (server mode only, with `failed_attempts` and `locked_until` for rate limiting).
- Schema versioned via Alembic.
- `migrate` CLI command converts `notes.json` → database with backup.

### Sandbox Binary Storage (R2.9, R14.3–R14.9)
- Previous model encrypted title and content independently, leaving timestamps, tags, and format type in plaintext — metadata leak.
- Intermediate model packed fields into a JSON blob — but treated content as UTF-8 strings, couldn't handle binary natively.
- **Final model: content-agnostic binary sandbox.** All note data treated as a raw bitstream regardless of original format. Uses length-prefixed framing: `[4-byte header_length][JSON header][raw payload bytes]`.
  - Header (JSON): `title`, `timestamps`, `tags`, `format` (MIME type), `original_filename`, `size_bytes`.
  - Payload: raw content bytes (UTF-8 text, audio, video, image, etc.).
  - Encrypted notes: entire framed blob encrypted with AES-256-GCM.
  - Unencrypted notes: framed blob stored as-is.
- **Retrieval:** decrypt → parse header. `text/*` → display as plaintext in terminal. Binary formats → write payload to `<data-dir>/exports/<original_filename>`, display path.
- **5 MB size threshold:** payloads ≤ 5 MB stored inline in DB `encrypted_blob` column. Payloads > 5 MB stored in filesystem at `<data-dir>/files/<user_id>/<note_id>.<ext>`. **Filesystem payloads are always AES-256-GCM encrypted before writing to disk** — encryption is the core product guarantee regardless of storage location.
- DB column `payload_location` (enum: `inline` | `filesystem`) tracks where payload lives.
- Pattern inspired by Git (deflated blobs), PostgreSQL `bytea` (opaque binary), S3 (byte streams + Content-Type), and CAS (content-addressable storage).
- Trade-off: database can't query encrypted fields; search requires client-side decryption. DB never interprets content — no parser CVEs, no polyglot exploits at storage layer.

### Authentication (US-11, R13)
- Interactive prompts with `hide_input=True` — credentials never accepted as positional CLI args (prevents shell history / process list exposure).
- Session token file at `<data-dir>/.session` with 24h expiry.
- Auth rate limiting: 5 consecutive failures → 5-min account lockout.
- Username: 3–32 chars, alphanumeric + underscore, case-insensitive uniqueness.
- `delete-account` command with password + typed `CONFIRM DELETE ACCOUNT`; purges all user data.
- bcrypt password hashing.

### Injection Prevention (R15)
- SQLAlchemy ORM as only DB interface — parameterized queries by default, raw SQL banned.
- Input validation at CLI boundary: reject null bytes and non-printable control characters.
- Path traversal prevention for `--data-dir`, `--output`, attachment paths.
- PostgreSQL role limited to DML only (no DDL).
- Plugins receive read-only note copies; no `exec()`/`eval()`/shell commands; no raw DB access.
- Strip ANSI escape sequences before terminal output.
- `DATABASE_URL` requires `sslmode=require`.

### Plugin Hardening (R4.10)
- Plugin allowlist in config (`allowed_plugins` key); unlisted plugins rejected with warning.

### Additional Features
- Passphrase rotation via `reencrypt <note_id>` command (R2.14).
- Attachment orphan cleanup on note delete (R14.8).
- Disk-full error handling at both JSON and DB layers (R3.8, R14.11).
- Config tampering guard: `deployment_mode` switch validated even via direct config edit (R13.13).
- Expanded audit trail scope: login, logout, register, delete-account, migrate, export (R8.2).
- Multi-passphrase search behavior defined: mismatched notes silently skipped (R10.3).
- Documented passphrase memory-residency limitation (R2.15).

## Planning Review & Hardening

Performed full review of all planning docs for conflicts, vagueness, and defensibility:

### Contradictions Fixed
- US-2 said "encrypt independently" but R2.9 defined envelope encryption → US-2 updated to match.
- R3 (JSON persistence) conflicted with R14 (database) → R3 scoped to pre-migration mode.
- R9.3 config keys missing `deployment_mode` and `allowed_plugins` → added.
- US-6 audit scope narrower than R8.2 → US-6 expanded to match.
- US-7 config keys didn't include new keys → updated.
- US-4 missing plugin allowlist from R4.10 → added.
- R4.5 "isolate malware notes" was vague → clarified to "plugin content never executed as code."
- R10.3 multi-passphrase search behavior undefined → defined as silent skip.

### Edge Cases Added (12 total)
1. Concurrent CLI instances — SQLite WAL mode + retry (B-66)
2. Disk full during write — ENOSPC handling (B-67)
3. Passphrase change — `reencrypt` command (B-62)
4. Account deletion — user data purge (B-61)
5. Username validation rules (B-60)
6. Multi-passphrase search behavior (R10.3 updated)
7. Encrypted note migration repackaging (B-72)
8. Plugin direct DB access blocked (R15.7 updated)
9. Config tampering guard (B-70)
10. Attachment orphaning — cleanup on delete (B-68)
11. Session token theft — 24h expiry (B-59)
12. Passphrase memory residency — documented limitation (B-73)

### Defensibility Audit Results
- ✅ AES-256-GCM + PBKDF2 100k — industry standard, NIST-approved
- ✅ Sandbox binary storage — content-agnostic, no parser CVEs at storage layer
- ✅ Hybrid encrypted filesystem — large payloads encrypted before writing to disk
- ✅ bcrypt for passwords — industry standard
- ✅ SQLAlchemy ORM — parameterization eliminates SQL injection
- ✅ Interactive auth prompts — no credential exposure in shell history
- ✅ Rate limiting — brute-force prevention
- ✅ Session expiry — stolen token has limited window
- ✅ SSL enforcement — no cleartext credentials on wire
- ✅ Plugin allowlist — prevents arbitrary code execution
- ⚠️ Passphrase in memory — Python string, not zeroizable (documented)
- ⚠️ SQLite unencrypted at rest — unencrypted notes' blobs readable (OS-level encryption recommended)

## Artifacts Modified
- `planning/user-stories.md` — US-2, US-4, US-6, US-7, US-8, US-11, US-12 updated (sandbox model, retrieval flow, 5 MB threshold)
- `planning/requirements.md` — R2.9 (sandbox blob), R14.3 (payload_location column), R14.4 (sandbox framing), R14.8 (5 MB threshold + encrypted filesystem), R14.9 (retrieval flow), R3 scoped, R4 (+1), R8.2 expanded, R9.3/R9.6, R13 (7→13), R15 (+1)
- `planning/backlog.md` — B-43 updated (sandbox), B-48 (sandbox repackaging), B-49 (hybrid 5 MB threshold), B-57–B-73 added; total: 73 items
- `planning/sprint-zero-plan.md` — Sprint 2 plan expanded with security items
- `docs/planning-summary.md` — removed for clarity

## Counts
- Requirements: 76 → 95 items across 15 categories
- User stories: 12 (1 deferred epic)
- Backlog items: 73 (23 done, 50 not started)
- Sprints planned: 0 (done), 1 (bugs), 2 (DB + auth + security)

## Next Actions
- Commit and push all planning doc changes.
- Sprint 1 implementation: start with B-31 (ID collision fix).
- Add `sqlalchemy`, `alembic`, `bcrypt`, `psycopg2-binary` to `requirements.txt` when Sprint 2 begins.
