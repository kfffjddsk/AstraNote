# AstraNotes — Design Document

**Version:** 1.2  
**Date:** May 4, 2026  
**Status:** Draft — under review  
**Owner:** Human team member  
**AI Partner:** Astra (GitHub Copilot)

> Traceability notation used throughout: `[REQ Rx.y]` = `planning/requirements.md`,
> `[US-n]` = `planning/user-stories.md`, `[BL B-nn]` = `planning/backlog.md`,
> `[LOG 04-08]` / `[LOG 04-15]` = `AI Working Log/`, `[SRC]` = current source code.

---

## 1. Purpose and Scope

This document describes the software design of AstraNotes: the module structure, class responsibilities, data flows, storage model, and the decisions that produced the current architecture. It bridges the requirements (`docs/prd.md`) and the implementation (`src/`).

AstraNotes uses a **three-layer additive model** — each layer is independent and optional on top of the previous:  `[LOG 05-04]`
- **Layer 1 — Local store (always on):** SQLite at `<data-dir>/notes.db`; all CRUD works immediately with no login or configuration.
- **Layer 2 — Account (opt-in):** `register`/`login` commands add an account. Notes gain a nullable `account_id`; existing anonymous notes can be associated on first login.
- **Layer 3 — Cloud sync (opt-in, requires account):** `sync push` / `sync pull` mirror account-associated notes to the FastAPI sync server; last-write-wins conflict resolution.

The CLI is the primary interface for Sprints 0–3. A PySide6 desktop app (Sprint 4: local CRUD; Sprint 5: sync added) shares the same core modules and SQLite local store. There is no browser-based surface — the sync server (Sprint 5) is a backend-only REST service.

Two design layers are described:
- **Implemented (Sprint Zero):** what exists in `src/` today.
- **Planned:** design for backlog items not yet coded, drawn from requirements and working logs.

---

## 2. UML Package Diagram

The system is organized into five top-level packages. The CLI and desktop GUI depend on Core; Core is self-contained; Plugins depend on Core; the sync server is a backend-only REST service called by the desktop GUI for push/pull. There is no browser-based surface.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  <<package>>  sync_server  [planned, Sprint 5]  `[LOG 05-04]`            │
│   FastAPI sync server (ADR-11 → decided: FastAPI) — backend REST only    │
│   SyncRouter  AuthMiddleware (JWT / OAuth via authlib; ADR-12)           │
│   No browser-facing endpoints; no static file serving                    │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ HTTPS (sync endpoints only)
   ┌─────────────────────────────┘
   │
   │    ┌──────────────────────────────────────────────────────┐
   │    │  <<package>>  desktop_gui  [planned, Sprint 4/5]     │
   │    │   PySide6 desktop app (ADR-13 → decided: PySide6)    │
   │    │   Sprint 4: CRUD + local SQLite                      │
   │    │   Sprint 5: adds sync button + OAuth login flow      │
   │    │   Shares NoteStore, EncryptionEngine, PluginRegistry │
   └────┼──► uses core modules                                 │
        └─────────────────────────┬────────────────────────────┘
                                  │ uses core modules
┌─────────────────────────────────▼────────────────────────────────────────┐
│  <<package>>  src                                                        │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │  <<package>>  cli                                                 │   │
│  │   cli.py  (Click commands: add, get, list, update, delete)        │   │
│  └────────────────────────────┬──────────────────────────────────────┘   │
│                               │ uses                                     │
│  ┌────────────────────────────▼──────────────────────────────────────┐   │
│  │  <<package>>  core                                                │   │
│  │                                                                   │   │
│  │   notes.py         security.py        plugin_base.py              │   │
│  │   Note             EncryptionEngine   PluginBase (ABC)            │   │
│  │   NoteStore        KeyManager         PluginRegistry              │   │
│  │                                                                   │   │
│  │   [Planned]        [Planned]           [Planned]                  │   │
│  │   DatabaseStore    AuditLogger         ConfigStore                │   │
│  │   AuthManager      BlobCodec                                      │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  <<package>>  plugins                                                    │
│   SummaryPlugin  (implements PluginBase)                                 │
│   [future plugins register via PluginRegistry]                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**Dependency rules:**
- `cli` → `core` → (stdlib / cryptography). `plugins` → `core`.
- `personal_gui` → `core` directly (no server required).
- `sync_server` → `core`; `web_client` → `sync_server` via HTTPS (sync push/pull only). `[LOG 05-04]`
- `core` **never** imports from `cli`, `plugins`, `personal_gui`, `rest_api`, or `web_client`.

---

## 3. Class Diagrams

### 3.1 Implemented Classes

```
┌──────────────────────────────┐
│  Note                        │
│  (dataclass)                 │
├──────────────────────────────┤
│ + id: str                    │
│ + title: str                 │
│ + content: str               │
│ + created_at: str  (ISO UTC) │
│ + modified_at: str (ISO UTC) │
│ + metadata: dict             │
│ + encrypted: bool            │
│ + encrypted_title: str|None  │
├──────────────────────────────┤
│ + update(title, content)     │
└──────────────┬───────────────┘
               │ stored in
               ▼
┌──────────────────────────────┐
│  NoteStore                   │
├──────────────────────────────┤
│ - path: Path                 │
│ - key_manager: KeyManager?   │
│ - _notes: dict[str, Note]    │
├──────────────────────────────┤
│ + load()                     │
│ + save()                     │
│ + add(note)                  │
│ + get(note_id) → Note?       │
│ + update(note_id, …) → Note  │
│ + delete(note_id)            │
│ + list() → List[Note]        │
└──────────────┬───────────────┘
               │ uses (optional)
               ▼
┌──────────────────────────────┐
│  KeyManager                  │
├──────────────────────────────┤
│ - passphrase: str            │
├──────────────────────────────┤
│ + get_engine() → Engine      │
└──────────────┬───────────────┘
               │ creates
               ▼
┌──────────────────────────────┐
│  EncryptionEngine            │
├──────────────────────────────┤
│ - passphrase: str            │
│ - salt: bytes  (16 B)        │
├──────────────────────────────┤
│ + derive_key() → bytes       │
│ + encrypt(plaintext) → str   │
│ + decrypt(ciphertext) → bytes│
└──────────────────────────────┘
  Algorithm: AES-256-GCM
  KDF: PBKDF2-HMAC-SHA256, 100 000 iterations
  Wire format: [16B salt][12B IV][16B GCM tag][ciphertext] → base64

┌──────────────────────────────┐
│  PluginBase  <<ABC>>         │
├──────────────────────────────┤
│ + name: str                  │
│ + version: str               │
│ + overrides: list            │
├──────────────────────────────┤
│ + register_hooks(registry)*  │
│ + get_commands() → dict      │
└──────────────────────────────┘

┌──────────────────────────────┐
│  PluginRegistry              │
├──────────────────────────────┤
│ - hooks: dict[str, list[fn]] │
│ - plugins: list[PluginBase]  │
├──────────────────────────────┤
│ + register_plugin(plugin)    │
│ + register_hook(name, fn)    │
│ + call_hook(name, *args)     │
└──────────────────────────────┘
```

### 3.2 Planned Classes (Backlog)

```
┌──────────────────────────────┐
│  DatabaseStore  [planned]    │  replaces NoteStore post-migrate
├──────────────────────────────┤  [BL B-42, B-44] [REQ R14]  `[LOG 05-04]`
│ - engine: SQLAlchemy Engine  │
│ - session: Session           │
├──────────────────────────────┤
│ + add(note) → note_id        │
│ + get(note_id, account_id)   │
│ + update(note_id, …)         │
│ + delete(note_id)            │
│ + list(account_id) → List    │  NULL = anonymous notes only
│ + search(query, account_id)  │
└──────────────────────────────┘
  Local store:  SQLite (WAL) — always on; no mode selection
  Sync server:  PostgreSQL (sslmode=require)
  All queries via ORM; no raw SQL  [REQ R15.1, R15.2]  `[LOG 05-04]`

┌──────────────────────────────┐
│  BlobCodec  [planned]        │  sandbox binary storage
├──────────────────────────────┤  [REQ R2.9, R14.4]
│ + encode(header, payload)    │  → [4B len][JSON header][payload]
│ + decode(blob) → (hdr, body) │
│ + encrypt(blob, engine)      │  → AES-256-GCM ciphertext
│ + decrypt(ciphertext, engine)│
└──────────────────────────────┘

┌──────────────────────────────┐
│  AuthManager  [planned]      │  optional; never gates local CRUD
├──────────────────────────────┤  [REQ R13] [BL B-45–B-48]  `[LOG 05-04]`
│ - session_path: Path         │
├──────────────────────────────┤
│ + register(username, pw)     │  bcrypt hash; creates accounts row
│ + login(username, pw)        │  → writes .session token
│ + logout()                   │  → deletes .session; notes intact
│ + verify_session()→account_id│
│ + delete_account(account_id) │  sets account_id=NULL on local notes
└──────────────────────────────┘

┌──────────────────────────────┐
│  AuditLogger  [planned]      │
├──────────────────────────────┤  [REQ R8] [BL B-25]
│ - log_path: Path             │
├──────────────────────────────┤
│ + log(operation, note_id,    │
│       outcome, detail)       │  append-only JSON line
└──────────────────────────────┘

┌──────────────────────────────┐
│  ConfigStore  [planned]      │
├──────────────────────────────┤  [REQ R9] [BL B-26]
│ - config_path: Path          │
│ - ALLOWED_KEYS: frozenset    │
├──────────────────────────────┤
│ + get(key) → value           │
│ + set(key, value)            │
│ + list() → dict              │
│ + reset(key)                 │
└──────────────────────────────┘

┌──────────────────────────────┐
│  DesktopGUI  [planned]        │  PySide6 desktop app (Sprint 4: CRUD; Sprint 5: sync)
├──────────────────────────────┤  [REQ R11.1–R11.12] [BL B-84, B-85, B-89, B-90]
│ - store: DatabaseStore       │  [US-9, US-14] [ADR-13 decided]
│ - key_manager: KeyManager    │
│ - auth_manager: AuthManager  │
├──────────────────────────────┤
│ + show_note_list()           │  QListWidget left pane
│ + show_note(note_id)         │  QTextEdit right pane
│ + prompt_passphrase() → str  │  QDialog modal, auto-focus, Escape closes
│ + on_add() / on_edit()       │
│ + on_delete()                │
│ + on_sync()                  │  Sprint 5: triggers push/pull; prompts login if no session
│ + show_settings()            │  QDialog (tabbed):
│                              │    General tab — data directory, default encryption on/off,
│                              │      min passphrase length, theme (light/dark), font size
│                              │    Account tab (Sprint 5) — username, login/logout button,
│                              │      delete-account button
│                              │    Sync tab (Sprint 5) — sync server URL, auto-sync interval
│                              │      (Off / 5 min / 15 min / 1 hr), last-synced timestamp
└──────────────────────────────┘
  Framework: PySide6 (ADR-13 decided)  [LOG 05-04]
  Startup: `astranotes gui` → QApplication → main window opens → blocks until window closed
  Layout: two-pane (note list + sync-status dot left; title + editor right); menu bar; toolbar
  Sprint 4 dependency: core modules only; no sync server required
  Sprint 5 dependency: adds sync server calls (HTTPS push/pull) and OAuth login flow

┌──────────────────────────────┐
│  SyncRouter  [planned]       │  sync server — push/pull only
├──────────────────────────────┤  [REQ R16.1] [BL B-86] [US-14]  `[LOG 05-04]`
│ + push(req) → status         │  POST  /sync/push
│ + pull(req, since) → List    │  GET   /sync/pull?since=<ts>
└──────────────────────────────┘
  All endpoints: require valid JWT (delegated to AuthMiddleware)
  Queries scoped by account_id from token  [REQ R16.4]  `[LOG 05-04]`

┌──────────────────────────────┐
│  AuthMiddleware  [planned]   │  OAuth + JWT validation
├──────────────────────────────┤  [REQ R13.14, R16.2, R16.7]
│                              │  [BL B-87, B-88, B-95] [US-11, US-14]
├──────────────────────────────┤
│ + validate_token(req)        │  → account_id or raise HTTP 401
│ + oauth_callback(code)       │  → exchange code → JWT (authlib)
│ + enforce_rate_limit(acct_id)│  60 req/min; HTTP 429 on excess  `[LOG 05-04]`
└──────────────────────────────┘
  Framework: FastAPI (ADR-11 — decided)  `[LOG 05-04]`
  OAuth provider: Google via authlib (ADR-12 — decided); extensible  `[LOG 05-04]`
```

---

## 4. Component Interactions

### 4.1 Add Note (unencrypted) — current

```
User
 │  astranotes add --title "T" --content "C"
 ▼
cli.add()
 │  validates title/content not empty          [REQ R1.6]
 │  NoteStore(path, key_manager=None)
 │  note_id = len(list) + 1                    [BL B-31 — gap-safe ID pending]
 │  Note(id, title, content, encrypted=False)
 │  store.add(note)
 │    └─ save() → writes notes.json            [REQ R3.2]
 ▼
"Note 'T' added with ID 1 (unencrypted)"
```

### 4.2 Add Note (encrypted) — current

```
User
 │  astranotes add --title "T" --content "C" --encrypt yes
 ▼
cli.add()
 │  ensure_store() → prompts passphrase        [REQ R2.1]
 │  KeyManager(passphrase)
 │  NoteStore(path, key_manager)
 │  Note(id, title, content, encrypted=True)
 │  store.add(note)
 │    └─ save()
 │         EncryptionEngine.encrypt(content)   [REQ R2.9] AES-256-GCM
 │         EncryptionEngine.encrypt(title)
 │         writes notes.json                   [REQ R3.2]
 ▼
"Note 'T' added with ID 1 (encrypted)"
```

### 4.3 Add Note — planned (post-sandbox-blob)

```
cli.add()
 │  validate input at CLI boundary             [REQ R15.3]
 │  BlobCodec.encode(header_json, payload_bytes)
 │  ─ if encrypted: BlobCodec.encrypt(blob, engine)
 │  ─ if payload > 5 MB and encrypted:
 │       write encrypted file to files/<note_id>.<ext>
 │       set payload_location = 'filesystem'    [REQ R14.8]
 │  DatabaseStore.add(note_row)                 [REQ R14.6] ACID
 │  AuditLogger.log("encrypt", note_id, …)      [REQ R8.2]
 │  PluginRegistry.call_hook("post_add_note")   [REQ R4.3]
```

### 4.4 Plugin Hook Dispatch

```
PluginRegistry.call_hook("post_add_note", note)
 │
 ├─ for each registered fn:
 │    try:
 │      fn(note_copy)      ← read-only copy     [REQ R15.7]
 │    except Exception as e:
 │      log warning, continue                   [REQ R4.7]
```

---

## 5. Data Model

### 5.1 Current: `notes.json`

```json
{
  "1": {
    "id": "1",
    "title": "My Note",
    "content": "Hello",
    "created_at": "2026-04-08T10:00:00Z",
    "modified_at": "2026-04-08T10:00:00Z",
    "metadata": {},
    "encrypted": false,
    "encrypted_title": null
  },
  "2": {
    "id": "2",
    "content": "<base64-encoded AES-256-GCM ciphertext>",
    "encrypted_title": "<base64-encoded AES-256-GCM ciphertext>",
    "encrypted": true,
    ...
  }
}
```

### 5.2 Planned: Database Schema

**`notes` table** — local SQLite (always active)  `[REQ R14.3]`  `[LOG 05-04]`

| Column | Type | Notes |
|--------|------|-------|
| `note_id` | TEXT PK | UUID (gap-safe) `[BL B-31]` |
| `account_id` | TEXT FK nullable | NULL = anonymous/device-local `[LOG 05-04]` |
| `title` | TEXT | Plaintext alias for fast listing `[REQ R14.5]` `[BL B-74]` |
| `format` | TEXT | MIME type, plaintext for fast listing |
| `encrypted_blob` | BLOB/bytea | Full sandbox blob (see §5.3) |
| `nonce` | BLOB nullable | NULL for unencrypted |
| `salt` | BLOB nullable | NULL for unencrypted |
| `is_encrypted` | BOOLEAN | |
| `payload_location` | TEXT | `inline` or `filesystem` `[REQ R14.8]` |
| `synced_at` | TIMESTAMP nullable | NULL = never synced to cloud `[LOG 05-04]` |

**`accounts` table** — local SQLite (created on first `register`/`login`)  `[REQ R14.10]`  `[LOG 05-04]`

| Column | Type | Notes |
|--------|------|-------|
| `account_id` | TEXT PK | UUID `[LOG 05-04]` |
| `username` | TEXT UNIQUE | Case-insensitive `[REQ R13.3]` |
| `password_hash` | TEXT | bcrypt `[REQ R13.2]` |
| `created_at` | TIMESTAMP | |
| `failed_attempts` | INTEGER | Default 0 `[REQ R13.7]` |
| `locked_until` | TIMESTAMP nullable | Rate-limit lockout `[REQ R13.7]` |

### 5.3 Sandbox Blob Wire Format  `[REQ R2.9, R14.4]`

```
┌────────────────┬──────────────────────────────────┬──────────────────┐
│  4 bytes       │  header_length bytes             │  remaining bytes │
│  header_length │  JSON header (UTF-8)             │  raw payload     │
│  (big-endian)  │  {title, timestamps, tags,       │  (any format)    │
│                │   format, original_filename,     │                  │
│                │   size_bytes}                    │                  │
└────────────────┴──────────────────────────────────┴──────────────────┘

For encrypted notes: entire blob above is the AES-256-GCM plaintext input.
Stored as: [16B salt][12B nonce][16B GCM tag][ciphertext]

For unencrypted notes: blob stored as-is. No sensitive metadata outside blob.
```

### 5.4 Session Token Format  `[REQ R13.5]`

```json
{
  "account_id": "<uuid>",
  "username": "alice",
  "created_at": "2026-05-04T09:00:00Z",
  "expires_at": "2026-05-05T09:00:00Z"
}
```
File: `<data-dir>/.session` — permissions restricted to owner only.  `[LOG 05-04]`
An expired session blocks cloud sync but does **not** prevent local CRUD.

### 5.5 Audit Log Format  `[REQ R8.1]`

One JSON object per line:
```json
{"timestamp": "2026-05-04T09:01:00Z", "operation": "encrypt", "note_id": "abc123", "outcome": "success", "detail": null}
{"timestamp": "2026-05-04T09:02:00Z", "operation": "passphrase_attempt", "note_id": "abc123", "outcome": "failure", "detail": "wrong passphrase"}
```

---

## 6. Architecture Decision Log

Each entry records the decision, alternatives considered, rationale, and the source artifact where it was made.

---

### ADR-01: Sandbox Binary Blob Storage Model  
**Status:** Accepted  `[LOG 04-15]` `[REQ R2.9, R14.4]`

**Context:** Early design encrypted title and content as separate strings. This left timestamps, tags, and MIME type in plaintext — a metadata leak that weakens the encryption guarantee.

**Decision:** Treat all note data as a raw bitstream regardless of format. Use length-prefixed framing `[4B header_length][JSON header][raw payload bytes]`. Encrypt the entire framed blob with AES-256-GCM for encrypted notes. No sensitive metadata stored outside the blob.

**Alternatives considered:**
- Encrypt each field independently → metadata still exposed in JSON keys
- Pack all fields into a single JSON string → breaks binary payloads (audio, video)

**Consequences:** Database cannot query encrypted fields; search requires client-side decryption. This is an accepted trade-off: the storage layer never interprets content (no parser CVEs, no polyglot exploits). Inspired by Git deflated blobs, PostgreSQL `bytea`, and S3 byte-stream model. `[LOG 04-15]`

---

### ADR-02: Local SQLite Always On; PostgreSQL for Sync Server Only  
**Status:** Planned  `[LOG 04-15]` `[REQ R12, R14]`  `[LOG 05-04]`

**Context:** JSON file storage does not support concurrent access or ACID transactions. Early design proposed forcing a mode selection (Personal/Server); this created unnecessary complexity.

**Decision:** SQLite is always active on the device — no mode selection required. PostgreSQL is used only for the cloud sync server (Sprint 5). A `migrate` CLI command converts existing `notes.json` → SQLite. Sync server reads `DATABASE_URL` env var only (never stored in config, `sslmode=require`).

**Alternatives considered:**
- Hard Personal/Server mode split with forced first-launch prompt → removed (over-engineered; blocked data access behind login)
- PostgreSQL only → too heavy for single-user local use

**Consequences:** `NoteStore` (JSON) replaced by `DatabaseStore` (SQLAlchemy) post-migration. Pre-migration code path remains active for backward compatibility. Schema versioned via Alembic. `[LOG 05-04]`

---

### ADR-03: SQLAlchemy ORM — No Raw SQL  
**Status:** Planned  `[LOG 04-15]` `[REQ R15.1, R15.2]` `[BL B-51]`

**Context:** Direct SQL string construction is the primary vector for SQL injection (OWASP A03).

**Decision:** All database access goes through SQLAlchemy ORM. Raw SQL string interpolation prohibited in application code. PostgreSQL application role limited to DML only — no DDL (DROP, ALTER, CREATE).

**Alternatives considered:**
- `sqlite3` module with parameterized `?` placeholders → safe but manual; also must re-implement for PostgreSQL
- Raw `psycopg2` with `%s` placeholders → parameterized but verbose; ORM preferred for portability

---

### ADR-04: AES-256-GCM with PBKDF2 (100 000 iterations)  
**Status:** Accepted (implemented)  `[SRC security.py]` `[REQ R2]` `[LOG 04-15]`

**Context:** Notes may contain sensitive personal information. Encryption must be both confidential and authenticated.

**Decision:** AES-256-GCM provides authenticated encryption (confidentiality + integrity). PBKDF2-HMAC-SHA256 with 100 000 iterations derives a 256-bit key from the user passphrase. A random 16-byte salt is generated per encrypt operation; the salt is stored alongside the ciphertext.

**Wire format:** `[16B salt][12B nonce][16B GCM tag][ciphertext]` → base64 encoded for JSON storage.

**Consequences:** Wrong passphrase is detected via GCM tag verification and raises `InvalidTag` — data is never silently corrupted. No default key; every encrypted operation requires an explicit passphrase. `[REQ R2.10]`

---

### ADR-05: Plugin Allowlist + Read-Only Note Copies  
**Status:** Partially implemented (PluginBase/Registry done; allowlist and read-only copies planned)  
`[LOG 04-15]` `[REQ R4.5, R4.10, R15.7]` `[BL B-56, B-69]`

**Context:** An unrestricted plugin API allows plugins to modify note content in memory, access the raw database, or execute arbitrary code via `exec`/`eval`.

**Decision:** Plugins receive a read-only copy (deep copy) of note data. Plugin content is never passed to `exec()`, `eval()`, or shell commands. Plugins cannot access the raw DB session. Only plugins listed in the `allowed_plugins` config key are loaded. Hook crashes are caught by the registry and logged — they never propagate to the calling operation.

**Alternatives considered:**
- Subprocess isolation → too heavy for hook-style plugins
- Signature verification → complex key distribution; allowlist achieves equivalent trust for single-operator use

---

### ADR-06: Interactive Auth Prompts — No CLI Argument Passwords  
**Status:** Planned  `[LOG 04-15]` `[REQ R13.1]` `[BL B-57]`

**Context:** Passwords passed as CLI positional arguments appear in shell history (`~/.bash_history`, `Get-History`) and in the system process list (`ps aux`), exposing credentials to other users and logging systems.

**Decision:** All credential input uses `click.prompt(..., hide_input=True)`. Username and password are never accepted as positional arguments or `--password` flags.

---

### ADR-07: Auth Rate Limiting (5 failures → 5-minute lockout)  
**Status:** Planned  `[LOG 04-15]` `[REQ R13.7]` `[BL B-58]`

**Context:** Without rate limiting, an attacker can brute-force passwords offline or against the CLI.

**Decision:** Track `failed_attempts` and `locked_until` in the `accounts` table. After 5 consecutive failures for a username, set `locked_until = now + 5 minutes`. All subsequent login attempts for that username during lockout return an error without checking the password.  `[LOG 05-04]`

---

### ADR-08: Hybrid Filesystem Storage (5 MB Threshold)  
**Status:** Planned  `[LOG 04-15]` `[REQ R14.8]` `[BL B-49]`

**Context:** Database BLOB columns are inefficient for large binary payloads (audio, video). Storing them inline bloats the database and slows queries.

**Decision:** Payloads ≤ 5 MB stored inline in the `encrypted_blob` column. Payloads > 5 MB written to `files/<note_id>.<ext>` under the per-user directory. **Filesystem payloads are always AES-256-GCM encrypted before writing to disk.** Unencrypted notes are always stored inline regardless of size (no plaintext files on disk). DB column `payload_location` tracks `inline` vs `filesystem`.

**Consequence:** Orphan cleanup required: when a note is deleted, the corresponding filesystem file must also be deleted. `[BL B-68]`

---

### ADR-09: Flat Data Directory — No Per-User Subdirectories on Device  
**Status:** Updated  `[LOG 04-15]` → `[LOG 05-04]` `[REQ R14.13]` `[BL B-77]`

**Context:** Original design stored per-user data under SHA-256(`user_id`) subdirectories. With the three-layer model, local notes can be anonymous (`account_id = NULL`) or account-associated, but all live in the same local database. Per-user subdirectories add complexity without security benefit on a single-user device.

**Decision:** Always flat layout: `<data-dir>/notes.db`, `<data-dir>/files/`, `<data-dir>/exports/`, `<data-dir>/audit.log`. No per-user subdirectory structure on the device. Isolation is enforced at the database query level (`account_id` scoping), not at the filesystem level. `[LOG 05-04]`

---

### ADR-10: Sequential Integer IDs → Gap-Safe IDs (UUID or max-ID+1)  
**Status:** Planned  `[BL B-31]` `[REQ R1.8]`

**Context:** Current implementation uses `len(list) + 1` as the new note ID. After deletions, this produces collisions: deleting note 3 from {1,2,3} then adding a note yields a second note with ID 3.

**Decision:** Replace with UUID v4 or `max(existing_ids) + 1`. UUID preferred for database backend (no coordination needed). ID collision on add raises `ValueError` and is caught at CLI layer.

---

### ADR-11: Sync Server Framework — FastAPI  
**Status:** Decided  `[LOG 05-04]` `[BL B-86]` `[REQ R16.10]`

**Context:** The sync server exposes `POST /sync/push` and `GET /sync/pull?since=` endpoints. It is not a full CRUD proxy — it only handles blob synchronisation between a logged-in account and the cloud store.

**Options considered:**
- **FastAPI** — async, auto-generates OpenAPI docs, native Pydantic validation, high performance
- **Flask-RESTX** — synchronous, familiar, less boilerplate, mature ecosystem
- **Django REST Framework** — full-featured, heavier dependency surface

**Decision:** **FastAPI.** Async concurrency aligns with concurrent sync requests (R16.6). Pydantic models enforce request validation without extra code. Auto-generated OpenAPI docs aid future client development. `[LOG 05-04]`

---

### ADR-12: OAuth / SSO — authlib + Google OIDC  
**Status:** Decided  `[LOG 05-04]` `[BL B-87]` `[REQ R13.13, R13.14]`

**Context:** The desktop app and sync server both need OAuth 2.0 / OpenID Connect login. The provider strategy must be extensible so additional providers can be added without rewriting the auth module.

**Decision:** **authlib** with Google OpenID Connect as the required minimum provider. `[LOG 05-04]`
- authlib is framework-neutral (works with FastAPI for the sync server and handles PKCE flow for the desktop client); implements RFC 6749/7636/7519 correctly.
- Extensible provider registry pattern: each provider implements `get_auth_url()`, `exchange_code()`, `get_user_info()`.
- Provider secrets in environment variables only; never stored in config files or source code.
- JWT issued by sync server after successful OAuth callback; `sub` claim = `account_id`; signed with server private key.

---

### ADR-13: GUI Framework — PySide6 Desktop Application  
**Status:** Decided  `[LOG 05-04]` `[BL B-84]` `[REQ R11.6]`

**Context:** The GUI layer needs to share Python core modules across both Sprint 4 (local CRUD) and Sprint 5 (sync added) without duplicating business logic. A single desktop app codebase serves both sprints.

**Options considered:**
- **Electron** — cross-platform web tech; requires Node.js toolchain alongside Python
- **Tkinter** — zero extra deps, Python-native; limited styling and widget richness
- **Local web server + browser SPA** — previously considered; dropped (browser UI eliminated by team decision)
- **PySide6** — Qt6 Python binding; native widgets; LGPL; no Node.js; same API as PyQt6 but safer licence

**Decision:** **PySide6 desktop application.** `[LOG 05-04]` A single PySide6 `QApplication` is the GUI for both Sprint 4 (local CRUD) and Sprint 5 (sync added). There is no browser-based surface; the sync server is a backend-only REST service. PySide6 is chosen over PyQt6 (same Qt6 API; LGPL licence is safer for course use) and over Electron/Tkinter (native widgets, no Node.js toolchain, richer styling than Tkinter). The Sprint 5 sync button triggers push/pull; if no valid session token is found, the app presents an OAuth login dialog (opens system browser for Google consent via PKCE flow, captures the redirect on `localhost:<ephemeral-port>/callback`). Both sprint deliverables share one codebase; sync features are activated by the presence of a valid session token.

Maps each requirement group to the implementing module, class, and test coverage.

| Requirement | Module | Class / Function | Test |
|-------------|--------|-----------------|------|
| R1.1 Add note (text) | `src/cli.py` | `add()` | `tests/steps/test_steps.py` — `add_note` step; `features/add_notes.feature` |
| R1.2 Get by ID | `src/cli.py` | `get()` | `features/get_notes.feature` |
| R1.3 List notes | `src/cli.py` | `list()` | `features/list_notes.feature` |
| R1.4 Update note | `src/cli.py` | `update()` | `features/update_notes.feature` |
| R1.5 Delete note | `src/cli.py` | `delete()` | `features/delete_notes.feature` |
| R1.6 Reject empty input | `src/cli.py` | `add()` guard | `tests/test_core.py` — empty title/content tests |
| R1.7 Non-existent ID error | `src/core/notes.py` | `NoteStore.get/update/delete` | `tests/test_core.py` |
| R1.8 Gap-safe IDs | *(planned)* `src/core/notes.py` | `NoteStore.add` | `[BL B-31]` — not yet tested |
| R1.9 `--data-dir` validation | *(planned)* `src/cli.py` | `cli()` group | `[BL B-36]` — not yet tested |
| R1.10 Corrupt JSON recovery | *(planned)* `src/core/notes.py` | `NoteStore.load` | `[BL B-35]` — not yet tested |
| R2.1 `--encrypt yes` | `src/cli.py` | `add()` | `features/add_notes.feature` encrypted scenario |
| R2.2 Passphrase confirmation | *(planned)* `src/cli.py` | `add()` | `[BL B-32]` — not yet tested |
| R2.3–R2.5 Passphrase on read/update/delete | `src/cli.py` | `get/update/delete` + `ensure_store` | `features/get/update/delete_notes.feature` encrypted scenarios |
| R2.6 No prompt on unencrypted | `src/cli.py` | `add/get/list/update/delete` | `features/` — unencrypted scenarios |
| R2.7 List hides encrypted title | `src/cli.py` | `list()` | `features/list_notes.feature` |
| R2.8 Reject wrong passphrase | `src/core/security.py` | `EncryptionEngine.decrypt` (raises `InvalidTag`) | `tests/test_core.py` — wrong passphrase test |
| R2.9 Sandbox blob model | *(planned)* `src/core/notes.py` | `BlobCodec` | `[BL B-43]` — not yet implemented |
| R2.10 No default key | `src/core/notes.py` | `NoteStore.__init__` | `tests/test_core.py` — no-key load test |
| R2.11 Min 8-char passphrase | *(planned)* `src/cli.py` | `ensure_store` | `[BL B-34]` — not yet tested |
| R2.12 No cross-note corruption | `src/core/notes.py` | `NoteStore.save` | `tests/test_core.py` — mixed note save test |
| R2.14 `reencrypt` command | *(planned)* `src/cli.py` | new command | `[BL B-62]` |
| R3.1–R3.4 JSON persistence | `src/core/notes.py` | `NoteStore.load/save` | `tests/test_core.py` — persistence tests |
| R3.5 1000+ notes performance | `src/core/notes.py` | `NoteStore` | `tests/test_core.py` — stress test (1001 notes) |
| R4.1–R4.2 Plugin base + registry | `src/core/plugin_base.py` | `PluginBase`, `PluginRegistry` | `tests/test_core.py` — plugin registry test |
| R4.3–R4.4 Hooks + CLI commands | `plugins/summary_plugin.py` | `SummaryPlugin` | `tests/test_core.py` — hook dispatch test |
| R4.6 Plugin discovery | *(planned)* `src/cli.py` | startup loader | `[BL B-37]` |
| R4.7 Hook error isolation | *(planned)* `src/core/plugin_base.py` | `PluginRegistry.call_hook` | `[BL B-38]` |
| R4.8 Duplicate plugin skip | *(planned)* `src/core/plugin_base.py` | `PluginRegistry.register_plugin` | `[BL B-38]` |
| R4.10 Plugin allowlist | *(planned)* `src/core/plugin_base.py` | startup loader + config | `[BL B-69]` |
| R5.1 `--data-dir` global option | `src/cli.py` | `cli()` | `tests/` — all BDD scenarios use temp data dir |
| R5.2 Non-zero exit on error | `src/cli.py` | `raise click.ClickException` | `tests/test_core.py` — exit code assertions |
| R7 Override policy | *(planned)* `src/cli.py` | new guard | `[BL B-24]` |
| R8 Audit trail | *(planned)* `src/core/` | `AuditLogger` | `[BL B-25, B-71]` |
| R9 Config module | *(planned)* `src/core/` | `ConfigStore` | `[BL B-26]` |
| R10.1–R10.3 Search | *(planned)* `src/cli.py` | `search()` command | `[BL B-29]` |
| R10.4–R10.7 Export | *(planned)* `src/cli.py` | `export()` command | `[BL B-30, B-76, B-78]` |
| R12 Deployment modes | *(planned)* `src/cli.py` | first-launch prompt | `[BL B-41]` |
| R13 Authentication | *(planned)* `src/core/` | `AuthManager` | `[BL B-45–B-48, B-57–B-61]` |
| R14.1–R14.13 Database backend | *(planned)* `src/core/` | `DatabaseStore` | `[BL B-42–B-44, B-51, B-63–B-68]` |
| R15.1–R15.2 ORM / no raw SQL | *(planned)* `src/core/` | `DatabaseStore` | `[BL B-51]` |
| R15.3 Input validation | *(planned)* `src/cli.py` | CLI boundary guard | `[BL B-52]` |
| R15.4 PostgreSQL DML-only role | *(planned)* deployment | DB role config | `[BL B-53]` |
| R15.5 ANSI strip | *(planned)* `src/cli.py` | output render | `[BL B-54]` |
| R15.7 Plugin read-only copies | *(planned)* `src/core/plugin_base.py` | `call_hook` | `[BL B-56]` |
| R15.8 Path traversal prevention | *(planned)* `src/cli.py` | input validation | `[BL B-55]` |

---

## 8. Directory Structure

```
AstraNotes/
├── src/
│   ├── cli.py                  # Click CLI entry point
│   └── core/
│       ├── notes.py            # Note dataclass + NoteStore
│       ├── security.py         # EncryptionEngine + KeyManager
│       └── plugin_base.py      # PluginBase + PluginRegistry
├── plugins/
│   └── summary_plugin.py       # Example plugin (SummaryPlugin)
├── tests/
│   ├── conftest.py             # Shared fixtures (runner, temp dir)
│   ├── test_core.py            # Unit tests (16 tests)
│   ├── features/               # Gherkin BDD feature files (17 scenarios)
│   │   ├── add_notes.feature
│   │   ├── get_notes.feature
│   │   ├── list_notes.feature
│   │   ├── update_notes.feature
│   │   └── delete_notes.feature
│   └── steps/
│       └── test_steps.py       # Behave step definitions
├── docs/
│   ├── prd.md                  # Product Requirements Document
│   ├── design.md               # This file
│   ├── bdd_testing.md
│   └── test_workflow.md
├── planning/
│   ├── requirements.md
│   ├── user-stories.md
│   ├── backlog.md
│   └── sprint-zero-plan.md
├── AI Working Log/
│   ├── working-log-2026-04-08.md
│   ├── working-log-2026-04-15.md
│   └── working-log-2026-04-29.md
├── Copilot/
│   ├── Definition of Done.md
│   └── Working Agreement.md
├── test_all.py                 # Top-level test runner (unit + BDD)
├── pytest.ini
└── requirements.txt
```

---

## 9. Design Weaknesses, Gaps, and Intentional Deferments

Four categories are distinguished. **Active bugs** are discrepancies between the current source code and what the design doc implies. **Missing design** means a transition or integration point has no design at all. **Underspecified design** means the design describes something but omits enough detail that implementation decisions are left undefined. **Intentional deferments** are explicitly scoped-down items whose absence is known and tracked.

---

### 9.1 Active Bugs Not Reflected in the Design

**B1 — ID collision after delete** `[REQ R1.8]` `[BL B-31]`  
`cli.add()` uses `str(len(store.list()) + 1)` as the new ID. Deleting any note causes `len` to undercount, producing a collision with an existing ID on the next add. The interaction diagram in §4.1 still shows this formula, making the diagram technically incorrect. The design correctly marks the fix as planned but does not acknowledge that the current diagram is wrong.

**B2 — Wrong-passphrase detection uses a sentinel string, not cryptography** `[REQ R2.8]`  
`get`, `update`, and `delete` check `if note.title == "[Encrypted Note]"` to infer a wrong passphrase. The class diagram in §3.1 implies detection via `EncryptionEngine.decrypt()` raising `cryptography.exceptions.InvalidTag`. In reality, `InvalidTag` is caught silently in `NoteStore.load()` and the note's title is replaced with the sentinel. The CLI then pattern-matches that string. A note legitimately titled `[Encrypted Note]` would be permanently inaccessible. The design doc does not document this discrepancy.

**B3 — Re-encryption on every save** `[REQ R3.2]`  
When a keyed `NoteStore` saves, `key_manager.get_engine()` is called per note, producing a new `EncryptionEngine` with a fresh random salt. Every encrypted note receives a new ciphertext on every save, including notes that were not modified. With 100,000 PBKDF2 iterations per derivation, this becomes progressively slower as the number of encrypted notes grows. Neither the class diagram nor any ADR documents this as a known limitation.

---

### 9.2 Critical Transitions with No Design

**T1 — No store factory or startup router**  
The design describes `NoteStore` (JSON) and `DatabaseStore` (SQLAlchemy) as separate classes but provides no `StoreFactory`, `get_store()`, or CLI startup logic to select between them. The decision point requires checking whether `migrate` has been run (i.e., whether `notes.db` exists). No sequence diagram, no function, no class handles this startup selection. Every planned interaction diagram in §4.3 skips directly to `DatabaseStore` without showing how it was chosen.

**T2 — No migration sequence diagram** `[REQ R14.7]` `[BL B-48]`  
`migrate` is the most structurally complex command in the backlog: back up `notes.json`, repackage independent field-level ciphertexts (old format: title and content each separately base64-encoded) into the sandbox blob format (new format: `[4B len][JSON header][raw payload]` → single AES-256-GCM operation). These two formats are structurally incompatible. The design describes the two endpoints but provides no conversion path, no intermediate representation, and no error flow for skipped notes.

**T3 — No session validation integration point** `[REQ R13.9]`  
In server mode every command must call `AuthManager.verify_session()` and check expiry before executing. None of the interaction diagrams include this step. There is no designed CLI decorator, middleware, or Click callback that enforces it. A developer implementing server mode from this design doc has no guidance on where the auth check lives.

**T4 — No replacement design for `ensure_store()`**  
The current `ensure_store()` prompts for passphrase once per process and caches a keyed `NoteStore` in `ctx.obj`. In server mode this model is invalid — authentication is via session token, not per-command passphrase. The design never describes what replaces `ensure_store()` in the post-migration architecture or how passphrase prompting interacts with session-based auth.

---

### 9.3 Described but Underspecified Design

**U1 — `Note.title` dual-role state machine**  
The `Note` dataclass carries both `title` (sometimes plaintext, sometimes the `"[Encrypted Note]"` sentinel) and `encrypted_title` (the raw ciphertext bytes). The class diagram in §3.1 shows both fields but does not specify the state machine: when is `title` authoritative? When is `encrypted_title`? When are both populated? When is neither? The planned `BlobCodec` resolves this by making the title inside the encrypted blob the sole authoritative source, but the current class is left in an undocumented dual-field state.

**U2 — No error flows in any interaction diagram**  
All four diagrams in §4 show only the happy path. Missing alternate flows: `InvalidTag` on wrong passphrase, `KeyError` on missing note ID, `OSError` on disk full (`ENOSPC`), corrupt JSON on load, and `ValueError` on ID collision. Every error-handling decision for these cases is left entirely to the implementer.

**U3 — Plugin allowlist and read-only copies have no designed call site**  
§3.2 (planned classes) and ADR-05 both state that plugins receive read-only copies and that only allowlisted plugins are loaded. The current `PluginRegistry.call_hook()` implementation has neither a `copy.deepcopy()` call nor a config-read guard. The class diagram for `PluginRegistry` reflects the current (unguarded) implementation without marking the gap, making the diagram inconsistent with ADR-05.

**U4 — `BlobCodec` has no designed call site**  
§3.2 defines `BlobCodec` with four methods. No interaction diagram shows where it is called. It is unclear whether `DatabaseStore`, `NoteStore`, or both invoke it, and whether it is called inside `add()`, `save()`, or `get()`.

**U5 — `ConfigStore` has no designed integration point**  
`ConfigStore` appears in §3.2 but in no interaction diagram. It is not shown being read at startup, per-command, or by any other class (`PluginRegistry`, `AuthManager`, `StoreFactory`). The first-launch mode selection flow (R12.1) would require `ConfigStore` to be read before any other module is initialized, but this ordering is undesigned.

---

### 9.4 Intentional Scope Reductions (Acknowledged Deferments)

These are not bugs. They are explicit backlog decisions whose absence is tracked.

| Item | Deferment Reason | Risk If Not Addressed Before Next Sprint |
|------|-----------------|------------------------------------------|
| Sandbox blob (`BlobCodec`) not coded `[BL B-43]` | Sprint Zero scope | Current storage leaks timestamps and format type in plaintext; violates R2.13 |
| All of R13–R15 (auth, DB, injection) | Requires DB backend first | No injection prevention, no user isolation, no audit trail in current build |
| Passphrase confirmation on encrypt `[BL B-32]` | Sprint Zero scope | Typo passphrase → note permanently inaccessible; no recourse |
| `--data-dir` writable validation `[BL B-36]` | Sprint Zero scope | Unwritable path produces unhelpful `OSError` with no actionable message |
| Corrupt JSON recovery `[BL B-35]` | Sprint Zero scope | Corrupt `notes.json` crashes `NoteStore.load()` with no `.bak` fallback |
| GUI layer `[BL B-27]` | Explicit post-CLI-stabilization | No risk; correctly deferred until CLI is stable |
| Search and export `[BL B-29, B-30]` | Sprint Zero scope | Feature absent; no partial implementation that could conflict |
| Desktop GUI (Sprint 4) `[BL B-84, B-85]` | ADR-13 decided: PySide6 `[LOG 05-04]` | No risk; no implementation started |
| Sync Server + Desktop Sync UI (Sprint 5) `[BL B-86–B-95]` | ADR-11/12/13 decided `[LOG 05-04]` | No risk; no implementation started |

---

### 9.5 Architecture Design Gaps Introduced by GUI Redesign `[LOG 05-04]`

**T5 — No interaction diagram for sync server request flow**  
§4 has four interaction diagrams (SD-1–SD-4) covering CLI flows only. There is no sequence diagram showing a desktop app sync call → `AuthMiddleware` token validation → `SyncRouter` push/pull → `DatabaseStore` query → JSON response. This is the primary flow of the Sprint 5 sync path.

**T6 — No OAuth PKCE desktop flow diagram**  
The OAuth 2.0 / PKCE callback flow for the desktop app (app opens system browser → user consents → provider redirects to `localhost:<port>/callback` → code exchange → JWT issuance → session token written to disk) is undesigned. The sequence of interactions between `AuthMiddleware.oauth_callback()`, the OAuth provider, and the session/JWT system is not described anywhere.

**T7 — No cloud sync conflict resolution design**  
`R11.10` and `US-14` require sync-on-demand with conflict resolution. There is no design for conflict detection (e.g., what if the server note was updated since the last pull?) or the resolution strategy (last-write-wins by `modified_at`, both versions in `note_conflicts` table for 30 days, as stated in R16.3). This must be detailed before Sprint 5B begins.

**T8 — No desktop GUI startup sequence**  
The desktop GUI's startup interaction with core modules (how it instantiates `DatabaseStore`, how it handles passphrase prompts via `QDialog`, how it handles the SQLite WAL concurrent-access case when both CLI and GUI are open simultaneously) is undesigned.

---

## 10. Traceability Metrics

See [`docs/traceability-metrics.md`](traceability-metrics.md) for the full breakdown:

| Metric | Count | % |
|--------|-------|---|
| Total requirements reviewed | 121 | 100% |
| Fully Traced | 29 | 24% |
| Partially Traced | 17 | 14% |
| Weakly Traced | 71 | 59% |
| Not Traced | 4 | 3% |
| UML elements without a requirement | 5 | — |

---

*This document was drafted by Astra (GitHub Copilot) from existing source code, planning artifacts, and working logs. Subject to human review before acceptance per `Copilot/Working Agreement.md`.*
