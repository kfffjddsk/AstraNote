# AstraNotes (Python Edition)

AstraNotes is a secure, modular note-taking platform built in Python as a CLI-first application with a plugin ecosystem and a future GUI extension path.

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
python -m src.cli add --title "Meeting Notes" --content "Discuss project timeline"
python -m src.cli list
python -m src.cli get 1
python -m src.cli update 1 --title "Updated Title"
python -m src.cli delete 1
```

### Encrypt a note

```bash
python -m src.cli add --title "Secret" --content "Sensitive data" --encrypt yes
```

You will be prompted for a passphrase. Encrypted notes require the passphrase to view, update, or delete.

### Search and export

```bash
python -m src.cli search "meeting"
python -m src.cli export --format json --output notes.json
```

---

## For Developers

### Project structure

- `src/core/` — business logic
  - `notes.py` — Note model, `NoteStore`, encrypted persistence
  - `security.py` — `EncryptionEngine`, `KeyManager` (core, high-trust)
  - `plugin_base.py` — plugin interface + registry
  - `config.py` — settings storage and override config (future)
  - `audit.py` — append-only audit log (future)
- `src/cli.py` — command-line entrypoint
- `plugins/` — plugin packages and extensions
- `tests/` — unit and BDD test suites
- `docs/` — requirements, architecture, and governance
- `planning/` — user stories, requirements, backlog, sprint plans

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
pytest -q
```

#### 4. Run CLI

```bash
python -m src.cli add --title "Test" --content "Hello"
python -m src.cli list
```

### Functional milestones

1. Note CRUD with encrypted storage
2. Plugin discovery + hook system
3. Override flow with explicit user consent
4. Test coverage for security, reliability, and governance
5. GUI-ready API layer (desktop or web front-end)

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
| pytest | MIT |
| pytest-bdd | MIT |
| python-docx | MIT |

Future dependencies (not yet in `requirements.txt`):

| Package | License |
|---------|---------|
| SQLAlchemy | MIT |
| Alembic | MIT |
| bcrypt | Apache-2.0 |
| psycopg2-binary | LGPL |

## AI-Use Disclosure

This project uses AI assistance (GitHub Copilot) as a documented development tool. All AI-generated output is reviewed and validated by the human team member. See [docs/ai-use-disclosure.md](docs/ai-use-disclosure.md) for full details.

