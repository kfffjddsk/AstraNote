# GUI Architecture Discussion — Scratch File

> **Purpose:** Working scratch space to resolve the GUI architecture before updating any design documents.
> Delete or archive this file once decisions are recorded in design.md and traceability-metrics.md.

---

## What We Agreed Before This Discussion

| Item | Previous Decision | Status |
|------|------------------|--------|
| ADR-13 | Local web server + browser SPA (FastAPI serves Svelte SPA; `cli gui` opens browser) | **REVERTING** |
| Sprint 4 GUI surface | `personal_gui` — Svelte SPA on localhost | **UNDER DISCUSSION** |
| Sprint 5 GUI surface | `web_client` — browser SPA | **UNDER DISCUSSION** |
| Sync server | FastAPI; `POST /sync/push`, `GET /sync/pull` | Unchanged ✓ |
| ADR-11 (FastAPI for sync server) | Decided | Unchanged ✓ |
| ADR-12 (authlib + Google OIDC) | Decided | Unchanged ✓ |

**New direction stated by human team member:** Both GUI surfaces should be desktop apps, not browser-based. Framework selected: **PyQt / PySide6**.

---

## Decisions — RESOLVED ✓

### Q1 — Sprint 5 surface ✓
**Decision: Option C.** Browser UI dropped entirely. There is one app. Sprint 4 builds the desktop app (local CRUD). Sprint 5 adds the FastAPI sync server backend and wires sync into the same desktop app (sync button, login prompt if no session). No "web client" concept; no browser surface.

### Q2 — Component sharing ✓
**Decision: Option C (follows from Q1).** One PySide6 codebase throughout. Sprint 4 and Sprint 5 share Python core modules (NoteStore, EncryptionEngine, PluginRegistry) and PySide6 widgets directly. No cross-language component sharing needed.

### Q3 — Sync server role ✓
**Decision: FastAPI sync server is backend-only.** User clicks a sync button in the desktop app. The app handles the OAuth/JWT flow transparently — it may prompt for login if there is no valid session token, then proceeds automatically. No browser-facing endpoints; no static file serving. `StaticFiles` FastAPI mount removed.

### Q4 — PySide6 vs PyQt6 ✓
**Decision: PySide6.** No performance or usability difference at this scope (both are Qt6 wrappers with identical APIs). PySide6 is LGPL, safer for a course project that may be shared or published.

### Q5 — `cli gui` startup ✓
**Decision: confirmed.**
```
astranotes gui
```
→ `QApplication` starts  
→ Main window opens  
→ Blocks until user closes window  
→ Process exits  
No localhost server, no browser, no port management.

### Q6 — Desktop UI layout ✓
**Decision: two-pane layout confirmed, with standard desktop app features added.**
- Left pane: scrollable note list (title, format badge, lock icon, sync-status dot)
- Right pane: title field + content area + toolbar (New / Save / Delete / Sync buttons)
- Passphrase: `QDialog` modal, auto-focused password field, closes on Escape
- Sync button triggers push/pull; shows login dialog if no valid session
- **Settings:** `QDialog` (or dedicated settings panel) for data directory, account details, sync server URL, theme, etc.
- Standard menu bar: File / Edit / View / Help
- System tray icon (optional, Sprint 4 stretch goal)

---

---

## Files to Update (ready to execute)

### design.md
- §1 scope: "browser-based web client" → "PySide6 desktop client (Sprint 4: local CRUD; Sprint 5: sync added)"
- §2 package diagram: `web_client` package **removed**; `personal_gui` redescribed as "PySide6 desktop app"
- `PersonalGUI` class block: add `MainWindow`, `NoteListPanel`, `NoteEditorPanel`, `PassphraseDialog`, `SettingsDialog`; startup = `QApplication`; framework = PySide6
- ADR-13: rewrite — PySide6 desktop app; `QApplication` startup; no browser; settings dialog; shared widget library Sprint 4→5

### traceability-metrics.md
- FR-109: gap note updated (PySide6; `QApplication` startup)
- FR-110–FR-112: `web_client` → desktop client; "browser SPA" → "PySide6 desktop app"
- FR-113: rewrite — sync polling interval, not WebSocket/SSE (desktop app polls on sync button click)
- FR-114: rewrite — "offline mode" is local SQLite (already Layer 1); IndexedDB reference **removed**
- FR-115: "Svelte" → "PySide6 shared widget library"
- R11-B section heading: "Server Web Client" → "Sync-Enabled Desktop Client (Sprint 5)"

### user-stories.md
- US-14: remove "browser SPA, Sprint 5B" bullet; replace with PySide6 sync-enabled desktop description

### planning/requirements.md
- R11.7–R11.12: audit for "browser SPA" / "web client" language; replace with desktop client

### planning/backlog.md
- B-89 (`web_client` SPA): redescribe as PySide6 sync-enabled desktop
- B-90 (WebSocket/SSE): rewrite — sync on button click, no persistent connection
- B-91 (IndexedDB): **DROP** — offline is Layer 1 (local SQLite always on); IndexedDB is browser-only and redundant
- FR-114: **DROPPED** from traceability matrix; covered by FR-76 (R12.1) which is updated to explicitly state offline CRUD behavior

### planning/sprint-zero-plan.md
- Sprint 5 items: remove browser/IndexedDB references; update to PySide6 desktop sync UI

### docs/prd.md
- §3.x web client references: update to PySide6 desktop
