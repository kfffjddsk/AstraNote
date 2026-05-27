# Test Workflow

## Testing Strategy

BDD-first approach:

- **BDD** (`tests/steps/test_steps.py`) — 17 Gherkin scenarios for all CLI CRUD behavior.
- **Unit** (`tests/test_core.py`) — 39 tests for core modules + bounded stress test.
- **CLI integration** (`tests/test_sprint1.py`, `tests/test_sprint2.py`) — Sprint 1 and Sprint 2 CLI, auth, and storage tests.

All BDD tests are Gherkin features in `tests/features/`. The full suite (Sprint 2 complete) totals 246 tests; 1 skipped on Windows (POSIX permission test).

## BDD Scenario Coverage

| Feature | Scenarios | Key assertions |
|---------|-----------|----------------|
| Add Notes | 3 | passphrase prompt behavior, invalid input rejection, empty store after invalid |
| Get Notes | 4 | correct/wrong passphrase, no-prompt for unencrypted, not-found error |
| List Notes | 2 | encrypted content hidden, no passphrase prompt, empty-list message |
| Update Notes | 4 | content verified after update, wrong passphrase preserves original, no-prompt for unencrypted |
| Delete Notes | 4 | note removed/preserved, wrong passphrase blocked, no-prompt for unencrypted |

## Encryption Rules

Passphrase required for encrypted note actions:
- add, get, update, delete encrypted → prompt.
- list → no prompt, shows `[Encrypted Note]`.
- unencrypted operations → no prompt.

## Stress Test

Bounded 1001-note test in temp workspace. Validates add, reload, delete without corruption. Marked `stress` for selective runs.

## Recommended Commands

Run the full automated suite:

```powershell
python -m pytest -q
```

Run BDD tests only:

```powershell
python -m pytest tests/steps/test_steps.py -v
```

Run the stress test only:

```powershell
python -m pytest -q -m stress
```

Run the comprehensive project script:

```powershell
python test_all.py
```

---

## Sprint 1 Test Plan *(Historical — Sprint 1 complete)*

> Sprint 1 is done. All items below were completed. See `docs/test-execution-evidence.md` for the Sprint 1 gate pass results.

Sprint 1 items (B-31–B-40, B-83) required the following new test coverage.

### New BDD Scenarios Required

| Backlog Item | Feature File | Scenario Description |
|--------------|-------------|----------------------|
| B-31 | `add_notes.feature` | Add three notes, delete the middle one, add a fourth — verify IDs do not collide |
| B-32 | `add_notes.feature` | Add encrypted note with mismatched passphrase confirmation → error, no note stored |
| B-32 | `add_notes.feature` | Add encrypted note with passphrase shorter than 8 chars → rejected |
| B-33 | `delete_notes.feature` | Delete an unencrypted note → verify encrypted co-stored note is still retrievable |
| B-33 | `update_notes.feature` | Update an unencrypted note → verify encrypted co-stored note content unchanged |
| ~~B-35~~ | ~~*(new)*~~ ~~`persistence.feature`~~ | ~~Corrupt `notes.json` on load → backup created at `notes.json.bak`, empty store starts, warning shown~~ — **DROPPED** `[D-10]` (SQLite ACID replaces JSON corruption; B-35 dropped) |
| B-36 | *(new)* `cli_validation.feature` | `--data-dir` pointing to an existing file → error with actionable message |
| B-36 | `cli_validation.feature` | `--data-dir` pointing to a non-writable path → error with actionable message |
| B-39 | `cli_validation.feature` | Simulate write failure on save → actionable error message, no crash |

### New Unit Tests Required

| Backlog Item | Test Class | Test Description |
|--------------|-----------|-----------------|
| B-31 | `TestDatabaseStore` *(renamed from `TestNoteStore` — D-10)* | `test_id_gap_safe_after_deletion` — add 3 notes, delete note 2, add a 4th, assert no ID collision |
| B-34 | `TestDatabaseStore` (via CLI) | `test_short_passphrase_rejected` — assert ValueError or CLI error for passphrase < 8 chars |
| B-83 | `TestPluginBase` *(new class)* | `test_plugin_registration` — register a plugin, assert it appears in registry |
| B-83 | `TestPluginBase` | `test_duplicate_plugin_skipped` — register same plugin twice, assert warning, only one entry |
| B-83 | `TestPluginBase` | `test_hook_dispatch` — register hook, trigger it, assert callback invoked |
| B-83 | `TestPluginBase` | `test_hook_crash_does_not_kill_operation` — register hook that raises, assert exception caught |

### Sprint 1 Exit Criteria for Tests
- All items above written and passing before corresponding backlog item is marked Done
- Total test count grows from 33 (baseline) to at least 46 (33 + 8 new BDD + 5 new unit) — *(B-35 dropped; 9→8 BDD scenarios)* `[D-10]`
- All 33 existing Sprint Zero tests continue to pass (no regression)
- `pytest -v` reports 0 failures
