# AstraNotes — Requirements

## R1: Note Management (CRUD)

Create, read, list, update, and delete notes via CLI.

| ID | Requirement |
|----|-------------|
| R1.1 | Add a note with title and content; support text, audio, video formats |
| R1.2 | Retrieve note by ID; encrypted notes require passphrase |
| R1.3 | List notes with ID and title; hide title for encrypted notes |
| R1.4 | Update a note's title or content by ID |
| R1.5 | Delete a note by ID |
| R1.6 | Reject empty title or content on add |
| R1.7 | Return clear error for non-existent note IDs |

## R2: Encryption

Per-note opt-in encryption using AES-256-GCM with PBKDF2 key derivation.

| ID | Requirement |
|----|-------------|
| R2.1 | Opt-in encryption per note via `--encrypt yes` |
| R2.2 | Prompt for passphrase when adding an encrypted note |
| R2.3 | Prompt for passphrase when reading an encrypted note |
| R2.4 | Prompt for passphrase when updating an encrypted note |
| R2.5 | Prompt for passphrase when deleting an encrypted note |
| R2.6 | Never prompt for passphrase on unencrypted note operations |
| R2.7 | List command hides encrypted content as `[Encrypted Note]` without prompting |
| R2.8 | Reject wrong passphrase and preserve data |
| R2.9 | Encrypt both title and content independently |
| R2.10 | No default key; key manager required for encrypted operations |

## R3: Data Persistence

Local JSON store with cross-session persistence.

| ID | Requirement |
|----|-------------|
| R3.1 | Store notes in `<data-dir>/notes.json` |
| R3.2 | Save after every mutation (add, update, delete) |
| R3.3 | Load existing notes on startup |
| R3.4 | Preserve encrypted records when loaded without a key |
| R3.5 | Handle listing, searching, fetching, deleting 1000+ notes within 0.5 seconds without crashes or exceptions |

## R4: Plugin System

Hook-based architecture for extending CLI behavior.

| ID | Requirement |
|----|-------------|
| R4.1 | Plugin base class with name, version, and hook registration |
| R4.2 | Plugin registry manages hooks and dispatches calls |
| R4.3 | Plugins can register post-action hooks (e.g., `post_add_note`) |
| R4.4 | Plugins can provide additional CLI commands |
| R4.5 | Core security (CRUD and extension modules) immutable; handle extension crashes and isolate malware notes |

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

## R7: Override Policy

Red-alert confirmation for destructive core overrides.

| ID | Requirement |
|----|-------------|
| R7.1 | Display red warning: "Further action may damage notes or app—ensure you know what you are doing" |
| R7.2 | Require exact typed confirmation phrase to proceed |
| R7.3 | Abort on incorrect or empty confirmation |
| R7.4 | Log all override attempts (success and failure) |

## R8: Audit Trail

Append-only log for security operations.

| ID | Requirement |
|----|-------------|
| R8.1 | Log encryption, decryption, passphrase attempts, and overrides with timestamp, operation type, note ID, outcome |
| R8.3 | Log is append-only; no modification or deletion of entries |
| R8.4 | Store audit log in `<data-dir>/audit.log` |
| R8.5 | CLI `audit` command with optional `--limit` filter |

## R9: Configuration

Persistent settings module.

| ID | Requirement |
|----|-------------|
| R9.1 | Store settings in `<data-dir>/config.json` |
| R9.2 | `config set` and `config get` CLI commands |
| R9.3 | Default values when config missing or key absent |
| R9.4 | Handle invalid key/value with error message |

## R10: Search and Export

Find notes and export to external formats.

| ID | Requirement |
|----|-------------|
| R10.1 | `search <query>` matches title or content (case-insensitive) |
| R10.2 | Encrypted notes excluded from search unless decrypted |
| R10.3 | `export --format text\|json` writes notes to file |
| R10.4 | Encrypted notes exported as `[Encrypted Note]` unless passphrase provided |

## R11: GUI Layer

Graphical interface sharing core logic.

| ID | Requirement |
|----|-------------|
| R11.1 | GUI uses same core modules as CLI (NoteStore, EncryptionEngine, PluginRegistry) |
| R11.2 | Supports all CRUD operations through UI controls |
| R11.3 | Passphrase prompted via dialog for encrypted notes |
| R11.4 | No core logic duplication |
