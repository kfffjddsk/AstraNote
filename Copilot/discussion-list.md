# Discussion List

**Purpose:** Open questions and unresolved items that need a decision before the affected sprint begins.  
At the start of each session, Astra reads this file and raises any items that are blocking upcoming work.  
Add an item here whenever the team decides to defer a decision, or by saying "add that to the discussion list."  
When an item is resolved, mark it **Resolved** with a brief note and the date — do not delete it.

---

## Open Items

*No open items.*

---

## Resolved Items

### ~~D-14 — Sync Server Interaction Diagrams and Conflict Resolution~~
**Added:** 2026-05-11  
**Resolved:** 2026-05-14  
**Decisions:**

- **T5 — Push/pull sequence (§4.8):** Two-endpoint happy path designed. Push: `POST /sync/push` → `AuthMiddleware.verify_token()` extracts `account_id` → `SyncRouter.push()` → UPSERT on PG `notes` table → 200 `{synced_at}`. Pull: `GET /sync/pull?since=<ts>` → same auth gate → `SELECT WHERE modified_at > since AND account_id = ?` → 200 `[note blobs]`. All queries scoped by `account_id` from JWT only. Post-pull: desktop compares `server_modified_at` and `local_modified_at` vs `local_synced_at` to detect conflicts.
- **T6 — OAuth PKCE flow (§4.9):** `DesktopGUI.on_sync()` generates `code_verifier` + `code_challenge`; opens system browser via `QDesktopServices.openUrl()`; receives redirect at `astranotes://callback` custom URI scheme (ADR-12); verifies `state` nonce (CSRF); POSTs `code` + `verifier` to sync server `/auth/callback`; server exchanges via authlib, verifies `id_token` via Google JWKS, upserts account, returns JWT; desktop writes JWT to `<data-dir>/.session` (mode 0600).
- **T7 — Conflict resolution (§4.10):** No `note_conflicts` table (previous R16.3 language removed). Conflict detected desktop-side when both `server_modified_at > local_synced_at` and `local_modified_at > local_synced_at`. Conflicted note shows `!` badge (yellow circle) in left file list. Clicking opens `MergeWindow` (`QDialog` subclass): local version read-only on left (diffs highlighted), remote version editable on right. `[Use Local ←]` copies full local into right pane. `[Save Final]` writes right-pane content to `DatabaseStore`, clears badge, triggers push. Server blob held in memory only — if app closed without resolving, next pull re-detects.

New design: §4.8 (push/pull), §4.9 (PKCE), §4.10 (MergeWindow). New class: `MergeWindow` (§3.2). Updated: R16.3, B-86, FR-122. `[LOG 05-14]`

---

### ~~D-13 — Desktop GUI Startup Sequence~~
**Added:** 2026-05-11  
**Resolved:** 2026-05-13  
**Decisions:**

- **Startup orchestrator (Q1):** `AppController` (Option C) owns all startup wiring. `main.py` constructs `AppController` and calls `run()`. Initialization order: `ConfigStore.load()` → `DatabaseStore(data_dir)` → `SessionManager.acquire_lock()` → `PluginRegistry.load_manifests()` → `QApplication` + `DesktopGUI(store, session_mgr, config)` → `populate_note_list()` → `start_idle_timer()` → `app.exec()`. `DesktopGUI` receives `DatabaseStore` via constructor injection — never creates it internally.
- **Passphrase prompt timing (Q2):** Lazy — note list shows `[Encrypted]` placeholder; `QDialog` appears only when user clicks an encrypted note. No passphrase prompt at startup.
- **Session exclusivity + idle auto-lock (Q3):** Session exclusivity enforced by a PID-based lock file at `<data-dir>/.app.lock`. New session checks lock: alive PID → blocked with error dialog; dead PID → stale lock overwritten. Lock deleted on clean exit. Idle auto-lock: encrypted note open for 5 minutes without interaction → auto-close, clear passphrase from memory, redisplay `[Encrypted]`. Security feature, not multi-user locking.
- **First launch (Q4):** Already handled — `DatabaseStore.__init__` calls `create_all()` transparently. No special case needed in `AppController`.

New backlog: B-101 (`AppController` + `SessionManager` session lock), B-102 (idle auto-lock timer). New requirements: R9.7 (session exclusivity), R9.8 (idle auto-lock). New design: §4.7. `[LOG 05-13]`

---

### ~~D-12 — Extension Plugin Manifest Schema and Sandboxing Trust Model~~
**Added:** 2026-05-11  
**Resolved:** 2026-05-12  
**Decisions:**

- **Manifest format:** JSON (`plugin.json`) in each plugin subdirectory. Validated at `load_manifests()` time with `jsonschema`. Malformed or missing manifests rejected with warning; plugin skipped.
- **Required fields:** `plugin_id` (unique namespace), `name`, `version` (semver), `engines` (min AstraNotes version), `main` (entrypoint module path).
- **Optional fields:** `supported_mime_types`, `keywords` (list[str]), `categories` (list[str]), `repository` (str URL), `extensionDependencies` (list of `plugin_id`s).
- **`is_official` is server-assigned only** — NOT a manifest field. `load_manifests()` rejects any manifest containing `is_official`. Value injected by `PluginRegistry.register_plugin(plugin, is_official)` from the backend-verified extension registry record. Sideloaded plugins always default to `is_official = False`.
- **Trust tiers:** `is_official = True` (server-approved) → full `EditorProvider` + `PluginBase` API. `is_official = False` (user-installed) → `EditorProvider` only; `PluginBase` hook registration blocked at `register_plugin()` time with warning.
- **Trust tier rationale:** `PluginBase` hooks receive a copy of every note on post-add/post-update. Allowing user-installed plugins unrestricted hook access would enable silent note exfiltration. `EditorProvider` restriction limits access to only notes the user actively opens in that plugin's editor.
- **`EditorProvider` class updated:** `engines: str` and `main: str` added as required fields. `is_official: bool` annotation updated to "server-assigned — NOT read from plugin.json."
- **`PluginRegistry` updated:** `register_plugin()` signature updated to `register_plugin(plugin, is_official: bool)`; trust-tier enforcement added.

New backlog: B-99 (manifest validation), B-100 (trust-tier enforcement in `register_plugin`). New requirements: R4.11, R4.12, R4.13. New ADR-14. `[LOG 05-12]`

---

### ~~D-11 — Session Validation Integration Point and `ensure_store()` Replacement~~
**Added:** 2026-05-11  
**Resolved:** 2026-05-12  
**Decisions:**

- **T3 — Sync gating:** `sync` is its own Click subgroup. Its group callback calls `AuthManager.verify_session()` — blocking: raises `ClickException` + exit 1 on expired or missing session. The main startup callback (§4.5) calls `try_load_session()` — non-blocking, sets `account_id = None` on miss. Local CRUD is unaffected by session state. See §4.6 for the new sequence diagram. `[REQ R13.8]`
- **Note scoping:** Logged-out → anonymous notes only (`account_id = NULL`). Logged-in → own account notes + anonymous notes. No cross-user visibility.
- **Two-section list layout:** `DatabaseStore.list(account_id)` returns `(account_notes: List[Note], local_notes: List[Note])`. CLI renders **"Your Notes"** (account notes) then **"Local Open Notes"** (anonymous). "Your Notes" omitted entirely when logged out. When anonymous notes are associated on login (R12.3 "Yes"), they get `account_id` set and move to "Your Notes". R1.3 updated. `[LOG 05-12]`
- **Passphrase caching (T4):** `get_key_manager(ctx)` module-level helper in `cli.py`. Checks `ctx.obj['key_manager']` first; if None, prompts passphrase, constructs `KeyManager`, caches it. Within-process only — no OS keychain, no cross-invocation caching. Each new CLI invocation = re-prompt.
- **`add` command:** Constructs `KeyManager` inline — not cached in `ctx.obj`.
- **`list` command:** Never needs `key_manager` — reads plaintext columns only.
- **Commands using `get_key_manager(ctx)`:** `get`, `update`, `delete`, `reencrypt`.
- **`ctx.obj` schema:** `{'store': DatabaseStore, 'account_id': str|None, 'key_manager': KeyManager|None}`.
- **GUI passphrase security level (B-98, Sprint 4):** `security_level` config key. `high` (default): clear passphrase on note close, navigate away, minimize, or focus loss. `session`: clear only on app close.

Files updated: design.md (§3.1, §3.2, §4.1, §4.2, §4.2a, §4.5, new §4.6, §9.2 T2–T4, §9.3 U4), requirements.md (R1.3), backlog.md (B-97 line fix + B-98 added). `[LOG 05-12]`

---

### ~~D-10 — Migration Sequence Diagram~~
**Added:** 2026-05-11  
**Resolved:** 2026-05-12  
**Decision:** Eliminated — no migration needed. `DatabaseStore` (SQLite) used from Sprint 0; no JSON storage phase ever shipped. `migrate` CLI command (B-48) dropped; B-72 and B-80 dropped as dependents. D-10 closes as "not needed." Sprint plans, backlog, and design updated accordingly. `[LOG 05-12]`

---

### D-06 — CLI Startup: Store Factory and ConfigStore Integration
**Added:** 2026-05-11  
**Resolved:** 2026-05-11  
**Decisions:**
- **ConfigStore location (Option 2):** `ConfigStore` lives at a fixed OS-standard path (`~/.config/astranotes/config.json` on Linux/macOS, `%APPDATA%\astranotes\config.json` on Windows), not inside `data_dir`. The data directory is read from `config["data_dir"]`; the `--data-dir` CLI flag overrides it at runtime. This separates configuration from data and supports portable use (e.g., pointing `--data-dir` at a USB drive requires no config file on the drive). `[LOG 05-11]`
- **Startup sequence:** (1) `ConfigStore.load()` from fixed OS path; (2) resolve `data_dir` — CLI `--data-dir` flag overrides `config["data_dir"]`; (3) store creation — always `DatabaseStore(data_dir)` (`create_all()` creates `notes.db` on first run); (4) `PluginRegistry` loads manifests eagerly (MIME-type validation), defers plugin code import until first relevant note is opened (VS Code activation-events model). `[LOG 05-11]` `[D-10 resolved 2026-05-12]`
- **Code location:** Single central Click group callback in `src/cli.py`. Runs once before every subcommand. `--help` and `--version` short-circuit before the callback runs (Click and `@click.version_option` handle this automatically — no startup I/O for help/version). `[LOG 05-11]`

### D-09 — `PluginRegistry`: Allowlist and Read-Only Copy Call Sites
**Added:** 2026-05-11  
**Resolved:** 2026-05-11  
**Decisions:** `[LOG 05-11]`
- **Allowlist check location:** `register_plugin()` — mirrors VS Code's install-time publisher validation. A plugin not in `config["allowed_plugins"]` is logged as a warning and skipped; it never enters the registry. Checking at registration time (not at `call_hook()` time) means the guard runs once, not on every hook dispatch.
- **Note isolation:** `dataclasses.replace(note)` — safe for current `Note` (all-primitive fields: `str`, `bool`, `bytes | None`). Rule: any future mutable field added to `Note` (e.g. `tags: list[str]`) **must** be explicitly shallow-copied at the `call_hook()` call site: `dataclasses.replace(note, tags=list(note.tags))`.
- **Files updated:** `planning/design.md` — `PluginRegistry` class diagram (`_allowed: frozenset` field added, `call_hook` signature updated), §4.4 hook-dispatch diagram, ADR-05 decision text, §9.3 U3 marked resolved.

### D-08 — Error Flows Missing from All Interaction Diagrams
**Added:** 2026-05-11  
**Resolved:** 2026-05-11  
**Decisions:** Error flows added to §4.1, §4.2, §4.2a (new), and §4.5. `StoreLoadError` added to §3.2 planned classes. `[LOG 05-11]`

| Case | Exception source | Catch site | Exit |
|------|-----------------|-----------|------|
| Wrong passphrase | `InvalidTag` propagates from `BlobCodec.decrypt()` through `DatabaseStore.get()` | CLI `get`/`update`/`delete` — `ClickException("[DatabaseStore] Wrong passphrase …")` | 1 |
| Note not found | `DatabaseStore.get()` returns `None` | CLI checks return value — `ClickException("Note <id> not found.")` | 1 |
| Disk full / permission | `OperationalError` propagates from `DatabaseStore` | CLI — `ClickException("[DatabaseStore] Write failed: <msg>")` | 1 |
| ~~Corrupt `notes.json`~~ | ~~`NoteStore.load()` raises `StoreLoadError(path)`~~ | ~~CLI startup callback~~ | ~~1~~ | — **RETIRED** `[D-10]` (SQLite ACID replaces JSON corruption) |

### D-07 — `Note.title` Dual-Field State Machine
**Added:** 2026-05-11  
**Resolved:** 2026-05-11  
**Decision — Option C:** `encrypted_title` removed from `Note`. `Note.blob: bytes | None` is the sole authoritative storage for encrypted notes. `BlobCodec` moved to Sprint 0 `[D-10]`. `DatabaseStore` calls `BlobCodec.encode() + encrypt()` in `add()`; `BlobCodec.decrypt() + decode()` in `get()` when a key is present.

**`Note` field state machine:**

| State | `encrypted` | `blob` | `title` (in-memory) | `content` (in-memory) |
|-------|-------------|--------|--------------------|-----------------------|
| Unencrypted | `False` | `None` | Plaintext — authoritative | Plaintext — authoritative |
| Encrypted, no key | `True` | bytes | `"[Encrypted Note]"` — display only | `""` — empty |
| Encrypted, correct key | `True` | bytes | Decrypted from blob header | Decrypted from blob payload |

- `blob` is the sole authoritative source for encrypted notes; `title` and `content` are ephemeral in-memory views.
- On save, unchanged encrypted notes write `blob` verbatim — no re-encrypt. Only modified notes are re-encoded and re-encrypted. `[REQ R3.2]`
- `"[Encrypted Note]"` is display-only — no code path may branch on it to detect a wrong passphrase (Pitfall B2). `[LOG 05-11]`

### D-04 — Rich Text Editor as Official Extension
**Added:** 2026-05-07  
**Resolved:** 2026-05-11  
**Decisions:**
- **No built-in editor (Q2):** The core app has no editor widget. All content creation and viewing is delegated to registered editor extensions. The GUI shows a “+” picker; clicking it reveals a dropdown of installed format handlers (Text, Image, Video, Recording, …). If no extension is registered for a format, that option is greyed out. Official extensions are pre-installed and can be replaced by user-installed ones. `[D-05]` `[LOG 05-07]`
- **Font size (Q4):** System font size is the global default for all app UI. Each extension may expose its own settings panel (managed by the extension provider). If that panel includes a font size control, it overrides the system setting for that extension’s content area only. The core app does not control per-note font sizing. `[LOG 05-07]`
- **Rich text format (Q1):** The official text extension uses `QTextEdit` in rich mode (PySide6, LGPL). No additional dependencies. Output format: `text/html` (Qt HTML subset) via `toHtml()`, with `toMarkdown()` available. Intentionally kept basic — bold, italic, underline, alignment, bullet lists, font size via the extension's own toolbar. No tables, no custom block types, no slash commands. The limited feature set is deliberate: it leaves clear headroom for third-party extension authors to offer richer editors (e.g., a WebEngine-based TipTap extension). `[LOG 05-11]`

### D-05 — Extension System Architecture
**Added:** 2026-05-07  
**Resolved:** 2026-05-10  
**Decisions:**
- **Install / Uninstall:** App-managed via a dedicated “Add Extension” menu (VS Code-style). Users install extensions from a local file; uninstall from the same menu. No external marketplace required. `[LOG 05-10]`
- **Official extensions:** Pre-installed with the app and labeled with an “official” tag (visual badge, like VS Code). Users may replace any official extension with a user-installed one. `[LOG 05-10]`
- **MIME-type conflicts:** Forbidden — only one **active** extension may own a given MIME type at a time. Install is blocked if a conflict exists; the user must disable or uninstall the conflicting extension first, or choose to install the new extension in a **disabled** state. Re-activating a disabled extension that still conflicts with an active one is also blocked with the same error. Plugin IDs must be globally unique. `[LOG 05-10]`
- **Registry UI:** VS Code-style dedicated extension panel. Shows installed extensions, official badges, install-from-file button, and uninstall button. `[LOG 05-10]`
- **Layout terminology:** Left pane = **file list** (VS Code Explorer-style note browser); right pane = **file display window** (hosts the EditorProvider widget for the selected note). `[LOG 05-10]`

**Deferred (not blocking resolution):**
- **Manifest format:** Minimum fields implied (`plugin_id` (unique), `name`, `version`, `is_official`, `supported_mime_types`); full schema to be designed during Sprint 2 plugin system work.
- **Sandboxing:** Trust-level distinction between official and user-installed extensions to be designed during Sprint 2; current `PluginBase` allowlist + read-only copy model is the starting point.


### D-03 — Settings Dialog: Advanced / Future Fields
**Added:** 2026-05-05  
**Resolved:** 2026-05-07  
**Decision:**
- **Theme:** Applied immediately on selection (live preview); no OK/Apply required. `[LOG 05-07]`
- **Font size:** Applies to system UI only (note list labels, toolbar, menus). The note content editor widget uses its own sizing. Rich text formatting inside a note is deferred to the extension model (see D-04). `[LOG 05-07]`
- **Auto-sync interval:** Free numeric entry, minimum 5 seconds. User types a number; values below 5 are rejected with an inline validation message. `Off` (0) also accepted to disable background sync. `[LOG 05-07]`
- **Account login/logout:** Removed from Settings dialog entirely. Exposed as a dedicated menu action (e.g., `Account` menu or toolbar button). Settings dialog retains only non-account fields (data directory, encryption defaults, passphrase min length, theme, font size, plugin directory, sync server URL, auto-sync interval). `[LOG 05-07]`

### D-01 — OAuth PKCE Desktop Redirect Mechanism
**Added:** 2026-05-05  
**Resolved:** 2026-05-07  
**Decision:** **Option B — custom URI scheme (`astranotes://callback`).** The app ships with an installer; the installer registers the URI scheme with the OS. Google's consent screen opens in the system browser; the OS routes the redirect directly back to the app — no HTTP listener, no port-conflict risk, no inbound socket. Embedded WebViews (Option C) are prohibited by Google's OAuth policy. Loopback HTTP (Option A) is safe with PKCE but inferior once an installer is available. ADR-12 updated. `[LOG 05-07]`

### D-02 — System Tray Icon
**Added:** 2026-05-05  
**Resolved:** 2026-05-07  
**Decision:** Add system tray icon as Sprint 4 item (B-97, Medium priority). `QSystemTrayIcon` + `QMenu` with Show/Hide and Quit actions. Window close minimizes to tray rather than quitting. `[LOG 05-07]`
