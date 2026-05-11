# Discussion List

**Purpose:** Open questions and unresolved items that need a decision before the affected sprint begins.  
At the start of each session, Astra reads this file and raises any items that are blocking upcoming work.  
Add an item here whenever the team decides to defer a decision, or by saying "add that to the discussion list."  
When an item is resolved, mark it **Resolved** with a brief note and the date — do not delete it.

---

## Open Items

### D-06 — CLI Startup: Store Factory and ConfigStore Integration
**Added:** 2026-05-11  
**Blocking:** Sprint 1 — must be resolved before any CLI command implementation begins  
**Gap:** Two separate gaps converge on the same startup moment.

- **T1 — Store factory missing:** The design describes `NoteStore` (JSON) and `DatabaseStore` (SQLAlchemy) as separate classes but has no `get_store()` function, `StoreFactory`, or Click group callback to choose between them at runtime. The CLI must check whether `notes.db` exists (post-`migrate`) or only `notes.json` exists (pre-`migrate`) and instantiate the correct class. No interaction diagram shows this decision point. `[BL B-48]`
- **U5 — ConfigStore has no startup integration point:** `ConfigStore` appears in §3.2 but in no interaction diagram. It must be read before the store is selected (so that `data_dir` can come from config when `--data-dir` is not supplied), but its load order relative to store selection and plugin loading is undesigned.

**Decision needed:** Confirm startup sequence — (1) parse `--data-dir` CLI option; (2) `ConfigStore.load()`; (3) store selection (`notes.db` present → `DatabaseStore`, else `NoteStore`); (4) plugin loading. Assign responsibility to a named function or Click group callback in `src/cli.py`. `[LOG 05-11]`

**Research direction:** VS Code defers extension activation until the extension's declared `activationEvents` are triggered — no extension is loaded at startup unless it subscribes to `onStartupFinished` or a matching event. Applying this model to step (4): `PluginRegistry` loads plugin manifests eagerly (to validate IDs and MIME-type ownership) but does not import or instantiate plugin code until the first relevant note is opened. This avoids slow-startup risk as the plugin count grows. See VS Code Extension Activation Events docs.

---

### D-07 — `Note.title` Dual-Field State Machine
**Added:** 2026-05-11  
**Blocking:** Sprint 1 — affects every encrypted note read/write path  
**Gap (U1):** The `Note` dataclass carries both `title` (sometimes plaintext, sometimes the `"[Encrypted Note]"` sentinel) and `encrypted_title` (raw AES-256-GCM ciphertext). The class diagram in §3.1 shows both fields but does not specify the state machine: when is `title` authoritative? When is `encrypted_title`? When are both populated? The write path (what `NoteStore.add()` sets), the update path (which field changes), and the save path (which field is serialized) are all unspecified.

**Decision needed:** Formally define the state for each operation — create, load with correct key, load without key, update, save. Document in §3.1 and update the interaction diagrams in §4. `[LOG 05-11]`

---

### D-08 — Error Flows Missing from All Interaction Diagrams
**Added:** 2026-05-11  
**Blocking:** Sprint 1 — every interaction diagram is incomplete without error paths  
**Gap (U2):** All four diagrams in §4 show only the happy path. Missing alternate flows:
- `InvalidTag` (wrong passphrase) during get, update, delete of encrypted note
- `KeyError` / note not found on missing ID
- `OSError` (`ENOSPC` disk full) during `NoteStore.save()`
- Corrupt `notes.json` on `NoteStore.load()`

Without these, implementers must invent error behavior that may not match REQ R5.2–R5.3 (non-zero exit codes, module-identifying error messages). `[BL B-35]`

**Decision needed:** Add alternate-path branches to diagrams §4.1 and §4.2 at minimum, covering `InvalidTag` and missing-ID cases. The `OSError` and corrupt-JSON cases should be added to §4.5. `[LOG 05-11]`

---

### D-09 — `PluginRegistry`: Allowlist and Read-Only Copy Call Sites
**Added:** 2026-05-11  
**Blocking:** Sprint 1 plugin infrastructure  
**Gap (U3):** ADR-05 and §3.2 both require that plugins receive a `copy.deepcopy()` of note data (not the live object) and that only plugins in the `allowed_plugins` config key are loaded. Neither constraint appears in the `PluginRegistry` class diagram, and no interaction diagram shows where the deep-copy happens or where the allowlist check is enforced (at `register_plugin()` vs. the startup loader). The class diagram is therefore inconsistent with ADR-05. `[BL B-56, B-69]`

**Decision needed:** Update `PluginRegistry.call_hook()` to show the deep-copy step. Decide whether the allowlist check is inside `register_plugin()` or in the startup loader before calling it. Reflect in the class diagram and the §4.4 hook-dispatch diagram. `[LOG 05-11]`

**Research direction:** VS Code runs each extension in a separate **Extension Host** process, so a misbehaving extension cannot corrupt VS Code's memory. AstraNotes cannot afford a full separate process per plugin, but VS Code's *in-process* API surface design is directly applicable: VS Code exposes only a frozen, read-only `vscode` API object to each extension — extensions never receive a reference to internal state objects. This maps directly onto the `copy.deepcopy()` requirement: `call_hook()` should pass a frozen dataclass copy (or a `types.MappingProxyType` wrapper) rather than the live `Note` object, mirroring VS Code's "extensions never touch internals" contract. For the allowlist, VS Code validates the `publisher.extensionName` identifier against a trusted-publisher list at install time — applying the same pattern: the allowlist check belongs in `register_plugin()` at registration time, not at call time, so a disallowed plugin is never in the registry at all.

---

### D-10 — `BlobCodec` Call Site and Migration Sequence
**Added:** 2026-05-11  
**Blocking:** Sprint 2 — BlobCodec and `migrate` command implementation  
**Gap:**

- **U4 — BlobCodec has no designed call site:** `BlobCodec` is defined in §3.2 with `encode()`, `decode()`, `encrypt()`, `decrypt()` but appears in no interaction diagram. It is unclear whether `DatabaseStore`, `NoteStore`, or `cli.py` invokes it, and at which method boundary (`add`, `save`, `get`, `update`).
- **T2 — No migration sequence diagram:** The `migrate` command must convert Sprint 0 JSON storage (separate base64-encoded title and content fields) into the sandbox blob format (`[4B len][JSON header][raw payload]` → single AES-256-GCM encrypt). These formats are structurally incompatible; the design provides no conversion path, no per-encrypted-note passphrase prompt flow, and no error flow for notes that fail conversion. `[REQ R14.7]` `[BL B-48, B-72]`

**Decision needed:** (1) Determine which class owns BlobCodec calls and at which method. (2) Write a `migrate` sequence diagram covering: backup, schema creation, per-note conversion, passphrase prompts for encrypted notes, skip-on-mismatch behavior, and post-migration verification. `[LOG 05-11]`

---

### D-11 — Session Validation Integration Point and `ensure_store()` Replacement
**Added:** 2026-05-11  
**Blocking:** Sprint 2 (account/auth layer)  
**Gap:**

- **T3 — No session validation integration point:** Once accounts exist (Layer 2), every sync-related CLI command must call `AuthManager.verify_session()` before executing. No interaction diagram includes this step; there is no designed Click decorator, middleware, or group callback that enforces it. An expired session must block sync but must NOT block local CRUD — this conditional logic is undesigned. `[REQ R13.9]`
- **T4 — No replacement for `ensure_store()`:** The Sprint 0 `ensure_store()` cached a keyed `NoteStore` in `ctx.obj` after prompting for passphrase once per process. In the Layer 2 architecture, passphrase prompts must coexist with session-based auth (a logged-in user still encrypts notes with a passphrase, not their account password). The design never describes the replacement pattern for this context.

**Decision needed:** (1) Design a Click group callback or decorator that conditionally calls `AuthManager.verify_session()` (required for sync operations only). (2) Define the replacement for `ensure_store()` and document how passphrase caching works alongside the session model. Update §4.5. `[LOG 05-11]`

---

### D-12 — Extension Plugin Manifest Schema and Sandboxing Trust Model
**Added:** 2026-05-11  
**Blocking:** Sprint 4 — extension registry, install, and uninstall cannot be implemented without a defined manifest format  
**Gap:** D-05 explicitly deferred two items as "not blocking resolution":

- **Manifest format:** Minimum fields are implied (`plugin_id`, `name`, `version`, `is_official`, `supported_mime_types`). The full schema — file format (JSON/TOML), required vs. optional fields, version constraint syntax, entrypoint declaration, permissions list — has not been designed. Without it, the install-from-file flow and `PluginRegistry` cannot validate an extension bundle.
- **Sandboxing trust model:** D-05 noted "trust-level distinction between official and user-installed extensions to be designed during Sprint 2." What additional restrictions apply to user-installed extensions beyond the `PluginBase` allowlist + read-only copy model? Are there filesystem, network, or API restrictions? Does `EditorProvider` need a separate sandbox boundary from `PluginBase` hooks?

**Decision needed:** (1) Define the manifest file format and all required/optional fields. (2) Define in concrete terms what each trust tier (official vs. user-installed) can and cannot do. `[LOG 05-11]`

**Research direction:** VS Code's `package.json` extension manifest is the clearest available model:
- **Required fields to adopt:** `publisher` (maps to our `plugin_id` namespace), `name`, `version` (semver), `engines` (maps to our minimum AstraNotes version), `main` (entrypoint module path), `contributes` (maps to our `supported_mime_types`).
- **Trust tier model:** VS Code distinguishes *Marketplace-verified* (signed, publisher-verified) vs. *VSIX sideload* (user-installed from file). The practical enforcement is: sideloaded extensions show a persistent "not verified" badge and cannot access restricted APIs (e.g., proposed APIs). For AstraNotes: official extensions (pre-installed, `is_official: true`) are allowed to call the full `EditorProvider` + `PluginBase` API; user-installed extensions are restricted to `EditorProvider` only (no `PluginBase` hooks that can read all notes) until a future sandbox tier is designed.
- **Manifest format recommendation:** JSON (`plugin.json`) rather than TOML — simpler to validate with `jsonschema`, no extra dependency, consistent with `package.json` familiarity.

---

### D-13 — Desktop GUI Startup Sequence
**Added:** 2026-05-11  
**Blocking:** Sprint 4 — `DesktopGUI` implementation  
**Gap (T8):** The `DesktopGUI` class in §3.2 is well-specified for its widget and action responsibilities, but the startup interaction with core modules is completely undesigned:
- How does `DesktopGUI` instantiate `DatabaseStore` — passed in at construction or created internally?
- When is the `QDialog` passphrase prompt shown for encrypted notes — lazily on first access, or on app open?
- If both the CLI and the GUI are open simultaneously, SQLite WAL handles concurrent reads, but concurrent writes need a retry / lock-detection strategy. `[BL B-66]`
- What is the startup sequence on first launch when `notes.db` does not exist yet?

**Decision needed:** Write a startup sequence diagram for `DesktopGUI` covering: `QApplication` init → `DatabaseStore` creation → file list population → encrypted note passphrase prompt timing → concurrent-access handling. `[LOG 05-11]`

---

### D-14 — Sync Server Interaction Diagrams and Conflict Resolution
**Added:** 2026-05-11  
**Blocking:** Sprint 5 — sync server and sync-enabled desktop client  
**Gap:**

- **T5 — No sync server interaction diagram:** There is no sequence diagram showing: desktop app sync call → `AuthMiddleware` JWT validation → `SyncRouter.push/pull()` → `DatabaseStore` query → JSON response. This is the primary Sprint 5 data flow. `[BL B-86, B-88]`
- **T6 — No OAuth PKCE desktop flow diagram:** The PKCE callback sequence is undesigned — app opens system browser → user consents → Google redirects to `astranotes://callback?code=...` → OS routes to app → `AuthMiddleware.oauth_callback()` exchanges code → JWT issued → session token written to disk. The interactions between `AuthMiddleware`, the `authlib` client, and the session file are not sequenced. `[ADR-12]` `[D-01]`
- **T7 — No conflict resolution design:** `R16.3` states last-write-wins by `modified_at`, with both versions retained in a `note_conflicts` table for 30 days. There is no design for conflict detection (compare server vs. local `modified_at`), the pull-with-conflict flow, how `note_conflicts` is exposed to the user, or how the 30-day auto-delete is triggered. `[REQ R16.3]` `[BL B-86]`

**Decision needed:** Write sequence diagrams for (1) push/pull happy path, (2) OAuth PKCE login flow, and (3) pull-with-conflict scenario before Sprint 5 implementation begins. `[LOG 05-11]`

---

## Resolved Items

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
