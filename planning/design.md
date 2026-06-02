# AstraNotes — Design Document

**Version:** 1.3  
**Date:** May 7, 2026  
**Status:** Draft — under review  
**Owner:** Human team member  
**AI Partner:** Astra (GitHub Copilot)

> Traceability notation used throughout: `[REQ Rx.y]` = `planning/requirements.md`,
> `[US-n]` = `planning/user-stories.md`, `[BL B-nn]` = `planning/backlog.md`,
> `[LOG 04-08]` / `[LOG 04-15]` = `AI Working Log/`, `[SRC]` = current source code.

---

## 1. Purpose and Scope

This document describes the software design of AstraNotes: the module structure, class responsibilities, data flows, storage model, and the decisions that produced the current architecture. It bridges the requirements (`planning/prd.md`) and the implementation (`src/`).

AstraNotes uses a **three-layer additive model** — each layer is independent and optional on top of the previous:  `[LOG 05-04]`
- **Layer 1 — Local store (always on):** SQLite at `<data-dir>/notes.db`; all CRUD works immediately with no login or configuration.
- **Layer 2 — Account (opt-in):** `register`/`login` commands add an account. Notes gain a nullable `account_id`; existing anonymous notes can be associated on first login.
- **Layer 3 — Cloud sync (opt-in, requires account):** `sync push` / `sync pull` mirror account-associated notes to the FastAPI sync server; last-write-wins conflict resolution.

The CLI is the primary interface for Sprints 0–3. A PySide6 desktop app (Sprint 4: local CRUD; Sprint 5: sync added) shares the same core modules and SQLite local store. There is no browser-based surface — the sync server (Sprint 5) is a backend-only REST service.

**Design status (updated 2026-05-21):** Sprint 2 complete. Core modules (`DatabaseStore`, `BlobCodec`, `EncryptionEngine`, `KeyManager`, `PluginBase`, `PluginRegistry`, `AccountStore`, `SessionManager`) and the Click CLI (including `register`, `login`, `logout`, `delete-account` commands) are implemented and tested. 246 tests pass; 100% branch coverage on all six core modules. Components marked `[planned]` are scheduled for Sprints 3–5. Open design gaps tracked in `Copilot/discussion-list.md`. `[LOG 05-21]`

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
   │    │   Shares DatabaseStore, EncryptionEngine, PluginRegistry │
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
│  │   DatabaseStore    KeyManager         PluginRegistry              │   │
│  │   BlobCodec                                                       │   │
│  │                                                                   │   │
│  │   [Planned]        [Planned]           [Planned]                  │   │
│  │   AuthManager      AuditLogger         ConfigStore                │   │
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

### 3.1 Sprint 0–1 Classes (Implemented)

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
│ + encrypted: bool            │
│ + blob: bytes | None         │  encrypted sandbox blob; None for unencrypted  [D-07]
├──────────────────────────────┤
│ + update(title, content)     │
└──────────────┬───────────────┘
               │ stored in
               ▼
┌──────────────────────────────┐
│  DatabaseStore               │  SQLite, always-on  [D-10]
├──────────────────────────────┤  [BL B-42, B-51, B-74] [REQ R14]
│ - engine: SQLAlchemy Engine  │
│ - session: Session           │
├──────────────────────────────┤
│ + add(note) → note_id        │
│ + get(note_id) → Note?       │
│ + update(note_id, …) → Note  │
│ + delete(note_id)            │
│ + list(account_id)           │  → (List[Note], List[Note])  [D-11]
│                              │    tuple: (account_notes, local_notes)
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
│  EditorProvider  <<ABC>>     │  extension type for content editing/viewing  [D-04, D-05]
├──────────────────────────────┤
│ + plugin_id: str             │  unique namespace identifier  [D-05]
│ + name: str                  │
│ + version: str               │  semver string
│ + engines: str               │  minimum AstraNotes version required  [D-12]
│ + main: str                  │  entrypoint Python module path  [D-12]
│ + is_official: bool          │  server-assigned by PluginRegistry — NOT read from plugin.json  [D-12]
│ + supported_mime_types: list │  e.g. ['text/html', 'text/markdown']; each type may only be
│                              │  owned by one active extension at a time  [D-05]
├──────────────────────────────┤
│ + open_editor(note) → widget │  returns a QWidget embedded in the file display window
│ + get_content() → bytes      │  serializes editor state to raw bytes (blob payload)
│ + show_settings()            │  optional; extension-owned settings panel
└──────────────────────────────┘
  Extension decisions (D-05, 2026-05-10): install/remove via app "Add Extension" menu;
  official badge label; MIME conflicts forbidden (one active owner per type); install
  blocked on conflict — user must disable/uninstall conflicting extension first, or install
  new extension disabled; re-activating a conflicted extension also blocked.
  Manifest format: plugin.json — see manifest schema below (D-12 resolved 2026-05-12).
  Trust tier: is_official injected by PluginRegistry from server-verified registry record — see ADR-14.
  Font size: inherits system setting; extension show_settings() may override for its content area.

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
│  PluginRegistry              │  [D-09 resolved 2026-05-11] [D-12 resolved 2026-05-12]
├──────────────────────────────┤
│ - hooks: dict[str, list[fn]] │
│ - plugins: list[PluginBase]  │
│ - _allowed: frozenset[str]   │  loaded from config["allowed_plugins"] at startup
├──────────────────────────────┤
│ + load_manifests()           │  reads plugin.json from plugins/ subdirs; validates with jsonschema  [REQ R4.11] [D-12]
│ + register_plugin(plugin,    │  checks allowlist; injects is_official from server-verified record
│     is_official: bool)       │  (NOT from manifest); enforces trust-tier API restriction  [REQ R4.10, R4.12, R4.13]
│ + register_hook(name, fn)    │
│ + call_hook(name, note, …)   │  passes dataclasses.replace(note) copy; mutable fields copied explicitly  [REQ R15.7]
└──────────────────────────────┘
  Allowlist check: at register_plugin() time — disallowed plugins never enter the registry  [D-09]
  Trust-tier enforcement: is_official = True → EditorProvider + PluginBase API allowed
    is_official = False (user-installed) → EditorProvider only; PluginBase hooks blocked  [D-12]
  is_official source: server-verified registry record only — any is_official field in plugin.json is rejected  [D-12]
  Note isolation: dataclasses.replace(note) for all-primitive Note; any future mutable field
    (e.g. tags: list[str]) must be explicitly copied at the call site:  [D-09]
    dataclasses.replace(note, tags=list(note.tags))

**plugin.json Manifest Schema** *(D-12 resolved 2026-05-12)* `[REQ R4.11]`

Format: JSON file named `plugin.json` at the root of each plugin subdirectory under `plugins/`. Validated by `PluginRegistry.load_manifests()` using `jsonschema`.

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `plugin_id` | ✅ | `str` | Unique namespace identifier — must match `allowed_plugins` config key |
| `name` | ✅ | `str` | Human-readable display name |
| `version` | ✅ | `str` | Semver string (e.g. `"1.0.0"`) |
| `engines` | ✅ | `str` | Minimum AstraNotes version required (e.g. `">=1.0.0"`) |
| `main` | ✅ | `str` | Entrypoint Python module path relative to plugin root (e.g. `"summary_plugin.py"`) |
| `supported_mime_types` | optional | `list[str]` | MIME types this plugin handles; each type owned by at most one active plugin |
| `keywords` | optional | `list[str]` | Search/browse tags for the extension browser |
| `categories` | optional | `list[str]` | Category tags for the extension browser |
| `repository` | optional | `str` | URL of the plugin's open-source repository |
| `extensionDependencies` | optional | `list[str]` | `plugin_id` values that must be installed before this plugin can activate |

> **`is_official` is NOT a manifest field.** It is server-assigned only — set by the AstraNotes backend after review/approval. `PluginRegistry.load_manifests()` must reject any manifest that contains an `is_official` field. Sideloaded plugins always default to `is_official = False` at runtime regardless of manifest content. `[D-12]` `[REQ R4.12]`
```

**`Note` field state rules** *(D-07 resolved 2026-05-11 — Option C: BlobCodec in Sprint 1)*

`encrypted_title` removed. `blob: bytes | None` is the sole authoritative storage for encrypted notes. `title` and `content` are in-memory views populated by `BlobCodec.decrypt() + decode()` when a key is present.

| State | `encrypted` | `blob` | `title` (in-memory) | `content` (in-memory) |
|-------|-------------|--------|--------------------|-----------------------|
| Unencrypted note | `False` | `None` | Plaintext — authoritative | Plaintext — authoritative |
| Encrypted, no key (listing) | `True` | bytes | `"[Encrypted Note]"` — display only | `""` — empty |
| Encrypted, correct key | `True` | bytes | Decrypted from blob header — in-memory only | Decrypted from blob payload — in-memory only |

**Rules:**
- `blob` is the **sole authoritative source** for encrypted notes — `title` and `content` are ephemeral in-memory views derived from the blob.
- `"[Encrypted Note]"` is a **display-only placeholder** — no code path may branch on `title == "[Encrypted Note]"` to detect a wrong passphrase (Pitfall B2, §9.1).
- On save, unchanged encrypted notes write `blob` verbatim — no re-encrypt. Only the note that was added or modified is re-encoded and re-encrypted. `[REQ R3.2]`
- `DatabaseStore` calls `BlobCodec.encode() + encrypt()` in `add()` when encrypted; `BlobCodec.decrypt() + decode()` in `get()` when a key is present. `[BL B-43]` `[D-07]`

> `Note.metadata: dict` permanently removed. No requirement defines a freeform metadata field; R2.9 places all metadata inside the blob header. If new per-note fields are needed in the future (e.g. `tags: list[str]`, `format: str`), they must be added as **typed `Note` fields** populated by `BlobCodec.decode()` from the JSON header — not as a freeform dict. A `metadata: dict` grab-bag bypasses the blob structure, cannot be validated, and would recreate the dual-source problem D-07 resolved. `[LOG 05-07]`

### 3.2 Planned Classes (Backlog)

```
┌──────────────────────────────┐
│  DatabaseStore               │  SQLite, always-on  [Sprint 0 — D-10]
├──────────────────────────────┤  [BL B-42, B-44] [REQ R14]  `[LOG 05-04]`
│ - engine: SQLAlchemy Engine  │
│ - session: Session           │
├──────────────────────────────┤
│ + add(note) → note_id        │
│ + get(note_id, account_id)   │
│ + update(note_id, …)         │
│ + delete(note_id)            │
│ + list(account_id)           │  → (List[Note], List[Note])  [D-11]
│                              │    (account_notes, local_notes) tuple
│                              │    account_id=None → ([], local_notes)
│ + search(query, account_id)  │
└──────────────────────────────┘
  Local store:  SQLite (WAL) — always on; no mode selection; Sprint 0 `create_all()` init  [D-10]
  Sync server:  PostgreSQL (sslmode=require)
  All queries via ORM; no raw SQL  [REQ R15.1, R15.2]  `[LOG 05-04]`

┌──────────────────────────────┐
│  BlobCodec  [Sprint 0]       │  sandbox binary storage  [D-10]
├──────────────────────────────┤  [REQ R2.9, R14.4]
│ + encode(header, payload)    │  → [4B len][JSON header][payload]
│ + decode(blob) → (hdr, body) │
│ + encrypt(blob, engine)      │  → AES-256-GCM ciphertext
│ + decrypt(ciphertext, engine)│
└──────────────────────────────┘

┌──────────────────────────────┐
│  AuthManager  [planned]      │  optional; never gates local CRUD
├──────────────────────────────┤  [REQ R13] [BL B-45–B-47]  `[LOG 05-04]`
│ - session_path: Path         │
├──────────────────────────────┤
│ + register(username, pw)     │  bcrypt hash; creates accounts row
│ + login(username, pw)        │  → writes .session token
│ + logout()                   │  → deletes .session; notes intact
│ + try_load_session()         │  → account_id|None; non-blocking  [D-11]
│ + verify_session()→account_id│  → raises SessionExpiredError if expired/missing  [D-11]
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
│ - config_path: Path          │  fixed OS path: %APPDATA%\astranotes\config.json
│                              │  (~/.config/astranotes/config.json on Linux/macOS)
│                              │  NOT inside data_dir  [D-06]
│ - ALLOWED_KEYS: frozenset    │
├──────────────────────────────┤
│ + get(key) → value           │
│ + set(key, value)            │
│ + list() → dict              │
│ + reset(key)                 │
└──────────────────────────────┘

┌──────────────────────────────┐
│  AppController  [planned]    │  Startup orchestrator — owns all top-level wiring  [Sprint 4]
├──────────────────────────────┤  [REQ R9.7] [BL B-101] [D-13 decided 2026-05-13]
│ - config: ConfigStore        │  Constructed in main.py; GUI never created externally
│ - store: DatabaseStore       │
│ - session_mgr: SessionManager│
│ - gui: DesktopGUI            │
├──────────────────────────────┤
│ + __init__(data_dir: Path)   │  Resolves data_dir from ConfigStore; stores ref only
│ + run() → int                │  Full startup sequence (§4.7); returns exit code
└──────────────────────────────┘
  Initialization order: ConfigStore.load() → DatabaseStore(data_dir) →
    SessionManager.acquire_lock() → PluginRegistry.load_manifests() →
    QApplication + DesktopGUI(store, session_mgr, config) → populate_note_list() →
    start_idle_timer() → app.exec()
  On clean exit: SessionManager.release_lock()

┌──────────────────────────────┐
│  SessionManager  [planned]   │  PID lock file + idle auto-lock timer  [Sprint 4]
├──────────────────────────────┤  [REQ R9.7, R9.8] [BL B-101, B-102] [D-13 decided 2026-05-13]
│ - lock_path: Path            │  <data-dir>/.app.lock  (JSON: {"pid": int, "launched_at": str})
│ - idle_timeout: int          │  seconds; default 300 (5 min)
│ - _timer: QTimer             │  Qt timer; reset on user interaction
├──────────────────────────────┤
│ + acquire_lock()             │  Write lock; raises SessionConflictError if alive PID found
│ + release_lock()             │  Delete lock file on clean exit
│ + start_idle_timer(gui)      │  Start QTimer; on timeout → gui.auto_close_encrypted_note()
│ + reset_idle_timer()         │  Called by DesktopGUI on any user interaction event
└──────────────────────────────┘
  SessionConflictError: raised by acquire_lock() when another live session is detected.
  Stale lock (PID not alive): overwritten silently — no error raised.
  Idle timeout fires silently; no user prompt before auto-close.

┌──────────────────────────────┐
│  DesktopGUI  [planned]       │  PySide6 desktop app (Sprint 4: CRUD; Sprint 5: sync)
├──────────────────────────────┤  [REQ R11.1–R11.12] [BL B-84, B-85, B-89, B-90]
│ - store: DatabaseStore       │  [US-9, US-14] [ADR-13 decided]
│ - key_manager: KeyManager    │
│ - auth_manager: AuthManager  │
├──────────────────────────────┤
│ + show_file_list()           │  file list — QListWidget left pane (VS Code Explorer-style)
│ + show_file(note_id)         │  file display window — right pane; loads EditorProvider widget
│ + prompt_passphrase() → str  │  QDialog modal, auto-focus, Escape closes
│ + on_add()                   │  shows "+" picker dropdown: registered format types
│                              │  (e.g. Text | Image | Video | Recording | …);
│                              │  opens the EditorProvider extension for chosen MIME type;
│                              │  greyed out if no extension registered for that type  [D-04]
│ + on_edit()                  │  opens EditorProvider extension for note's MIME type
│ + on_delete()                │
│ + on_sync()                  │  Sprint 5: triggers push/pull; prompts login if no session
│ + setup_tray()               │  QSystemTrayIcon + QMenu (Show/Hide, Quit)  [BL B-97]
│ + on_tray_activated(reason)  │  double-click or single-click → show window
│ + show_settings()            │  QDialog (tabbed):
│                              │    General tab — data directory, default encryption on/off,
│                              │      min passphrase length, plugin directory
│                              │    Appearance tab — theme (light/dark, applied immediately
│                              │      on selection  [D-03]), font size (system UI only;
│                              │      does not affect note content  [D-03])
│                              │    Sync tab (Sprint 5) — sync server URL, auto-sync interval
│                              │      (numeric entry ≥5 s or Off=0; inline validation  [D-03]),
│                              │      last-synced timestamp
│                              │  Account login/logout: dedicated menu action, not in Settings  [D-03]
└──────────────────────────────┘
  Framework: PySide6 (ADR-13 decided)  [LOG 05-04]
  Startup: `astranotes gui` → QApplication → main window opens → blocks until window closed
  Layout: two-pane; left = file list (VS Code Explorer-style; note list + sync-status dot);
          right = file display window (hosts EditorProvider widget); menu bar; toolbar
  **No built-in editor:** all content creation and viewing delegated to EditorProvider extensions
  (see D-04, D-05). Official extensions pre-installed; can be replaced by user-installed ones.
  Sprint 4 dependency: core modules only; no sync server required
  Sprint 5 dependency: adds sync server calls (HTTPS push/pull) and OAuth login flow

┌──────────────────────────────┐
│  MergeWindow  [planned]      │  2-pane conflict merge dialog (Sprint 5B)
├──────────────────────────────┤  [REQ R16.3] [BL B-89] [D-14 decided 2026-05-14]
│                              │
├──────────────────────────────┤
│ + open(local_blob,           │
│        remote_blob, note_id) │  opens QDialog with 2 panes
└──────────────────────────────┘
  QDialog subclass. Left pane: local version, read-only, diffs highlighted yellow.
  Right pane: remote version, editable (start here). [Use Local ←] copies left → right.
  [Save Final] writes right-pane content to DatabaseStore, clears ! badge, triggers push.
  No note_conflicts table — server blob held in memory from pull response only.
  Unresolved conflict: ! badge persists for session; next pull re-detects if unresolved.

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

### 4.1 Add Note (unencrypted)  `[D-08]` `[D-10]`

```
User
 │  astranotes add --title "T" --content "C"
 ▼
cli.add()
 │  validates title/content not empty          [REQ R1.6]
 │  ── empty title or content ──────────────────────────────── [REQ R1.6]
 │       raise ClickException("Title and content must not be empty.") → exit 1
 │  store       = ctx.obj['store']        (DatabaseStore — startup callback)
 │  account_id  = ctx.obj['account_id']   (str|None — try_load_session result)  [D-11]
 │  note_id = str(uuid.uuid4())                [REQ R1.8] [BL B-31]
 │  Note(id, title, content, encrypted=False)
 │  store.add(note)
 │    └─ session.commit()  ACID transaction    [REQ R14.6]
 │         ── OperationalError (disk full / locked) ───────── [REQ R5.2, R5.3]
 │              raise ClickException("[DatabaseStore] Write failed: <msg>") → exit 1
 ▼
"Note 'T' added with ID <uuid> (unencrypted)"
```

### 4.2 Add Note (encrypted)  `[D-07]` `[D-08]` `[D-10]`

```
User
 │  astranotes add --title "T" --content "C" --encrypt yes
 ▼
cli.add()
 │  validates title/content not empty          [REQ R1.6]
 │  ── empty title or content ──────────────────────────────── [REQ R1.6]
 │       raise ClickException("Title and content must not be empty.") → exit 1
 │  prompt passphrase (first entry)            [REQ R2.1]
 │  prompt passphrase (confirm)                [REQ R2.2] [BL B-32]
 │  ── mismatch ────────────────────────────────────────────── [REQ R2.2]
 │       raise ClickException("Passphrases do not match.") → exit 1
 │  key_manager = KeyManager(passphrase)       ← constructed inline for add; NOT cached in ctx.obj  [D-11]
 │  engine = key_manager.get_engine()
 │  store       = ctx.obj['store']        (DatabaseStore — startup callback)
 │  account_id  = ctx.obj['account_id']   (str|None — try_load_session result)  [D-11]
 │  note_id = str(uuid.uuid4())               [REQ R1.8] [BL B-31]
 │  raw_blob = BlobCodec.encode(               [REQ R2.9] [BL B-43]
 │    header={title, created_at, modified_at},
 │    payload=content.encode('utf-8'))
 │  encrypted_blob = BlobCodec.encrypt(raw_blob, engine)
 │  Note(id=note_id, title=title, content=content,
 │       encrypted=True, blob=encrypted_blob)
 │  store.add(note)
 │    └─ session.commit()  ACID transaction    [REQ R14.6]
 │         unchanged encrypted notes: blob written verbatim  [REQ R3.2]
 │         ── OperationalError (disk full / locked) ───────── [REQ R5.2, R5.3]
 │              raise ClickException("[DatabaseStore] Write failed: <msg>") → exit 1
 ▼
"Note 'T' added with ID <uuid> (encrypted)"
```

### 4.2a Get / Update / Delete (encrypted note) — error flows  `[D-08]`

Applies to `cli.get()`, `cli.update()`, `cli.delete()` when the target note has `encrypted=True`.

```
cli.get(note_id) / cli.update(note_id, …) / cli.delete(note_id)
 │  store = ctx.obj['store']  (DatabaseStore — startup callback)
 │  store.get(note_id)
 │    ── returns None (note not found) ────────────────────── [REQ R5.2, R5.3]
 │         raise ClickException("Note <note_id> not found.") → exit 1
 │  note.encrypted == True:
 │    engine = get_key_manager(ctx).get_engine()            [D-11]
 │    BlobCodec.decrypt(note.blob, engine)
 │    ── InvalidTag (wrong passphrase) ────────────────────── [REQ R2.8, R5.2, R5.3]
 │         raise ClickException("[DatabaseStore] Wrong passphrase — note <note_id> could not be decrypted.") → exit 1
 │  … (continue with normal get/update/delete logic)
 │  store.update/delete commit  (update/delete only)
 │    ── OperationalError ─────────────────────────────────── [REQ R5.2, R5.3]
 │         raise ClickException("[DatabaseStore] Write failed: <msg>") → exit 1
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

### 4.4 Plugin Hook Dispatch  `[D-09 resolved 2026-05-11]`

```
PluginRegistry.call_hook("post_add_note", note)
 │
 │  note_copy = dataclasses.replace(note)       [REQ R15.7] [D-09]
 │    # mutable fields copied explicitly, e.g.:
 │    # dataclasses.replace(note, tags=list(note.tags))
 │    # Current Note fields are all immutable primitives — plain replace() is safe.
 │
 ├─ for each registered fn:  (only allowlisted plugins reached register_plugin())
 │    try:
 │      fn(note_copy)      ← isolated copy; plugin cannot mutate original  [REQ R15.7]
 │    except Exception as e:
 │      log warning, continue                   [REQ R4.7]
```

### 4.5 Store Startup and Initialization — planned (resolves gaps T1, U5 — D-06 decided 2026-05-11; T3/T4 — D-11 decided 2026-05-12)

The CLI `cli()` group callback (invoked before every sub-command) runs the startup sequence below. `--help` and `--version` short-circuit before the callback runs (Click handles `--help` automatically; `@click.version_option` handles `--version`). `[D-06]` `[D-11]` `[LOG 05-11]`

```
cli() group callback (invoked before every command)
 │
 │  1. ConfigStore.load(OS_CONFIG_PATH)          [REQ R9.1] [BL B-26]
 │     OS_CONFIG_PATH:
 │       Windows : %APPDATA%\astranotes\config.json
 │       Linux   : ~/.config/astranotes/config.json
 │       macOS   : ~/.config/astranotes/config.json
 │     (defaults used if file absent; no error on first run)
 │
 │  2. Resolve data_dir                          [REQ R1.9] [BL B-36]
 │     ── if --data-dir flag given ──
 │          data_dir = Path(ctx.params['data_dir'])
 │     ── else ──
 │          data_dir = Path(config['data_dir'])  (from ConfigStore)
 │     validate data_dir is writable directory
 │
 │  3. Store creation                                         [D-10 resolved 2026-05-12]
 │          store = DatabaseStore(data_dir)      [REQ R14.1] [BL B-42]
 │          (SQLite — always-on; create_all() creates notes.db on first run)
 │
 │  4. Plugin loading (VS Code activation-events model)  [REQ R4.6] [BL B-37] [D-12]
 │     PluginRegistry.load_manifests()  ← eager
 │       reads plugin.json per plugin subdir; validates required fields (plugin_id, name,
 │       version, engines, main) with jsonschema; rejects is_official in manifest;
 │       validates MIME ownership (no two active plugins own the same MIME type)
 │     PluginRegistry.activate()        ← deferred to first relevant note open
 │
 │  5. Session probe — non-blocking                          [REQ R13.8] [D-11]
 │     account_id = AuthManager.try_load_session(data_dir)
 │     ── session file absent or expired ──
 │          account_id = None   (silent — local CRUD continues unaffected)
 │     ── session valid ──
 │          account_id = <str>  (UUID from session token)
 │
 │  ctx.obj = {
 │    'store'       : store,           # DatabaseStore — always present
 │    'account_id'  : account_id,      # str|None — None = logged out
 │    'key_manager' : None,            # KeyManager|None — set lazily by get_key_manager()
 │  }
│
│  Error flows (startup only):                          [REQ R5.2, R5.3] [D-08]
│  ── OperationalError (notes.db locked / unreadable) ───────────────────────
│       raise ClickException("[DatabaseStore] Cannot open notes.db: <msg>") → exit 1
│  ── OSError (data_dir not writable) ──────────────────────────────────────
│       raise ClickException("[ConfigStore] data_dir <path> is not writable.") → exit 1
```

Notes:
- `ConfigStore` lives at a **fixed OS-standard path**, not inside `data_dir`. The `--data-dir` CLI flag overrides `config["data_dir"]` at runtime; it does not move the config file. `[D-06]` `[REQ R9.1]`
- `key_manager` is **not** constructed at startup. `get_key_manager(ctx)` is a module-level helper in `cli.py`: on first call it prompts the passphrase, constructs `KeyManager`, and caches it in `ctx.obj['key_manager']`. Subsequent calls within the same process reuse the cached instance. Called only by commands that decrypt blobs: `get`, `update`, `delete`, `reencrypt`. `[REQ R2.1]` `[D-11]`
- `add` constructs `KeyManager` inline when `--encrypt yes` — not cached, because `add` encrypts exactly one note per invocation. `[D-11]`
- `list` never calls `get_key_manager()` — reads plaintext `title`/`format` columns only via `DatabaseStore.list()`. `[BL B-74]` `[D-11]`
- This diagram resolves gap **T1** (store factory), gap **U5** (`ConfigStore` integration point), and gap **T3/T4** (session probe + passphrase caching). `[D-06 resolved 2026-05-11]` `[D-11 resolved 2026-05-12]`

---

### 4.6 Sync Subgroup Callback — planned (Sprint 2, resolves gap T3 — D-11 decided 2026-05-12)

`sync push` and `sync pull` are subcommands of a dedicated `sync` Click group. The `sync` group callback calls `AuthManager.verify_session()` before any sync command executes. CRUD commands (`add`, `get`, `list`, `update`, `delete`) are in the top-level group and never pass through this callback. `[REQ R13.8]` `[D-11]`

```
astranotes sync <push|pull>  →  sync group callback runs first
 │
 │  account_id = AuthManager.verify_session(data_dir)   [REQ R13.8] [BL B-46]
 │    ── session file absent ─────────────────────────────────────────────────
 │         raise ClickException("Not logged in. Run 'astranotes login' first.") → exit 1
 │    ── session expired ──────────────────────────────────────────────────────
 │         raise ClickException("Session expired. Run 'astranotes login' to renew.") → exit 1
 │    ── session valid ────────────────────────────────────────────────────────
 │         ctx.obj['account_id'] = account_id  (overrides startup probe value)
 │
 │  → subcommand (push or pull) continues
│
│  Local CRUD is unaffected — it runs through the top-level group callback only,
│  which uses the non-blocking try_load_session() (§4.5 step 5).
```

---

### 4.7 AppController Startup Sequence — planned (Sprint 4, resolves gap T8 — D-13 decided 2026-05-13)

`AppController` is an orchestrator class constructed in `main.py`. It owns `ConfigStore`, `DatabaseStore`, `SessionManager`, and `DesktopGUI` and controls their initialization order. `DesktopGUI` receives `DatabaseStore` via constructor injection — it never creates storage internally. `[D-13 Q1]`

```
main.py  →  AppController(data_dir).run()
 │
 │  Step 1 — Load config
 │  config = ConfigStore.load()            # fixed OS path: %APPDATA%/astranotes/config.json
 │  data_dir = CLI --data-dir override ?? config["data_dir"]   [REQ R9.1]
 │    ── OSError (data_dir not writable) ─────────────────────────────────────────
 │         show error QMessageBox + exit 1
 │
 │  Step 2 — Create DatabaseStore
 │  store = DatabaseStore(data_dir)        # calls create_all() → creates notes.db if absent
 │    ── first launch (notes.db does not exist) ───────────────────────────────────
 │         create_all() creates it transparently — no special case needed  [D-13 Q4]
 │    ── OperationalError (disk full / permissions) ───────────────────────────────
 │         show error QMessageBox + exit 1
 │
 │  Step 3 — Acquire session lock
 │  session_mgr = SessionManager(data_dir)
 │  session_mgr.acquire_lock()   # writes <data-dir>/.app.lock: {"pid": <int>, "launched_at": "<ISO>"}
 │    ── lock file exists and PID is alive ────────────────────────────────────────
 │         show error QMessageBox:
 │           "Another AstraNotes session is already running for this account.
 │            Close it before opening a new session."
 │         exit 1
 │    ── lock file exists but PID is dead (stale lock) ────────────────────────────
 │         overwrite lock with current PID and continue
 │
 │  Step 4 — Load plugins  [Sprint 4B — B-99, D-12]
 │  PluginRegistry.load_manifests(config["plugin_dir"])
 │
 │  Step 5 — Launch desktop GUI
 │  app = QApplication(sys.argv)
 │  gui = DesktopGUI(store=store, session_mgr=session_mgr, config=config)
 │
 │  Step 6 — Populate note list  (lazy passphrase — no QDialog at startup)
 │  gui.populate_note_list()
 │    Loads Note stubs (id, title, encrypted flag) via DatabaseStore.list().
 │    Encrypted notes shown as "[Encrypted]" placeholder.  [D-13 Q2] [REQ R11.4]
 │    No passphrase prompt at this step.
 │
 │  Step 7 — Start idle timer
 │  session_mgr.start_idle_timer(timeout_seconds=300)   [REQ R9.8] [BL B-102]
 │    On any user interaction: reset timer.
 │    On timeout: if an encrypted note is open → auto-close it, clear passphrase
 │    from memory, redisplay "[Encrypted]" placeholder.  Fires silently.
 │
 │  Step 8 — Enter Qt event loop
 │  sys.exit(app.exec())
 │
 │  On app close:
 │    session_mgr.release_lock()   # deletes <data-dir>/.app.lock
```

Notes:
- `DesktopGUI` never creates `DatabaseStore` internally — it receives the instance from `AppController` (Option C — orchestrator pattern). `[D-13 Q1 decided 2026-05-13]`
- Passphrase `QDialog` is **lazy** — shown only when the user opens an encrypted note, not at startup. `[D-13 Q2 decided 2026-05-13]` `[REQ R11.4]`
- `SessionManager.acquire_lock()` uses a PID-based lock file at `<data-dir>/.app.lock`. If the lock exists and the recorded PID is alive, the new session is blocked with an error dialog. Stale locks (dead PID) are overwritten silently. On clean exit, the lock file is deleted. **This enforces session exclusivity — only one AstraNotes session (GUI or CLI) may run per account at a time.** `[D-13 Q3 decided 2026-05-13]` `[REQ R9.7]` `[BL B-101]`
- The 5-minute idle timer (`SessionManager.start_idle_timer`) auto-closes open encrypted notes and clears their passphrase from memory on timeout. This is a **security feature**, not a multi-user locking mechanism. `[D-13 Q3 decided 2026-05-13]` `[REQ R9.8]` `[BL B-102]`
- First launch (no `notes.db`): `DatabaseStore.__init__` calls `create_all()` automatically — no special case in `AppController`. `[D-13 Q4 decided 2026-05-13]`
- This diagram resolves gap **T8** (desktop GUI startup sequence). `[D-13 resolved 2026-05-13]`

---

### 4.8 Sync Server Push/Pull Sequence — planned (Sprint 5A, resolves gap T5 — D-14 decided 2026-05-14)

**Push happy path (`POST /sync/push`):**

```
Desktop                   AuthMiddleware        SyncRouter       DatabaseStore (PG)
  │                             │                   │                  │
  │── POST /sync/push ─────────►│                   │                  │
  │   Authorization: Bearer jwt │                   │                  │
  │                 verify_token(req)               │                  │
  │                 extract account_id              │                  │
  │                             │── push(account_id, blobs) ──────────►│
  │                             │                   │── UPSERT notes   │
  │                             │                   │   ON CONFLICT    │
  │                             │                   │   DO UPDATE SET  │
  │                             │                   │◄── {synced_at}   │
  │◄── 200 {synced_at} ─────────│                   │                  │
  │                             │                   │                  │
  ── invalid/missing JWT ──────►│                   │                  │
  │◄── 401 Unauthorized ────────│                   │                  │
```

**Pull happy path (`GET /sync/pull?since=<ts>`):**

```
Desktop                   AuthMiddleware        SyncRouter       DatabaseStore (PG)
  │                             │                   │                  │
  │── GET /sync/pull?since=<ts>►│                   │                  │
  │                 verify_token(req)               │                  │
  │                 extract account_id              │                  │
  │                             │── pull(account_id, since) ──────────►│
  │                             │                   │── SELECT * WHERE │
  │                             │                   │   account_id = ? │
  │                             │                   │   AND modified_at│
  │                             │                   │   > since        │
  │                             │                   │◄── [note blobs]  │
  │◄── 200 [note blobs] ────────│                   │                  │
```

**Desktop post-pull merge logic:**
For each blob returned by pull:
- If `server_modified_at > local_synced_at` **and** `local_modified_at > local_synced_at` → **conflict** → set `!` badge on note row, hold server blob in memory; open `MergeWindow` when user clicks note (see §4.10).
- Otherwise → safe auto-accept → overwrite local row, update `synced_at`.

Notes:
- All sync queries scoped by `account_id` from JWT — never trusted from request body. `[REQ R16.4]` `[REQ R16.5]`
- `synced_at` on local `notes` row updated only after successful write.
- This diagram resolves gap **T5** (sync server interaction diagram). `[D-14 resolved 2026-05-14]`

---

### 4.9 OAuth PKCE Desktop Login Flow — planned (Sprint 5A, resolves gap T6 — D-14 decided 2026-05-14)

Triggered by `DesktopGUI.on_sync()` when no valid session token exists at `<data-dir>/.session`.

```
DesktopGUI         OS / system browser    Google OIDC         Sync Server
  │                       │                    │                   │
  │  generate code_verifier + code_challenge   │                   │
  │  build auth URL: accounts.google.com/o/oauth2/auth             │
  │    ?response_type=code                     │                   │
  │    &redirect_uri=astranotes://callback     │                   │
  │    &scope=openid+email                     │                   │
  │    &code_challenge=<S256>                  │                   │
  │    &state=<nonce>                          │                   │
  │── QDesktopServices.openUrl(auth_url) ─────►│                   │
  │                        │── GET auth_url ──►│                   │
  │                        │   (user consents) │                   │
  │                        │◄── redirect:      │                   │
  │                        │    astranotes://callback?code=<c>&state=<s>
  │◄── handle_url(url) ────│                   │                   │
  │  verify state == nonce (CSRF check)        │                   │
  │── POST /auth/callback {code, verifier} ───────────────────────►│
  │                                            │  exchange via authlib
  │                                            │  POST Google token endpoint
  │                                            │◄── {id_token, ...}
  │                                            │  verify id_token via JWKS
  │                                            │  upsert account record
  │◄── {jwt} ──────────────────────────────────────────────────────│
  │  write jwt → <data-dir>/.session (mode 0600)                   │
  │  proceed with push/pull                    │                   │
```

Notes:
- `astranotes://callback` custom URI scheme registered at install time — OS routes the browser redirect directly to the running app process; no inbound HTTP socket required. `[ADR-12]`
- `code_verifier` and `state` nonce are generated fresh per login attempt, held in memory only, discarded after exchange.
- JWT `sub` claim = `account_id`; signed with server private key. `[ADR-12]`
- Session file written with mode 0600; never logged or included in config. `[REQ R9.6]`
- This diagram resolves gap **T6** (OAuth PKCE desktop login flow). `[D-14 resolved 2026-05-14]`

---

### 4.10 Pull-with-Conflict and Merge Window — planned (Sprint 5B, resolves gap T7 — D-14 decided 2026-05-14)

**Conflict condition** (detected desktop-side during post-pull merge, see §4.8):
- `server_modified_at > local_synced_at` — server version changed since last sync
- `local_modified_at  > local_synced_at` — local version also changed since last sync

**Note row badge:** conflicted notes display a `!` indicator (yellow circle) in the left file list. The badge is cleared once the user saves a final version. If the app is closed without resolving, the badge does not persist — the next pull will re-detect the conflict.

**MergeWindow flow:**

```
User                      DesktopGUI / MergeWindow        DatabaseStore (SQLite)
  │                               │                               │
  │── click note (! badge) ──────►│                               │
  │                               │── load_local(note_id) ───────►│
  │                               │◄── local blob                 │
  │                               │   (server blob in memory      │
  │                               │    from pull response)        │
  │                               │  open MergeWindow:            │
  │                               │    left  = local (read-only,  │
  │                               │            diffs highlighted) │
  │                               │    right = remote (editable)  │
  │                               │                               │
  │  edit right pane freely;      │                               │
  │  [Use Local ←] copies left   ►│                               │
  │  into right pane              │                               │
  │                               │                               │
  │── click [Save Final] ────────►│                               │
  │                               │── update(note_id,             │
  │                               │    right_pane_content,        │
  │                               │    modified_at=now())         │
  │                               │◄── ok                         │
  │                               │  close MergeWindow            │
  │                               │  clear ! badge on note row    │
  │                               │  trigger push(note_id)        │
```

Notes:
- `MergeWindow` is a `QDialog` subclass with two `QTextEdit` panes. Left: `setReadOnly(True)`, diff highlighting via `QSyntaxHighlighter`. Right: editable, pre-populated with remote blob content.
- `[Use Local ←]` button replaces the right pane content with the full local version as a starting point.
- **No `note_conflicts` table.** The server blob is passed in memory from the pull response to `MergeWindow`. If the user closes without saving, the local version is unchanged and the `!` badge persists for the session.
- After [Save Final]: `modified_at` updated to `now()`; `synced_at` updated; a push is triggered immediately so the merged version propagates back to the server.
- This diagram resolves gap **T7** (conflict resolution design). `[D-14 resolved 2026-05-14]` `[REQ R16.3]`

---

## 5. Data Model

### 5.2 Database Schema

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

**Decision:** SQLite is always active on the device — no mode selection required. PostgreSQL is used only for the cloud sync server (Sprint 5). `DatabaseStore` (SQLAlchemy/SQLite) is used from Sprint 0; there is no JSON storage phase and no `migrate` command. `[D-10]` Sync server reads `DATABASE_URL` env var only (never stored in config, `sslmode=require`).

**Alternatives considered:**
- Hard Personal/Server mode split with forced first-launch prompt → removed (over-engineered; blocked data access behind login)
- PostgreSQL only → too heavy for single-user local use

**Consequences:** `NoteStore` (JSON) was never implemented — `DatabaseStore` (SQLAlchemy) is the only local store from Sprint 0. No backward-compatibility JSON path needed. Schema versioned via Alembic from Sprint 1 baseline. `[D-10 resolved 2026-05-12]`

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
**Status:** Accepted (planned)  `[REQ R2]` `[LOG 04-15]`

**Context:** Notes may contain sensitive personal information. Encryption must be both confidential and authenticated.

**Decision:** AES-256-GCM provides authenticated encryption (confidentiality + integrity). PBKDF2-HMAC-SHA256 with 100 000 iterations derives a 256-bit key from the user passphrase. A random 16-byte salt is generated per encrypt operation; the salt is stored alongside the ciphertext.

**Wire format:** `[16B salt][12B nonce][16B GCM tag][ciphertext]` → base64 encoded for JSON storage.

**Consequences:** Wrong passphrase is detected via GCM tag verification and raises `InvalidTag` — data is never silently corrupted. No default key; every encrypted operation requires an explicit passphrase. `[REQ R2.10]`

---

### ADR-05: Plugin Allowlist + Read-Only Note Copies  
**Status:** Planned  `[LOG 04-15]` `[REQ R4.5, R4.10, R15.7]` `[BL B-56, B-69]`

**Context:** An unrestricted plugin API allows plugins to modify note content in memory, access the raw database, or execute arbitrary code via `exec`/`eval`.

**Decision:** Plugins receive an isolated copy of note data via `dataclasses.replace(note)`. Any future mutable `Note` field (e.g. `tags: list[str]`) must be explicitly shallow-copied at the `call_hook()` call site — e.g. `dataclasses.replace(note, tags=list(note.tags))`. Plugin content is never passed to `exec()`, `eval()`, or shell commands. Plugins cannot access the raw DB session. Only plugins listed in the `allowed_plugins` config key are loaded — the check runs inside `register_plugin()` at startup, so a disallowed plugin never enters the registry. Hook crashes are caught by the registry and logged — they never propagate to the calling operation. `[D-09 resolved 2026-05-11]`

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

**Decision:** **authlib** with Google OpenID Connect as the required minimum provider; PKCE redirect via **custom URI scheme** (`astranotes://callback`). `[LOG 05-04]` `[D-01 resolved 2026-05-07]`
- authlib is framework-neutral (works with FastAPI for the sync server and handles PKCE flow for the desktop client); implements RFC 6749/7636/7519 correctly.
- Extensible provider registry pattern: each provider implements `get_auth_url()`, `exchange_code()`, `get_user_info()`.
- Provider secrets in environment variables only; never stored in config files or source code.
- JWT issued by sync server after successful OAuth callback; `sub` claim = `account_id`; signed with server private key.
- **PKCE redirect mechanism (D-01):** The desktop app registers the custom URI scheme `astranotes://callback` during installation (Windows: `HKCU\Software\Classes\astranotes` registry key; macOS: `Info.plist`; Linux: `.desktop` `MimeType=x-scheme-handler/astranotes`). Google's consent screen opens in the system browser; after approval the browser fires `astranotes://callback?code=<code>&state=<state>` and the OS routes it directly to the running app process — no inbound HTTP socket required. Embedded WebViews (`QWebEngineView`) are explicitly prohibited: Google blocks OAuth in embedded user-agents.
- **Why not loopback HTTP (Option A):** Loopback is safe with PKCE but requires an inbound socket and is fragile if the port is already bound. Because the app ships with an installer, the custom URI scheme is cleaner, has no port-conflict risk, and opens no network surface.

---

### ADR-13: GUI Framework — PySide6 Desktop Application  
**Status:** Decided  `[LOG 05-04]` `[BL B-84]` `[REQ R11.6]`

**Context:** The GUI layer needs to share Python core modules across both Sprint 4 (local CRUD) and Sprint 5 (sync added) without duplicating business logic. A single desktop app codebase serves both sprints.

**Options considered:**
- **Electron** — cross-platform web tech; requires Node.js toolchain alongside Python
- **Tkinter** — zero extra deps, Python-native; limited styling and widget richness
- **Local web server + browser SPA** — previously considered; dropped (browser UI eliminated by team decision)
- **PySide6** — Qt6 Python binding; native widgets; LGPL; no Node.js; same API as PyQt6 but safer licence

**Decision:** **PySide6 desktop application.** `[LOG 05-04]` A single PySide6 `QApplication` is the GUI for both Sprint 4 (local CRUD) and Sprint 5 (sync added). There is no browser-based surface; the sync server is a backend-only REST service. PySide6 is chosen over PyQt6 (same Qt6 API; LGPL licence is safer for course use) and over Electron/Tkinter (native widgets, no Node.js toolchain, richer styling than Tkinter). The Sprint 5 sync button triggers push/pull; if no valid session token is found, the app presents an OAuth login dialog (opens system browser for Google consent via PKCE flow; redirect captured via `astranotes://callback` custom URI scheme — see ADR-12). Both sprint deliverables share one codebase; sync features are activated by the presence of a valid session token.

---

### ADR-14: Plugin Manifest Format and Trust Tier Model
**Status:** Decided  `[LOG 05-12]` `[BL B-99, B-100]` `[REQ R4.11, R4.12, R4.13]`

**Context:** D-05 deferred manifest format and sandboxing trust model as not blocking at the time. Both are required before Sprint 4 extension registry implementation. Without a manifest schema, `PluginRegistry.load_manifests()` cannot validate extension bundles. Without a trust tier model, user-installed extensions have the same API access as official ones, which violates the privacy-first architecture.

**Options considered:**
- **TOML manifest** — human-friendly, but adds `tomllib` / `tomli` dependency (Python 3.10 only for stdlib). Not worth it.
- **JSON manifest** — validated with `jsonschema` (already a plausible dep), consistent with VS Code's `package.json` model, simpler schema tooling.
- **Subprocess sandbox** — full OS-level process isolation. Too heavyweight for hook-style plugins; adds IPC complexity. Deferred to a future tier.
- **Restricted API tier** — user-installed plugins simply cannot call `PluginBase` hook-registration methods. Enforced in `register_plugin()`. Zero runtime overhead.

**Decision:** `[LOG 05-12]`
- **Format:** JSON (`plugin.json`) in each plugin subdirectory. Validated against a `jsonschema` schema at `load_manifests()` time. Malformed or missing manifests are rejected with a warning; the plugin is skipped.
- **Required fields:** `plugin_id`, `name`, `version` (semver), `engines` (min AstraNotes version), `main` (entrypoint module path).
- **Optional fields:** `supported_mime_types`, `keywords`, `categories`, `repository` (str URL), `extensionDependencies` (list of `plugin_id`s).
- **`is_official` is server-assigned only** — never read from `plugin.json`. Any manifest containing `is_official` is rejected. `PluginRegistry.register_plugin(plugin, is_official)` receives this value from the backend-verified extension registry record. Sideloaded plugins are always `is_official = False`.
- **Trust tiers:**
  - `is_official = True` (pre-installed, server-approved) → allowed to call full `EditorProvider` + `PluginBase` API (hooks, CLI commands, read-only note copies).
  - `is_official = False` (user-installed) → restricted to `EditorProvider` only (content editing/viewing for owned MIME types). `PluginBase` hook registration is blocked at `register_plugin()` time with a warning.
- **Rationale for tier boundary:** `PluginBase` hooks receive a copy of every note on post-add/post-update. Giving user-installed plugins unrestricted hook access would allow a malicious plugin to silently exfiltrate all note content. Restricting to `EditorProvider` limits the plugin to notes the user actively opens in that plugin's editor.
- **Future work:** A subprocess sandbox tier (OS-level process isolation, IPC) is tracked as a future backlog item for when third-party plugins require stricter containment.

Maps each requirement group to the implementing module, class, and test coverage. All entries are **planned and unimplemented**. Sprint 0 source code was removed on 2026-05-11; no `src/` directory or tests exist. The module paths listed are the Sprint 1+ targets. `[LOG 05-11]`

| Requirement | Module | Class / Function | Test |
|-------------|--------|-----------------|------|
| R1.1 Add note (text) | *(planned)* `src/cli.py` | `add()` | `[BL B-01]` — not yet tested |
| R1.2 Get by ID | *(planned)* `src/cli.py` | `get()` | `[BL B-04]` — not yet tested |
| R1.3 List notes | *(planned)* `src/cli.py` | `list()` | `[BL B-07]` — not yet tested |
| R1.4 Update note | *(planned)* `src/cli.py` | `update()` | `[BL B-08]` — not yet tested |
| R1.5 Delete note | *(planned)* `src/cli.py` | `delete()` | `[BL B-11]` — not yet tested |
| R1.6 Reject empty input | *(planned)* `src/cli.py` | `add()` guard | `[BL B-03]` — not yet tested |
| R1.7 Non-existent ID error | *(planned)* `src/core/notes.py` | `DatabaseStore.get/update/delete` | `[BL B-14]` — not yet tested |
| R1.8 Gap-safe IDs | *(planned)* `src/core/notes.py` | `DatabaseStore.add` | `[BL B-31]` — not yet tested |
| R1.9 `--data-dir` validation | *(planned)* `src/cli.py` | `cli()` group | `[BL B-36]` — not yet tested |
| R2.1 `--encrypt yes` | *(planned)* `src/cli.py` | `add()` | `[BL B-02]` — not yet tested |
| R2.2 Passphrase confirmation | *(planned)* `src/cli.py` | `add()` | `[BL B-32]` — not yet tested |
| R2.3–R2.5 Passphrase on read/update/delete | *(planned)* `src/cli.py` | `get/update/delete` + `get_key_manager(ctx)` `[D-11]` | `[BL B-05, B-09, B-12]` — not yet tested |
| R2.6 No prompt on unencrypted | *(planned)* `src/cli.py` | `add/get/list/update/delete` | `[BL B-01–B-15]` — not yet tested |
| R2.7 List hides encrypted title | *(planned)* `src/cli.py` | `list()` | `[BL B-07]` — not yet tested |
| R2.8 Reject wrong passphrase | *(planned)* `src/core/security.py` | `EncryptionEngine.decrypt` (raises `InvalidTag`) | `[BL B-06, B-10, B-13]` — not yet tested |
| R2.9 Sandbox blob model | *(planned)* `src/core/notes.py` | `BlobCodec` | `[BL B-43]` — not yet implemented |
| R2.10 No default key | *(planned)* `src/core/notes.py` | `DatabaseStore.__init__` | `[BL B-16]` — not yet tested |
| R2.11 Min 8-char passphrase | *(planned)* `src/cli.py` | `get_key_manager(ctx)` `[D-11]` | `[BL B-34]` — not yet tested |
| R2.12 No cross-note corruption | *(planned)* `src/core/notes.py` | `DatabaseStore` ACID | `[BL B-21]` — not yet tested |
| R2.14 `reencrypt` command | *(planned)* `src/cli.py` | new command | `[BL B-62]` |
| R3.5 1000+ notes performance | *(planned)* `src/core/notes.py` | `DatabaseStore` | `[BL B-22]` — not yet tested |
| R4.1–R4.2 Plugin base + registry | *(planned)* `src/core/plugin_base.py` | `PluginBase`, `PluginRegistry` | `[BL B-18, B-83]` — not yet tested |
| R4.3–R4.4 Hooks + CLI commands | *(planned)* `plugins/summary_plugin.py` | `SummaryPlugin` | `[BL B-18]` — not yet tested |
| R4.6 Plugin discovery | *(planned)* `src/cli.py` | startup loader | `[BL B-37]` |
| R4.7 Hook error isolation | *(planned)* `src/core/plugin_base.py` | `PluginRegistry.call_hook` | `[BL B-38]` |
| R4.8 Duplicate plugin skip | *(planned)* `src/core/plugin_base.py` | `PluginRegistry.register_plugin` | `[BL B-38]` |
| R4.10 Plugin allowlist | *(planned)* `src/core/plugin_base.py` | startup loader + config | `[BL B-69]` |
| R5.1 `--data-dir` global option | *(planned)* `src/cli.py` | `cli()` | `[BL B-19]` — not yet tested |
| R5.2 Non-zero exit on error | *(planned)* `src/cli.py` | `raise click.ClickException` | `[BL B-23]` — not yet tested |
| R7 Override policy | ✅ `src/cli.py` + `src/core/plugin_base.py` | red warning + `CONFIRM OVERRIDE` prompt | `[BL B-24]` |
| R8 Audit trail | ✅ `src/core/audit.py` | `AuditLogger` — append-only JSON log | `[BL B-25, B-71]` |
| R9 Config module | ✅ `src/core/config.py` | `ConfigStore` — known-key whitelist, set/get/list/reset | `[BL B-26]` |
| R10.1–R10.3 Search | ✅ `src/cli.py` | `search_cmd()` — DB layer returns `blob=None` for encrypted notes; `--encrypted` prompts passphrase **per note** (each note may use a different passphrase) | `[BL B-29]` |
| R10.4–R10.7 Export | ✅ `src/cli.py` | `export_cmd()` — text/JSON, `--output`, `--encrypted`, binary payloads, `--cleanup` | `[BL B-30, B-76, B-78]` |
| R12 Local-first architecture with opt-in account | *(planned)* `src/cli.py` | `get_store()` startup factory; first-login prompt (one-time) | `[BL B-41, B-42]` |
| R13 Authentication | *(planned)* `src/core/` | `AuthManager` | `[BL B-45–B-47, B-57–B-61]` |
| R14.1–R14.13 Database backend | *(planned)* `src/core/` | `DatabaseStore` | `[BL B-42–B-44, B-51, B-63–B-68]` |
| R15.1–R15.2 ORM / no raw SQL | *(planned)* `src/core/` | `DatabaseStore` | `[BL B-51]` |
| R15.3 Input validation | *(planned)* `src/cli.py` | CLI boundary guard | `[BL B-52]` |
| R15.4 PostgreSQL DML-only role | *(planned)* deployment | DB role config | `[BL B-53]` |
| R15.5 ANSI strip | *(planned)* `src/cli.py` | output render | `[BL B-54]` |
| R15.7 Plugin read-only copies | *(planned)* `src/core/plugin_base.py` | `call_hook` | `[BL B-56]` |
| R15.8 Path traversal prevention | *(planned)* `src/cli.py` | input validation | `[BL B-55]` |

---

## 8. Directory Structure

**Current state (as of 2026-05-11):** Sprint 0 source deleted. `src/`, `tests/`, `plugins/`, `pytest.ini`, and `test_all.py` were removed. The planned Sprint 1 target structure is described in §2 (UML Package Diagram). `[LOG 05-11]`

```
AstraNotes/
├── AI Working Log/
│   ├── working-log-2026-04-08.md
│   ├── working-log-2026-04-15.md
│   ├── working-log-2026-04-29.md
│   ├── working-log-2026-05-04.md
│   ├── working-log-2026-05-05.md
│   └── working-log-2026-05-10.md
├── Copilot/
│   ├── Definition of Done.md
│   ├── discussion-list.md
│   └── Working Agreement.md
├── docs/
│   ├── ai-use-disclosure.md
│   ├── bdd-testing.md
│   ├── test-execution-evidence.md
│   └── test-workflow.md
├── planning/
│   ├── backlog.md
│   ├── design.md               # This file
│   ├── prd.md
│   ├── requirements.md
│   ├── sprint-zero-plan.md
│   ├── traceability-metrics.md
│   └── user-stories.md
├── LICENSE
├── README.md
└── requirements.txt
```

---

## 9. Design Weaknesses, Gaps, and Intentional Deferments

Four categories are distinguished. **Known pitfalls** are implementation mistakes identified from the prior codebase that must not be repeated in the new implementation. **Missing design** means a transition or integration point has no design at all. **Underspecified design** means the design describes something but omits enough detail that implementation decisions are left undefined. **Intentional deferments** are explicitly scoped-down items whose absence is known and tracked.

---

### 9.1 Known Pitfalls from Prior Implementation — Avoid in New Code

**B1 — ID collision after delete** `[REQ R1.8]` `[BL B-31]`  
The new implementation MUST use `str(uuid.uuid4())` as the note ID inside `DatabaseStore.add()`. Do NOT compute the ID as `str(len(store.list()) + 1)` — that formula collides after any deletion (deleting note 3 from {1, 2, 3} then adding yields a second note 3). UUIDs are gap-safe, require no coordination, and require no reading of existing IDs before insertion. The interaction diagram in §4.1 shows the correct UUID approach.

**B2 — Wrong-passphrase detection must use cryptography, not a sentinel string** `[REQ R2.8]`  
`EncryptionEngine.decrypt()` raises `cryptography.exceptions.InvalidTag` on a wrong passphrase. The new implementation MUST let this exception propagate from `EncryptionEngine` through `BlobCodec.decrypt()` to the CLI. Do NOT catch `InvalidTag` silently inside `DatabaseStore.get()` and replace the note title with `"[Encrypted Note]"`. Do NOT then branch on `if note.title == "[Encrypted Note]"` in CLI commands to detect a wrong passphrase — any note legitimately titled that string would be permanently inaccessible. Correct pattern: `BlobCodec.decrypt()` propagates `InvalidTag` to the caller; the CLI `get`, `update`, and `delete` commands catch it and exit with a non-zero code and an error message.

**B3 — Only encrypt the note being added; never re-encrypt existing notes on add** `[REQ R3.2]`  
The new implementation MUST NOT call `key_manager.get_engine()` once per note inside `DatabaseStore.add()` when persisting other notes. That approach would produce a new random salt per call and re-encrypt notes that were not modified. With 100,000 PBKDF2 iterations per derivation, performance degrades proportionally to the number of encrypted notes. Correct approach: each `Note` stores its own `salt` alongside its ciphertext; on add, only the new note is encrypted; unchanged notes are never touched (`blob` bytes stored verbatim from their last-write operation). The wire format `[16B salt][12B nonce][16B GCM tag][ciphertext]` supports independent per-note salts natively.

---

### 9.2 Critical Transitions with No Design

**T1 — No store factory or startup router** ✅ *Resolved — see §4.5 and D-06 (2026-05-11)*  
Resolved by §4.5 startup sequence diagram: a Click group callback always creates `DatabaseStore(data_dir)`. `[D-06]` `[LOG 05-11]`

**T2 — No migration sequence diagram** ✅ *Resolved — D-10 (2026-05-12)*  
Eliminated — `DatabaseStore` (SQLite) used from Sprint 0; no JSON storage phase; no `migrate` command. `[D-10]`

**T3 — No session validation integration point** ✅ *Resolved — D-11 (2026-05-12)*  
~~No session validation integration point.~~ Resolved by §4.6: a dedicated `sync` Click group callback calls `AuthManager.verify_session()` — blocking, exits on expired/missing session. CRUD commands run through the top-level callback only (non-blocking `try_load_session()`). Expired session blocks sync only; local CRUD unaffected. `[REQ R13.8]` `[D-11 resolved 2026-05-12]`

**T4 — No passphrase caching design** ✅ *Resolved — D-11 (2026-05-12)*  
~~No replacement design for `ensure_store()`.~~ `ensure_store()` belonged to the deleted Sprint 0 codebase and is not carried forward. New design: `get_key_manager(ctx)` helper in `cli.py` — prompts passphrase on first call, caches `KeyManager` in `ctx.obj['key_manager']` for the lifetime of the process. Called only by `get`, `update`, `delete`, `reencrypt`. `add` constructs `KeyManager` inline (not cached). `list` never calls it. `[D-11 resolved 2026-05-12]`

---

### 9.3 Described but Underspecified Design

**U1 — `Note.title` dual-role state machine** ✅ *Resolved — D-07 (2026-05-11)*  
~~`encrypted_title` removed from `Note`.~~ Option C adopted: `Note.blob: bytes | None` is the sole authoritative storage for encrypted notes. `title` and `content` are in-memory views populated by `BlobCodec.decrypt() + decode()`. See §3.1 state table. `[D-07]` `[LOG 05-11]`

**U2 — No error flows in any interaction diagram** ✅ *Resolved — D-08 (2026-05-11)*  
Error flows added to §4.1, §4.2, §4.2a, and §4.5. Decisions: `InvalidTag` propagates from `BlobCodec.decrypt()` through `DatabaseStore.get()` to CLI, caught as `ClickException` (Option B). Missing note ID: `DatabaseStore.get()` returns `None`; CLI checks and raises `ClickException` (Option A). `OperationalError` on write propagates to CLI, caught as `ClickException` (Option A). All error paths exit 1. `[D-08]` `[LOG 05-11]`

**U3 — Plugin allowlist and read-only copies have no designed call site** ✅ *Resolved — D-09 (2026-05-11)*  
Allowlist check placed in `register_plugin()` — disallowed plugins never enter the registry (VS Code install-time validation model). Note isolation uses `dataclasses.replace(note)` — safe for current all-primitive `Note` fields; mutable fields added in future must be explicitly shallow-copied at the call site. `PluginRegistry` class diagram updated (`_allowed: frozenset`, `call_hook` signature); §4.4 diagram updated. ADR-05 updated. `[D-09]` `[LOG 05-11]`

**U4 — `BlobCodec` has no designed call site** ✅ *Resolved — D-07 (2026-05-11), D-10 (2026-05-12)*  
Call site fully decided: `DatabaseStore` calls `BlobCodec.encode() + encrypt()` in `add()` when `--encrypt yes`; `BlobCodec.decrypt() + decode()` in `get()` when note is encrypted and `key_manager` is present. `add` constructs `KeyManager` inline; `get`/`update`/`delete`/`reencrypt` use `get_key_manager(ctx)` helper. No `migrate` call site — D-10 eliminated migration. `[D-07]` `[D-10]` `[D-11]` `[LOG 05-11]`

**U5 — `ConfigStore` has no designed integration point** ✅ *Resolved — see §4.5 and D-06 (2026-05-11)*  
~~`ConfigStore` appears in §3.2 but in no interaction diagram.~~ Resolved by §4.5: `ConfigStore` loads first in the Click group callback from a fixed OS-standard path (`%APPDATA%\astranotes\config.json` / `~/.config/astranotes/config.json`). `data_dir` is then resolved from config (with `--data-dir` CLI flag overriding). `[D-06]` `[LOG 05-11]`

---

### 9.4 Intentional Scope Reductions (Acknowledged Deferments)

These are not bugs. They are explicit backlog decisions whose absence is tracked.

| Item | Deferment Reason | Risk If Not Addressed Before Next Sprint |
|------|-----------------|------------------------------------------|
| ~~Sandbox blob (`BlobCodec`) not coded~~ `[BL B-43]` | ~~Sprint Zero scope~~ — **Sprint 0** `[D-07 resolved 2026-05-11]` `[D-10 resolved 2026-05-12]` | Risk eliminated; `BlobCodec` built in Sprint 0 alongside `DatabaseStore` |
| All of R13–R15 (auth, DB, injection) | Requires DB backend first | No injection prevention, no user isolation, no audit trail in current build |
| Passphrase confirmation on encrypt `[BL B-32]` | Sprint Zero scope | Typo passphrase → note permanently inaccessible; no recourse |
| `--data-dir` writable validation `[BL B-36]` | Sprint Zero scope | Unwritable path produces unhelpful `OSError` with no actionable message |
| ~~Corrupt JSON recovery `[BL B-35]`~~ | **DROPPED** `[D-10]` | N/A — SQLite ACID replaces JSON corruption risk; no `.bak` fallback needed |
| GUI layer `[BL B-27]` | Explicit post-CLI-stabilization | No risk; correctly deferred until CLI is stable |
| Search and export `[BL B-29, B-30]` | Sprint Zero scope | Feature absent; no partial implementation that could conflict |
| Desktop GUI (Sprint 4) `[BL B-84, B-85]` | ADR-13 decided: PySide6 `[LOG 05-04]` | No risk; no implementation started |
| Sync Server + Desktop Sync UI (Sprint 5) `[BL B-86–B-95]` | ADR-11/12/13 decided `[LOG 05-04]` | No risk; no implementation started |

---

### 9.5 Architecture Design Gaps Introduced by GUI Redesign `[LOG 05-04]`

**T5 — No interaction diagram for sync server request flow** ✅ *Resolved — see §4.8 and D-14 (2026-05-14)*  
~~§4 has four interaction diagrams (SD-1–SD-4) covering CLI flows only. There is no sequence diagram showing a desktop app sync call → `AuthMiddleware` token validation → `SyncRouter` push/pull → `DatabaseStore` query → JSON response.~~ Resolved by §4.8: push/pull happy-path sequences + 401 error flow; post-pull conflict detection logic documented in §4.8 notes. `[D-14 resolved 2026-05-14]`

**T6 — No OAuth PKCE desktop flow diagram** ✅ *Resolved — see §4.9 and D-14 (2026-05-14)*  
~~The OAuth 2.0 / PKCE callback flow for the desktop app is undesigned.~~ Resolved by §4.9: full PKCE sequence from `QDesktopServices.openUrl()` → user consent → `astranotes://callback` redirect → code exchange via authlib → JWT issuance → session file written at mode 0600. `[ADR-12]` `[D-14 resolved 2026-05-14]`

**T7 — No cloud sync conflict resolution design** ✅ *Resolved — see §4.10 and D-14 (2026-05-14)*  
~~`R11.10` and `US-14` require sync-on-demand with conflict resolution. There is no design for conflict detection or resolution strategy.~~ Resolved by §4.10: conflict detected desktop-side (both `server_modified_at` and `local_modified_at` newer than `local_synced_at`); `!` badge on note row; 2-pane `MergeWindow` (`QDialog`) with local read-only left and remote editable right; [Use Local ←] and [Save Final] buttons. No `note_conflicts` table. `[REQ R16.3]` `[D-14 resolved 2026-05-14]`

**T8 — No desktop GUI startup sequence** ✅ *Resolved — see §4.7 and D-13 (2026-05-13)*  
~~The desktop GUI's startup interaction with core modules (how it instantiates `DatabaseStore`, how it handles passphrase prompts via `QDialog`, how it handles the SQLite WAL concurrent-access case when both CLI and GUI are open simultaneously) is undesigned.~~ Resolved by §4.7 startup sequence diagram: `AppController` (Option C orchestrator) owns `ConfigStore`, `DatabaseStore`, `SessionManager`, and `DesktopGUI`. `DesktopGUI` receives `DatabaseStore` by injection. Passphrase `QDialog` is lazy — shown only on note open. Session exclusivity enforced by a PID lock file (`<data-dir>/.app.lock`); concurrent CLI + GUI blocked with error dialog. Encrypted note idle auto-lock after 5 minutes (security feature). First launch handled transparently by `DatabaseStore.create_all()`. `[D-13 resolved 2026-05-13]` `[REQ R9.7, R9.8]` `[BL B-101, B-102]`

---

## 10. Traceability Metrics

See [`planning/traceability-metrics.md`](traceability-metrics.md) for the full breakdown:

| Metric | Count | % |
|--------|-------|---|
| Total requirements reviewed | 138 | 100% |
| Fully Traced | 0 | 0% |
| Partially Traced | 0 | 0% |
| Weakly Traced | 121 | 88% |
| Not Traced | 17 | 12% |
| UML elements without a requirement | 4 | — |

> **Note (2026-05-07):** All Sprint Zero source code and tests were removed. All items previously Fully Traced or Partially Traced are now Weakly Traced (design only, no code). See `planning/traceability-metrics.md` for the full matrix.

---

*This document was drafted by Astra (GitHub Copilot) from existing source code, planning artifacts, and working logs. Subject to human review before acceptance per `Copilot/Working Agreement.md`.*
