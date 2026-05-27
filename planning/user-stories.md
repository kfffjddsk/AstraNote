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
- `--data-dir` sets storage location at runtime (overrides `config['data_dir']` from `ConfigStore`; see design.md §4.5). Must be a writable directory; existing file at path → error; no write permission → error with message. Creates directory if needed. `[REQ R1.9]` `[D-06]`
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

## US-3: Persist Notes Across Sessions — **Superseded by US-12**

> `DatabaseStore` (SQLite) is the only local store from Sprint 0. Persistence requirements are fully covered by US-12 (R14). `[D-10]`

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
- Audit log at `<data-dir>/audit.log` on the local device (flat layout; no per-user paths on device). `[REQ R8.4]` Missing file → created on first write. On the sync server (if self-hosted), a separate per-account audit log is maintained server-side; per-user server log deleted on `delete-account`.
- `audit` CLI command with `--limit N`, `--operation <type>`, `--since <date>` filters.
- Audit file unwritable → warn, do not block the operation.

## US-7: Configuration
**As a** user, **I want** a configuration module **so that** I can store and retrieve app settings without editing code.

**Acceptance Criteria:**
- Settings stored at a fixed OS-standard path: `%APPDATA%\astranotes\config.json` (Windows) / `~/.config/astranotes/config.json` (Linux/macOS). Config is separate from `data_dir`; `--data-dir` overrides `config["data_dir"]` at runtime but does not move the config file. `[D-06 resolved 2026-05-11]`
- Known keys: `default_encrypt` (yes/no), `passphrase_min_length` (int), `data_dir` (path), `plugin_dir` (path), `allowed_plugins` (list), `theme` (light/dark), `font_size` (int), `sync_server_url` (URL), `sync_auto_interval` (int, seconds, 0 = disabled). Free-form keys rejected. `DATABASE_URL` accepted from environment variable only, never stored in config.
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

## US-9: Personal GUI *(Planned — Sprint 4)*
**As a** personal user, **I want** a simple graphical note-taking app **so that** I can manage notes without the command line, with an experience similar to mainstream note apps.

**Source:** R11.1–R11.6 `[LOG 05-04]`

**Acceptance Criteria:**
- GUI exposes all CRUD operations (add, get, list, update, delete) through visual controls — no terminal required.
- Note list displayed on the left; content editor displayed on the right. Minimal chrome; no unneeded sidebars or toolbars.
- Passphrase for encrypted notes prompted via modal dialog (not terminal prompt).
- Desktop app uses the same local SQLite store as the CLI; no server required. The core modules (`DatabaseStore`, `EncryptionEngine`, `PluginRegistry`) are shared directly — no duplication of logic.
- GUI framework decided: PySide6 (ADR-13); `astranotes gui` launches a `QApplication` main window directly; no terminal remains open.
- All data operations pass the same test suite as the CLI (shared core).

## US-13: Security & Injection Prevention
**As a** user, **I want** the app to reject malicious inputs and enforce secure data access **so that** my notes and credentials cannot be compromised through injection attacks.

**Source:** R15 (Injection Prevention)

**Acceptance Criteria:**
- All database queries use parameterized statements via SQLAlchemy ORM; no raw SQL string concatenation or f-string interpolation allowed. `[R15.1, R15.2]`
- All user inputs validated at the CLI boundary: null bytes (`\x00`) and non-printable control characters (U+0000–U+001F except `\n`, `\t`) rejected in title, content, username, and search queries. Invalid input → clear error message. `[R15.3]`
- PostgreSQL connection role limited to `SELECT`, `INSERT`, `UPDATE`, `DELETE` on application tables; no DDL privileges (`DROP`, `ALTER`, `CREATE`). `[R15.4]`
- ANSI escape sequences and terminal control codes stripped from note content before rendering to terminal output. `[R15.5]`
- Export output never evaluated or interpreted as code; special characters escaped. `[R15.6]`
- Plugins receive note data as read-only copies; plugin code never receives `exec()`, `eval()`, or shell-access APIs; plugins cannot access raw DB connection. `[R15.7]`
- File path inputs (`--data-dir`, `--output`, attachment paths) validated against path traversal (`../`, absolute paths outside data-dir); invalid paths rejected. `[R15.8]`
- PostgreSQL connections must use `sslmode=require`; connections without SSL rejected at startup. `[R15.9]`

## US-10: Local-First with Opt-In Account  `[LOG 05-04]`
**As a** user, **I want** the app to work immediately without any setup or login **so that** I can start taking notes right away, and optionally add an account later to enable sync.

**Source:** R12 `[LOG 05-04]`

**Acceptance Criteria:**
- App starts and all CRUD operations work with no configuration, no login prompt, and no mode selection.
- Notes created without an account have `account_id = NULL` (device-local / anonymous).
- `astranotes login` (or GUI login button) is available at any time but is never required to use the app.
- When a user logs in for the first time on a device that already has anonymous notes, a one-time prompt appears: "You have N local notes. Associate them with your account? [Yes / No / Ask me for each]". The user's answer is recorded; the prompt never repeats.
- After login, new notes automatically receive the active `account_id`. A `--local` flag allows creating a note that stays anonymous even while logged in.
- `logout` detaches the session. Local notes (including account-associated ones) remain fully accessible offline. Cloud sync simply stops until next login.
- Multiple accounts may coexist on one device; switching account shows that account's notes plus optionally anonymous notes.

## US-11: Optional Account and Authentication  `[LOG 05-04]`
**As a** user, **I want** to optionally create an account **so that** I can sync notes across devices and separate my notes from others on shared machines.

**Source:** R13 `[LOG 05-04]`

**Acceptance Criteria:**
- `register` → prompts for username and password interactively (`hide_input=True`). Username: 3–32 chars, alphanumeric + underscore, case-insensitive unique. Password min 8 chars; stored as bcrypt hash. Credentials never accepted as positional arguments.
- `login` → prompts interactively. Correct credentials → session token written to `<data-dir>/.session` (`account_id`, `username`, `created_at`, `expires_at`). File permissions restricted to owner only.
- Wrong credentials → error, no session created. Rate limiting: 5 failures → account locked 5 minutes.
- Session tokens expire after 24 hours. An expired session only blocks cloud sync and account-scoped visibility — **all local CRUD operations continue unaffected**.
- `logout` → deletes session token. Local notes (including account-associated ones) remain readable and writable.
- When logged in, note list shows the active account's notes plus anonymous notes. When logged out, only anonymous notes shown.
- `delete-account` → prompts password + typed `CONFIRM DELETE ACCOUNT`. Detaches `account_id` from all local notes (sets to NULL); deletes account record from server; warns user that cloud copies will be deleted.
- OAuth 2.0 / OpenID Connect (Google minimum, via authlib) supported as alternative login method in the desktop app. Provider token exchanged for a local session token. `[R13.13, R13.14]`

## US-12: SQLite Local Store and Cloud Sync Backend  `[LOG 05-04]`
**As a** user, **I want** notes stored reliably in a local SQLite database with an optional path to cloud sync **so that** my data is safe, fast, and portable.

**Source:** R14, R16 `[LOG 05-04]`

**Acceptance Criteria:**
- Local store: SQLite at `<data-dir>/notes.db`. Zero-config, always-on. WAL mode with retry logic for concurrent CLI + GUI access.
- `notes` table includes a nullable `account_id` column (`NULL` = anonymous/device-local; non-null = account-associated and sync-eligible), plus `synced_at` (nullable timestamp, `NULL` = never synced).
- `accounts` table created locally on first `register` or `login`: `account_id` (UUID PK), `username`, `password_hash`, `created_at`, `failed_attempts`, `locked_until`.
- Data directory is flat: `<data-dir>/notes.db`, `<data-dir>/files/`, `<data-dir>/exports/`, `<data-dir>/audit.log`. No per-user subdirectory structure on the local device.
- **Sandbox binary storage:** blob format `[4-byte header_length][JSON header][raw payload bytes]`. Encrypted notes: entire blob is AES-256-GCM ciphertext.
- **Retrieval:** decrypt blob → parse header. `text/*` → display in terminal. Binary → write to `<data-dir>/exports/<original_filename>` with restricted permissions; display path + cleanup warning.
- **Size threshold:** payloads ≤ 5 MB inline in DB. Payloads > 5 MB: only encrypted notes may use filesystem storage at `<data-dir>/files/<note_id>.<ext>`; path stored in blob header. Unencrypted notes always stored inline.
- **Cloud sync (requires account session):** `sync push` sends blobs newer than last `synced_at` to the sync server; `sync pull` fetches account notes updated after the last pull timestamp and merges into local SQLite. Conflict resolution: on pull conflict, desktop shows `MergeWindow` (2-pane: local read-only left, remote editable right); user saves final version. `[D-14 decided 2026-05-14]`
- Sync server uses PostgreSQL via `DATABASE_URL` env var only (`sslmode=require`). Schema versioned via Alembic.
- All queries use SQLAlchemy ORM (parameterized). ACID transactions on every mutation. Disk-full errors reported without silent data loss.

## US-14: Cloud Sync via Desktop App  `[LOG 05-04]`
**As a** logged-in user, **I want** to sync my notes to a cloud server and access them from the desktop app on any device **so that** I'm not locked to a single machine.

**Source:** R11.7–R11.10, R11.12, R13.13–R13.14, R16 `[LOG 05-04]`

**Acceptance Criteria:**
- Login via Google OAuth 2.0 / OpenID Connect (authlib) or local username/password. Both flows produce a local session token.
- `sync push` sends all account-associated notes newer than last `synced_at` to the sync server. `sync pull` fetches notes updated since last pull and merges into local SQLite.
- Conflict resolution: on pull conflict, desktop shows `MergeWindow` (2-pane: local read-only left, remote editable right); user saves final version. `[D-14 decided 2026-05-14]`
- **Desktop app (Sprint 5B):** sync button triggers push/pull; login dialog (Google OAuth PKCE or local credentials) appears if no active session. Sync-status dot per note row reflects last sync timestamp.
- **GUI (Sprint 4):** same local SQLite; sync button triggers push/pull.
- All sync server traffic over HTTPS. Sync endpoints require valid JWT; return HTTP 401 otherwise.
- Rate limiting: 60 sync requests/minute per account; HTTP 429 with `Retry-After` on excess.
