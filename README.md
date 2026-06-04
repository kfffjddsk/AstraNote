# AstraNotes (Python Edition)

[![User Guide](https://img.shields.io/badge/📖_User_Guide-blue?style=for-the-badge)](#for-users)
[![Developer Guide](https://img.shields.io/badge/🔧_Developer_Guide-green?style=for-the-badge)](#for-developers)
[![License](https://img.shields.io/badge/License-Apache_2.0-orange?style=for-the-badge)](LICENSE)

AstraNotes is a secure, modular note-taking platform built in Python as a CLI-first application with a plugin ecosystem and a future GUI extension path.

> **Status: Sprint 2 complete.** Core CRUD, AES-256-GCM encryption, plugin system, WAL-mode SQLite persistence, CLI, opt-in account layer, session management, auth rate-limiting, hybrid filesystem storage, and disk-full handling are fully implemented and tested (246 tests, 100% branch coverage on all core modules).

## Vision

- Local-first encrypted note storage
- Plugin support with override mechanics (storage, encryption, commands)
- Safety-first mechanism: red-alert + typed confirmation for overrides
- Append-only audit trail and governance for security-sensitive operations (per-user logs deleted on account deletion)
- Future compatibility with a GUI layer

---

## For Users

### Install

```bash
pip install -r requirements.txt
```

### Usage

```bash
# Add a plain note
python -m src.cli --data-dir .astranotes add --title "Meeting Notes" --content "Discuss project timeline"

# Add an encrypted note (will prompt for passphrase)
python -m src.cli --data-dir .astranotes add --title "Secret" --content "Sensitive data" --encrypt

# List all notes
python -m src.cli --data-dir .astranotes list

# Get a note by UUID
python -m src.cli --data-dir .astranotes get <uuid>

# Update a note
python -m src.cli --data-dir .astranotes update <uuid> --title "Updated Title"

# Delete a note
python -m src.cli --data-dir .astranotes delete <uuid>
```

Set `ASTRANOTES_DATA_DIR` in your environment to avoid passing `--data-dir` every time:

```bash
$env:ASTRANOTES_DATA_DIR = ".astranotes"   # PowerShell
export ASTRANOTES_DATA_DIR=.astranotes      # bash/zsh
```

---

## For Developers

### Project structure

- `src/core/` — business logic
  - `notes.py` — `Note` dataclass, `DatabaseStore` (SQLite via SQLAlchemy, WAL mode, retry, hybrid filesystem storage)
  - `auth.py` — `AccountStore` (bcrypt registration/auth, rate-limiting), `SessionManager` (24h token file)
  - `security.py` — `EncryptionEngine` (AES-256-GCM + PBKDF2), `KeyManager`
  - `blob_codec.py` — length-prefixed binary blob encoder/decoder
  - `plugin_base.py` — `PluginBase` ABC, `PluginRegistry`, `discover_plugins`
- `src/cli.py` — Click CLI (`add`, `get`, `list`, `update`, `delete`, `register`, `login`, `logout`, `delete-account`)
- `plugins/` — plugin packages (auto-discovered on startup)
- `tests/` — unit, BDD, and CLI integration test suites
- `alembic/` — database migrations
- `docs/` — requirements, architecture, test evidence
- `planning/` — user stories, backlog, sprint plans, traceability matrix

### Getting started

#### 1. Set up environment (recommended)

Using a virtual environment is recommended but not required:

```bash
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate
```

#### 2. Install dependencies

```bash
pip install -r requirements.txt
```

#### 3. Run tests

```bash
# All tests
pytest -q

# Unit tests only (fast)
pytest -q -m unit

# With branch coverage report
pytest -m "unit or stress" --cov=src/core --cov-branch --cov-report=term-missing
```

#### 4. Run CLI

```bash
python -m src.cli --data-dir .astranotes add --title "Test" --content "Hello"
python -m src.cli --data-dir .astranotes list
```

### Functional milestones

1. ✅ Note CRUD with encrypted storage
2. ✅ Plugin discovery + hook system
3. ✅ Opt-in account layer — registration, login/logout, session management, rate-limiting
4. ✅ Hybrid filesystem storage for large encrypted payloads (≥5 MB threshold)
5. Override flow with explicit user consent *(planned)*
4. ✅ Test coverage for security, reliability, and governance (100% branch coverage on all core modules)
5. GUI-ready API layer (desktop or web front-end) *(planned)*

### Running the sync server (Sprint 5A.1, MVP)

The optional cloud-sync server is a FastAPI application under `src/server/`. It exposes `POST /auth/login`, `POST /sync/push`, and `GET /sync/pull?since=<ts>`. All sync endpoints require a JWT bearer token issued by `/auth/login`.

```bash
# 1. Set the JWT secret (REQUIRED in production)
$env:ASTRANOTES_JWT_SECRET = "<long-random-secret>"

# 2. Optional: override the SQLite default
$env:ASTRANOTES_SYNC_DATABASE_URL = "sqlite:///./astranotes_sync.db"
$env:ASTRANOTES_SYNC_DATA_DIR     = "./astranotes_server_data"

# 3. Launch
python -m uvicorn src.server.app:create_app --factory --host 0.0.0.0 --port 8000
```

A client connects with the existing CLI:

```bash
astranotes config set sync_server_url http://localhost:8000
astranotes sync login          # prompts username + password
astranotes sync push           # uploads notes whose synced_at is stale
astranotes sync pull           # pulls notes the server has modified since last sync
astranotes sync logout         # forgets the cached token
```

> **Status:** The Sprint 5A.1 MVP runs on SQLite without HTTPS or rate limiting and is intended for development. Postgres backend, `sslmode=require`, HTTPS enforcement, connection-pool tuning, and per-account rate limiting land in Sprint 5A.2.

### Plugin development

- Extend plugin samples in `plugins/`.
- Plugins register hooks (e.g., `post_add_note`) via `PluginRegistry`.
- Hook execution is isolated — plugin crashes are logged but do not kill the operation.
- Core security modules are immutable to plugins.
- When plugin override fails, automatically revert to core and report.

### Future GUI path

- Add `src/gui/` with shared core dependency (no duplicated logic).
- GUI can use same plugin registry and override policy.
- Focus on progressive disclosure and secure UI controls.

---

## Security and governance

- Default encryption: AES-256-GCM with PBKDF2 key derivation
- Plugin overrides can optionally provide alternate encryption providers
- Core key management never exposes raw keys to plugins
- Audit trail logs encryption, decryption, passphrase attempts, overrides, plugin loads, auth events, migration, and export
- Per-user data isolation in server mode with hashed directory names

## Plugin override policy

- Core feature overrides require explicit confirmation:
  - Show warning (red-alert)
  - Require typed confirmation: `CONFIRM OVERRIDE`
  - Persist decision in audit log

## License

Licensed under the [Apache License 2.0](LICENSE).

**Note:** Apache 2.0 permits commercial use. If you intend to restrict commercial redistribution, consider adding a Commons Clause or switching to a non-commercial license.

## Dependency Licenses

| Package | License |
|---------|---------|
| click | BSD-3-Clause |
| cryptography | Apache-2.0 / BSD-3-Clause |
| SQLAlchemy | MIT |
| Alembic | MIT |
| pytest | MIT |
| pytest-bdd | MIT |
| pytest-cov | MIT |
| jsonschema | MIT |
| fastapi | MIT |
| uvicorn | BSD-3-Clause |
| PySide6 | LGPL-3.0 |
| authlib | BSD-3-Clause |

## AI-Use Disclosure

This project uses AI assistance (GitHub Copilot) as a documented development tool. All AI-generated output is reviewed and validated by the human team member. See [docs/ai-use-disclosure.md](docs/ai-use-disclosure.md) for full details.

