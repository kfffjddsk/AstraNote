# Discussion List

**Purpose:** Open questions and unresolved items that need a decision before the affected sprint begins.  
At the start of each session, Astra reads this file and raises any items that are blocking upcoming work.  
Add an item here whenever the team decides to defer a decision, or by saying "add that to the discussion list."  
When an item is resolved, mark it **Resolved** with a brief note and the date — do not delete it.

---

## Open Items

*(No open items.)*

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
