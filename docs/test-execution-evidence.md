# AstraNotes — Test Execution Evidence

> **⚠ HISTORICAL RECORD (2026-05-07):** This document records the test execution results for the Sprint Zero codebase as it existed on 2026-05-04. On 2026-05-07, all source code (`src/`) and test files (`tests/`, `test_all.py`) were permanently deleted. **No code or tests currently exist.** This document is preserved as a reference for the expected test outcomes when Sprint Zero is reimplemented from scratch. The 33-test baseline shown below is the Sprint Zero target to re-achieve.

## Sprint Zero Gate Pass

**Date:** 2026-05-04 *(historical — code since removed)*
**Baseline:** Sprint Zero exit criteria — 33 tests pass (`pytest -v`)  
**Environment:** Python 3.12.10, pytest 9.0.2, pytest-bdd 8.1.0, Windows (PowerShell)  
**Command:** `python -m pytest tests/ -v --tb=short`

### Result: 33 PASSED / 0 FAILED

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: E:\Santa Clara\CSEN 296-B\AstraNotes
configfile: pytest.ini
plugins: bdd-8.1.0
collected 33 items

tests/steps/test_steps.py::test_add_unencrypted_note PASSED              [  3%]
tests/steps/test_steps.py::test_add_encrypted_note PASSED                [  6%]
tests/steps/test_steps.py::test_add_invalid_note PASSED                  [  9%]
tests/steps/test_steps.py::test_list_mixed_notes PASSED                  [ 12%]
tests/steps/test_steps.py::test_list_empty PASSED                        [ 15%]
tests/steps/test_steps.py::test_get_unencrypted PASSED                   [ 18%]
tests/steps/test_steps.py::test_get_encrypted_correct PASSED             [ 21%]
tests/steps/test_steps.py::test_get_encrypted_wrong PASSED               [ 24%]
tests/steps/test_steps.py::test_get_nonexistent PASSED                   [ 27%]
tests/steps/test_steps.py::test_update_unencrypted PASSED                [ 30%]
tests/steps/test_steps.py::test_update_encrypted PASSED                  [ 33%]
tests/steps/test_steps.py::test_update_encrypted_wrong PASSED            [ 36%]
tests/steps/test_steps.py::test_update_nonexistent PASSED                [ 39%]
tests/steps/test_steps.py::test_delete_unencrypted PASSED                [ 42%]
tests/steps/test_steps.py::test_delete_encrypted_correct PASSED          [ 45%]
tests/steps/test_steps.py::test_delete_encrypted_wrong PASSED            [ 48%]
tests/steps/test_steps.py::test_delete_nonexistent PASSED                [ 51%]
tests/test_core.py::TestNote::test_note_creation PASSED                  [ 54%]
tests/test_core.py::TestNote::test_note_update PASSED                    [ 57%]
tests/test_core.py::TestEncryptionEngine::test_encrypt_decrypt PASSED    [ 60%]
tests/test_core.py::TestEncryptionEngine::test_wrong_passphrase_fails PASSED [ 63%]
tests/test_core.py::TestKeyManager::test_get_engine PASSED               [ 66%]
tests/test_core.py::TestNoteStore::test_add_get_note PASSED              [ 69%]
tests/test_core.py::TestNoteStore::test_update_note PASSED               [ 72%]
tests/test_core.py::TestNoteStore::test_delete_note PASSED               [ 75%]
tests/test_core.py::TestNoteStore::test_list_notes PASSED                [ 78%]
tests/test_core.py::TestNoteStore::test_duplicate_add_raises PASSED      [ 81%]
tests/test_core.py::TestNoteStore::test_add_encrypted_note_requires_key_manager PASSED [ 84%]
tests/test_core.py::TestNoteStore::test_load_encrypted_note_without_key_hides_title_and_content PASSED [ 87%]
tests/test_core.py::TestNoteStore::test_load_encrypted_note_with_wrong_key_hides_title_and_content PASSED [ 90%]
tests/test_core.py::TestNoteStore::test_load_encrypted_note_with_correct_key_decrypts PASSED [ 93%]
tests/test_core.py::TestNoteStore::test_delete_unencrypted_note_preserves_other_encrypted_records PASSED [ 96%]
tests/test_core.py::test_store_handles_1001_adds_and_deletes_safely PASSED [100%]

============================= 33 passed in 5.77s ==============================
```

### Test Breakdown

| Suite | Count | Coverage |
|-------|-------|----------|
| BDD scenarios (`tests/steps/test_steps.py`) | 17 | All CLI CRUD + encryption paths (R1, R2) |
| Unit — `TestNote` | 2 | Note creation, update (R1.4) |
| Unit — `TestEncryptionEngine` | 2 | AES-256-GCM encrypt/decrypt, wrong-passphrase rejection (R2.17) |
| Unit — `TestKeyManager` | 1 | Engine construction (R2.10) |
| Unit — `TestNoteStore` | 10 | Add/get/update/delete/list, duplicate rejection, encrypted record preservation (R1, R2, R3) |
| Stress — `test_store_handles_1001_adds_and_deletes_safely` | 1 | 1001 notes within bounds (R3.5) |
| **Total** | **33** | |

### Known Test Gaps (to be closed in Sprint 1 via B-40, B-83)

| Gap | Status | Closing Item |
|-----|--------|-------------|
| No tests for `PluginBase` / `PluginRegistry` (B-18 test debt) | Open | B-83 |
| No test for gap-safe ID generation after deletion (B-31) | Open | B-40 |
| No test for passphrase confirmation mismatch (B-32) | Open | B-40 |
| No test for corrupt JSON recovery (B-35) | Open | B-40 |
| No test for `--data-dir` validation (B-36) | Open | B-40 |
| No test for passphrase min-length enforcement (B-34) | Open | B-40 |

---

## Sprint 1 Evidence

*(To be filled when Sprint 1 completes. Expected: ≥47 tests passing.)*

---

## Sprint 2 Evidence

*(To be filled when Sprint 2 completes.)*
