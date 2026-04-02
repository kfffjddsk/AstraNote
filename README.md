# AstraNotes (Python Edition)

AstraNotes is a secure, modular note-taking application originally scoped as a C++ engineering project, now implemented in Python for rapid development and testability.

## Project goals

- Local-first note storage
- Plugin architecture (Text, Voice, Secure, etc.)
- Note history and version tracking
- Encryption for private notes at rest
- Unit tests with `pytest`
- MVC-like separation (model/business, controllers, optional UI)

## Repository layout

- `src/` - core application logic
- `tests/` - unit tests (`pytest`)
- `plugins/` - plugin definitions/implementations
- `docs/` - architecture docs, UML, charters, etc.
- `Requirments/` - project charter and requirements source

## Quick start

1. Create a venv:

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows
source .venv/bin/activate       # macOS/Linux
```

2. Install dependencies:

```bash
pip install -r requirements.txt  # add this file to repo root
```

3. Clean old compiled artifacts and set isolated cache:

```bash
# on Windows PowerShell
Remove-Item -Recurse -Force __pycache__, *.pyc -ErrorAction SilentlyContinue
$env:PYTHONPYCACHEPREFIX = "$PWD/python_cache"

# on macOS/Linux
rm -rf __pycache__ *.pyc
export PYTHONPYCACHEPREFIX="$PWD/python_cache"

mkdir -p python_cache
```

4. Run tests:

```bash
pytest -q
```

## Security notes

- Avoid storing plaintext secrets in source
- Use AESCipher symmetric encryption for private notes
- Keep user keys secure in local secure storage

## Project workflow

1. Draft model interfaces (`Note`, `NoteStore`, `EncryptionEngine`)
2. Implement and test feature stubs (add, update, delete, history)
3. Add plugin layer with explicit contract classes
4. Add CLI/GUI entrypoints

## Optional future features

- Sync to cloud using encrypted blobs
- Markdown rendering + preview
- Multi-user profile vaults
- Search with full-text indexing
