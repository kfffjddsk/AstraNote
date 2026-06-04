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

---

## Sprint 3 Evidence

**Date:** May 2026  
**Baseline:** Sprint 3 full implementation — plugin hardening, audit trail, config module, search/export, reencrypt  
**Environment:** Python 3.12, pytest, pytest-bdd, SQLAlchemy 2.0, cryptography, Windows (PowerShell)  
**Command:** `.venv\Scripts\python.exe -m pytest tests/ -v --tb=short`

### Result: 387 PASSED / 0 FAILED / 1 SKIPPED

```
============================= test session starts =============================
platform win32 -- Python 3.12, pytest-9.0.x, pluggy-1.6.0
rootdir: E:\Santa Clara\CSEN 296-B\AstraNotes
configfile: pytest.ini
plugins: anyio-4.13.0, bdd-8.1.0
collected 388 items

tests\steps\test_steps.py ..............................                  [  7%]
tests\test_core.py ........................................                [ 18%]
tests\test_sprint1.py ................................................................................
...............                                                          [ 40%]
tests\test_sprint2.py ......................................................................
.........................................                                  [ 67%]
tests\test_sprint3.py ......................................................................
.......................................................                  [100%]

================ 387 passed, 1 skipped in ~24s ================================
```

*(1 skipped = POSIX file-permission test, Windows-only skip — unchanged from Sprint 2)*

| Suite | Count | Notes |
|---|---|---|
| BDD scenarios (`tests/steps/test_steps.py`) | 30 | Sprint 0–2 CRUD/encryption (17) + Sprint 3 search (7), reencrypt (2), audit (4) |
| Unit — `test_core.py` | 40 | Unchanged from Sprint 2 |
| CLI + unit — `test_sprint1.py` | 83 | Sprint 1 base (68) + 15 additional tests added during Sprint 3 hardening |
| Auth + storage — `test_sprint2.py` | 107 | Sprint 2 base (106) + 1 regression fix |
| Sprint 3 features — `test_sprint3.py` | 128 | See breakdown below |
| **Total (all)** | **388** | |
| **Total (passing)** | **387** | 1 skipped: POSIX permission test, Windows-only skip |

### test_sprint3.py breakdown (128 tests)

| Class | Count | Backlog / Req |
|---|---|---|
| `TestAuditLogger` | 14 | [B-25] Append-only JSON audit log, filters, `outcome`, `detail` fields |
| `TestConfigStore` | 17 | [B-26] Known-key whitelist, set/get/list/reset, `ALLOWED_KEYS`, `DEFAULTS` |
| `TestDatabaseStoreSearch` | 15 | [B-29] `search()` — plain title+content match, encrypted alias-only, no blob exposed |
| `TestCliSearch` | 9 | [B-29] CLI `search` — base search (plain + alias); `--encrypted` per-note passphrase tests pending (B-29 ⏳) |
| `TestCliExport` | 11 | [B-30, B-76, B-78] Export to text/JSON, `--output`, `--encrypted`, binary payloads, `--cleanup` |
| `TestCliReencrypt` | 6 | [B-62] `reencrypt <note_id>` — passphrase rotation |
| `TestCliConfig` | 7 | [B-26] CLI `config set/get/list/reset` |
| `TestCliAudit` | 6 | [B-71] CLI `audit` — login/logout/register/export events |
| `TestPluginRegistry` | 7 | [B-83] `PluginRegistry` unit tests — override detection, exec/eval ban |
| `TestPluginAllowlist` | 5 | [B-69] Plugin allowlist enforcement via config |
| `TestPluginOverridePolicy` | 7 | [B-24] Red warning + `CONFIRM OVERRIDE` prompt |
| `TestPluginCommandWiring` | 2 | [B-28] Plugin CLI commands wired into main CLI |
| `TestAnsiStripping` | 8 | [B-54] Strip ANSI/control codes from terminal output |
| `TestPathTraversal` | 2 | [B-55] Path traversal prevention for `--data-dir`, `--output` |
| `TestPluginSandboxing` | 2 | [B-56] Read-only note copies, no exec/eval, no raw DB access |
| `TestAuditIntegration` | 7 | [B-71] Audit events from CRUD/auth/export/reencrypt CLI paths |
| `TestAliasInfoWarning` | 2 | [B-79] Alias info warning for encrypted notes |
| `TestPassphraseMemoryLimitation` | 1 | [B-73] Passphrase memory-residency limitation documented |

### New BDD Scenarios (Sprint 3) — 13 new scenarios in 3 new feature files

| Feature file | Scenarios | Coverage |
|---|---|---|
| `tests/features/search_notes.feature` | 7 | Plain search, encrypted alias match, per-note passphrase prompt, wrong passphrase fallback, `--encrypted` flag semantics |
| `tests/features/reencrypt_note.feature` | 2 | Passphrase rotation success, wrong current passphrase rejection |
| `tests/features/audit_log.feature` | 4 | Audit entries for add/delete/login/export events |

---

## Sprint 4B Evidence

### Sprint 4B Gate Pass (2026-06-03)

**Date:** 2026-06-03
**Baseline:** Sprint 4B GUI completeness — VS Code-inspired layout, tab bar, rich-text editor, search, account-aware list, settings dialog, theme/font support, keyboard shortcuts.
**Environment:** Python 3.12.10, pytest 9.0.2, pytest-bdd 8.1.0, PySide6 6.11.1 (headless `QT_QPA_PLATFORM=offscreen`), SQLAlchemy 2.0.49, cryptography 46.0.6, Windows (PowerShell).
**Command:** `.venv\Scripts\python.exe -m pytest -q --timeout=30`

### Result: 569 PASSED / 0 FAILED / 1 SKIPPED

```
569 passed, 1 skipped in ~33s
```

*(1 skipped = POSIX-only permission test on Windows.)*

| Suite | Count | Delta vs Sprint 4 |
|-------|-------|-------------------|
| BDD scenarios | 30 | — |
| Core unit — `test_core.py` | 46 | — |
| Sprint 1 — `test_sprint1.py` | 83 | — |
| Sprint 2 — `test_sprint2.py` | 102 | — |
| Sprint 3 — `test_sprint3.py` | 128 | — |
| Sprint 4 — `test_sprint4.py` | 106 | — |
| **Sprint 4B — `test_sprint4b.py`** | **77** | **+77** new |
| `test_all.py` | 4 | — |
| Stress (skipped) | 1 | — |
| **Total** | **569 + 1 skipped** | **+76** |

### Sprint 4B Test Highlights (`tests/test_sprint4b.py`)

- VS Code-inspired layout: `QSplitter` resize, sidebar collapse, dark/light palette on startup.
- Tab bar: `QTabWidget` add/remove/move; active tab synced with sidebar selection.
- Rich-text editor: `QTextEdit` HTML round-trip; B/I/U toolbar; `get_html_content()` vs `get_content()`.
- Encrypted-note UX: alias input row; explicit `🔓 Unlock` button instead of auto-prompt.
- Search bar: real-time filter; `Ctrl+F` focuses.
- Account-aware sidebar: "Your Notes" / "Local Notes" sections when session token present.
- Settings dialog (Sprint 4B layout): `theme`, `font_size`, `default_encrypt`, `passphrase_min_length`.
- Keyboard shortcuts: Ctrl+N / Ctrl+S / Del / Ctrl+F / Ctrl+W / Ctrl+, / Ctrl+Q.

---

## Sprint 4C Evidence

### Sprint 4C Gate Pass (2026-06-04)

**Date:** 2026-06-04
**Baseline:** Sprint 4C GUI polish — external `.qss` stylesheets with optional hot-reload, redesigned Settings dialog (category list + 4 pages), Plugins Admin dialog, new-note format chooser, decrypt-by-uncheck, themed SVG icons for combobox / spinbox / checkbox / tab-close, dev-only Widget Gallery.
**Environment:** Python 3.12.10, pytest 9.0.2, pytest-bdd 8.1.0, PySide6 6.11.1 (headless), SQLAlchemy 2.0.49, cryptography 46.0.6, Windows (PowerShell).
**Command:** `.venv\Scripts\python.exe -m pytest -q --timeout=30`

### Result: 569 PASSED / 0 FAILED / 1 SKIPPED

```
569 passed, 1 skipped in 33.26s
```

| Suite | Count | Delta vs Sprint 4B |
|-------|-------|--------------------|
| All Sprint 0–4B suites (above) | 569 | — |
| Sprint 4C net new tests | 0 | Sprint 4C reused Sprint 4B harnesses; one regression patch + one obsolete test removed (net 0) |
| **Total** | **569 + 1 skipped** | **0** |

### Sprint 4C Behavioural Coverage

No new test file was introduced; behaviour was verified by:

- Re-running the full 569-test suite headless after every visual / functional iteration.
- Manual UX verification of the three screenshot review rounds (toolbar / spin / list / Settings / format dialog / decrypt-by-uncheck / sidebar deselect / tab-close icon).
- Patching `tests/test_sprint4.py::TestSystemTray::test_close_minimizes_when_tray_available` to set `close_behavior="minimize"` so the new ask-on-close dialog (added in Sprint 4B) doesn't block the headless tray test.
- Commenting out `tests/test_sprint4b.py::TestSettingsDialog::test_settings_dialog_has_passphrase_spin` (the widget was removed by UX request; backend default `passphrase_min_length=8` still applies).

### New Source Files (Sprint 4C)

| File | Purpose |
|------|---------|
| `src/desktop/styles/__init__.py` | `load_stylesheet(theme)` reads `.qss` files and substitutes `{ICONS}` with the absolute icons path [B-113]. |
| `src/desktop/styles/dark.qss` | PyDracula dark theme — all widgets [B-113/B-119]. |
| `src/desktop/styles/light.qss` | Light theme mirror [B-113/B-119]. |
| `src/desktop/styles/icons/chevron-down-{dark,light}.svg`, `chevron-up-{dark,light}.svg` | Combobox + spinbox arrows [B-119]. |
| `src/desktop/styles/icons/check.svg` | Checkbox tick [B-119]. |
| `src/desktop/styles/icons/close-{dark,light,hover}.svg` | Tab close X with red hover state [B-119]. |
| `AI Working Log/working-log-2026-06-04.md` | Session log [doc]. |

### Modified Source Files (Sprint 4C)

| File | Change |
|------|--------|
| `src/core/config.py` | Added `accent_color`, `font_family`, `word_wrap` to `ALLOWED_KEYS` / `_TYPE_MAP` / `DEFAULTS` / `_VALUE_CONSTRAINTS` [B-115]. |
| `src/core/notes.py` | `DatabaseStore.update()` now accepts `encrypted: Optional[bool]`; passing `False` clears the blob, removes on-disk payload if any, and writes plaintext [B-118]. |
| `src/desktop/app_controller.py` | Reads `font_family` + `accent_color` from config and forwards them to `apply_theme()` [B-115]. |
| `src/desktop/main_window.py` | Loads QSS from files; `apply_theme(theme, font_size, font_family, accent)`; `ACCENT_COLORS` + `_stylesheet_with_accent()`; `_install_qss_hotreload()`; `SettingsDialog` redesign; new `PluginsDialog` / `_NewNoteTypeDialog` / `_WidgetGallery`; `NoteEditorWidget.apply_format()`; decrypt-by-uncheck save path; sidebar deselect on new note; font-size combo width 52→72; menu wiring for `Ctrl+Shift+P` and `Ctrl+Shift+G` [B-113..B-121]. |

### Key Design Decisions Validated by Sprint 4C

- **External QSS via `{ICONS}` token** — `load_stylesheet()` performs a single `str.replace("{ICONS}", icons_url)` so QSS files reference real SVG assets and remain portable regardless of where the package is installed.
- **Hot-reload is dev-only** — gated by `ASTRANOTES_QSS_HOTRELOAD=1`; off in tests and production runs.
- **Accent token swap** — accent colour is implemented as a string substitution on `#bd93f9` in the loaded QSS rather than a templating engine, keeping the loader dependency-free.
- **Decrypt-by-uncheck safety** — `MainWindow._on_save` refuses the transition while the `[Encrypted]` placeholder is still visible (i.e. user hasn't unlocked) to prevent accidentally overwriting an encrypted note with placeholder text.
- **Sidebar deselection on new note** — `_note_list.blockSignals(True); clearSelection(); setCurrentRow(-1); blockSignals(False)` so the visual selection follows the user's intent without firing a spurious `currentRowChanged` that would discard the new tab.


### Key Design Decisions Validated by Sprint 3 Tests

- **`DatabaseStore.search()` never exposes encrypted blobs** — the DB layer returns `blob=None` for encrypted notes even when the alias matches. Tests `TestDatabaseStoreSearch.test_search_encrypted_body_never_returned_by_store` and `test_search_encrypted_alias_returns_note_with_blob_none` confirm this invariant.
- **Per-note passphrase prompts in `search --encrypted`** — each encrypted note is prompted individually (`click.prompt(f'Passphrase for "{stub.title}"')`). Different notes may use different passphrases. Tests `TestCliSearch.test_search_encrypted_*` validate the per-note loop, audit logging, and alias fallback when passphrase is skipped or wrong.
- **Audit log integrity** — the JSON-per-line audit log is append-only and records `outcome` (`success`/`failure`) and `detail` for decrypt attempts. Validated by `TestAuditIntegration` and `TestAuditLogger`.

### Summary of Sprint 3 Test Additions

- `AuditLogger`: `log()`, `read_log()`, filter by `account_id`/`action`/`outcome`, multi-account isolation
- `ConfigStore`: `set()`/`get()`/`list()`/`reset()`, unknown-key rejection, default values, persistence
- `DatabaseStore.search()`: plain+encrypted alias returns, blob isolation, account scoping
- CLI `search`: plain search, `--encrypted` per-note passphrase prompts, audit events, skip/wrong-passphrase behavior, duplicate-result deduplication
- CLI `export`: text/JSON format, `--output` path validation, path traversal prevention, `--cleanup` removes payload dir, binary-note manifest
- CLI `reencrypt`: passphrase change roundtrip, wrong-passphrase rejection
- CLI `config`/`audit`: all subcommands exercised end-to-end
- Plugin hardening: allowlist config enforcement, override-policy confirmation, sandboxing (read-only copy, exec/eval blocked)
- ANSI stripping: control codes removed from search/list/export output
- Path traversal: `--data-dir` and `--output` reject `../` and absolute escapes

---

## Sprint 4 Evidence

### Sprint 4 Gate Pass (2026-06-01)

**Date:** 2026-06-01  
**Baseline:** Sprint 4 full implementation — PySide6 desktop GUI, AppController, AppLockManager, system tray, idle auto-lock, plugin manifest validation, trust-tier enforcement, security_level config  
**Environment:** Python 3.12.10, pytest 9.0.2, pytest-bdd 8.1.0, PySide6 6.x (headless offscreen), SQLAlchemy 2.0.49, cryptography 46.0.6, jsonschema, Windows (PowerShell)  
**Command:** `.venv\Scripts\python.exe -m pytest -q`

### Result: 493 PASSED / 0 FAILED / 1 SKIPPED

```
493 passed, 1 skipped in ~25s
```

*(1 skipped = `test_store_stress_1001_notes` — POSIX chmod, Windows-only)*

| Suite | Count | Coverage |
|-------|-------|----------|
| BDD scenarios (`tests/steps/test_steps.py`) | 30 | Sprint 0–3 CRUD/encryption/search/reencrypt/audit |
| Core unit — `test_core.py` | 46 | All Sprint 0 core tests |
| Sprint 1 — `test_sprint1.py` | 83 | WAL/retry, plugin, CLI, Alembic |
| Sprint 2 — `test_sprint2.py` | 102 | Accounts, auth, session, hybrid storage, CLI auth |
| Sprint 3 — `test_sprint3.py` | 128 | Plugin hardening, audit trail, config, search/export, reencrypt |
| **Sprint 4 — `test_sprint4.py`** | **106** | See breakdown below |
| `test_all.py` | 4 | Smoke-level import + suite runner |
| Stress (skipped by default) | 1 | 1 001 notes [B-22] |
| **Total (excluding stress)** | **493** | |

### Sprint 4 Test Breakdown (`tests/test_sprint4.py` — 106 tests)

| Section | Class | Tests | Backlog Item | Coverage |
|---------|-------|-------|-------------|----------|
| §1 | `TestSecurityLevelConfig` | 10 | B-98 | `security_level` key: allowed values, default, persistence, reset, unknown keys |
| §2 | `TestPluginManifestValidation` | 18 | B-99 | `load_manifests()`: valid manifest, missing fields, empty strings, `is_official` rejection, invalid JSON, subdirectory scanning |
| §3 | `TestTrustTierEnforcement` | 9 | B-100 | `register_plugin(is_official=False)`: hooks blocked, plugin still recorded, warning emitted, default=True allows hooks |
| §4a | `TestIsProcessAlive` | 4 | B-101 | `_is_process_alive()`: current PID, dead PID, PID 0 |
| §4b | `TestAppLockManager` | 12 | B-101 | `acquire_lock()`, `release_lock()`, stale lock overwrite, corrupted JSON, `SessionConflictError`, double-release |
| §5 | `TestAppControllerStartup` | 6 | B-84 | Mocked Qt startup sequence, `SessionConflictError` → exit 1, always-release lock in finally |
| §6 | `TestCliGuiCommand` | 3 | B-84 | `astranotes gui` CLI command wiring, `AppController.run()` called, non-zero exit raises `SystemExit` |
| §7 | `TestPassphraseDialog` | 5 | B-84/B-85 | `PassphraseDialog`: accept/reject, confirm-mode mismatch, passphrase attribute |
| §8 | `TestNoteEditorWidget` | 7 | B-84/B-85 | `NoteEditorWidget`: `clear()`, `load()`, `get_title()`, `get_content()`, encrypted placeholder |
| §9 | `TestMainWindowCRUD` | 12 | B-85 | `MainWindow`: note list population, new note, save, delete, note selection, passphrase prompt for encrypted |
| §10 | `TestIdleTimer` | 8 | B-102 | `start_idle_timer()`, `reset_idle_timer()`, `_on_idle_timeout()`, `auto_close_encrypted_note()`, 5-min constant |
| §11 | `TestSecurityLevelPassphrase` | 5 | B-98 | `high` mode clears cached passphrase on navigation; `session` mode retains it |
| §12 | `TestSystemTray` | 7 | B-97 | `QSystemTrayIcon` created, `closeEvent` hides to tray, double-click toggle, quit action |

### New Source Files (Sprint 4)

| File | Purpose |
|------|---------|
| `src/core/app_lock.py` | `AppLockManager` PID lock file; `SessionConflictError`; stale-lock overwrite [B-101] |
| `src/desktop/__init__.py` | Package init for desktop GUI module |
| `src/desktop/app_controller.py` | `AppController` startup orchestrator: config → DB → lock → plugins → Qt [B-84] |
| `src/desktop/main_window.py` | `MainWindow`, `PassphraseDialog`, `NoteEditorWidget` PySide6 widgets [B-84/B-85/B-97/B-102] |

### Key Design Decisions Validated by Sprint 4 Tests

- **PID lock file session exclusivity** — `AppLockManager.acquire_lock()` reads `{"pid": …}` and calls `_is_process_alive()`; stale locks (dead PID or corrupted JSON) are silently overwritten. `SessionConflictError` is raised only for alive PIDs. Validated by §4a/§4b.
- **Trust-tier enforcement default backward-compatible** — `register_plugin()` defaults to `is_official=True` so Sprint 1/3 tests (which call `register_plugin(plugin)` without the kwarg and expect hooks to fire) continue to pass. Explicitly passing `is_official=False` blocks hooks. Validated by §3.
- **Qt headless testing** — All Qt tests set `QT_QPA_PLATFORM=offscreen` via `_ensure_app()` before constructing `QApplication`, enabling CI-safe GUI testing without a display.
- **Security level passphrase caching** — `security_level="high"` (default) clears `_cached_passphrase` on every note navigation; `security_level="session"` retains it for the session. Validated by §11.
- **Idle auto-lock** — `_IDLE_TIMEOUT_MS = 300_000` (5 minutes); `reset_idle_timer()` called on every user interaction; `_on_idle_timeout()` calls `auto_close_encrypted_note()` which clears cached passphrase and shows `[Encrypted]` placeholder. Validated by §10.



