# Behavior-Driven Testing for AstraNotes

## Overview

BDD is the primary approach for CLI testing. All CLI integration tests are Gherkin scenarios with `pytest-bdd` step definitions. Unit tests for core modules remain in `tests/test_core.py`.

## Framework

`pytest-bdd` with Gherkin syntax.

## Structure

> **Updated May 2026 (Sprint 3):** Sprint 3 is complete. All 30 BDD scenarios pass. The full suite totals 396 tests across `test_steps.py`, `test_core.py`, `test_sprint1.py`, `test_sprint2.py`, and `test_sprint3.py`. Three new feature files were added in Sprint 3: `search_notes.feature`, `reencrypt_note.feature`, and `audit_log.feature`.

```
tests/
├── features/          # .feature files describing behaviors
│   ├── add_notes.feature
│   ├── audit_log.feature       # Sprint 3
│   ├── delete_notes.feature
│   ├── get_notes.feature
│   ├── list_notes.feature
│   ├── reencrypt_note.feature  # Sprint 3
│   ├── search_notes.feature    # Sprint 3
│   └── update_notes.feature
├── steps/             # Step definitions in Python
│   └── test_steps.py
├── test_core.py       # Unit tests for core modules
└── conftest.py        # Shared fixtures
```

## Feature Files

Gherkin scenarios organized by feature:

- `add_notes.feature` – encrypted/unencrypted add, invalid input
- `audit_log.feature` – audit entries for add/delete/login/export *(Sprint 3)*
- `list_notes.feature` – mixed encryption list, empty list
- `get_notes.feature` – passphrase validation, wrong key, missing note
- `update_notes.feature` – correct/wrong passphrase, missing note
- `delete_notes.feature` – correct/wrong passphrase, missing note
- `search_notes.feature` – plain search, encrypted alias match, per-note passphrase prompt, wrong-passphrase fallback *(Sprint 3)*
- `reencrypt_note.feature` – passphrase rotation success, wrong-passphrase rejection *(Sprint 3)*

## Step Definitions

`tests/steps/test_steps.py` implements steps:

- `@given` – preconditions (create notes, clean state)
- `@when` – CLI actions (add, get, list, update, delete)
- `@then` – assertions (exit codes, output, prompts, data integrity)

## Running BDD Tests

### All BDD Tests
```bash
pytest tests/steps/test_steps.py -v
```

### Individual Scenario
```bash
pytest tests/steps/test_steps.py::test_add_unencrypted_note -v
```

### Full Suite (unit + BDD)
```bash
pytest -v
```

### Via test_all.py
```bash
python test_all.py
```

## Test Coverage

### BDD — 30 scenarios across 8 feature files

1. **Add (3)** – unencrypted, encrypted, reject empty title
2. **Get (4)** – unencrypted, correct passphrase decrypt, wrong passphrase (`InvalidTag`), not found
3. **List (2)** – mixed encryption (content always hidden in listing), empty store
4. **Update (4)** – unencrypted, not found (`KeyError`), co-existence invariant [B-33], replace encrypted blob
5. **Delete (4)** – unencrypted, not found (`KeyError`), encrypted, plain delete preserves encrypted [B-33]
6. **Search (7)** *(Sprint 3)* – plain text match, encrypted alias match, `--encrypted` per-note passphrase prompt, wrong passphrase fallback to alias, skip empty passphrase, duplicate deduplication, no results
7. **Reencrypt (2)** *(Sprint 3)* – passphrase rotation roundtrip, wrong current passphrase rejection
8. **Audit log (4)** *(Sprint 3)* – audit entries for add/delete/login/export events

### Unit — 39 tests in `tests/test_core.py`

| Group | Count | What it covers |
|-------|-------|----------------|
| Note dataclass | 6 | UUID, `modified_at`, no-op update, empty title, whitespace content, update variants |
| DatabaseStore add/get | 5 | persistence, encrypted blob, placeholder title |
| DatabaseStore update | 5 | unencrypted, encrypted (blob replace, content ignored), content-only, not-found |
| DatabaseStore delete | 2 | remove, not-found |
| DatabaseStore list | 3 | empty store, mixed encryption, account_id routing |
| Co-existence invariant | 1 | unencrypted update leaves encrypted blob intact [B-33] |
| Encryption / BlobCodec | 10 | AES-256-GCM roundtrip, public derive_key, wrong passphrase, BlobCodec encode/decode, blob-too-short, truncated-body, full pipeline; KeyManager short/empty/whitespace passphrase |
| **Injection hardening** | **7** | see section below |

### Stress — 1 test

`test_store_stress_1001_notes` — 1 001 notes add/list/delete; `list()` must complete in < 0.5 s.
Run with `pytest -m stress`.

## Injection-Hardening Tests

Added 2026-05-15 to cover OWASP A03 (Injection) and A08 (Software and Data Integrity Failures).
All 7 tests are `@pytest.mark.unit` in `tests/test_core.py`.

| Test | Surface | Attack prevented |
|------|---------|------------------|
| `test_note_create_rejects_null_byte_in_title` | `Note.create()` | Null-byte injection in SQLite TEXT — C-string truncation in DB drivers |
| `test_note_create_rejects_null_byte_in_content` | `Note.create()` | Same for content column |
| `test_note_update_rejects_null_byte_in_title` | `Note.update()` | Same via update path |
| `test_note_update_rejects_null_byte_in_content` | `Note.update()` | Same for content via update |
| `test_blobcodec_decode_rejects_oversized_header` | `BlobCodec.decode()` | DoS — 4-byte length field can claim ~4 GB; capped at 64 KiB |
| `test_blobcodec_decode_rejects_non_dict_header` | `BlobCodec.decode()` | JSON type confusion — crafted blob with array/number header causes `KeyError` downstream |
| `test_encryption_decrypt_rejects_short_ciphertext` | `EncryptionEngine.decrypt()` | Truncated salt fed to PBKDF2 before `InvalidTag` — now fails fast with `ValueError` |

Additional hardening (no separate test, covered by existing path tests):
- `DatabaseStore.__init__` resolves the path with `Path.resolve()` (path traversal) and builds the SQLAlchemy connection URL with `URL.create()` instead of an f-string (URL injection).

## Best Practices

1. **Descriptive Scenarios** – Describe user behavior clearly.
2. **Reusable Steps** – Generic steps shared across features.
3. **Data Isolation** – Temp directories via `conftest.py`; each test gets a fresh `DatabaseStore`.
4. **Passphrase Checks** – Every encryption scenario asserts `InvalidTag` on wrong passphrase.
5. **Content Checks** – Verify data integrity after mutations.
6. **Error Paths** – Test success and failure (ValueError, KeyError, InvalidTag).
7. **Injection Hardening** – Dedicated tests for null bytes, oversized blobs, and type confusion.

## Dependencies

pytest-bdd, pytest, cryptography, sqlalchemy

```bash
pip install -r requirements.txt
```