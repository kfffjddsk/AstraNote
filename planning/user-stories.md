# AstraNotes — User Stories & Acceptance Criteria

## US-1: Manage Notes (CRUD)
**As a** user, **I want to** add, view, list, update, and delete notes **so that** I can organize my information.

**Acceptance Criteria:**
- Add: valid title + content → saved with unique ID (UUID or max-ID+1). Empty/whitespace-only title or content → rejected.
- Get: retrieve by ID → title and content shown. Non-existent ID → "not found" error.
- List: all notes shown with ID, title, and format. Listing reads plaintext `title` and `format` columns; does not parse blobs. Empty store → "no notes found" message.
- Update: modify title/content by ID → saved. `get` reflects new content. Non-existent ID → error. No changes provided → no-op, no save triggered.
- Delete: remove by ID → gone from list. Non-existent ID → error.
- Non-zero exit code on all errors. Error messages are actionable.
- `--data-dir` sets storage location (default `data/`). Must be a writable directory; existing file at path → error; no write permission → error with message. Creates directory if needed.
- Corrupt `notes.json` → back up as `notes.json.bak`, start empty store, warn user.
- IDs are gap-safe; deletions never cause ID collision on subsequent adds.

## US-2: Encrypt and Decrypt Notes
**As a** user, **I want to** encrypt notes with a passphrase **so that** only I can access them.

**Acceptance Criteria:**
- `add --encrypt yes` → passphrase prompted twice (confirmation). Mismatch → retry or abort.
- **Sandbox binary storage:** all note data treated as a raw bitstream regardless of original format. The blob uses length-prefixed framing: `[4-byte header_length][JSON header][raw payload bytes]`. Header contains metadata (`title`, `timestamps`, `tags`, `format` MIME type, `original_filename`, `size_bytes`). Payload contains the raw content bytes (UTF-8 text, audio, video, image, etc.).
- For encrypted notes, the entire framed blob (header + payload) is encrypted with AES-256-GCM. No sensitive metadata stored outside the blob. On add, user may provide an optional alias for the plaintext `title` column (used for listing); defaults to `[Encrypted Note]` if omitted. When alias is provided, info message displayed: "Note: alias is stored unencrypted and visible without passphrase."
- For unencrypted notes, the framed blob is stored as-is (plaintext header + raw payload).
- Empty or whitespace-only passphrase → rejected. Minimum length: 8 characters.
- `reencrypt <note_id>` → prompts old passphrase, then new passphrase twice. Re-encrypts the blob with the new passphrase. If the note has a filesystem payload (>5 MB), the on-disk file is also re-encrypted.
- `get` encrypted note → passphrase prompted. Correct → decrypted content shown. Wrong → error, data preserved.
- `update` encrypted note → passphrase prompted. Correct → updated. Wrong → rejected, original preserved.
- `delete` encrypted note → passphrase prompted. Correct → removed. Wrong → rejected, note preserved.
- `list` → no passphrase prompt. Encrypted notes show user-chosen alias in title column (defaults to `[Encrypted Note]` if no alias provided). Listing reads plaintext `title` and `format` columns from the database — does not parse blobs.
- Unencrypted note operations never prompt for passphrase.
- Updating/deleting unencrypted notes must not corrupt co-stored encrypted notes.
- No default key; key manager required for all encrypted operations.

## US-3: Persist Notes Across Sessions *(Pre-migration only; superseded by US-12 after `migrate`)*
**As a** user, **I want** notes to persist after closing the CLI **so that** I keep my data.

**Acceptance Criteria:**
- Notes saved to `notes.json` after every add, update, or delete. (Pre-migration only; database storage via US-12 after migration.)
- All notes loaded on startup.
- Encrypted records preserved on no-key load.
- Corrupt JSON detected on load → back up as `.bak`, start empty, warn user.
- File write errors → catch and display actionable message (e.g., "Cannot write to <path>: permission denied").
- Store handles listing, searching, fetching, deleting 1000+ notes within 0.5 seconds without crashes or exceptions.

## US-4: Extend via Plugins
**As a** developer, **I want to** register plugins **so that** I can add behavior without modifying core code.

**Acceptance Criteria:**
- Plugins discovered and loaded from `plugins/` directory on startup.
- Plugins register hooks (e.g., `post_add_note`) via `PluginRegistry`.
- Plugins can provide additional CLI commands.
- Hook execution wrapped in try/except; plugin crash logged, does not kill the operation.
- Duplicate plugin registration → skip with warning.
- `overrides` field validated against override policy (US-5).
- Core security (CRUD and extension modules) immutable to plugins.
- Plugin allowlist in config (`allowed_plugins` key); only listed plugins loaded. Unsigned or unlisted plugins rejected with warning.

## US-5: Override Policy
**As a** developer, **I want** a red-alert confirmation before any core override **so that** destructive changes require explicit intent.

**Acceptance Criteria:**
- Triggered when a plugin declares an override on a core module (CRUD, encryption, persistence).
- Warning displayed in red: "Further action may damage notes or app — ensure you know what you are doing."
- User types `CONFIRM OVERRIDE` exactly to proceed; anything else → abort, no changes applied.
- Override scope limited to plugin hooks; normal user CRUD never triggers override prompt.
- All override attempts (success/failure) logged to audit trail (US-6).

## US-6: Audit Trail
**As a** user, **I want** an append-only audit log of security operations **so that** I can review what happened and when.

**Acceptance Criteria:**
- Log format: one JSON object per line. Fields: `timestamp` (ISO 8601), `operation` (encrypt/decrypt/passphrase_attempt/override/plugin_load/login/logout/register/delete_account/mode_switch/migrate/export), `note_id` (nullable), `outcome` (success/failure), `detail` (optional string).
- Encryption, decryption, passphrase attempts, overrides, plugin loads, login, logout, registration, account deletion, mode switches, migration, and export → appended to log.
- Log file is append-only during normal operation; entries never modified. Per-user log deleted only on `delete-account` (full user data purge).
- Personal mode: audit log at `<data-dir>/audit.log`. Server mode: per-user audit log at `<data-dir>/users/<hashed_user_id>/audit.log` (SHA-256 of `user_id`). Missing file → created on first write.
- `audit` CLI command with `--limit N`, `--operation <type>`, `--since <date>` filters.
- Audit file unwritable → warn, do not block the operation.

## US-7: Configuration
**As a** user, **I want** a configuration module **so that** I can store and retrieve app settings without editing code.

**Acceptance Criteria:**
- Settings stored in `<data-dir>/config.json`.
- Known keys: `default_encrypt` (yes/no), `passphrase_min_length` (int), `data_dir` (path), `plugin_dir` (path), `deployment_mode` (personal/server), `allowed_plugins` (list). Free-form keys rejected. `DATABASE_URL` accepted from environment variable only, never stored in config.
- `config set <key> <value>` → saves. `config get <key>` → retrieves. `config list` → shows all with defaults marked. `config reset <key>` → restores default.
- Config file missing → all defaults used, file created on first `config set`.
- Invalid value type for a key → error with expected type.
- Config changes take effect immediately without restart.

## US-8: Search and Export
**As a** user, **I want to** search and export notes **so that** I can find information quickly and use it outside the CLI.

**Acceptance Criteria:**
- `search <query>` → case-insensitive substring match on title and content.
- Search results show: ID, title, first 80 chars of content.
- No matches → "no notes found" message.
- Encrypted notes excluded from search unless `--encrypted` flag used (prompts passphrase once). Notes with different passphrases than the one provided remain excluded; no error, silently skipped.
- `export --format text|json --output <file>` → writes notes to specified file (default: `<data-dir>/export.<format>`). For binary notes, export writes raw payload file to per-user exports directory and includes path reference in the export manifest.
- Exported/retrieved files have restricted permissions (creator + administrator only). `export --cleanup` purges the user's exports directory. Warning displayed on export: "Decrypted data written to disk — run `export --cleanup` when done."
- Export 1000+ notes within 2 seconds.
- `export --encrypted` → prompt passphrase once, decrypt all encrypted notes for export. Without flag → encrypted notes exported as `[Encrypted Note]`.

## US-9: GUI Layer *(Epic — deferred)*
**As a** user, **I want** a graphical interface **so that** I can manage notes without the command line.

**Note:** Deferred to a future sprint after CLI stabilization. No acceptance criteria until framework decision made. Tracked as epic, not sprint-ready.

## US-10: Deployment Mode Selection
**As a** user, **I want to** choose between personal and server deployment modes **so that** the app fits my usage scenario.

**Acceptance Criteria:**
- On first launch (no config), prompt: "Personal" or "Server" mode.
- **Personal mode:** single-user, no login, local storage (SQLite). No account management commands exposed.
- **Server mode:** multi-user, login required on every launch. Database backend (PostgreSQL). User isolation enforced at data layer.
- Mode stored in `<data-dir>/config.json` under key `deployment_mode` (values: `personal` | `server`).
- Mode switch requires `CONFIRM MODE SWITCH` typed exactly; warns that data migration is needed.
- `config get deployment_mode` → shows current mode.

## US-11: User Authentication (Server Mode)
**As a** user in server mode, **I want to** log in before using the app **so that** my notes are isolated from other users.

**Acceptance Criteria:**
- `register` → prompts for username and password interactively (`hide_input=True`). Username must be unique, 3–32 chars, alphanumeric + underscore only, case-insensitive uniqueness (`admin` == `Admin`). Password min 8 chars; password stored as bcrypt hash. Credentials never accepted as positional CLI arguments.
- `login` → prompts for username and password interactively (`hide_input=True`). Correct credentials → session token written to `<data-dir>/.session` (JSON: `user_id`, `username`, `created_at`, `expires_at`). File permissions restricted to creator and administrator only. Wrong credentials → error, no session created.
- Session tokens expire after 24 hours. Expired token → "Session expired, please log in again" error.
- Auth rate limiting: 5 consecutive failed login attempts for a username → account locked for 5 minutes. Lockout tracked in `users` table (`failed_attempts`, `locked_until` columns).
- All CRUD, search, export, config commands require active session in server mode. Unauthenticated or expired → "Please log in first" error.
- `logout` → deletes session token file. Subsequent commands → login prompt.
- `delete-account` → prompts for password confirmation + typed `CONFIRM DELETE ACCOUNT`. Purges entire per-user directory (`<data-dir>/users/<hashed_user_id>/`) including notes, filesystem payloads, audit logs, and exported files. Deletes the user record from database.
- Each user's notes fully isolated; queries scoped by `user_id`. No cross-user access.
- Personal mode → these commands hidden; no auth checks on any operation.

## US-12: Database Storage Backend
**As a** user, **I want** notes stored in a database **so that** the app handles concurrency, multi-user isolation, and large volumes safely.

**Acceptance Criteria:**
- **Personal mode:** SQLite database at `<data-dir>/notes.db`. Zero-config, single file.
- **Server mode:** PostgreSQL connection configured via `DATABASE_URL` environment variable only (never stored in config file to avoid credential leakage). Connection must use `sslmode=require`.
- **Server mode user isolation (filesystem):** user-specific data stored under `<data-dir>/users/<hashed_user_id>/` where directory name is SHA-256 hash of `user_id` (prevents user enumeration). Contains: `audit.log`, `files/` (encrypted filesystem payloads), `exports/` (retrieved/exported files). Personal mode uses flat `<data-dir>/` layout. Entire per-user directory purged on `delete-account`.
- Schema: `users` table (server mode only), `notes` table with columns: `note_id` (PK), `user_id` (FK, nullable in personal mode), `title` (plaintext, for fast listing), `format` (MIME type, plaintext), `encrypted_blob`, `nonce` (nullable), `salt` (nullable), `is_encrypted` (bool), `payload_location` (enum: `inline` | `filesystem`).
- **Sandbox binary storage:** all content treated as a raw bitstream. Blob format: `[4-byte header_length][JSON header][raw payload bytes]`. Header: `{title, timestamps, tags, format (MIME), original_filename, size_bytes}`. Payload: raw content bytes.
- **Retrieval:** on `get`, decrypt blob → parse header. If `format` starts with `text/` → display content as plaintext in terminal. If binary (`audio/*`, `video/*`, `image/*`, `application/*`) → write payload to per-user exports directory (`exports/<original_filename>`) with restricted file permissions. Display path and cleanup warning.
- **Size threshold (5 MB):** payloads ≤ 5 MB stored inline in DB `encrypted_blob` column. Payloads > 5 MB: only encrypted notes may use filesystem storage under per-user directory at `files/<note_id>.<ext>` (server: `<data-dir>/users/<hashed_uid>/files/`; personal: `<data-dir>/files/`). AES-256-GCM encrypted before writing to disk; DB stores path reference in blob header. Unencrypted notes are always stored inline regardless of size. No plaintext files on disk.
- When a note is deleted, both inline blob and any filesystem payload are deleted (orphan cleanup).
- ACID transactions on every mutation; concurrent writes do not corrupt data.
- Migration path: `migrate` CLI command converts existing `notes.json` → database. Backs up JSON file before migration. Alerts user that encrypted notes require passphrase entry. If user confirms, prompts passphrase per encrypted note; mismatch → skip with warning; skipped notes remain in JSON backup. After all notes migrated successfully, prompt user to securely delete the backup; auto-deleted if confirmed. If any notes were skipped, warn that backup contains un-migrated notes and must be kept.
- Schema versioned via Alembic; future schema changes applied through migration scripts.
- SQLite uses WAL mode with retry logic for concurrent CLI instances.
- All database queries use parameterized statements via SQLAlchemy ORM; no raw SQL string interpolation.
- User inputs validated at CLI boundary: null bytes and non-printable control characters rejected.
- File path inputs validated against path traversal; reject `../` or absolute paths outside data-dir.
- PostgreSQL connection requires `sslmode=require`; `DATABASE_URL` accepted from env var only, never stored in config.
- PostgreSQL application role limited to DML only (no DDL privileges).
- Disk-full errors (`ENOSPC`) caught and reported as actionable error message; no silent data loss.
- Passphrase held in memory as Python string during session; not zeroizable (documented limitation).
