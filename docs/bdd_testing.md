# BDD Testing for AstraNotes

## Overview

AstraNotes uses Behavior-Driven Development (BDD) as the primary approach for testing user-facing CLI behavior. All CLI integration tests are written as Gherkin scenarios with step definitions implemented via `pytest-bdd`. Unit tests for core modules (Note, NoteStore, EncryptionEngine) remain in `tests/test_core.py`.

## Framework

We use `pytest-bdd` with Gherkin syntax for writing feature files.

## Structure

```
tests/
├── features/          # .feature files describing behaviors
│   ├── add_notes.feature
│   ├── get_notes.feature
│   ├── list_notes.feature
│   ├── update_notes.feature
│   └── delete_notes.feature
├── steps/             # Step definitions in Python
│   └── test_steps.py
├── test_core.py       # Unit tests for core modules
└── conftest.py        # Shared fixtures
```

## Feature Files

Feature files are written in Gherkin syntax and describe user scenarios:

- `add_notes.feature` – Adding encrypted and unencrypted notes, invalid input rejection
- `list_notes.feature` – Listing notes with proper encryption handling, empty list
- `get_notes.feature` – Retrieving notes with passphrase validation, wrong key, missing note
- `update_notes.feature` – Updating notes with correct/wrong passphrase, missing note
- `delete_notes.feature` – Deleting notes with correct/wrong passphrase, missing note

## Step Definitions

Step definitions in `tests/steps/test_steps.py` implement the Gherkin steps using pytest-bdd decorators:

- `@given` – Set up test preconditions (create notes, ensure clean state)
- `@when` – Perform CLI actions (add, get, list, update, delete)
- `@then` – Verify outcomes (exit codes, output content, passphrase prompts, data integrity)

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

BDD tests cover 17 scenarios across 5 feature files:

1. **Add Notes (3 scenarios)**
   - Unencrypted note – no passphrase prompt
   - Encrypted note – passphrase prompt
   - Invalid input – rejected, nothing stored

2. **Get Notes (4 scenarios)**
   - Unencrypted note – no passphrase prompt, full content
   - Encrypted with correct passphrase – decrypted content
   - Encrypted with wrong passphrase – error, non-zero exit
   - Non-existent note – not-found error

3. **List Notes (2 scenarios)**
   - Mixed encrypted/unencrypted – hides encrypted content, no passphrase prompt
   - Empty store – no-notes message

4. **Update Notes (4 scenarios)**
   - Unencrypted note – no passphrase prompt, content verified after
   - Encrypted with correct passphrase – content verified after
   - Encrypted with wrong passphrase – rejected, original content preserved
   - Non-existent note – error

5. **Delete Notes (4 scenarios)**
   - Unencrypted note – no passphrase prompt, note removed
   - Encrypted with correct passphrase – note removed
   - Encrypted with wrong passphrase – rejected, note preserved
   - Non-existent note – error

## Best Practices

1. **Descriptive Scenarios** – Write scenarios that clearly describe user behavior
2. **Reusable Steps** – Create generic step definitions that can be reused across features
3. **Data Isolation** – Use temporary directories via `conftest.py` fixtures
4. **Passphrase Verification** – Every scenario explicitly asserts whether a passphrase prompt appeared
5. **Content Verification** – Verify data integrity after mutations (update/delete)
6. **Error Handling** – Test both success and failure paths with exit code assertions

## Dependencies

- pytest-bdd
- pytest
- click (for CLI testing)

Install with:
```bash
pip install -r requirements.txt
```