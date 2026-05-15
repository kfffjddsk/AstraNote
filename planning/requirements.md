# AstraNotes — Requirements

## R1: Note Management (CRUD)

Create, read, list, update, and delete notes via CLI.

| ID | Requirement |
|----|-------------|
| R1.1 | Add a note with title and content; support text, audio, video formats |
| R1.2 | Retrieve note by ID; encrypted notes require passphrase |
| R1.3 | List notes with ID, title, and format; hide title for encrypted notes (show `[Encrypted Note]`). Listing reads plaintext `title` and `format` columns — does not parse blobs. CLI renders two sections: **"Your Notes"** (notes with `account_id = <current user>`) then **"Local Open Notes"** (notes with `account_id = NULL`). When the user is logged out, only "Local Open Notes" is shown — the "Your Notes" section is omitted entirely. `DatabaseStore.list(account_id)` returns `(account_notes: List[Note], local_notes: List[Note])`. `[D-11]` |
| R1.4 | Update a note's title or content by ID; no changes provided → no-op |
| R1.5 | Delete a note by ID |
| R1.6 | Reject empty or whitespace-only title or content on add |
| R1.7 | Return clear error for non-existent note IDs |
| R1.8 | Generate gap-safe unique IDs (UUID or max-ID+1); no collision after deletions |
| R1.9 | `--data-dir` must be a writable directory; existing file at path → error; no permission → error with message |
| ~~R1.10~~ | ~~Corrupt `notes.json` → back up as `notes.json.bak`, start empty, warn user~~ — **N/A** (SQLite ACID transactions replace JSON corruption recovery; no JSON storage layer) `[D-10]` |

## R2: Encryption

Per-note opt-in encryption using AES-256-GCM with PBKDF2 key derivation.

| ID | Requirement |
|----|-------------|
| R2.1 | Opt-in encryption per note via `--encrypt yes` |
| R2.2 | Prompt passphrase twice on encrypt (confirmation); mismatch → retry or abort |
| R2.3 | Prompt for passphrase when reading an encrypted note |
| R2.4 | Prompt for passphrase when updating an encrypted note |
| R2.5 | Prompt for passphrase when deleting an encrypted note |
| R2.6 | Never prompt for passphrase on unencrypted note operations |
| R2.7 | List command shows plaintext `title` column for encrypted notes — user-chosen alias if set, otherwise `[Encrypted Note]`. No passphrase prompt on list |
| R2.8 | Reject wrong passphrase and preserve data |
| R2.9 | Sandbox binary storage: all note data treated as raw bitstream with length-prefixed framing `[4-byte header_length][JSON header][raw payload bytes]`. Header: title, timestamps, tags, format (MIME type), original_filename, size_bytes. Payload: raw content bytes. Entire blob encrypted with AES-256-GCM for encrypted notes; no metadata left in plaintext |
| R2.10 | No default key; key manager required for encrypted operations |
| R2.11 | Reject empty or whitespace-only passphrase; minimum 8 characters |
| R2.12 | Updating/deleting unencrypted notes must not corrupt co-stored encrypted notes |
| R2.13 | Only routing fields (note_id, user_id, is_encrypted), crypto params (nonce, salt), listing fields (title, format), and payload_location stored unencrypted; all other fields inside the blob |
| R2.14 | `reencrypt <note_id>` command: prompt old passphrase, then new passphrase twice; re-encrypt the blob with the new key. If the note has a filesystem payload (>5 MB), the on-disk file is also re-encrypted with the new key |
| R2.15 | Passphrase held in memory as Python string during session; not zeroizable (documented limitation) |
| R2.16 | When user provides an alias for an encrypted note, display info message: "Alias is stored unencrypted and visible without passphrase" |

## R3: Data Persistence

**SUPERSEDED by R14 (SQLite, Sprint 0).** `[D-10 resolved 2026-05-12]` SQLite (`DatabaseStore`) is used from Sprint 0; there is no JSON storage phase. R3.1 and R3.6 are retired. R3.2–R3.5, R3.7–R3.8 remain applicable to `DatabaseStore` and are covered by R14.1–R14.13.

| ID | Requirement |
|----|-------------|
| ~~R3.1~~ | ~~Store notes in `<data-dir>/notes.json` (pre-migration only; replaced by database after migration)~~ — **RETIRED** (SQLite `notes.db` from Sprint 0 — R14.1) |
| R3.2 | Save after every mutation (add, update, delete) |
| R3.3 | Load existing notes on startup |
| R3.4 | Preserve encrypted records when loaded without a key |
| R3.5 | Handle listing, searching, fetching, deleting 1000+ notes within 0.5 seconds on reference hardware (documented test environment) without crashes or exceptions |
| ~~R3.6~~ | ~~Corrupt JSON detected on load → back up as `.bak`, start empty, warn user~~ — **RETIRED** (SQLite ACID transactions replace JSON corruption recovery) `[D-10]` |
| R3.7 | File write errors → catch and display actionable message (e.g., "Cannot write to <path>: permission denied") |
| R3.8 | Disk-full errors (`ENOSPC` / `OSError`) caught and reported as actionable error; no silent data loss |

## R4: Plugin System

Hook-based architecture for extending CLI behavior.

| ID | Requirement |
|----|-------------|
| R4.1 | Plugin base class with name, version, and hook registration |
| R4.2 | Plugin registry manages hooks and dispatches calls |
| R4.3 | Plugins can register post-action hooks (e.g., `post_add_note`) |
| R4.4 | Plugins can provide additional CLI commands |
| R4.5 | Core security (CRUD and extension modules) immutable; plugin hook crashes caught and logged; plugin content never executed as code (no eval/exec) |
| R4.6 | Discover and load plugins from `plugins/` directory on startup |
| R4.7 | Hook execution wrapped in try/except; plugin crash logged, does not kill the operation |
| R4.8 | Duplicate plugin registration → skip with warning |
| R4.9 | `overrides` field validated against override policy (R7) |
| R4.10 | Plugin allowlist in config (`allowed_plugins` key); only listed plugins loaded. Unsigned/unlisted plugins rejected with warning |
| R4.11 | Plugin manifest file (`plugin.json`) must be present in each plugin subdirectory; required fields: `plugin_id`, `name`, `version` (semver), `engines` (min AstraNotes version), `main` (entrypoint module path); validated with `jsonschema` at startup `[D-12]` |
| R4.12 | `is_official` is server-assigned only; any manifest containing `is_official` must be rejected; user-installed (sideloaded) plugins always default to `is_official = False` regardless of manifest content `[D-12]` |
| R4.13 | Trust tier enforcement: `is_official = True` (server-approved) grants full `EditorProvider` + `PluginBase` API; `is_official = False` (user-installed) restricted to `EditorProvider` only — `PluginBase` hook registration blocked at `register_plugin()` time with warning `[D-12]` |

## R5: CLI Interface

Click-based CLI with structured commands and error handling.

| ID | Requirement |
|----|-------------|
| R5.1 | Global `--data-dir` option for storage location |
| R5.2 | Non-zero exit code on errors |
| R5.3 | Error messages identify triggering module and current session actions |

## R6: Testing

BDD scenarios and unit tests validate all features.

| ID | Requirement |
|----|-------------|
| R6.1 | BDD feature files cover R1 CRUD scenarios |
| R6.2 | Unit tests cover core modules (Note, DatabaseStore, encryption) |
| R6.3 | Stress test validates 1000+ note volume safely |
| R6.4 | Tests run via `pytest` and `test_all.py` |
| R6.5 | Edge-case tests: whitespace inputs, ID collision, passphrase validation, permission errors, SQLite ACID error handling |

## R7: Override Policy

Red-alert confirmation for destructive core overrides.

| ID | Requirement |
|----|-------------|
| R7.1 | Display red warning: "Further action may damage notes or app — ensure you know what you are doing" |
| R7.2 | Require user to type `CONFIRM OVERRIDE` exactly to proceed |
| R7.3 | Abort on incorrect or empty confirmation |
| R7.4 | Log all override attempts (success and failure) to audit trail (R8) |
| R7.5 | Override scope limited to plugin hooks; normal user CRUD never triggers override |

## R8: Audit Trail

Append-only log for security operations.

| ID | Requirement |
|----|-------------|
| R8.1 | Log format: one JSON object per line with fields: timestamp (ISO 8601), operation, note_id (nullable), outcome, detail (optional) |
| R8.2 | Log encryption, decryption, passphrase attempts, overrides, plugin loads, login, logout, registration, account deletion, mode switches, migration, and export operations |
| R8.3 | Log is append-only during normal operation; entries never modified. Per-user log deleted only on `delete-account` (full user data purge) |
| R8.4 | Audit log at `<data-dir>/audit.log` on the local device (flat layout per ADR-09); missing file → created on first write. On the sync server (if self-hosted), a separate audit log is maintained per-account. Per-user log deleted from server on `delete-account`. `[LOG 05-04]` |
| R8.5 | CLI `audit` command with `--limit N`, `--operation <type>`, `--since <date>` filters |
| R8.6 | Audit file unwritable → warn, do not block the operation |

## R9: Configuration

Persistent settings module.

| ID | Requirement |
|----|-------------|
| R9.1 | Store settings at a fixed OS-standard path: `%APPDATA%\astranotes\config.json` (Windows) / `~/.config/astranotes/config.json` (Linux/macOS). Config is separate from `data_dir`; moving `--data-dir` does not move the config file. `data_dir` is a key inside the config file; `--data-dir` CLI flag overrides it at runtime. `[D-06 resolved 2026-05-11]` |
| R9.2 | CLI commands: `config set`, `config get`, `config list`, `config reset` |
| R9.3 | Known keys only: `default_encrypt` (yes/no), `passphrase_min_length` (int), `data_dir` (path), `plugin_dir` (path), `allowed_plugins` (list), `theme` (light/dark), `font_size` (int), `sync_server_url` (URL), `sync_auto_interval` (int, seconds, 0 = disabled); free-form keys rejected |
| R9.4 | Invalid value type for a key → error with expected type |
| R9.5 | Config file missing → all defaults used, file created on first `config set` |
| R9.6 | `DATABASE_URL` never stored in config; accepted from environment variable only |
| R9.7 | Session exclusivity: only one AstraNotes session (GUI or CLI) may run per account at a time. Enforced by a PID-based lock file at `<data-dir>/.app.lock`. New session startup checks the lock; if the recorded PID is alive, startup fails with an error dialog. Stale locks (dead PID) are overwritten silently. Lock file deleted on clean exit. `[D-13 resolved 2026-05-13]` |
| R9.8 | Encrypted note idle auto-lock: if an encrypted note has been open without user interaction for 5 minutes, auto-close it and clear the passphrase from memory. Idle timer reset on any user interaction. Fires silently — no prompt. This is a security feature; it is not a multi-user locking mechanism. `[D-13 resolved 2026-05-13]` |

## R10: Search and Export

Find notes and export to external formats.

| ID | Requirement |
|----|-------------|
| R10.1 | `search <query>` → case-insensitive substring match on title and content |
| R10.2 | Search results show: ID, title, first 80 chars of content |
| R10.3 | Encrypted notes excluded from search unless `--encrypted` flag used (prompts passphrase once); notes with mismatched passphrase silently skipped |
| R10.4 | `export --format text|json --output <file>` writes notes to file (default: `<data-dir>/export.<format>`). For binary notes, export writes raw payload file to per-user exports directory and includes path reference in the export manifest |
| R10.5 | `export --encrypted` → prompt passphrase once, decrypt all for export; without flag → `[Encrypted Note]` |
| R10.6 | Export 1000+ notes within 2 seconds |
| R10.7 | Exported/retrieved files have restricted permissions (creator + administrator only). `export --cleanup` purges the user's exports directory. Warning displayed on export: decrypted data written to disk |

## R11: GUI Layer

Two distinct GUI products share the same core Python modules (`DatabaseStore`, `EncryptionEngine`, `PluginRegistry`). The CLI remains the primary interface through Sprint 3; GUI variants are planned for Sprint 4 (local CRUD desktop) and Sprint 5 (sync added to same desktop app). There is no browser-based surface.

### R11-A: Personal GUI (Sprint 4)

| ID | Requirement |
|----|-------------|
| R11.1 | Personal GUI shares the same core modules as the CLI: `DatabaseStore`, `EncryptionEngine`, `PluginRegistry` — no logic duplication |
| R11.2 | Personal GUI supports all CRUD operations (add, get, list, update, delete) through UI controls |
| R11.3 | Personal GUI design is minimal and task-focused — note list on the left, content editor on the right; no unneeded chrome (inspired by Apple Notes / Simplenote / Notesnook) |
| R11.4 | Passphrase prompted via a modal dialog for encrypted notes |
| R11.5 | Desktop GUI uses the SQLite local store (Layer 1); no server dependency for Sprint 4 |
| R11.6 | GUI framework: PySide6 (ADR-13 decided); native Qt6 widgets; LGPL |

### R11-B: Sync-Enabled Desktop Client (Sprint 5)

| ID | Requirement |
|----|-------------|
| R11.7 | Sprint 5 extends the Sprint 4 desktop app with cloud sync UI; no separate browser-based surface; the sync server is backend-only |
| R11.8 | Desktop client communicates with the sync server exclusively via HTTPS sync endpoints (`/sync/push`, `/sync/pull`); it never accesses the remote database directly |
| R11.9 | Desktop client supports login via Google OAuth 2.0 / OpenID Connect (PKCE flow: opens system browser for consent, captures redirect on ephemeral localhost callback); local username/password login also supported |
| R11.10 | Cloud sync triggered by user action (sync button); app calls push/pull on demand; background sync is opt-in via config |
| R11.12 | Desktop client shares the same PySide6 codebase as Sprint 4; sync-related UI elements (sync button, sync-status dot, login dialog) activated by presence of a valid session token |

## R12: Local-First Architecture with Opt-In Account and Cloud Sync  `[LOG 05-04]`

The app uses a **three-layer additive model**. Each layer is independent and opt-in; no layer is required to use the layer below it.

| Layer | Description | Required? |
|-------|-------------|----------|
| **Local store** | SQLite on the device; always active | Always on |
| **Account** | Adds identity; separates notes from other users on the same device | Optional |
| **Cloud sync** | Uploads/downloads notes to/from a remote sync server | Optional; requires account |

| ID | Requirement |
|----|-------------|
| R12.1 | The local SQLite store is always active. No first-launch mode selection is required. The app works fully offline and account-free forever |
| R12.2 | Every note has a nullable `account_id` column. `NULL` means the note is device-local (anonymous). A non-null value means the note is associated with an account and is eligible for cloud sync |
| R12.3 | When a user logs in for the first time on a device that has existing anonymous notes (`account_id = NULL`), the app prompts once: "You have N local notes. Associate them with your account? [Yes / No / Ask me for each]". This prompt is the only migration step |
| R12.4 | After login, new notes are automatically associated with the active account (`account_id` set). A note can be explicitly created as local-only even while logged in |
| R12.5 | Cloud sync is triggered manually (`sync push` / `sync pull`) or automatically in the background if enabled in config; requires an active account session |
| R12.6 | Multiple accounts may exist on one device; notes are scoped by `account_id`. Switching accounts shows only that account's notes (plus anonymous notes if the user chooses to show them) |
| R12.7 | Logging out does not delete local notes; it detaches the account session. Notes with `account_id` set remain on the device; they simply will not sync until the user logs in again |

## R13: Account and Authentication *(Optional Layer)*  `[LOG 05-04]`

Account features are entirely opt-in. Data access never requires a session; authentication only gates cloud sync and account-scoped note visibility.

| ID | Requirement |
|----|-------------|
| R13.1 | `register` prompts for username and password interactively (`hide_input=True`); credentials never accepted as positional CLI arguments |
| R13.2 | Password stored as bcrypt hash; never stored or logged in plaintext |
| R13.3 | Username: 3–32 chars, alphanumeric + underscore only, case-insensitive uniqueness (`admin` == `Admin`) |
| R13.4 | Password minimum 8 characters |
| R13.5 | `login` prompts interactively; correct credentials → session token file at `<data-dir>/.session` (JSON: `account_id`, `username`, `created_at`, `expires_at`). File permissions restricted to creator and administrator only |
| R13.6 | Wrong credentials → error, no session created |
| R13.7 | Auth rate limiting: 5 consecutive failed login attempts → account locked for 5 minutes; tracked via `failed_attempts` and `locked_until` columns in `accounts` table |
| R13.8 | Session tokens expire after 24 hours; expired session → sync and account-scoped operations fail with "Session expired" error; local note operations (CRUD) continue unaffected |
| R13.9 | `logout` deletes session token file. Local notes remain accessible. Synced notes remain on the device with their `account_id` intact |
| R13.10 | Notes queries when logged in show the active account's notes plus anonymous notes. Notes queries when logged out show only anonymous notes |
| R13.11 | On the sync server: queries scoped by `account_id`; no cross-account data access |
| R13.12 | `delete-account` prompts password + typed `CONFIRM DELETE ACCOUNT`; removes account record from server; detaches `account_id` from all local notes (sets to NULL); user is warned that cloud copies will be deleted |
| R13.13 | Desktop GUI and CLI support OAuth 2.0 / OpenID Connect login (authlib); identity token from provider exchanged for a local session token. Local username/password registration also supported |
| R13.14 | Google is the required minimum OAuth provider; extensible provider pattern (authlib) allows adding GitHub or Microsoft without core changes |

## R14: Database Storage & Sandbox Binary Storage

Relational storage with sandbox binary model for note data.

| ID | Requirement |
|----|-------------|
| R14.1 | Local store: SQLite, zero-config, single-file database at `<data-dir>/notes.db`; WAL mode enabled with retry logic for concurrent access (CLI + GUI simultaneously) |
| R14.2 | Sync server (if self-hosted): PostgreSQL backend via `DATABASE_URL` environment variable only (never stored in config); connection must use `sslmode=require`. Cloud-hosted sync service uses the same schema |
| R14.3 | `notes` table columns: `note_id` (PK), `account_id` (FK, **nullable** — NULL = anonymous/device-local), `title` (plaintext, for fast listing), `format` (MIME type, plaintext), `encrypted_blob` (BLOB/bytea), `nonce` (nullable — NULL for unencrypted), `salt` (nullable — NULL for unencrypted), `is_encrypted` (bool), `payload_location` (enum: `inline` \| `filesystem` — filesystem only valid when `is_encrypted = true`), `synced_at` (nullable timestamp — NULL = never synced or local-only) |
| R14.4 | Sandbox binary storage: blob uses length-prefixed framing; header (JSON) + payload (raw bytes). Encrypted notes: entire blob is AES-256-GCM ciphertext. Unencrypted notes: plaintext header + raw payload |
| R14.5 | No sensitive metadata (content, timestamps, tags, original_filename) stored outside the blob. `title` column stores a user-chosen alias for encrypted notes (defaults to `[Encrypted Note]` if omitted; authoritative title remains inside the blob). `format` duplicated as plaintext column for fast listing; authoritative copy remains inside the blob |
| R14.6 | ACID transactions on every mutation; concurrent writes must not corrupt data |
| ~~R14.7~~ | ~~`migrate` CLI command converts `notes.json` → database; backs up JSON before migration. Alert user that encrypted notes require passphrase entry for conversion to sandbox blob format. If user confirms, prompt passphrase per encrypted note; mismatched passphrase → skip that note with warning. Skipped notes remain in JSON backup. After all notes migrated successfully, prompt to securely delete backup; auto-deleted if confirmed. If any notes skipped, warn that backup must be kept~~ — **DROPPED** (no JSON storage phase; SQLite from Sprint 0) `[D-10 resolved 2026-05-12]` |
| R14.8 | Size threshold: payloads ≤ 5 MB stored inline in `encrypted_blob` column. Payloads > 5 MB: only encrypted notes may use filesystem storage under per-user directory at `files/<note_id>.<ext>` (server: `<data-dir>/users/<hashed_uid>/files/`; personal: `<data-dir>/files/`). AES-256-GCM encrypted before writing to disk; DB stores path reference in blob header. Unencrypted notes always stored inline regardless of size (no plaintext files on disk). Orphan cleanup on note delete |
| R14.9 | Retrieval: decrypt blob → parse header. `text/*` format → display as plaintext. Binary format → write payload to per-user exports directory (`exports/<original_filename>`) with restricted permissions; display path and cleanup warning |
| R14.10 | `accounts` table (local, created on first `register` or `login`): `account_id` (PK, UUID), `username` (unique, case-insensitive), `password_hash`, `created_at`, `failed_attempts` (int, default 0), `locked_until` (nullable timestamp). This table exists in the local SQLite DB; a mirror exists on the sync server |
| R14.11 | Schema versioned via Alembic; future schema changes applied through migration scripts |
| R14.12 | Disk-full errors caught at DB layer; actionable error message, no silent data loss |
| R14.13 | Data directory is always flat: `<data-dir>/notes.db`, `<data-dir>/files/`, `<data-dir>/exports/`, `<data-dir>/audit.log`. No per-user subdirectory structure on the local device. On the sync server, data is stored per `account_id` |

## R15: Injection Prevention

Guard against SQL injection and input injection attacks.

| ID | Requirement |
|----|-------------|
| R15.1 | All database queries must use parameterized statements (`?` / `%s` bind variables); no string concatenation or f-string interpolation for SQL |
| R15.2 | Use SQLAlchemy ORM as the database adapter layer; raw SQL queries prohibited outside migrations |
| R15.3 | Validate all user inputs at CLI boundary: reject null bytes (`\x00`) and non-printable control characters (U+0000–U+001F except `\n`, `\t`) in title, content, username, and search queries |
| R15.4 | PostgreSQL connection role limited to `SELECT`, `INSERT`, `UPDATE`, `DELETE` on `notes` and `users` tables; no DDL privileges (`DROP`, `ALTER`, `CREATE`) in application role |
| R15.5 | Strip ANSI escape sequences and terminal control codes from note content before rendering to terminal output |
| R15.6 | Export output (JSON/text) must escape special characters; note content never evaluated or interpreted as code |
| R15.7 | Plugins receive note data as read-only copies; content never passed to `exec()`, `eval()`, or shell commands; plugins cannot access raw DB connection |
| R15.8 | File path inputs (`--data-dir`, `--output`, attachment paths) must be validated against path traversal (`../`, absolute paths outside data-dir); reject or normalize |
| R15.9 | `DATABASE_URL` must use `sslmode=require` for PostgreSQL; reject connections without SSL |

## R16: Cloud Sync Server *(Planned — Sprint 5)*  `[LOG 05-04]`

The sync server stores a cloud copy of account-associated notes. It is **not** a full CRUD proxy — clients always read and write to their local SQLite first; the sync server is the reconciliation point.

| ID | Requirement |
|----|-------------|
| R16.1 | Sync push endpoint: `POST /sync/push` — client sends a list of note blobs (with `account_id`, `note_id`, `synced_at`) that are newer than the last known server timestamp; server stores them |
| R16.2 | Sync pull endpoint: `GET /sync/pull?since=<timestamp>` — server returns all note blobs for the authenticated account that changed after `since`; client merges into local SQLite |
| R16.3 | Conflict resolution: on pull, if both server and local versions changed since last sync, the desktop shows a 2-pane `MergeWindow` — local version (read-only, diffs highlighted yellow) on the left, remote version (editable) on the right. User merges freely and clicks [Save Final]; final version overwrites local and is pushed back to the server. No `note_conflicts` table. `[D-14 decided 2026-05-14]` |
| R16.4 | All sync endpoints require a valid bearer token (JWT); requests without a valid token return HTTP 401 |
| R16.5 | Per-account data isolation: all server queries scoped by `account_id` from the token; no cross-account data access |
| R16.6 | Sync server handles concurrent requests via connection pooling (SQLAlchemy pool) |
| R16.7 | All sync server traffic over HTTPS/TLS; HTTP rejected |
| R16.8 | API responses use JSON; error responses include `status`, `error`, `message` fields |
| R16.9 | Rate limiting: 60 sync requests/minute per account; HTTP 429 with `Retry-After` on excess |
| R16.10 | Sync server framework: FastAPI (async, auto-generates OpenAPI docs, native Pydantic validation; see ADR-11) |
