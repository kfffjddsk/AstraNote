# AstraNotes

[![User Guide](https://img.shields.io/badge/📖_User_Guide-blue?style=for-the-badge)](#for-users)
[![Developer Guide](https://img.shields.io/badge/🔧_Developer_Guide-green?style=for-the-badge)](#for-developers)
[![License](https://img.shields.io/badge/License-Apache_2.0-orange?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-671_passing-brightgreen?style=for-the-badge)](#running-tests)

AstraNotes is a secure, local-first note-taking platform built in Python. It works as a CLI tool, a PySide6 desktop application, and an optional cloud-sync service — all sharing the same encrypted SQLite core. A plugin system lets you extend note formats (rich text, voice, video) without touching core logic.

---

## Table of Contents

- [For Users](#for-users)
  - [Install](#install)
  - [Launch the Desktop GUI](#launch-the-desktop-gui)
  - [CLI Quick Start](#cli-quick-start)
  - [Encrypted Notes](#encrypted-notes)
  - [Cloud Sync](#cloud-sync)
  - [Configuration](#configuration)
  - [Plugin Admin](#plugin-admin)
- [For Developers](#for-developers)
  - [Project Structure](#project-structure)
  - [Getting Started](#getting-started)
  - [Running Tests](#running-tests)
  - [Running the Sync Server](#running-the-sync-server)
  - [Writing a Plugin](#writing-a-plugin)
  - [Architecture Overview](#architecture-overview)
- [Security](#security)
- [License](#license)

---

## For Users

### Install

Python 3.11+ is required.

```bash
# Clone the repository
git clone <repo-url>
cd AstraNotes

# Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
# source .venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

### Launch the Desktop GUI

```bash
python -m src.cli gui
```

The GUI opens a multi-tab note editor with support for rich text (Tiptap), voice notes, and video notes. All notes are stored locally in an encrypted SQLite database.

**First launch** creates a `.astranotes/` directory inside the project folder. You can override this with `--data-dir` or the `ASTRANOTES_DATA_DIR` environment variable.

### CLI Quick Start

Every command accepts `--data-dir <path>` to choose a custom data location. Set `ASTRANOTES_DATA_DIR` in your environment to skip typing it every time:

```bash
# PowerShell
$env:ASTRANOTES_DATA_DIR = ".astranotes"
# bash / zsh
export ASTRANOTES_DATA_DIR=.astranotes
```

| Task | Command |
|------|---------|
| Add a note | `python -m src.cli add --title "Meeting" --content "Agenda…"` |
| List notes | `python -m src.cli list` |
| Read a note | `python -m src.cli get <id>` |
| Update a note | `python -m src.cli update <id> --title "New title"` |
| Delete a note | `python -m src.cli delete <id>` |
| Search | `python -m src.cli search "keyword"` |
| Export | `python -m src.cli export --format json --out notes.json` |
| View audit log | `python -m src.cli audit` |

### Encrypted Notes

Notes can be encrypted with AES-256-GCM. You are prompted for a passphrase at creation and again when reading.

```bash
# Add an encrypted note (prompts for passphrase)
python -m src.cli add --title "Journal" --content "Private entry" --encrypt

# Re-encrypt with a new passphrase
python -m src.cli reencrypt <id>
```

In the GUI, click the **lock icon** when creating a new note, or press the unlock button on an existing encrypted note to enter your passphrase.

### Cloud Sync

AstraNotes includes an optional FastAPI sync server. Once running, connect from the CLI:

```bash
# Point the client at the server
python -m src.cli config set sync_server_url http://localhost:8000

# Authenticate
python -m src.cli sync login

# Push local notes to the server
python -m src.cli sync push

# Pull notes from the server
python -m src.cli sync pull

# Log out (token is forgotten; local notes are kept)
python -m src.cli sync logout
```

In the GUI, use **Account → Connect to Sync Server** to log in, then the toolbar sync button to push/pull.

### Configuration

All settings are stored in a JSON file at the OS-standard config location:

| Location | Path |
|----------|------|
| All platforms | `<project_root>/.astranotes/config.json` |

Manage settings with the `config` command:

```bash
python -m src.cli config list              # show all keys and values
python -m src.cli config set theme dark    # change a setting
python -m src.cli config get font_size     # read a setting
python -m src.cli config reset theme       # restore default
```

**Available keys:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `theme` | `str` | `light` | UI theme: `light` or `dark` |
| `font_size` | `int` | `12` | Editor font size in pt |
| `font_family` | `str` | *(system)* | Editor font family |
| `accent_color` | `str` | `purple` | Accent colour for buttons and highlights |
| `word_wrap` | `str` | `yes` | `yes` / `no` |
| `data_dir` | `str` | `.astranotes/` *(project root)* | Notes database location |
| `default_encrypt` | `str` | `no` | Encrypt new notes by default: `yes` / `no` |
| `security_level` | `str` | `high` | `high` clears cached passphrase when switching notes |
| `auto_login` | `str` | `no` | Restore the last session automatically on launch |
| `sync_server_url` | `str` | *(empty)* | URL of your sync server |
| `sync_auto_interval` | `int` | `0` | Auto-sync every N seconds (0 = off) |
| `gpu_acceleration` | `str` | `no` | `yes` to enable GPU for the web editor (can fix rendering on some GPUs) |
| `plugin_dir` | `str` | `~/.astranotes/plugins` | Directory for user-installed plugins |
| `allowed_plugins` | `list` | *(all)* | Plugin names that may load; empty = all allowed |

### Plugin Admin

Open **Tools → Plugins Admin** in the GUI to see all installed plugins, enable or disable them, and browse the supported note formats.

- **Installed** tab — check or uncheck a plugin, then click **Apply** to commit.
  Disabling a plugin that has a note currently open is blocked until that tab is closed.
- **Supported formats** tab — lists all formats the active plugins can handle.
- Disabling a plugin persists across restarts; the plugin instance stays visible so you can re-enable it at any time.

---

## For Developers

### Project Structure

```
AstraNotes/
├── src/
│   ├── cli.py                  # Click CLI entry point
│   ├── core/                   # Business logic (no Qt, no FastAPI)
│   │   ├── note.py             # Note dataclass
│   │   ├── notes.py            # DatabaseStore — SQLite via SQLAlchemy, WAL mode
│   │   ├── store.py            # Abstract NoteStore protocol
│   │   ├── security.py         # EncryptionEngine (AES-256-GCM + PBKDF2)
│   │   ├── auth.py             # AccountStore, SessionManager
│   │   ├── config.py           # ConfigStore — typed key/value settings
│   │   ├── audit.py            # Append-only audit log
│   │   ├── plugin_base.py      # PluginBase ABC, PluginRegistry
│   │   ├── plugin_context.py   # PluginContext (sandboxed API for plugins)
│   │   ├── plugin_security.py  # AST-based import scanner
│   │   ├── editor_protocol.py  # EditorProtocol interface
│   │   ├── container.py        # Binary container framing
│   │   ├── blob_codec.py       # Length-prefixed blob encoder/decoder
│   │   ├── sync_client.py      # HTTP sync client
│   │   ├── app_lock.py         # Single-instance PID lock
│   │   └── paths.py            # OS-specific data/config paths
│   ├── desktop/                # PySide6 desktop GUI
│   │   ├── app_controller.py   # Startup orchestrator
│   │   ├── main_window.py      # MainWindow — tabs, note list, toolbar
│   │   ├── note_editor.py      # PluginEditorHost widget
│   │   ├── plugin_loader.py    # Plugin discovery, consent, and registration
│   │   ├── plugins_dialog.py   # Plugin Admin dialog
│   │   ├── dialogs.py          # New-note, export, passphrase dialogs
│   │   ├── settings_dialog.py  # Settings dialog
│   │   ├── theme.py            # Qt stylesheet generation
│   │   └── sync/               # Sync UI (worker thread, merge window, login)
│   ├── server/                 # FastAPI cloud-sync server
│   │   ├── app.py              # Application factory
│   │   ├── main.py             # Uvicorn entry point
│   │   ├── routers/            # Auth + sync endpoints
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   ├── security.py         # JWT helpers
│   │   ├── rate_limit.py       # Per-account rate limiting
│   │   └── settings.py         # Server config (env vars)
│   └── plugins/                # Bundled plugin packages
│       ├── tiptap_plugin/      # Rich-text editor (Tiptap + ProseMirror)
│       ├── voice_plugin/       # Microphone recording + audio playback
│       └── video_plugin/       # Webcam recording + video playback
├── tests/                      # 671 tests — unit, BDD, CLI integration
├── planning/                   # Backlog, PRD, requirements, design, traceability
├── Copilot/                    # Sprint plans, working agreement, discussion list
├── docs/                       # Architecture, AI-use disclosure
├── alembic/                    # Database migrations
└── requirements.txt
```

### Getting Started

#### 1. Set up environment

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

#### 2. Run the GUI

```bash
python -m src.cli gui
```

#### 3. Run the CLI

```bash
python -m src.cli --help
python -m src.cli add --title "Test" --content "Hello world"
python -m src.cli list
```

### Running Tests

```bash
# Full suite
python -m pytest tests/ -q

# Fast (no GUI) tests only
python -m pytest tests/ -q -m "not gui"

# With branch coverage
python -m pytest tests/ -q --cov=src/core --cov-branch --cov-report=term-missing
```

The test suite currently passes **671 tests** (1 skipped — requires a live microphone).

### Running the Sync Server

The sync server is a FastAPI app that stores notes in SQLite (or Postgres in production).

```bash
# Required: set a long random JWT secret
$env:ASTRANOTES_JWT_SECRET = "change-me-in-production"

# Optional overrides
$env:ASTRANOTES_SYNC_DATABASE_URL = "sqlite:///./astranotes_sync.db"
$env:ASTRANOTES_SYNC_DATA_DIR     = "./astranotes_server_data"

# Launch
python -m uvicorn src.server.app:create_app --factory --host 0.0.0.0 --port 8000
```

The server exposes:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | Create an account |
| `POST` | `/auth/login` | Get a JWT bearer token |
| `POST` | `/sync/push` | Upload notes (requires token) |
| `GET` | `/sync/pull` | Download notes since `?since=<ts>` (requires token) |

For production: add HTTPS (`--ssl-keyfile` / `--ssl-certfile`), switch to Postgres (`ASTRANOTES_SYNC_DATABASE_URL=postgresql://...`), and set `ASTRANOTES_SYNC_DATABASE_URL` to a connection pool URL.

### Writing a Plugin

Plugins live in their own subdirectory under `src/plugins/` (bundled) or `~/.astranotes/plugins/` (user-installed). Each plugin directory needs:

1. **`plugin.json`** — manifest
2. **A `.py` file** — implementation

#### Minimal manifest (`plugin.json`)

```json
{
  "plugin_id": "my_plugin",
  "name": "MyPlugin",
  "version": "1.0.0",
  "author": "You",
  "description": "What this plugin does.",
  "engines": { "astranotes": ">=5.0" },
  "main": "my_plugin.py",
  "mime_types": ["application/x-myplugin"],
  "permissions": [],
  "verified": false
}
```

Set `"verified": true` only for bundled plugins shipped with the app; user-installed plugins must go through the consent dialog.

#### Minimal implementation

```python
from src.core.plugin_base import PluginBase, PluginRegistry
from src.core.plugin_context import PluginContext

class MyPlugin(PluginBase):
    name    = "MyPlugin"
    version = "1.0.0"
    mime_types = ["application/x-myplugin"]

    # Advertise a note-format entry in the New Note dialog
    provides_formats = [
        ("My Format", "application/x-myplugin", "A short description."),
    ]

    def register_hooks(self, registry: PluginRegistry) -> None:
        # Optional: registry.register_hook("post_add_note", self._on_add)
        pass

    def initialize(self, context: PluginContext) -> None:
        context.log("MyPlugin ready.")

    def create_editor(self):
        from my_editor_widget import MyEditorWidget
        return MyEditorWidget()
```

#### How plugins are loaded

1. `plugin_loader.py` discovers every subdirectory under the plugin dir.
2. The manifest is validated against the JSON schema.
3. Python imports in the plugin file are scanned with AST analysis — any import not declared in `permissions` blocks the plugin.
4. Unverified plugins trigger a consent dialog on first load; consent is stored in config.
5. The plugin class is instantiated, `initialize()` is called, and `register_plugin()` is called on the registry.
6. The `allowed_plugins` config key (managed via Plugin Admin) controls which plugins are activated on each launch.

#### Plugin API surface

Plugins may only call:

- `PluginContext.log(msg)` — structured logging
- `PluginContext.get_config(key)` / `PluginContext.set_config(key, value)` — plugin-scoped config
- `PluginRegistry.register_hook(name, fn)` — subscribe to core events (`post_add_note`, `post_update_note`, `post_delete_note`)
- The `EditorProtocol` interface — implement `create_editor()` to return a Qt widget

Plugins never receive a reference to `DatabaseStore`, `EncryptionEngine`, or `SessionManager`. Core security modules are sealed off.

### Architecture Overview

AstraNotes uses a **three-layer additive model**:

```
Layer 3 ── Cloud Sync (FastAPI server + desktop sync UI)
               ↕  REST / JWT
Layer 2 ── Account Layer (AccountStore, SessionManager, OAuth)
               ↕  internal API
Layer 1 ── Local Core (DatabaseStore, EncryptionEngine, PluginRegistry)
```

Each layer is optional — the app is fully functional as a local, guest-mode note store without layers 2 or 3.

**Key design decisions:**

- **CLI-first**: all features available via CLI; GUI is an additive layer on top.
- **Plugin isolation**: plugins run in the same process but receive a `PluginContext` that limits what they can touch. AST-level import scanning at load time blocks undeclared dangerous imports.
- **Encryption at rest**: notes are encrypted before being written to SQLite. The passphrase never leaves memory and is not stored anywhere.
- **WAL mode**: SQLite is opened in Write-Ahead Log mode for concurrent read/write and crash safety.
- **Single-instance lock**: `AppLockManager` uses a PID file to prevent two GUI processes from opening the same database simultaneously.
- **Startup order**: config → database → PID lock → manifests → Qt app + window → plugins → note list. Plugins load *after* the window is shown to avoid blocking the splash.

---

## Security

| Feature | Detail |
|---------|--------|
| Encryption | AES-256-GCM with a random 12-byte nonce per note |
| Key derivation | PBKDF2-HMAC-SHA256, 600 000 iterations, 16-byte random salt |
| Plugin sandboxing | AST import scan; dangerous modules blocked unless declared in manifest permissions |
| Audit log | Append-only log of encryption, auth, plugin load, export, and sync events |
| Auth rate limiting | Failed login attempts are rate-limited per account |
| Session tokens | 24-hour local session file; deleted on logout and on startup unless auto-login is on |
| JWT (server) | HS256 tokens with configurable expiry; secret must be set via environment variable |

---

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

## License

Licensed under the [Apache License 2.0](LICENSE).

## AI-Use Disclosure

This project uses AI assistance (GitHub Copilot / Claude Code) as a documented development tool. All AI-generated output is reviewed and validated by the human team member. See [docs/ai-use-disclosure.md](docs/ai-use-disclosure.md) for full details.
