# Working Log — 2026-05-19

## Summary
Environment setup and comprehensive test-quality session. Created `.venv`, investigated SQLite GUI tooling, hardened the `conftest.py` fixture for full per-test database isolation, ran branch-coverage audit across all core modules, and closed every reachable coverage gap. 125 tests passing. Core modules at 99% branch coverage (one structurally unreachable branch remains). All related documentation updated.

---

## What Changed

### `tests/conftest.py`
- **`tmp_store` fixture refactored** — was `DatabaseStore(Path(".test_db"))` (all tests shared one DB file, causing state leakage). Now creates a per-test sub-directory under `.test_db/<sanitised_test_name>/` using `request.node.name`.
- Added `import re` and `import shutil`.
- Strategy: directory is `shutil.rmtree`'d before the test starts (no stale data from previous runs), but left on disk after the run for GUI inspection.
- Updated module docstring to explain the isolation strategy.

### `tests/test_core.py`
Added **10 new unit tests** covering previously unreachable branches identified by `pytest-cov --cov-branch`:

| Test | Gap closed |
|---|---|
| `test_note_update_content_only_refreshes_modified_at` | `Note.update(content=…)` with `title=None` — `self.content = content` line |
| `test_store_update_content_only_leaves_title_unchanged` | `store.update(id, content=…)` with `title=None` — branch `317→319` |
| `test_store_update_encrypted_note_ignores_plaintext_content` | passing `content=` to encrypted row is silently ignored — branch `319→321` |
| `test_store_update_encrypted_note_blob` | `row.encrypted_blob = blob` write path — line 322 |
| `test_store_list_returns_account_notes_for_matching_account_id` | `account_notes.append(note)` — line 374, account routing in `list()` [D-11] |
| `test_encryption_engine_public_derive_key_matches_private` | public `derive_key()` method — security.py line 76 |
| `test_keymanager_rejects_empty_passphrase` | `KeyManager("")` empty-passphrase guard — security.py line 102 |
| `test_keymanager_rejects_whitespace_only_passphrase` | `KeyManager("   ")` whitespace-passphrase guard — security.py line 102 |
| `test_blobcodec_decode_rejects_blob_shorter_than_prefix` | blob < 4 bytes → `ValueError("too short")` — blob_codec.py line 55 |
| `test_blobcodec_decode_rejects_truncated_body` | header claims N bytes but body is shorter → `ValueError("truncated")` — blob_codec.py line 66 |

- Added `import os` and `from src.core.notes import _NoteRow` to imports.
- Updated module docstring: "23 tests" → "39 unit tests + 1 stress" with full section breakdown.

### `tests/test_sprint1.py`
Added **1 new unit test**:

| Test | Gap closed |
|---|---|
| `test_discover_plugins_skips_file_when_spec_is_none` | `spec_from_file_location` returns `None` → `logger.warning` + `continue` — plugin_base.py lines 111–112 |

- Updated §3 description in module docstring to mention spec=None branch.

### `docs/test-execution-evidence.md`
- Filled in the **Sprint 1 Evidence** section (was placeholder "To be filled").
- Recorded 125 PASSED / 0 FAILED result with full per-file breakdown.
- Added **Branch Coverage** table showing 99% on core modules.
- Added **Test Isolation** section explaining the new `conftest.py` strategy.
- Updated **Known Test Gaps** to reflect what has been closed vs. what remains.

### `planning/traceability-metrics.md`
- Bumped version from 2.1 → 2.2, date to 2026-05-19.
- Updated **Status Definitions** — removed "no items qualify" notes (code now exists).
- Added `Sprint1:S1` abbreviation for `tests/test_sprint1.py`.
- Updated `Unit:stress` test name to match current `test_store_stress_1001_notes`.
- **FR-4** status: `Weakly Traced` → `Fully Traced` — all `update()` branches now covered.
- **FR-9** status: `Partially Traced` → `Fully Traced` — `_validate_data_dir` tested in Sprint 1 §5.

---

## Branch Coverage — Final State

```
Name                      Stmts   Miss Branch BrPart  Cover   Missing
---------------------------------------------------------------------
src\core\__init__.py          0      0      0      0   100%
src\core\blob_codec.py       35      0      8      0   100%
src\core\notes.py           151      0     42      1    99%   62->exit (unreachable)
src\core\plugin_base.py      63      0     16      0   100%
src\core\security.py         45      0      6      0   100%
---------------------------------------------------------------------
TOTAL                       294      0     72      1    99%
```

### Why `notes.py 62->exit` is unreachable
The `for` loop in `_execute_with_retry` iterates over `range(1, _RETRY_ATTEMPTS + 1)` (always `range(1, 6)`). Every iteration either:
- returns a value via `return fn()`, or
- raises via the `raise` inside the `except` block.

The loop can never exit normally (fall-through after the last iteration) because the `raise` on the last attempt propagates out of the function before the loop body completes. The coverage tool flags the "loop exits normally" branch, but it is structurally impossible to reach. No test is added for this.

---

## Key Decisions

### Per-test database isolation via `request.node.name`
Using `tmp_path` was the original approach but it auto-deletes the DB after the test, making post-run inspection impossible. Using a single shared path broke test isolation. The chosen approach (per-test named directory under `.test_db/`, wiped before each run) satisfies both constraints: each test owns its state, and the DB files remain on disk for GUI debugging.

### `_NoteRow` direct access in `test_store_list_returns_account_notes_for_matching_account_id`
The public `DatabaseStore.add()` always writes `account_id=NULL`. The `account_notes` routing branch in `list()` is only reachable by inserting a row with a non-None `account_id` directly. Accessing the internal `_NoteRow` ORM class and `store._Session` from a test is acceptable — this is white-box testing of an internal data partition that has no public API yet.

---

## Test Counts

| Suite | File | Tests | Status |
|---|---|---|---|
| BDD scenarios | `tests/steps/test_steps.py` | 17 | ✅ all pass |
| Unit | `tests/test_core.py` | 39 | ✅ all pass |
| Stress | `tests/test_core.py` | 1 | ✅ passes (deselected by default) |
| Unit + CLI | `tests/test_sprint1.py` | 68 | ✅ all pass |
| **Total** | | **125** | ✅ |
