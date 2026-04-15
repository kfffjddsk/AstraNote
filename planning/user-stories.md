# AstraNotes — User Stories & Acceptance Criteria

## US-1: Manage Notes (CRUD)
**As a** user, **I want to** add, view, list, update, and delete notes **so that** I can organize my information.

**Acceptance Criteria:**
- Add: valid title + content → saved with ID confirmation. Empty title/content → rejected.
- Get: retrieve by ID → title and content shown. Non-existent ID → "not found" error.
- List: all notes shown with IDs. Empty store → "no notes found" message.
- Update: modify title/content by ID → saved. `get` reflects new content. Non-existent ID → error.
- Delete: remove by ID → gone from list. Non-existent ID → error.
- Non-zero exit code on all errors. Error messages are actionable.
- `--data-dir` sets storage location (default `data/`), creates directory if needed.

## US-2: Encrypt and Decrypt Notes
**As a** user, **I want to** encrypt notes with a passphrase **so that** only I can access them.

**Acceptance Criteria:**
- `add --encrypt yes` → passphrase prompted, title and content encrypted independently.
- `get` encrypted note → passphrase prompted. Correct → decrypted content shown. Wrong → error, data preserved.
- `update` encrypted note → passphrase prompted. Correct → updated. Wrong → rejected, original preserved.
- `delete` encrypted note → passphrase prompted. Correct → removed. Wrong → rejected, note preserved.
- `list` → no passphrase prompt. Encrypted notes show `[Encrypted Note]`.
- Unencrypted note operations never prompt for passphrase.
- No default key; key manager required for all encrypted operations.

## US-3: Persist Notes Across Sessions
**As a** user, **I want** notes to persist after closing the CLI **so that** I keep my data.

**Acceptance Criteria:**
- Notes saved to `notes.json` after every add, update, or delete.
- All notes loaded on startup.
- Encrypted records preserved on no-key load.
- Store handles 1000+ notes without corruption.

## US-4: Extend via Plugins
**As a** developer, **I want to** register plugins **so that** I can add behavior without modifying core code.

**Acceptance Criteria:**
- Plugins register hooks (e.g., `post_add_note`) via `PluginRegistry`.
- Plugins can provide additional CLI commands.
- Core security immutable to plugins.

## US-5: Override Policy
**As a** developer, **I want** a red-alert confirmation before any core override **so that** destructive changes require explicit intent.

**Acceptance Criteria:**
- Core-override attempt → red-alert warning displayed with risk description.
- User must type exact confirmation phrase (e.g., `CONFIRM OVERRIDE`) to proceed.
- Incorrect or empty confirmation → operation aborted, no changes applied.
- Override policy enforced for plugin hooks that touch core security.
- All override attempts logged (success and failure).

## US-6: Audit Trail
**As a** user, **I want** an append-only audit log of security operations **so that** I can review what happened and when.

**Acceptance Criteria:**
- Encryption, decryption, passphrase attempts, and overrides → appended to audit log.
- Each entry includes timestamp, operation type, note ID, and outcome (success/failure).
- Log file is append-only; existing entries never modified or deleted.
- Audit log stored in `<data-dir>/audit.log`.
- `audit` CLI command lists recent entries with optional `--limit` filter.

## US-7: Configuration
**As a** user, **I want** a configuration module **so that** I can store and retrieve app settings without editing code.

**Acceptance Criteria:**
- Settings stored in `<data-dir>/config.json`.
- `config set <key> <value>` → saves setting. `config get <key>` → retrieves it.
- Default values used when config file missing or key absent.
- Invalid key/value → error with actionable message.
- Config changes take effect immediately without restart.

## US-8: Search and Export
**As a** user, **I want to** search and export notes **so that** I can find information quickly and use it outside the CLI.

**Acceptance Criteria:**
- `search <query>` → returns notes matching title or content (case-insensitive).
- No matches → "no notes found" message.
- Encrypted notes excluded from search unless decrypted first.
- `export --format text|json` → writes all notes to file in chosen format.
- Export respects `--data-dir` for output location.
- Encrypted notes exported as `[Encrypted Note]` unless passphrase provided.

## US-9: GUI Layer
**As a** user, **I want** a graphical interface **so that** I can manage notes without using the command line.

**Acceptance Criteria:**
- GUI shares core logic (`NoteStore`, `EncryptionEngine`, `PluginRegistry`).
- Supports add, get, list, update, delete through UI controls.
- Encrypted note operations prompt for passphrase via dialog.
- No core logic duplicated; GUI calls the same modules as CLI.
