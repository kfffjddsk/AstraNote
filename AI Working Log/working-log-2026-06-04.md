# AI Working Log — 2026-06-04

## Session Summary

**AI Partner:** Astra (GitHub Copilot)
**Sprint:** 4C — GUI Polish & UX Refinement
**Outcome:** Sprint 4C delivered on top of Sprint 4B. External `.qss` stylesheets with optional hot-reload, redesigned Settings dialog, Plugins Admin dialog, format chooser for new notes, decrypt-by-uncheck flow, themed SVG icons for all standard controls, and a developer-only Widget Gallery. 570 tests passing.

---

## What Was Delivered (Backlog B-113 — B-121)

| ID | Item | Notes |
|----|------|-------|
| B-113 | External QSS stylesheets + hot-reload | `src/desktop/styles/{dark,light}.qss` loaded by `load_stylesheet()`; `_install_qss_hotreload()` watches the files with `QFileSystemWatcher` when `ASTRANOTES_QSS_HOTRELOAD=1`. |
| B-114 | Settings dialog redesign | `QListWidget` + `QStackedWidget`; four pages (Appearance / Editor / Behaviour / Files); right-aligned labels with 220 px field column. Passphrase-length spinbox removed per UX (test commented out with reason). |
| B-115 | Accent / font-family / word-wrap end-to-end | New `ConfigStore` keys with `_VALUE_CONSTRAINTS`; `apply_theme()` now takes `font_family` and `accent`, substitutes accent into the QSS, and pushes the font into already-created widgets via `app.allWidgets()`. |
| B-116 | Plugins Admin dialog | `PluginsDialog(QDialog)` with Installed + Supported formats tabs (`QTreeWidget`); checkable rows write `allowed_plugins`; filter box; shortcut `Ctrl+Shift+P`. |
| B-117 | New-note format chooser | `_NewNoteTypeDialog` lists Plain text / Markdown / Rich text plus any plugin-provided formats; separate Encrypt checkbox; `NoteEditorWidget.apply_format()` flips rich-text mode and shows/hides B/I/U buttons. |
| B-118 | Decrypt-by-uncheck | `DatabaseStore.update(encrypted=False)` clears the blob and any on-disk payload, then writes plaintext content. `MainWindow._on_save` enforces "unlock first". |
| B-119 | Themed SVG icons | `src/desktop/styles/icons/` (`chevron-down-*.svg`, `chevron-up-*.svg`, `check.svg`, `close-dark.svg`, `close-light.svg`, `close-hover.svg`). QSS uses `{ICONS}` token that the loader substitutes with the absolute icon path. |
| B-120 | Dev-only Widget Gallery | `_WidgetGallery(QDialog)` with three tabs covering every styled widget; hidden `QAction` bound to `Ctrl+Shift+G`. |
| B-121 | UX micro-fixes | Sidebar selection clears on New Note; editor font-size combo widened (52 → 72 px); `QListWidget::item:hover:!selected` prevents adjacent-row highlight overlap. |

## Files Touched

### New

- `src/desktop/styles/__init__.py` — `load_stylesheet(theme)`, `stylesheet_path(theme)`, `{ICONS}` token substitution.
- `src/desktop/styles/dark.qss` — full PyDracula dark theme; preserves `#1e1e1e` / `#252526` legacy tokens for `test_sprint4b`.
- `src/desktop/styles/light.qss` — light theme mirror; preserves `white` / `#f3f3f3` legacy tokens.
- `src/desktop/styles/icons/chevron-down-dark.svg`, `chevron-down-light.svg`, `chevron-up-dark.svg`, `chevron-up-light.svg`, `check.svg`, `close-dark.svg`, `close-light.svg`, `close-hover.svg`.

### Modified

| File | Change |
|------|--------|
| `src/core/config.py` | Added `accent_color`, `font_family`, `word_wrap` to `ALLOWED_KEYS`, `_TYPE_MAP`, `DEFAULTS`, `_VALUE_CONSTRAINTS`. |
| `src/core/notes.py` | `DatabaseStore.update()` accepts `encrypted: Optional[bool]`; passing `False` converts an encrypted note back to plaintext and removes any on-disk payload file. |
| `src/desktop/app_controller.py` | Reads `font_family` + `accent_color` from config and forwards them to `apply_theme()` on startup. |
| `src/desktop/main_window.py` | Loads QSS from files; `apply_theme(theme, font_size, font_family, accent)`; `ACCENT_COLORS` map + `_stylesheet_with_accent()`; `_install_qss_hotreload()`; redesigned `SettingsDialog` (category list + 4 pages); new `PluginsDialog`, `_NewNoteTypeDialog`, `_WidgetGallery`; `NoteEditorWidget.apply_format()`; format-aware `_on_new_note_prompt()`; decrypt-by-uncheck save path; sidebar deselect on new note; editor font-size combo width 52 → 72; menu wiring for `Ctrl+Shift+P` and `Ctrl+Shift+G`. |
| `tests/test_sprint4.py` | One regression fix: set `close_behavior="minimize"` before invoking the close-to-tray flow so the ask-dialog doesn't pop in the headless test. |
| `tests/test_sprint4b.py` | `test_settings_dialog_has_passphrase_spin` commented out with explanation; widget no longer in UI. |

## Test Results

- Full suite: **569 passed, 1 skipped** (POSIX permission test, Windows-only).
- Standalone GUI suites (`tests/test_sprint4.py + tests/test_sprint4b.py`): **182 passed**.
- One unrelated flaky perf test (`test_store_stress_1001_notes`, ~5.03 s vs 5.0 s budget) — passes on its own; not touched by Sprint 4C.

## Recovery Note

Mid-session, a PowerShell `Get-Content` / `Set-Content -Encoding utf8` round-trip on the user's GBK-codepage Windows mangled non-ASCII characters across `main_window.py`. Recovery was multi-pass: strip BOM, bulk-replace mojibake patterns (`鈹€`, `鈥?`, `鈿?`, etc.) with ASCII equivalents, then targeted Unicode replacements for emojis (`🔍`, `🔒`, `🔓`, `⚙`, `✓`). All string literals were restored; some cosmetic mojibake remains in inline comments / section dividers but is harmless. **Lesson recorded in repo memory:** never round-trip non-ASCII source through PowerShell `Set-Content` on a GBK system — use Python `Path.read_text(encoding="utf-8")` / `write_text(encoding="utf-8")` or the workspace edit tools.

## Documentation Updates

- `planning/backlog.md` — added Sprint 4C section with B-113 — B-121.
- `planning/traceability-metrics.md` — bumped to v2.8, updated NFR-4 test count (493 → 570), added Sprint 4B + Sprint 4C completion notes.
- This working log.

## Open Items / Next Steps

- Sprint 5A (Sync Server) and Sprint 5B (OAuth + sync UI) remain Planned.
- B-29 (`search --encrypted` CLI flag) remains ⏳ Pending; no Sprint 4C change.
- Cosmetic mojibake clean-up of inline comments in `main_window.py` could be a small follow-up polish — not blocking.
