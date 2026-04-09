# Test Workflow

## Testing Strategy

AstraNotes follows a BDD-first testing approach:

- **BDD tests** (`tests/steps/test_steps.py`) — 17 Gherkin scenarios covering all CLI CRUD behavior. This is the primary layer for verifying user-facing functionality.
- **Unit tests** (`tests/test_core.py`) — 16 tests covering core modules (Note, NoteStore, EncryptionEngine, KeyManager) and a bounded stress test.

All CLI integration tests are written as Gherkin feature files in `tests/features/` with step definitions in `tests/steps/test_steps.py`. There are no imperative CLI test files.

## BDD Scenario Coverage

| Feature | Scenarios | Key assertions |
|---------|-----------|----------------|
| Add Notes | 3 | passphrase prompt behavior, invalid input rejection, empty store after invalid |
| Get Notes | 4 | correct/wrong passphrase, no-prompt for unencrypted, not-found error |
| List Notes | 2 | encrypted content hidden, no passphrase prompt, empty-list message |
| Update Notes | 4 | content verified after update, wrong passphrase preserves original, no-prompt for unencrypted |
| Delete Notes | 4 | note removed/preserved, wrong passphrase blocked, no-prompt for unencrypted |

## Encryption Rules

Encrypted note actions must request a passphrase when the action can reveal or modify encrypted data:
- add encrypted notes requires a passphrase
- get encrypted notes requires a passphrase
- update encrypted notes requires a passphrase
- delete encrypted notes requires a passphrase
- list does not request a passphrase and must hide encrypted note details
- unencrypted note actions do not request a passphrase

## Stress Test Safety

The stress test uses a temporary workspace and a bounded dataset of 1001 notes.
It validates that the store can add, reload, and delete over 1000 notes without leaving corrupted persisted data.
This test is marked with `stress` so it can be run explicitly if needed, but it remains small enough for safe local execution in the normal suite.

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
