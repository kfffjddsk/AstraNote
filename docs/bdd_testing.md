# Behavior-Driven- Testing for AstraNotes

## Overview

BDD is the primary approach for CLI testing. All CLI integration tests are Gherkin scenarios with `pytest-bdd` step definitions. Unit tests for core modules remain in `tests/test_core.py`.

## Framework

`pytest-bdd` with Gherkin syntax.

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

Gherkin scenarios organized by feature:

- `add_notes.feature` – encrypted/unencrypted add, invalid input
- `list_notes.feature` – mixed encryption list, empty list
- `get_notes.feature` – passphrase validation, wrong key, missing note
- `update_notes.feature` – correct/wrong passphrase, missing note
- `delete_notes.feature` – correct/wrong passphrase, missing note

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

17 scenarios across 5 feature files:

1. **Add (3)** – unencrypted, encrypted, invalid input
2. **Get (4)** – unencrypted, correct/wrong passphrase, not found
3. **List (2)** – mixed encryption, empty store
4. **Update (4)** – unencrypted, correct/wrong passphrase, not found
5. **Delete (4)** – unencrypted, correct/wrong passphrase, not found

## Best Practices

1. **Descriptive Scenarios** – Describe user behavior clearly.
2. **Reusable Steps** – Generic steps shared across features.
3. **Data Isolation** – Temp directories via `conftest.py`.
4. **Passphrase Checks** – Every scenario asserts prompt behavior.
5. **Content Checks** – Verify data integrity after mutations.
6. **Error Paths** – Test success and failure with exit code assertions.

## Dependencies

pytest-bdd, pytest, click

```bash
pip install -r requirements.txt
```