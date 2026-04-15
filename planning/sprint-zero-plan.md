# AstraNotes — Sprint Zero Plan

## Goal
Establish project foundation: architecture, tooling, tests, docs, agreements.

## Duration
1 sprint (1 week)

## Deliverables

### 1. Project Setup
- [x] Python project structure (`src/`, `tests/`, `plugins/`, `docs/`)
- [x] Virtual environment with pinned dependencies (`requirements.txt`)
- [x] `pytest.ini` configured with test paths and markers

### 2. Core Architecture
- [x] `Note` data model with timestamps, metadata, encryption flag
- [x] `NoteStore` for JSON-based persistence with save-on-mutate
- [x] `EncryptionEngine` (AES-256-GCM) and `KeyManager`
- [x] `PluginBase` and `PluginRegistry` for hook-based extensibility

### 3. CLI Foundation
- [x] Click-based CLI with `add`, `get`, `list`, `update`, `delete`
- [x] Global `--data-dir` option
- [x] Input validation and non-zero exit codes on errors

### 4. Testing Infrastructure
- [x] `conftest.py` with shared fixtures (runner, temp dir, cli_app)
- [x] BDD feature files for all CRUD + encryption scenarios (17 scenarios)
- [x] Unit tests for core modules (16 tests)
- [x] Bounded stress test (1001 notes)
- [x] `test_all.py` runner (unit + BDD pillars)

### 5. Documentation & Process
- [x] Working Agreement in `Copilot/`
- [x] Definition of Done in `Copilot/`
- [x] BDD testing guide in `docs/`
- [x] Test workflow in `docs/`
- [x] Git pushing rules and writing style norms

### 6. Planning Artifacts
- [x] Requirements (`planning/requirements.md`)
- [x] User stories with acceptance criteria (`planning/user-stories.md`)
- [x] Product backlog (`planning/backlog.md`)
- [x] Sprint zero plan (`planning/sprint-zero-plan.md`)

## Exit Criteria
- 33 tests pass (`pytest -v`).
- `test_all.py` green.
- Clean working tree, all pushed.
- B-01 through B-23 done.
- Agreements and planning docs committed.

## Next Sprint Candidates
- B-24: Override policy (US-5)
- B-25: Audit trail (US-6)
- B-28: Plugin CLI commands (US-4)
