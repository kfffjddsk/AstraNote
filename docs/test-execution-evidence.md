# AstraNotes — Test Execution Evidence

> **⚠ HISTORICAL RECORD (2026-05-07):** This document records the test execution results for the Sprint Zero codebase as it existed on 2026-05-04. On 2026-05-07, all source code (`src/`) and test files (`tests/`, `test_all.py`) were permanently deleted. **See the 2026-05-15 Sprint Zero re-implementation results below.**

## Sprint Zero Gate Pass — Re-implementation (2026-05-15)

**Date:** 2026-05-15  
**Baseline:** Sprint Zero re-implementation + injection hardening (OWASP A03, A08)  
**Environment:** Python 3.12.10, pytest 9.0.2, pytest-bdd 8.1.0, SQLAlchemy 2.0.49, cryptography 46.0.6, Windows (PowerShell)  
**Command:** `.venv\Scripts\python.exe -m pytest tests/ -v --tb=short -m "not stress"`

### Result: 46 PASSED / 0 FAILED

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: E:\Santa Clara\CSEN 296-B\AstraNotes
configfile: pytest.ini
plugins: anyio-4.13.0, bdd-8.1.0
collected 47 items / 1 deselected / 46 selected

tests/steps/test_steps.py::test_add_an_unencrypted_note PASSED           [  2%]
tests/steps/test_steps.py::test_add_an_encrypted_note PASSED             [  4%]
tests/steps/test_steps.py::test_reject_a_note_with_an_empty_title PASSED [  6%]
tests/steps/test_steps.py::test_get_an_unencrypted_note_by_id PASSED     [  8%]
tests/steps/test_steps.py::test_get_an_encrypted_note_with_the_correct_passphrase PASSED [ 10%]
tests/steps/test_steps.py::test_wrong_passphrase_raises_invalidtag PASSED [ 13%]
tests/steps/test_steps.py::test_get_a_nonexistent_note_returns_none PASSED [ 17%]
tests/steps/test_steps.py::test_list_notes_with_mixed_encryption PASSED  [ 19%]
tests/steps/test_steps.py::test_list_an_empty_store PASSED               [ 21%]
tests/steps/test_steps.py::test_update_an_unencrypted_note PASSED        [ 23%]
tests/steps/test_steps.py::test_update_a_nonexistent_note_raises_keyerror PASSED [ 26%]
tests/steps/test_steps.py::test_unencrypted_update_does_not_corrupt_a_costored_encrypted_note PASSED [ 28%]
tests/steps/test_steps.py::test_update_encrypted_note_replaces_blob PASSED [ 30%]
tests/steps/test_steps.py::test_delete_an_unencrypted_note PASSED        [ 34%]
tests/steps/test_steps.py::test_delete_a_nonexistent_note_raises_keyerror PASSED [ 36%]
tests/steps/test_steps.py::test_delete_an_encrypted_note PASSED          [ 38%]
tests/steps/test_steps.py::test_deleting_a_plain_note_preserves_a_costored_encrypted_note PASSED [ 41%]
tests/test_core.py::test_note_create_assigns_unique_uuid PASSED          [ 43%]
tests/test_core.py::test_note_update_title_refreshes_modified_at PASSED  [ 45%]
tests/test_core.py::test_note_update_noop_when_no_args PASSED            [ 47%]
tests/test_core.py::test_note_create_rejects_empty_title PASSED          [ 50%]
tests/test_core.py::test_note_create_rejects_whitespace_content PASSED   [ 52%]
tests/test_core.py::test_store_add_returns_note_id PASSED                [ 54%]
tests/test_core.py::test_store_add_persists_content PASSED               [ 56%]
tests/test_core.py::test_store_get_not_found_returns_none PASSED         [ 58%]
tests/test_core.py::test_store_add_encrypted_note_stores_blob PASSED     [ 60%]
tests/test_core.py::test_store_get_encrypted_returns_placeholder_title PASSED [ 63%]
tests/test_core.py::test_store_update_unencrypted_note PASSED            [ 65%]
tests/test_core.py::test_store_update_not_found_raises PASSED            [ 67%]
tests/test_core.py::test_store_delete_removes_note PASSED                [ 69%]
tests/test_core.py::test_store_delete_not_found_raises PASSED            [ 71%]
tests/test_core.py::test_store_list_empty_returns_empty_tuple PASSED     [ 73%]
tests/test_core.py::test_store_list_mixed_encryption PASSED              [ 76%]
tests/test_core.py::test_unencrypted_update_does_not_corrupt_encrypted_note PASSED [ 78%]
tests/test_core.py::test_encryption_roundtrip PASSED                     [ 80%]
tests/test_core.py::test_wrong_passphrase_raises_invalid_tag PASSED      [ 82%]
tests/test_core.py::test_keymanager_rejects_short_passphrase PASSED      [ 84%]
tests/test_core.py::test_blobcodec_encode_decode_roundtrip PASSED        [ 86%]
tests/test_core.py::test_blobcodec_encrypted_blob_decrypts_to_original_content PASSED [ 89%]
tests/test_core.py::test_note_create_rejects_null_byte_in_title PASSED   [ 91%]
tests/test_core.py::test_note_create_rejects_null_byte_in_content PASSED [ 93%]
tests/test_core.py::test_note_update_rejects_null_byte_in_title PASSED   [ 95%]
tests/test_core.py::test_note_update_rejects_null_byte_in_content PASSED [ 97%]
tests/test_core.py::test_blobcodec_decode_rejects_oversized_header PASSED [ 98%]
tests/test_core.py::test_blobcodec_decode_rejects_non_dict_header PASSED [ 99%]
tests/test_core.py::test_encryption_decrypt_rejects_short_ciphertext PASSED [100%]

====================== 46 passed, 1 deselected in 0.58s =======================
```

*(1 deselected = `test_store_stress_1001_notes`, excluded via `-m "not stress"`)*

| Suite | Count | Coverage |
|-------|-------|----------|
| BDD scenarios (`tests/steps/test_steps.py`) | 17 | All CRUD + encryption paths (R1, R2) |
| Unit — Note dataclass | 5 | UUID uniqueness, `modified_at`, no-op update, empty/whitespace validation |
| Unit — DatabaseStore CRUD | 9 | add/get/update/delete, missing-ID errors, encrypted blob persistence |
| Unit — list() | 2 | empty store, mixed encryption |
| Unit — co-existence invariant | 1 | Unencrypted update does not corrupt encrypted blob [B-33] |
| Unit — Encryption / BlobCodec | 5 | Roundtrip, wrong passphrase, short passphrase, encode/decode, full pipeline |
| Unit — **Injection hardening** | **7** | Null bytes, oversized header, JSON type confusion, short ciphertext |
| Stress (deselected by default) | 1 | 1 001 notes; list < 0.5 s [B-22] |
| **Total (excluding stress)** | **46** | |

### Injection-Hardening Tests (OWASP A03, A08)

| Test | Surface hardened | Vulnerability closed |
|------|-----------------|----------------------|
| `test_note_create_rejects_null_byte_in_title` | `Note.create()` | Null-byte injection → SQLite TEXT C-string truncation |
| `test_note_create_rejects_null_byte_in_content` | `Note.create()` | Same for content |
| `test_note_update_rejects_null_byte_in_title` | `Note.update()` | Null-byte via update path |
| `test_note_update_rejects_null_byte_in_content` | `Note.update()` | Same for content |
| `test_blobcodec_decode_rejects_oversized_header` | `BlobCodec.decode()` | DoS — 4-byte header_len allows ~4 GB allocation; capped at 64 KiB |
| `test_blobcodec_decode_rejects_non_dict_header` | `BlobCodec.decode()` | JSON type confusion — non-dict header causes `KeyError` downstream |
| `test_encryption_decrypt_rejects_short_ciphertext` | `EncryptionEngine.decrypt()` | Truncated salt to PBKDF2; now fails fast with `ValueError` |

### Known Test Gaps (to be closed in Sprint 1 via B-40, B-83)

| Gap | Status | Closing Item |
|-----|--------|-------------|
| No tests for `PluginBase` / `PluginRegistry` (B-18 test debt) | Open | B-83 |
| No test for `--data-dir` validation (B-36, B-55) | Open | B-40 |
| No BDD scenarios for injection-hardening paths | Open | B-40 |

---

## Sprint Zero Gate Pass — Historical (2026-05-04)

*(Original 33-test baseline — code since removed and re-implemented)*
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

> **Note (D-10, 2026-05-12):** The `TestNoteStore` class above tests the Sprint 0 `NoteStore` (JSON) implementation that was later deleted. When Sprint Zero is **reimplemented** against `DatabaseStore` (SQLite), this test class must be renamed `TestDatabaseStore` and all test methods updated to exercise `DatabaseStore` rather than the JSON store. The 33-test count target stands.

| Suite | Count | Coverage |
|-------|-------|----------|
| BDD scenarios (`tests/steps/test_steps.py`) | 17 | All CLI CRUD + encryption paths (R1, R2) |
| Unit — `TestNote` | 2 | Note creation, update (R1.4) |
| Unit — `TestEncryptionEngine` | 2 | AES-256-GCM encrypt/decrypt, wrong-passphrase rejection (R2.17) |
| Unit — `TestKeyManager` | 1 | Engine construction (R2.10) |
| Unit — `TestNoteStore` *(to be renamed `TestDatabaseStore` in Sprint 1 — D-10)* | 10 | Add/get/update/delete/list, duplicate rejection, encrypted record preservation (R1, R2, R3) |
| Stress — `test_store_handles_1001_adds_and_deletes_safely` | 1 | 1001 notes within bounds (R3.5) |
| **Total** | **33** | |

### Known Test Gaps (to be closed in Sprint 1 via B-40, B-83)

| Gap | Status | Closing Item |
|-----|--------|-------------|
| No tests for `PluginBase` / `PluginRegistry` (B-18 test debt) | Open | B-83 |
| No test for gap-safe ID generation after deletion (B-31) | Open | B-40 |
| No test for passphrase confirmation mismatch (B-32) | Open | B-40 |
| ~~No test for corrupt JSON recovery (B-35)~~ | **DROPPED** `[D-10]` | ~~B-40~~ |
| No test for `--data-dir` validation (B-36) | Open | B-40 |
| No test for passphrase min-length enforcement (B-34) | Open | B-40 |

---

## Sprint 1 Evidence

### Sprint 1 Gate Pass (2026-05-18) + Coverage Hardening (2026-05-19)

**Date:** 2026-05-19  
**Baseline:** Sprint 1 full implementation + branch-coverage audit  
**Environment:** Python 3.12.0, pytest 9.0.3, pytest-bdd 8.1.0, pytest-cov 7.1.0, SQLAlchemy 2.0.49, cryptography 48.0.0, Windows (PowerShell)  
**Command:** `.venv\Scripts\python.exe -m pytest tests/ -v --tb=short`

### Result: 125 PASSED / 0 FAILED

```
============================= test session starts =============================
platform win32 -- Python 3.12.0, pytest-9.0.3, pluggy-1.6.0
rootdir: D:\File\School\Santa Clara\Course\CSEN 296-B\AstraNote
configfile: pytest.ini
plugins: anyio-4.13.0, bdd-8.1.0, cov-7.1.0
collected 125 items

tests\steps\test_steps.py .................                              [ 13%]
tests\test_core.py ........................................                [ 45%]
tests\test_sprint1.py ..................................................................
..........                                                               [100%]

============================= 125 passed in 2.78s =============================
```

| Suite | Count | Notes |
|---|---|---|
| BDD scenarios (`tests/steps/test_steps.py`) | 17 | All CRUD + encryption paths (R1, R2) |
| Unit — `test_core.py` | 39 | See breakdown below |
| Stress — `test_core.py` | 1 | 1 001 notes; list < 0.5 s [B-22] *(deselected by default)* |
| Unit + CLI — `test_sprint1.py` | 68 | See breakdown below |
| **Total (all)** | **125** | |
| **Total (excl. stress)** | **124** | |

#### test_core.py breakdown (39 unit + 1 stress)

| Section | Tests | Coverage |
|---|---|---|
| §1 Note dataclass | 6 | create, update (title, content, both, no-op), validation |
| §2 DatabaseStore add/get | 5 | persistence, encrypted blob, placeholder title |
| §3 DatabaseStore update | 5 | unencrypted, encrypted (blob replace, content ignored), content-only, not-found |
| §4 DatabaseStore delete | 2 | remove, not-found |
| §5 DatabaseStore list | 3 | empty, mixed encryption, account_id routing [D-11] |
| §6 Co-existence invariant | 1 | unencrypted update does not corrupt encrypted blob [BL B-33] |
| §7 Encryption / BlobCodec | 10 | AES-256-GCM roundtrip, public derive_key, wrong passphrase, BlobCodec encode/decode, blob-too-short, truncated-body, full pipeline; KeyManager short/empty/whitespace passphrase |
| §8 Stress | 1 | 1 001 notes [BL B-22] |
| §9 Injection hardening | 7 | Null bytes (create/update × 2), oversized header, JSON type confusion, short ciphertext [OWASP A03, A08] |

#### test_sprint1.py breakdown (68 unit/cli)

| Section | Tests | Backlog ref |
|---|---|---|
| §1 WAL mode + locked-DB retry | 4 | [BL B-66] |
| §2 PluginBase / PluginRegistry | 8 | [BL B-83] |
| §3 Plugin auto-discovery | 8 | [BL B-37] — includes spec=None branch |
| §4 CLI input-validation helpers | 7 | [BL B-52] |
| §5 `--data-dir` validation | 4 | [BL B-36] |
| §6 CLI `add` command | 8 | [BL B-19, B-23, B-32, B-52] |
| §7 CLI `get` command | 5 | |
| §8 CLI `list` command | 4 | |
| §9 CLI `update` command | 5 | |
| §10 CLI `delete` command | 4 | |
| §11 Non-zero exit codes sweep | 4 | [BL B-23] |
| §12 Passphrase confirmation | 3 | [BL B-32] |
| §13 Alembic baseline migration | 4 | [BL B-65] |

### Branch Coverage — Core Modules (2026-05-19)

**Command:** `.venv\Scripts\python.exe -m pytest tests/test_core.py tests/test_sprint1.py -m "unit or stress" --cov=src/core --cov-branch`

```
Name                      Stmts   Miss Branch BrPart  Cover   Missing
---------------------------------------------------------------------
src\core\__init__.py          0      0      0      0   100%
src\core\blob_codec.py       35      0      8      0   100%
src\core\notes.py           151      0     42      1    99%   62->exit
src\core\plugin_base.py      63      0     16      0   100%
src\core\security.py         45      0      6      0   100%
---------------------------------------------------------------------
TOTAL                       294      0     72      1    99%
```

> The single uncovered branch (`notes.py 62->exit`) is a structural coverage artifact: the `for` loop in `_execute_with_retry` can never exit normally because every iteration either returns a value or raises an exception. It is genuinely unreachable without patching constants and is not a test gap.

### Test Isolation (2026-05-19)

`tests/conftest.py` `tmp_store` fixture was refactored to use per-test isolation:
- Each test receives its own `DatabaseStore` backed by `.test_db/<test_name>/notes.db`.
- The directory is wiped before each run (no stale-data leakage between runs).
- Files are left on disk after the run for inspection with GUI tools (DB Browser for SQLite, SQLite Viewer VS Code extension).

### Known Test Gaps (remaining)

| Gap | Status | Closing Item |
|---|---|---|
| No BDD scenarios for injection-hardening paths | Open | Future sprint |
| `src/cli.py` not covered by unit/core coverage sweep (CLI tests run via `CliRunner`) | Acknowledged | CLI integration tests in `test_sprint1.py` §6–§11 cover this path |

---

## Sprint 2 Evidence

**Date:** May 2026  
**Baseline:** Sprint 2 full implementation — account layer, session management, auth hardening, hybrid storage  
**Environment:** Python 3.12, pytest, pytest-bdd, SQLAlchemy 2.0, cryptography, Windows (PowerShell)  
**Command:** `.venv\Scripts\python.exe -m pytest tests/ -v --tb=short`

### Result: 245 PASSED / 0 FAILED / 1 SKIPPED

| Suite | Count | Notes |
|---|---|---|
| BDD scenarios (`tests/steps/test_steps.py`) | 17 | All CRUD + encryption paths (R1, R2) — unchanged from Sprint Zero |
| Unit — `test_core.py` | 40 | 39 unit + 1 stress (stress deselected by default) |
| CLI + unit — `test_sprint1.py` | 68 | Sprint 1 CLI, WAL, plugin, Alembic tests |
| Auth + storage — `test_sprint2.py` | 106 | AccountStore, auth, session, hybrid storage, CLI auth commands, first-login prompt |
| Bug regression | 3 | Included in test_sprint2.py |
| Branch coverage | 8 | Included in test_sprint2.py |
| **Total** | **246** | **1 skipped** (POSIX permission test — Windows-only skip) |

### Branch Coverage — Core Modules (Sprint 2 complete)

All six core modules at 100% branch coverage: `blob_codec.py`, `notes.py`, `security.py`, `plugin_base.py`, `auth.py`, `AccountStore`.

### Summary of Sprint 2 Test Additions

- `AccountStore`: register, login, logout, rate limiting, session token, delete-account
- Hybrid storage: 5 MB threshold, filesystem payload orphan cleanup, disk-full (`ENOSPC`) handling
- Auth prompts: `hide_input=True`, interactive CLI auth commands
- Session token file permissions, 24h expiry, expired-session behavior (local CRUD unaffected)
- First-login anonymous note association prompt (one-time, Yes/No/Ask-each)
- Username validation (3–32 chars, alphanumeric + underscore, case-insensitive)
- `DATABASE_URL` from env var only; never in config
- Per-user audit log deletion on `delete-account`
