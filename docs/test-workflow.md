# Test Workflow

> **Updated 2026-06-08 (Sprint 5D + UI coverage complete):** 715 tests pass, 1 skipped (microphone hardware). Coverage: 66% overall; core modules ≥ 90% branch; `plugins_dialog.py` 87%; `main_window.py` 61%.

## Testing Strategy

Four complementary layers:

| Layer | Files | Count | What it covers |
|-------|-------|-------|----------------|
| **BDD (Gherkin)** | `tests/steps/test_steps.py` + `tests/features/*.feature` | 30 | CLI behaviors end-to-end via Click runner |
| **Unit** | `tests/test_core.py` | 41 | Note, DatabaseStore, EncryptionEngine, BlobCodec, injection hardening |
| **Sprint integration** | `tests/test_sprint1.py` – `tests/test_sprint5b.py` | 474 | Per-sprint feature tests, auth, server, desktop GUI, sync UI |
| **Desktop UI** | `tests/test_sprint4b.py`, `tests/test_sprint5_ui.py` | 121 | PySide6 widget behavior, selection guards, plugin dialogs |

**Total:** 715 passing, 1 skipped (716 collected).

---

## Test Counts by File

| File | Tests | Sprint / Focus |
|------|-------|----------------|
| `tests/steps/test_steps.py` | 30 | BDD — all 8 Gherkin feature files |
| `tests/test_core.py` | 41 | Core unit tests + injection hardening |
| `tests/test_sprint1.py` | 83 | CLI, WAL/retry, plugin integration, Alembic |
| `tests/test_sprint2.py` | 106 | AccountStore, auth, session, hybrid storage |
| `tests/test_sprint3.py` | 126 | Plugin hardening, audit, config, search/export, reencrypt |
| `tests/test_sprint4.py` | 109 | AppController, MainWindow, PassphraseDialog, tray, idle-lock, plugin manifest |
| `tests/test_sprint4b.py` | 77 | GUI completeness: tab widget, search bar, sync menu, settings dialog |
| `tests/test_sprint5a.py` | 40 | Sync server MVP: auth, push, pull, JWT, account isolation |
| `tests/test_sprint5a2.py` | 22 | Server hardening: HTTPS enforcement, rate limiting, Postgres DSN, concurrency |
| `tests/test_sprint5b.py` | 38 | Desktop sync UI: SyncWorker, MergeWindow, OAuth callback, MainWindow sync actions |
| `tests/test_sprint5_ui.py` | 44 | Sprint 5 UI coverage: selection guard, revert, plugin-missing, PluginsDialog |
| **Total** | **716** | **715 pass + 1 skipped** |

---

## BDD Scenario Coverage (30 scenarios, 8 feature files)

| Feature file | Scenarios | Key assertions |
|-------------|-----------|----------------|
| `add_notes.feature` | 3 | passphrase prompt, invalid input rejection |
| `get_notes.feature` | 4 | correct/wrong passphrase, not-found error |
| `list_notes.feature` | 2 | encrypted content hidden, empty-list message |
| `update_notes.feature` | 4 | content verified, wrong passphrase preserves original |
| `delete_notes.feature` | 4 | note removed/preserved, wrong passphrase blocked |
| `search_notes.feature` | 7 | plain match, alias match, encrypted excluded by default |
| `reencrypt_note.feature` | 2 | passphrase rotation roundtrip, wrong-passphrase rejection |
| `audit_log.feature` | 4 | audit entries for add/delete/login/export |

---

## Encryption Rules (validated by BDD)

- add, get, update, delete encrypted → passphrase prompt.
- list → no prompt; shows `[Encrypted Note]` or alias.
- unencrypted operations → no prompt.

---

## Recommended Commands

```powershell
# Full suite
python -m pytest -q

# BDD scenarios only
python -m pytest tests/steps/test_steps.py -v

# Desktop UI tests only (requires offscreen display)
python -m pytest tests/test_sprint4b.py tests/test_sprint5_ui.py -v

# With coverage
python -m pytest --cov=src --cov-report=term-missing -q

# Stress test (1001 notes)
python -m pytest -q -m stress

# Run the project test script
python test_all.py
```

---

## Coverage Targets

| Module group | Coverage | Branch |
|---|---|---|
| `src/core/` | ≥ 90% | ≥ 88% |
| `src/server/` | ≥ 85% | ≥ 82% |
| `src/desktop/plugins_dialog.py` | 87% | — |
| `src/desktop/main_window.py` | 61% | — |
| Overall `src/` | 66% | — |

The desktop UI layer (PySide6 widgets) has the most coverage headroom. `tests/test_sprint5_ui.py` specifically targets the uncovered paths in `main_window.py` and `plugins_dialog.py` identified in the Sprint 5D coverage report.

---

## Sprint Test Plan History

Sprint plans and gate-pass evidence are in `docs/test-execution-evidence.md`. Each sprint section documents: result summary, test breakdown, new source files, modified source files, and key design decisions validated by the new tests.

| Sprint | Gate evidence section |
|--------|----------------------|
| Sprint 0 | Sprint Zero Re-implementation (2026-05-15) |
| Sprint 1 | Sprint 1 Evidence |
| Sprint 2 | Sprint 2 Evidence |
| Sprint 3 | Sprint 3 Evidence |
| Sprint 4 | Sprint 4 Evidence |
| Sprint 4B/4C | Sprint 4B Evidence |
| Sprint 5A.1 | Sprint 5A.1 Evidence |
| Sprint 5A.2 | Sprint 5A.2 Evidence |
| Sprint 5B | Sprint 5B Evidence |
| Sprint 5D + UI | Sprint 5D / UI Coverage Evidence |
