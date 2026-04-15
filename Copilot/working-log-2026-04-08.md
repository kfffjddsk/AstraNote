# Working Log - 2026-04-08

## Summary
Expanded test coverage: full CRUD, encryption-key enforcement, load behavior, 1000+ note stress test.

## Why
Broader validation needed for encrypted note handling and volume testing per working agreement and DoD.

## Key Decisions
- Removed implicit default key manager from `NoteStore`.
- Encrypted records preserved on no-key load.
- Passphrase verified before update/delete on encrypted notes.
- CLI regression tests cover valid, invalid, encrypted, unencrypted.
- Bounded stress test (1001 notes) uses temp path for safety.

## Validation
- Ran core and CLI regression tests.
- `test_all.py` runs full pytest + BDD suite.
- Documented in `docs/test_workflow.md`.

## BDD Migration
Migrated CLI integration tests from imperative `test_cli_workflow.py` to BDD Gherkin scenarios.

### Changes
- Expanded 5 feature files: 14 → 17 scenarios (added encrypted delete/update wrong-passphrase).
- Added steps: `delete_note_with_passphrase`, `no_passphrase_prompt`, `passphrase_prompt`, `no_note_stored`, `no_notes_remain`, `note_still_exists`, `note_content_check`, `note_content_check_encrypted`.
- Enhanced Then steps for passphrase prompt and data integrity checks.
- Removed `tests/test_cli_workflow.py` (16 tests absorbed by BDD).
- Simplified `test_all.py` to unit + BDD pillars.
- Updated `docs/bdd_testing.md` and `docs/test_workflow.md`.

### Validation
- `python -m pytest -v` → 33 passed (17 BDD + 16 unit/core)
- `python test_all.py` → ALL TESTS PASSED

## Next Actions
- Push remaining changes after review.
- Consider splitting fast/stress suites in CI.
