# AstraNotes — Requirements

## R1: Note Management (CRUD)

Create, read, list, update, and delete notes via CLI.

| ID | Requirement |
|----|-------------|
| R1.1 | Add a note with title and content; support text, audio, video formats |
| R1.2 | Retrieve note by ID; encrypted notes require passphrase |
| R1.3 | List notes with ID, title, and format; hide title for encrypted notes (show `[Encrypted Note]`). Listing reads plaintext `title` and `format` columns — does not parse blobs |
| R1.4 | Update a note's title or content by ID; no changes provided → no-op |
| R1.5 | Delete a note by ID |
| R1.6 | Reject empty or whitespace-only title or content on add |
| R1.7 | Return clear error for non-existent note IDs |
| R1.8 | Generate gap-safe unique IDs (UUID or max-ID+1); no collision after deletions |
| R1.9 | `--data-dir` must be a writable directory; existing file at path → error; no permission → error with message |
| R1.10 | Corrupt `notes.json` → back up as `notes.json.bak`, start empty, warn user |

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

Local JSON store with cross-session persistence. Scoped to pre-migration mode; superseded by R14 (database) after `migrate` command is run.

| ID | Requirement |
|----|-------------|
| R3.1 | Store notes in `<data-dir>/notes.json` (pre-migration only; replaced by database after migration) |
| R3.2 | Save after every mutation (add, update, delete) |
| R3.3 | Load existing notes on startup |
| R3.4 | Preserve encrypted records when loaded without a key |
| R3.5 | Handle listing, searching, fetching, deleting 1000+ notes within 0.5 seconds on reference hardware (documented test environment) without crashes or exceptions |
| R3.6 | Corrupt JSON detected on load → back up as `.bak`, start empty, warn user (pre-migration only; DB mode uses ACID transactions) |
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
| R6.2 | Unit tests cover core modules (Note, NoteStore, encryption) |
| R6.3 | Stress test validates 1000+ note volume safely |
| R6.4 | Tests run via `pytest` and `test_all.py` |
| R6.5 | Edge-case tests: whitespace inputs, ID collision, corrupt JSON, passphrase validation, permission errors |

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
| R8.4 | Personal mode: audit log at `<data-dir>/audit.log`. Server mode: per-user audit log at `<data-dir>/users/<hashed_user_id>/audit.log` (SHA-256 of `user_id`); missing file → created on first write |
| R8.5 | CLI `audit` command with `--limit N`, `--operation <type>`, `--since <date>` filters |
| R8.6 | Audit file unwritable → warn, do not block the operation |

## R9: Configuration

Persistent settings module.

| ID | Requirement |
|----|-------------|
| R9.1 | Store settings in `<data-dir>/config.json` |
| R9.2 | CLI commands: `config set`, `config get`, `config list`, `config reset` |
| R9.3 | Known keys only: `default_encrypt` (yes/no), `passphrase_min_length` (int), `data_dir` (path), `plugin_dir` (path), `deployment_mode` (personal/server), `allowed_plugins` (list); free-form keys rejected |
| R9.4 | Invalid value type for a key → error with expected type |
| R9.5 | Config file missing → all defaults used, file created on first `config set` |
| R9.6 | `DATABASE_URL` never stored in config; accepted from environment variable only |

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

## R11: GUI Layer *(Deferred)*

Graphical interface sharing core logic. Deferred to future sprint after CLI stabilization.

| ID | Requirement |
|----|-------------|
| R11.1 | GUI uses same core modules as CLI (NoteStore, EncryptionEngine, PluginRegistry) |
| R11.2 | Supports all CRUD operations through UI controls |
| R11.3 | No core logic duplication; framework decision pending |
| R11.4 | Passphrase prompted via dialog for encrypted notes |

## R12: Deployment Modes

Personal (single-user, local) vs Server (multi-user, remote DB) deployment.

| ID | Requirement |
|----|-------------|
| R12.1 | First-launch prompt: choose Personal or Server mode |
| R12.2 | Personal mode: single-user, no login, SQLite backend at `<data-dir>/notes.db` |
| R12.3 | Server mode: multi-user, login required, PostgreSQL backend via `DATABASE_URL` |
| R12.4 | Mode stored in `config.json` under `deployment_mode` (personal \| server) |
| R12.5 | Mode switch requires typed `CONFIRM MODE SWITCH`; warns about data migration |
| R12.6 | Account management commands hidden in personal mode |

## R13: Authentication (Server Mode)

User accounts and session management for multi-user deployment.

| ID | Requirement |
|----|-------------|
| R13.1 | `register` prompts for username and password interactively (`hide_input=True`); credentials never accepted as positional CLI arguments |
| R13.2 | Password stored as bcrypt hash; never stored or logged in plaintext |
| R13.3 | Username: 3–32 chars, alphanumeric + underscore only, case-insensitive uniqueness (`admin` == `Admin`) |
| R13.4 | Password minimum 8 characters |
| R13.5 | `login` prompts interactively; correct credentials → session token file at `<data-dir>/.session` (JSON: `user_id`, `username`, `created_at`, `expires_at`). File permissions restricted to creator and administrator only (Unix: `chmod 600`; Windows: ACL restricted to owner + Administrators) |
| R13.6 | Wrong credentials → error, no session created |
| R13.7 | Auth rate limiting: 5 consecutive failed login attempts → account locked for 5 minutes; tracked via `failed_attempts` and `locked_until` columns in `users` table |
| R13.8 | Session tokens expire after 24 hours; expired token → "Session expired, please log in again" error |
| R13.9 | All data commands require active, non-expired session in server mode; unauthenticated → error |
| R13.10 | `logout` deletes session token file; subsequent commands require re-login |
| R13.11 | Queries scoped by `user_id`; no cross-user data access |
| R13.12 | `delete-account` prompts password + typed `CONFIRM DELETE ACCOUNT`; purges entire per-user directory (audit logs, filesystem payloads, exports) and deletes user record from database |
| R13.13 | Config file tampering: `deployment_mode` changes validated — switching from `server` to `personal` requires `CONFIRM MODE SWITCH` even via config edit; mismatch between config and DB state → error |

## R14: Database Storage & Sandbox Binary Storage

Relational storage with sandbox binary model for note data.

| ID | Requirement |
|----|-------------|
| R14.1 | Personal mode: SQLite, zero-config, single-file database; WAL mode enabled with retry logic for concurrent CLI instances |
| R14.2 | Server mode: PostgreSQL, connection via `DATABASE_URL` environment variable only (never stored in config); connection must use `sslmode=require` |
| R14.3 | `notes` table columns: `note_id` (PK), `user_id` (FK, nullable in personal), `title` (plaintext, for fast listing), `format` (MIME type, plaintext), `encrypted_blob` (BLOB/bytea), `nonce` (nullable — NULL for unencrypted), `salt` (nullable — NULL for unencrypted), `is_encrypted` (bool), `payload_location` (enum: `inline` \| `filesystem` — filesystem only valid when `is_encrypted = true`) |
| R14.4 | Sandbox binary storage: blob uses length-prefixed framing; header (JSON) + payload (raw bytes). Encrypted notes: entire blob is AES-256-GCM ciphertext. Unencrypted notes: plaintext header + raw payload |
| R14.5 | No sensitive metadata (content, timestamps, tags, original_filename) stored outside the blob. `title` column stores a user-chosen alias for encrypted notes (defaults to `[Encrypted Note]` if omitted; authoritative title remains inside the blob). `format` duplicated as plaintext column for fast listing; authoritative copy remains inside the blob |
| R14.6 | ACID transactions on every mutation; concurrent writes must not corrupt data |
| R14.7 | `migrate` CLI command converts `notes.json` → database; backs up JSON before migration. Alert user that encrypted notes require passphrase entry for conversion to sandbox blob format. If user confirms, prompt passphrase per encrypted note; mismatched passphrase → skip that note with warning. Skipped notes remain in JSON backup. After all notes migrated successfully, prompt to securely delete backup; auto-deleted if confirmed. If any notes skipped, warn that backup must be kept |
| R14.8 | Size threshold: payloads ≤ 5 MB stored inline in `encrypted_blob` column. Payloads > 5 MB: only encrypted notes may use filesystem storage under per-user directory at `files/<note_id>.<ext>` (server: `<data-dir>/users/<hashed_uid>/files/`; personal: `<data-dir>/files/`). AES-256-GCM encrypted before writing to disk; DB stores path reference in blob header. Unencrypted notes always stored inline regardless of size (no plaintext files on disk). Orphan cleanup on note delete |
| R14.9 | Retrieval: decrypt blob → parse header. `text/*` format → display as plaintext. Binary format → write payload to per-user exports directory (`exports/<original_filename>`) with restricted permissions; display path and cleanup warning |
| R14.10 | `users` table (server mode only): `user_id` (PK), `username` (unique, case-insensitive), `password_hash`, `created_at`, `failed_attempts` (int, default 0), `locked_until` (nullable timestamp) |
| R14.11 | Schema versioned via Alembic; future schema changes applied through migration scripts |
| R14.12 | Disk-full errors caught at DB layer; actionable error message, no silent data loss |
| R14.13 | Server mode: user-specific data (audit log, filesystem payloads, exports) stored under `<data-dir>/users/<hashed_user_id>/` where directory name is SHA-256 hash of `user_id` (prevents enumeration). Personal mode: flat `<data-dir>/` layout. Per-user directory purged on `delete-account` |

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
