# Working Log — 2026-05-11

## Summary
Design maintenance and decision session. Fixed stale content in `docs/design.md` left over from Sprint 0 code removal. Identified and documented all open design gaps as discussion items D-06 through D-14. Added VS Code extension system research directions to plugin-related items. Fully resolved D-06 (CLI startup sequence + ConfigStore location). Performed DoD cross-check and fixed conflicts in `requirements.md`, `prd.md`, and `docs/design.md`. No code written.

---

## What Changed

### `docs/design.md`
- **§1** — Replaced stale "Two design layers (Sprint Zero / Planned)" paragraph with a "Design status (updated 2026-05-11)" note: Sprint 0 removed, Sprint 1 starts clean, all designs are planned, gaps tracked in discussion list.
- **§4.5** — Corrected startup sequence diagram: `ConfigStore` now loads from fixed OS-standard path (not `data_dir/config.json`). Corrected startup order: ConfigStore → resolve `data_dir` (with `--data-dir` override) → store selection → plugin manifest loading (eager) + activation (lazy). `--help`/`--version` short-circuit noted.
- **§3.2 ConfigStore** — `config_path: Path` annotated with OS-standard path and "NOT inside data_dir" note.
- **§7 traceability preamble** — Updated to state Sprint 0 source was deleted; all entries are unimplemented; paths are Sprint 1+ targets.
- **§8 directory structure** — Replaced stale Sprint Zero target tree (deleted `src/`, `tests/`, etc.) with actual current workspace layout.
- **§9.2 T1** — Marked resolved, referencing §4.5 and D-06.
- **§9.3 U5** — Marked resolved, referencing §4.5 and D-06.

### `planning/requirements.md`
- **R9.1** — Updated from `<data-dir>/config.json` to fixed OS-standard path (`%APPDATA%\astranotes\config.json` / `~/.config/astranotes/config.json`). Noted `data_dir` is a key inside config, and `--data-dir` overrides it at runtime. `[D-06]`

### `docs/prd.md`
- **R9.1 reference** — Updated "Settings stored in `<data-dir>/config.json`" to reflect fixed OS-standard path. `[D-06]`

### `Copilot/discussion-list.md`
- Added open items **D-06 through D-14** covering all design gaps from `docs/design.md` §9 (T1–T8, U1–U5, extension manifest).
- Added **VS Code extension system research directions** to D-06, D-09, D-12.
- **D-06 resolved** and moved to Resolved Items section.

---

## Key Decisions

### D-06 — CLI Startup: Store Factory and ConfigStore Integration (resolved 2026-05-11)
- **ConfigStore location:** Fixed OS-standard path (`%APPDATA%\astranotes\config.json` on Windows; `~/.config/astranotes/config.json` on Linux/macOS). Not inside `data_dir`. Moving `--data-dir` does not move the config file.
- **`data_dir` resolution:** Read from `config["data_dir"]`; `--data-dir` CLI flag overrides at runtime.
- **Startup order:** (1) `ConfigStore.load()` from OS path; (2) resolve `data_dir`; (3) store selection (`notes.db` → `DatabaseStore`, else `NoteStore`); (4) `PluginRegistry.load_manifests()` eagerly, activation deferred to first relevant note open (VS Code activation-events model).
- **Code location:** Single Click group callback in `src/cli.py`. `--help`/`--version` short-circuit before it.

---

## DoD Cross-Check Performed
- Checked `requirements.md`, `prd.md`, `docs/design.md`, `planning/backlog.md`, `Copilot/discussion-list.md` for consistency after D-06 resolution.
- Found and fixed: R9.1 conflict in `requirements.md` and `prd.md` (both said `<data-dir>/config.json`; corrected to OS-standard path per D-06).
- Found and fixed: `§3.2 ConfigStore.config_path` had no location annotation; added.
- No conflicts found in `backlog.md`.

---

## Tests Performed
No code written; no tests applicable.

---

## Follow-Up Actions
- D-07 through D-14 remain open — to be resolved in order before their blocking sprints begin.
- Next priority: D-07 (`Note.title` dual-field state machine) — blocks Sprint 1.
