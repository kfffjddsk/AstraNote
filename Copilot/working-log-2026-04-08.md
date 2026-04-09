# Working Log - 2026-04-08

## Summary
Expanded the AstraNotes test workflow to cover full CRUD behavior, encryption-key enforcement, load behavior, and a bounded 1000+ note stress test.

## Why
The project needed broader validation aligned with the working agreement and definition of done, especially around encrypted note handling and realistic volume testing.

## Key Decisions
- Removed the implicit default key manager from `NoteStore` so no-key loads behave explicitly.
- Preserved encrypted note records safely when a store is loaded without a key.
- Enforced passphrase verification before update and delete operations on encrypted notes.
- Added CLI regression tests for valid, invalid, encrypted, and unencrypted scenarios.
- Added a bounded stress test over 1001 notes using a temporary path to avoid unsafe hardware impact.

## Validation
- Ran targeted regression tests for core and CLI coverage.
- Restored the full `test_all.py` workflow to run the full pytest suite and BDD tests.
- Documented the new workflow in `docs/test_workflow.md`.

## BDD Migration
Migrated all CLI integration tests from imperative `test_cli_workflow.py` to BDD feature files with Gherkin scenarios.

### Changes
- Expanded 5 feature files from 14 to 17 scenarios, adding encrypted delete (correct/wrong passphrase) and encrypted update (wrong passphrase) coverage.
- Added new step definitions: `delete_note_with_passphrase`, `no_passphrase_prompt`, `passphrase_prompt`, `no_note_stored`, `no_notes_remain`, `note_still_exists`, `note_content_check`, `note_content_check_encrypted`.
- Enhanced existing Then steps to verify passphrase prompt behavior and data integrity after mutations.
- Removed `tests/test_cli_workflow.py` — all 16 imperative tests absorbed by the BDD suite.
- Simplified `test_all.py` to two pillars: unit tests (`test_core.py`) + BDD tests (`test_steps.py`).
- Updated `docs/bdd_testing.md` and `docs/test_workflow.md` to reflect BDD-first testing approach.

### Validation
- `python -m pytest -v` → 33 passed (17 BDD + 16 unit/core)
- `python test_all.py` → ALL TESTS PASSED

## Next Actions
- Push the remaining test workflow changes after review.
- Consider splitting fast and stress suites in CI if runtime becomes noticeable.
