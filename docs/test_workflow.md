# Test Workflow

## Testing Strategy

BDD-first approach:

- **BDD** (`tests/steps/test_steps.py`) — 17 Gherkin scenarios for all CLI CRUD behavior.
- **Unit** (`tests/test_core.py`) — 16 tests for core modules + bounded stress test.

All CLI tests are Gherkin features in `tests/features/`. No imperative CLI test files.

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
