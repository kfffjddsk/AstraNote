# Working Log — 2026-05-10

## Summary
Design discussion session: resolved D-05 (Extension System Architecture) and made partial progress on D-04 (Rich Text Editor as Official Extension). Updated `docs/design.md` to reflect new extension model decisions and VS Code-inspired UI layout terminology. No code written.

---

## What Changed

### `Copilot/discussion-list.md`
- **D-04** restructured: partial decisions (Q2 no built-in editor, Q4 font size) broken out clearly; Q1 (rich text format) remains the only open question; Q3 extracted to D-05.
- **D-05** fully resolved and moved to Resolved Items section. All five decisions recorded (install/uninstall mechanism, official badge, MIME conflict policy, registry UI, layout terminology).

### `docs/design.md`
- **EditorProvider ABC** fields updated: `plugin_id` (globally unique), `is_official`, `supported_mime_types` annotated with one-active-owner rule. Architecture note rewritten to reflect D-05 decisions.
- **DesktopGUI** methods renamed: `show_note_list()` → `show_file_list()`, `show_note()` → `show_file()`.
- **Layout description** updated: left pane = file list (VS Code Explorer-style); right pane = file display window.

---

## Key Decisions

### D-05 — Extension System Architecture (resolved 2026-05-10)
- **Install / Uninstall:** App-managed "Add Extension" menu; users install from local file; no external marketplace.
- **Official extensions:** Pre-installed, labeled with an official badge (VS Code-style); replaceable by user-installed extensions.
- **MIME-type conflicts: FORBIDDEN.** Only one active extension may own a given MIME type at a time. Install blocked on conflict — user must disable/uninstall the conflicting extension first, or install the new one as disabled. Re-activating a conflicted extension is also blocked.
- **Plugin IDs:** Globally unique; required field in extension manifest.
- **Registry UI:** VS Code-style dedicated extension panel (installed list, badges, install-from-file, uninstall).
- **Layout terminology:** Left pane = file list; right pane = file display window.
- **Deferred (non-blocking):** Full manifest schema and sandboxing model — to be designed during Sprint 2 plugin system work.

### D-04 — Rich Text Editor (partial, still open)
- No built-in editor in the core app (decided 2026-05-07).
- Font size controlled by extension's own settings panel, not the core app (decided 2026-05-07).
- **Q1 still open:** Rich text library and MIME format (`text/html` vs `text/markdown`) not yet chosen. Research needed before Sprint 4 locks the editor widget.

### GUI Layout Model
The app UI follows the VS Code three-panel model:
- Left panel: file list (note browser, sync-status indicator)
- Right panel: file display window (hosts the active EditorProvider widget)
- Scrollbar / sidebar pattern replaces the earlier "note scroll bar" terminology

---

## Tests Performed
None — documentation-only session.

---

## Follow-Up Actions
- **D-04 Q1:** Research open-source rich text editors compatible with PySide6 (e.g., `QTextEdit` rich mode, Quill/TipTap via `QWebEngineView`, ProseMirror). Confirm format choice before Sprint 4 begins.
- **D-05 deferred items:** Design full extension manifest schema and sandboxing model during Sprint 2 plugin system work.
- **Sprint Zero:** All B-01–B-23 implementation items remain unstarted. Highest development priority.
