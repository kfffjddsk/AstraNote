# Working Log — 2026-05-15

**Sprint:** Sprint Zero  
**Focus:** Full Sprint 0 implementation — `Note`, `DatabaseStore`, core security, BDD tests, unit tests  
**AI Pair:** GitHub Copilot (Claude Sonnet 4.6)

---

## Summary

Completed the entirety of Sprint Zero in a single session. This covers all
backlog items scoped to Sprint 0 (B-01 through B-22, B-42, B-43, B-51, B-74),
excluding CLI items (B-19, B-23) which are deferred to Sprint 1.

---

## What Was Created

### Project Structure
```
src/
  __init__.py
  core/
    __init__.py
    security.py       — EncryptionEngine + KeyManager
    blob_codec.py     — BlobCodec (length-prefixed binary blobs)
    notes.py          — Note dataclass + _NoteRow ORM + DatabaseStore
    plugin_base.py    — PluginBase ABC + PluginRegistry
plugins/
  __init__.py
tests/
  __init__.py
  conftest.py         — shared fixtures, make_encrypted_note helper
  test_core.py        — 23 unit + stress tests
  test_all.py         — convenience runner
  features/
    __init__.py
    add_notes.feature
    get_notes.feature
    list_notes.feature
    update_notes.feature
    delete_notes.feature
  steps/
    __init__.py
    test_steps.py     — all BDD step definitions
pytest.ini
```

### Test Results (final run)
```
39 passed, 1 deselected (stress) in 0.55s
```
- 22 unit tests (`@pytest.mark.unit`) + 1 stress test (`@pytest.mark.stress`)
- 17 BDD scenarios across 5 feature files (all passing)

---

## Key Decisions Made

### D-10 revisited — SQLite from Sprint 0
No JSON storage phase. SQLite via SQLAlchemy ORM from day one. The `_NoteRow`
ORM model mirrors the schema in `design.md` with one pragmatic addition:
a `content TEXT NULL` column for storing plaintext content in Sprint 0
(the official schema uses encrypted_blob for all content; this deviation is
intentional for usability before the account layer lands in Sprint 1).

### Encryption wire format
`[16B salt][12B nonce][ciphertext + 16B GCM tag]` — all embedded in the blob,
no separate `salt`/`nonce` columns used. `BlobCodec` wraps the payload in a
length-prefixed binary envelope: `[4B header_length][JSON header][payload]`.

### PBKDF2 iterations for tests
Production `EncryptionEngine` defaults to 100,000 PBKDF2 iterations. Tests use
`_TEST_ITERATIONS = 1_000` (passed via `iterations=` kwarg) to keep the suite
under 1 second.

### `parsers.re` for empty-string BDD step
`parsers.parse` (backed by the `parse` library) does not match empty `{field}`
placeholders. The "Reject a note with an empty title" scenario passes `""` for
the title, so the step definition uses `parsers.re` with `[^"]*` regex instead.

---

## Backlog Changes

- Sprint Zero section updated from "Not Started" to "Done ✅"
- Items B-42, B-43, B-51, B-74 added to Sprint Zero done list (they were
  previously in the general backlog)
- B-19, B-23 (CLI items) remain open, moved to Sprint 1
- B-21 count corrected: 23 tests (was 16 in original entry; count grew with
  thorough encryption + BlobCodec coverage)

---

## Test Suite Overview

| File | Tests | Type |
|------|-------|------|
| `tests/test_core.py` | 22 unit + 1 stress | `@pytest.mark.unit` / `@pytest.mark.stress` |
| `tests/steps/test_steps.py` | 17 BDD scenarios | `@pytest.mark.bdd` (via pytest-bdd) |
| **Total** | **40** | — |

### BDD Scenarios (17)
| Feature | Scenarios |
|---------|-----------|
| add_notes | add unencrypted, add encrypted, reject empty title |
| get_notes | get unencrypted, get encrypted+correct pass, wrong pass, not found |
| list_notes | mixed encryption, empty store |
| update_notes | update plain, not found KeyError, coexistence invariant (B-33), replace blob |
| delete_notes | delete plain, not found KeyError, delete encrypted, plain delete preserves encrypted |

---

## Environment
- Python 3.12.10
- SQLAlchemy 2.0.49
- cryptography 46.0.6
- pytest 9.0.2 + pytest-bdd 8.1.0
- click 8.3.1 (CLI — Sprint 1)
- Virtual env: `.venv\` at project root
- Run command: `.venv\Scripts\python.exe -m pytest tests/ -v -m "not stress"`

---

## Next Steps (Sprint 1)
1. Implement CLI (`src/cli/main.py`) using click
2. Wire `add`, `get`, `list`, `update`, `delete` commands to `DatabaseStore`
3. Implement `--data-dir` global option (B-19)
4. Non-zero exit codes on error (B-23)
5. Input validation at CLI boundary: null bytes, control characters (B-52)
6. Alembic schema versioning (B-65)
7. SQLite WAL mode (B-66)
