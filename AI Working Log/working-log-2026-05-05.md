# Working Log — 2026-05-05

## Summary
Clean-up session following the 2026-05-04 PySide6 architecture document update.  
Resolved two documentation conflicts, expanded the Settings dialog specification, and established the Discussion List process.

No code changed. All 33 tests continue to pass.

---

## What Changed

### Conflict Fixes
| Location | Fix |
|----------|-----|
| `planning/user-stories.md` US-14 source | `R11.7–R11.12` → `R11.7–R11.10, R11.12` (R11.11 was dropped last session) |
| `planning/requirements.md` R9.3 | Added `theme`, `font_size`, `sync_server_url`, `sync_auto_interval` to known-keys list |
| `planning/user-stories.md` US-7 | Same known-keys list updated |
| `docs/prd.md` §3.9 | Same known-keys list updated |

### Settings Dialog Specified (`docs/design.md` §3.2)
`DesktopGUI.show_settings()` expanded from a vague note to a concrete tabbed `QDialog`:
- **General tab** — data directory, default encryption, min passphrase length, theme (light/dark), font size
- **Account tab** *(Sprint 5)* — username display, login/logout button, delete-account button
- **Sync tab** *(Sprint 5)* — sync server URL, auto-sync interval (Off / 5 min / 15 min / 1 hr), last-synced timestamp

### Discussion List Process Established
- **New file:** `Copilot/discussion-list.md` — tracks open questions and deferred decisions; reviewed at the start of every session.
- **Working Agreement** updated with Discussion List section (process, trigger phrase "add that to the discussion list", resolution protocol).
- **Definition of Done** updated: a session is not fully done until new blocking items are on the discussion list.

Three items logged today: D-01 (OAuth PKCE redirect mechanism, Sprint 5B), D-02 (system tray icon, Sprint 4 scope), D-03 (Settings UX behaviour, Sprint 4+5).

---

## Key Decisions
- `sync_auto_interval` (int, seconds; 0 = disabled) is the config key for optional background sync, resolving the R9.3 / R11.10 gap.
- OAuth PKCE redirect question deferred to discussion list (D-01) — no decision needed until Sprint 5B design phase.
- Settings dialog fields are now specified enough to begin Sprint 4 implementation.

---

## Follow-Up Actions (Discussion List)
- D-01: Decide OAuth PKCE redirect mechanism before Sprint 5B design phase
- D-02: Decide system tray icon scope before Sprint 4 kickoff
- D-03: Decide Settings UX behaviour (apply-on-change vs OK, font scope, login placement) before Sprint 4 GUI implementation
