# AstraNotes (Python Edition)

AstraNotes is a secure, modular note-taking platform built in Python as a CLI-first application with a plugin ecosystem and a future GUI extension path.

## Vision

- Local-first encrypted note storage
- Plugin support with override mechanics (storage, encryption, commands)
- Safety-first mechanism: red-alert + typed confirmation for overrides
- Immutable audit trail and governance for security-sensitive operations
- Future compatibility with a GUI layer

## Modules and structure

- `src/core/` - business logic
  - `notes.py` - Note model, `NoteStore`, encrypted persistence
  - `security.py` - `EncryptionEngine`, `KeyManager` (core, high-trust)
  - `plugin_base.py` - plugin interface + registry
  - `config.py` - settings storage and override config (future)
  - `audit.py` - append-only audit log (future)
- `src/cli.py` - command-line entrypoint
- `plugins/` - plugin packages and extensions
- `tests/` - unit test suites
- `docs/` - requirements, architecture, and governance

## Functional milestones

1. Note CRUD with encrypted storage
2. Plugin discovery + hook system
3. Override flow with explicit user consent
4. Test coverage for security, reliability, and governance
5. GUI-ready API layer (desktop or web front-end)

## Quickstart

### 1. Setup

```bash
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Clean compiled artifacts

```bash
# Windows PowerShell
Remove-Item -Recurse -Force __pycache__, *.pyc -ErrorAction SilentlyContinue
$env:PYTHONPYCACHEPREFIX = "$PWD/python_cache"

# macOS/Linux
rm -rf __pycache__ *.pyc
export PYTHONPYCACHEPREFIX="$PWD/python_cache"

mkdir -p python_cache
```

### 4. Run tests

```bash
pytest -q
```

### 5. Run CLI

```bash
python -m src.cli add --title "Test" --content "Hello"
python -m src.cli list
```

## Security and governance

- Default encryption: AES-256-GCM with PBKDF2 key derivation
- Plugin overrides can optionally provide alternate encryption providers
- Core key management never exposes raw keys to plugins
- Audit trail logs override attempts and user confirmations

## Plugin override policy

- Core feature overrides require explicit confirmation:
  - show warning (red-alert)
  - require typed override token (e.g., `OVERRIDE-ENCRYPTION`)
  - persist decision in audit log
- When plugin override fails, automatically revert to core and report

## Future GUI path

- Add `src/gui/` with shared core dependency (no duplicated logic)
- GUI can use same plugin registry and override policy
- Focus on progressive disclosure and secure UI controls

## Notes

- You can extend plugin samples in `plugins/`.
- Keep the core module stable and plugin integration safe.
- Use tests systematically as regression and acceptance criteria.

