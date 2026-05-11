# AstraNotes — Product Requirements Document

**Version:** 1.2  `[LOG 05-04]`  
**Date:** May 4, 2026  
**Status:** Draft — under review  
**Owner:** Human team member  
**AI Partner:** Astra (GitHub Copilot)

> **Traceability note:** Every section in this document is sourced from an existing project artifact.
> Each item is tagged with its primary source in square brackets:
> `[REQ Rx.y]` = `planning/requirements.md`, `[US-n]` = `planning/user-stories.md`,
> `[BL B-nn]` = `planning/backlog.md`, `[LOG 04-15]` = `Copilot/working-log-2026-04-15.md`,
> `[SP0]` = `planning/sprint-zero-plan.md`.
> Items with no tag were added by AI and are marked **[AI — needs owner review]**.

---

## 1. Problem Statement

> Source: `planning/requirements.md` section headers and `Copilot/working-log-2026-04-15.md` key decisions.

Knowledge workers and developers need a lightweight, privacy-first note-taking tool that:

- Works entirely from the command line with no cloud dependency. `[LOG 04-15]`
- Provides opt-in, per-note AES-256-GCM encryption with no plaintext metadata leakage. `[REQ R2.9]` `[LOG 04-15]`
- Can be extended without modifying core application code. `[REQ R4]` `[US-4]`
- Scales from a single anonymous local user to a multi-device account with opt-in cloud sync. `[REQ R12]` `[US-10]`

Existing tools either expose note content to third-party services, provide no per-note encryption, or cannot be extended safely. AstraNotes is local-first: data never leaves the device unless the user explicitly opts in to cloud sync via `sync push`/`sync pull`. `[LOG 04-15]` `[LOG 05-04]`

---

## 2. Target Users

> Source: `planning/user-stories.md` persona headers (US-1 through US-14). `[LOG 05-04]`

| Persona | Description | Source |
|---------|-------------|--------|
| **Personal CLI user** | Developer or power user running locally; no login required; single SQLite store; values privacy and CLI ergonomics | `[US-1]` `[US-10]` |
| **Personal GUI user** | Non-technical user who prefers a simple graphical note app (Sprint 4); same privacy guarantees as CLI; no server required | `[US-9]` `[REQ R11.1–R11.6]` `[LOG 05-04]` |
| **Logged-in desktop user** | User who opts in to an account and syncs via the desktop app (Sprint 5); uses Google OAuth or local credentials | `[US-14]` `[REQ R11.7–R11.12]` `[LOG 05-04]` |
| **Logged-in CLI/GUI user** | Power user who has created an account and uses `sync push`/`sync pull` to sync notes across devices `[LOG 05-04]` | `[US-11]` `[US-14]` |
| **Account administrator** | Manages sync server; configures PostgreSQL and OAuth provider `[LOG 05-04]` | `[US-10]` `[REQ R16]` |
| **Plugin developer** | Engineer who extends AstraNotes behavior via the hook API without touching core code | `[US-4]` `[REQ R4]` |

---

## 3. Core Features

### 3.1 Note Management (CRUD)

> Source: `[REQ R1]` `[US-1]` `[BL B-01–B-14, B-31, B-35, B-36, B-52]`

- Add notes with title and content; supported formats: text, audio, video. `[REQ R1.1]`
- Get, list, update, and delete by unique gap-safe ID (UUID or max-ID+1). `[REQ R1.8]` `[BL B-31]`
- `--data-dir` global option; validated as a writable directory; existing file at path → error. `[REQ R1.9]` `[BL B-36]`
- Corrupt store detected on load → back up as `.bak`, start empty, warn user. `[REQ R1.10]` `[BL B-35]`
- Input validation at CLI boundary: reject empty/whitespace, null bytes, and non-printable control characters. `[REQ R1.6]` `[REQ R15.3]` `[BL B-52]`
- Non-zero exit codes on all errors; error messages identify the triggering module. `[REQ R5.2]` `[REQ R5.3]`
- Listing reads plaintext `title` and `format` columns; does not parse blobs. `[REQ R1.3]` `[BL B-74]`

### 3.2 Per-Note Encryption

> Source: `[REQ R2]` `[US-2]` `[BL B-02, B-05–B-06, B-09–B-10, B-12–B-13, B-17, B-32–B-34, B-62, B-79]` `[LOG 04-15]`

- Opt-in AES-256-GCM encryption with PBKDF2 key derivation via `--encrypt yes`. `[REQ R2.1]` `[REQ R2.17]`
- Passphrase prompted twice on creation (confirmation); mismatch → retry or abort. `[REQ R2.2]` `[BL B-32]`
- Minimum passphrase length: 8 characters; empty or whitespace-only passphrase rejected. `[REQ R2.11]` `[BL B-34]`
- **Sandbox binary blob model:** length-prefixed framing `[4-byte header_length][JSON header][raw payload bytes]`. Header contains metadata (title, timestamps, tags, format MIME type, original_filename, size_bytes). For encrypted notes, the entire blob is AES-256-GCM ciphertext — no sensitive metadata left in plaintext. `[REQ R2.9]` `[LOG 04-15]`
- Passphrase required for all read, write, and delete operations on encrypted notes. `[REQ R2.3–R2.5]`
- Unencrypted note operations never prompt for passphrase. `[REQ R2.6]`
- `list` shows user-chosen alias or `[Encrypted Note]`; no passphrase prompt on list. `[REQ R2.7]` `[REQ R1.3]`
- Updating or deleting unencrypted notes must not corrupt co-stored encrypted notes. `[REQ R2.12]` `[BL B-33]`
- Passphrase rotation via `reencrypt <note_id>`; re-encrypts blob and any filesystem payload. `[REQ R2.14]` `[BL B-62]`
- Optional unencrypted alias displayed with info warning: "Alias is stored unencrypted and visible without passphrase." `[REQ R2.16]` `[BL B-79]`
- Passphrase held as Python string during session; not zeroizable — documented limitation. `[REQ R2.15]` `[BL B-73]`
- No default key; key manager required for all encrypted operations. `[REQ R2.10]`

### 3.3 Storage and Persistence

> Source: `[REQ R3]` `[REQ R14]` `[US-3]` `[US-12]` `[BL B-15–B-16, B-42–B-43, B-48–B-49, B-51, B-63–B-68, B-74]` `[LOG 04-15]`

- **Pre-migration:** JSON file (`notes.json`), save after every mutation. `[REQ R3.1]` `[REQ R3.2]`
- **Post-migration:** SQLite (personal) or PostgreSQL (server) via `migrate` CLI command. `[REQ R14.7]` `[BL B-48]`
- Sandbox blob stored inline for payloads ≤ 5 MB; payloads > 5 MB stored as AES-256-GCM encrypted files on disk (encrypted notes only); unencrypted notes always stored inline regardless of size. `[REQ R14.8]` `[BL B-49]`
- SQLAlchemy ORM with parameterized queries; no raw SQL in application code. `[REQ R15.1]` `[REQ R15.2]` `[BL B-51]`
- ACID transactions on every mutation; concurrent writes must not corrupt data. `[REQ R14.6]`
- SQLite WAL mode with retry logic for concurrent CLI instances. `[REQ R14.1]` `[BL B-66]`
- Schema versioned via Alembic; future schema changes applied through migration scripts. `[REQ R14.11]` `[BL B-65]`
- Disk-full errors (`ENOSPC`) caught and reported; no silent data loss. `[REQ R3.8]` `[REQ R14.12]` `[BL B-67]`
- Orphan cleanup: filesystem payloads deleted when associated note is deleted. `[REQ R14.8]` `[BL B-68]`
- `notes` table columns: `note_id` (PK), `account_id` (FK, nullable — NULL = anonymous), `title`, `format`, `encrypted_blob`, `nonce`, `salt`, `is_encrypted`, `payload_location`, `synced_at` (nullable, NULL = never synced). `[REQ R14.3]` `[LOG 05-04]`

### 3.4 Local-First with Opt-In Account  `[LOG 05-04]`

> Source: `[REQ R12]` `[US-10]` `[BL B-41, B-42, B-47, B-90, B-96]` `[LOG 05-04]`

- App works immediately without any login or configuration; SQLite always active. `[REQ R12.1]`
- Notes created without an account have `account_id = NULL` (anonymous / device-local). `[REQ R12.2]`
- On first login on a device with existing anonymous notes, a one-time prompt appears: "Associate N local notes with your account? [Yes / No / Ask me for each]". `[REQ R12.3]`
- After login, new notes automatically receive the active `account_id`; a `--local` flag keeps a specific note anonymous. `[REQ R12.4]`
- `sync push` / `sync pull` commands (and optional background sync) require an active account session. `[REQ R12.5]`
- Multiple accounts may coexist on one device; note list scoped by active `account_id`. `[REQ R12.6]`
- `logout` detaches the session; all local notes (including account-associated ones) remain accessible offline. `[REQ R12.7]`

### 3.5 Optional Account and Authentication  `[LOG 05-04]`

> Source: `[REQ R13]` `[US-11]` `[BL B-45–B-47, B-57–B-61, B-75, B-81, B-87, B-96]` `[LOG 05-04]`

- `register` / `login` are available at any time but are never required to use the app. `[REQ R13.1]`
- Passwords stored as bcrypt hashes; never stored or logged in plaintext. `[REQ R13.2]`
- Username: 3–32 chars, alphanumeric + underscore, case-insensitive uniqueness. `[REQ R13.3]` `[BL B-60]`
- Session token file at `<data-dir>/.session` (JSON: `account_id`, `username`, `created_at`, `expires_at`); restricted to owner. `[REQ R13.5]` `[BL B-59, B-75]` `[LOG 05-04]`
- Session tokens expire after 24 hours. An expired session blocks cloud sync only — **local CRUD is unaffected**. `[REQ R13.8]` `[LOG 05-04]`
- Rate limiting: 5 consecutive failed logins → 5-minute lockout per username. `[REQ R13.7]` `[BL B-58]`
- When logged in: note list shows the active account's notes plus anonymous notes. When logged out: only anonymous notes shown. `[REQ R13.10]`
- `logout` detaches session token; local notes (including account-associated) remain accessible. `[REQ R13.9]` `[LOG 05-04]`
- `delete-account` prompts password + typed `CONFIRM DELETE ACCOUNT`; sets `account_id = NULL` on all local notes; deletes account record from sync server; warns user that cloud copies will be deleted. `[REQ R13.12]` `[BL B-61, B-81]` `[LOG 05-04]`
- Queries scoped by `account_id`; no cross-account data access. `[REQ R13.11]` `[BL B-47]` `[LOG 05-04]`
- OAuth 2.0 / OpenID Connect via authlib; Google is the required minimum provider; extensible pattern for additional providers. `[REQ R13.13, R13.14]` `[BL B-87]` `[LOG 05-04]`
- Data directory is always flat: `<data-dir>/notes.db`, `<data-dir>/files/`, `<data-dir>/exports/`, `<data-dir>/audit.log`. No per-user subdirectory structure on device. `[REQ R14.13]` `[BL B-77]` `[LOG 05-04]`

### 3.6 Plugin System

> Source: `[REQ R4]` `[US-4]` `[BL B-18, B-37–B-38, B-56, B-69]` `[LOG 04-15]`

- Plugin base class with name, version, and hook registration. `[REQ R4.1]`
- Plugin registry manages hooks and dispatches calls. `[REQ R4.2]`
- Plugins discovered and loaded from `plugins/` directory on startup. `[REQ R4.6]` `[BL B-37]`
- Plugins may register post-action hooks (e.g., `post_add_note`) and provide additional CLI commands. `[REQ R4.3]` `[REQ R4.4]`
- Allowlist enforced via `allowed_plugins` key in config; unlisted or unsigned plugins rejected with warning. `[REQ R4.10]` `[BL B-69]`
- Plugins receive read-only note copies; `exec`/`eval` and raw DB access prohibited. `[REQ R4.5]` `[REQ R15.7]` `[BL B-56]`
- Hook crashes isolated with try/except; logged, never propagate to the operation. `[REQ R4.7]` `[BL B-38]`
- Duplicate plugin registration → skip with warning. `[REQ R4.8]`

### 3.7 Override Policy

> Source: `[REQ R7]` `[US-5]` `[BL B-24]`

- Destructive plugin overrides require typed `CONFIRM OVERRIDE` with a red warning. `[REQ R7.1]` `[REQ R7.2]`
- Scope limited to plugin hooks; normal user CRUD never triggers override flow. `[REQ R7.5]`
- All override attempts (success and failure) appended to audit trail. `[REQ R7.4]`
- Incorrect or empty confirmation → abort, no changes applied. `[REQ R7.3]`

### 3.8 Audit Trail

> Source: `[REQ R8]` `[US-6]` `[BL B-25, B-71, B-81]` `[LOG 04-15]`

- Append-only, one JSON object per line. Fields: `timestamp` (ISO 8601), `operation`, `note_id` (nullable), `outcome`, `detail` (optional). `[REQ R8.1]`
- Covered operations: encrypt/decrypt, passphrase attempts, overrides, plugin loads, login, logout, register, delete-account, mode switch, migrate, export. `[REQ R8.2]` `[BL B-71]`
- Log entries never modified during normal operation; per-user log deleted only on `delete-account`. `[REQ R8.3]` `[BL B-81]`
- Audit log at `<data-dir>/audit.log` (always flat; no per-user paths on device). `[REQ R8.4]` `[LOG 05-04]`
- CLI: `audit --limit N --operation <type> --since <date>`. `[REQ R8.5]`
- Audit file unwritable → warn, do not block the operation. `[REQ R8.6]`

### 3.9 Configuration

> Source: `[REQ R9]` `[US-7]` `[BL B-26, B-64]` `[LOG 04-15]`

- Settings stored in `<data-dir>/config.json`. `[REQ R9.1]`
- Known keys only: `default_encrypt`, `passphrase_min_length`, `data_dir`, `plugin_dir`, `allowed_plugins`, `theme`, `font_size`, `sync_server_url`, `sync_auto_interval`; free-form keys rejected. `[REQ R9.3]`
- CLI: `config set / get / list / reset`. `[REQ R9.2]`
- `DATABASE_URL` accepted from environment variable only; never stored in config. `[REQ R9.6]` `[BL B-64]`
- Config file missing → all defaults used; file created on first `config set`. `[REQ R9.5]`

### 3.10 Search and Export

> Source: `[REQ R10]` `[US-8]` `[BL B-29–B-30, B-76, B-78]`

- Case-insensitive substring search on title and content; `--encrypted` flag prompts passphrase once; mismatched notes silently skipped. `[REQ R10.1]` `[REQ R10.3]`
- Search results show: ID, title, first 80 chars of content. `[REQ R10.2]`
- Export to text/JSON with `--format`, `--output`, `--encrypted` options. Binary notes export raw payload file + path reference in manifest. `[REQ R10.4]` `[BL B-76]`
- Exported files restricted to creator + administrator; `export --cleanup` purges exports directory; decrypted-data warning displayed on export. `[REQ R10.7]` `[BL B-78]`
- Export 1000+ notes within 2 seconds. `[REQ R10.6]`

---

## 4. Non-Functional Constraints

> Source: `[REQ R3.5]` `[REQ R10.6]` `[REQ R13–R15]` `[LOG 04-15]`

| Category | Constraint | Source |
|----------|------------|--------|
| **Performance** | List/search/fetch/delete 1000+ notes within 0.5 s | `[REQ R3.5]` |
| **Performance** | Export 1000+ notes within 2 s | `[REQ R10.6]` |
| **Cryptography** | AES-256-GCM; PBKDF2 key derivation; no default keys | `[REQ R2.1]` `[REQ R2.10]` |
| **Database security** | All queries via SQLAlchemy ORM (parameterized); no raw SQL in app code | `[REQ R15.1]` `[REQ R15.2]` |
| **Database security** | PostgreSQL role limited to DML only (no DDL: DROP/ALTER/CREATE) | `[REQ R15.4]` `[BL B-53]` |
| **Database security** | PostgreSQL connection must use `sslmode=require` | `[REQ R14.2]` `[BL B-63]` |
| **Input safety** | Null bytes and non-printable control characters rejected at CLI boundary | `[REQ R15.3]` `[BL B-52]` |
| **Output safety** | ANSI escape sequences stripped before terminal rendering | `[REQ R15.5]` `[BL B-54]` |
| **Path safety** | `--data-dir`, `--output`, attachment paths validated against path traversal | `[REQ R15.8]` `[BL B-55]` |
| **Auth security** | bcrypt passwords; interactive prompts only (`hide_input=True`) | `[REQ R13.2]` `[BL B-57]` |
| **Auth security** | Rate limiting: 5 failures → 5-min lockout | `[REQ R13.7]` `[BL B-58]` |
| **Auth security** | Session token file permissions restricted to owner only `[LOG 05-04]` | `[REQ R13.5]` `[BL B-75]` |
| **Reliability** | ACID transactions; disk-full caught and reported without silent data loss | `[REQ R14.6]` `[REQ R14.12]` |
| **Extensibility** | Core security modules immutable to plugins | `[REQ R4.5]` |
| **Traceability** | Every feature traceable requirement → implementation → test | `[Copilot/Definition of Done.md]` |
| **Schema management** | Schema versioned via Alembic; changes applied through migration scripts | `[REQ R14.11]` `[BL B-65]` |

---

## 5. Risks

> Source: `[REQ R2.15]` `[LOG 04-15]` `[BL B-56, B-58, B-66, B-68, B-72]`  `[LOG 05-04]`

| Risk | Likelihood | Impact | Mitigation | Source |
|------|------------|--------|------------|--------|
| Passphrase held as Python string (not zeroizable) | Certain | Medium | Documented limitation; no mitigation at language level | `[REQ R2.15]` `[BL B-73]` |
| Plugin malicious content executed if sandboxing incomplete | Medium | High | Allowlist + read-only copies + no exec/eval enforced | `[REQ R4.5]` `[REQ R15.7]` `[BL B-56]` |
| SQLite WAL concurrency corruption under parallel CLI instances | Low | High | Retry logic | `[REQ R14.1]` `[BL B-66]` |
| `DATABASE_URL` accidentally logged | Medium | High | Accepted from env var only; not stored in config | `[REQ R9.6]` `[BL B-64]` |
| Filesystem payload orphans after failed delete | Medium | Medium | Orphan cleanup on note delete | `[REQ R14.8]` `[BL B-68]` |
| Migration skips encrypted notes, leaves data in JSON backup | Medium | Medium | User warned; backup retained if any notes skipped | `[REQ R14.7]` `[BL B-72]` |
| Wrong passphrase corrupts co-stored encrypted note on update/delete | Low | High | Passphrase verified before any write; explicit regression test | `[REQ R2.12]` `[BL B-33]` |
| Sync conflict data loss | Low | High | Last-write-wins with 30-day conflict table; both versions preserved | `[REQ R16.3]` `[BL B-86]` `[LOG 05-04]` |

---

## 6. Out of Scope

> Source: `[REQ R11]` `[US-9]` `[US-14]` `[REQ R13.11]` `[REQ R2.10]` `[REQ R9.3]` `[REQ R14.8]` `[BL B-27]` `[LOG 05-04]`

| Item | Rationale | Source |
|------|-----------|--------|
| **Mobile-native app (iOS/Android)** | Desktop app covers desktop platforms; mobile access is out of scope | `[LOG 05-04]` |
| **Note sharing between users** | No cross-account data access by design | `[REQ R13.11]` |
| **Key escrow / passphrase recovery** | No default key and no recovery path by design | `[REQ R2.10]` |
| **Real-time collaboration** | Not mentioned in any planning artifact | `[AI — needs owner review]` |
| **Free-form config keys** | Only known whitelist accepted | `[REQ R9.3]` |
| **Unencrypted large-file filesystem storage** | Unencrypted notes always stored inline regardless of size | `[REQ R14.8]` |

---

## 7. Implementation Status

> Source: `planning/backlog.md` Done and Backlog sections. `[BL]`

### Sprint Zero — Not Yet Started

> **Note (2026-05-07):** All Sprint Zero source code and test files were removed. No code or tests currently exist. All B-01–B-23 items below are planned but not yet implemented.

### High-Priority Backlog (Not Started)

| ID | Item | Source |
|----|------|--------|
| B-31 | Gap-safe IDs (UUID or max-ID+1) | `[REQ R1.8]` |
| B-32 | Passphrase confirmation prompt on encrypt | `[REQ R2.2]` |
| B-33 | Fix encrypted-note corruption on unencrypted update/delete | `[REQ R2.12]` |
| B-34 | Reject empty/short passphrase (min 8 chars) | `[REQ R2.11]` |
| B-35 | Corrupt JSON recovery with `.bak` backup | `[REQ R1.10]` |
| B-41 | First-login anonymous note association prompt (one-time, only if anonymous notes exist): Yes / No / Ask me for each | `[REQ R12.3]` |
| B-42 | SQLite local store — always-on, zero-config, at `<data-dir>/notes.db`; WAL mode; `account_id` nullable FK + `synced_at` nullable timestamp on `notes` table | `[REQ R14.1]` |
| B-43 | Sandbox binary blob storage | `[REQ R2.9]` `[REQ R14.4]` |
| B-49 | Hybrid storage: 5 MB threshold + filesystem payloads | `[REQ R14.8]` |
| B-51 | SQLAlchemy ORM — no raw SQL | `[REQ R15.2]` |
| B-52 | Input validation: null bytes + control chars at CLI boundary | `[REQ R15.3]` |
| B-57 | Interactive auth prompts (`hide_input=True`) | `[REQ R13.1]` |
| B-58 | Auth rate limiting — 5 failures → 5-min lockout | `[REQ R13.7]` |
| B-59 | Session token file with 24h expiry | `[REQ R13.5]` |
| B-74 | Plaintext `title`/`format` columns for fast listing | `[REQ R1.3]` `[REQ R14.5]` |
| B-75 | Session token file permissions | `[REQ R13.5]` |
| B-77 | Flat data directory — always `<data-dir>/notes.db`, `<data-dir>/files/`, `<data-dir>/exports/`, `<data-dir>/audit.log`; no per-user subdirectory structure on the local device | `[REQ R14.13]` |
| B-78 | Export file permissions + `export --cleanup` | `[REQ R10.7]` |
| B-81 | Per-user audit log deletion on `delete-account` | `[REQ R8.3]` |

### Deferred
GUI layer umbrella (`[BL B-27]`) superseded by two concrete sprints:
- **Sprint 4 — Desktop GUI** (B-84, B-85): PySide6 desktop app sharing core modules; ADR-13 decided. `[LOG 05-04]`
- **Sprint 5 — Sync Server + Sync-Enabled Desktop Client** (B-86–B-95): FastAPI push/pull sync server + PySide6 sync-enabled desktop UI with Google OAuth; ADR-11/12/13 decided. `[LOG 05-04]`
