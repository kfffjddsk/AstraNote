"""Data and config directory helpers.

Both data and config are stored inside the application folder so the project
is self-contained and portable.  The ``.astranotes`` directory is created next
to the repository root (i.e. alongside ``src/``, ``tests/``, etc.).

  Data   : ``<project_root>/.astranotes/``
  Config : ``<project_root>/.astranotes/config.json``

Override either with ``--data-dir`` (CLI) or the ``data_dir`` config key (GUI),
or set the ``ASTRANOTES_DATA_DIR`` environment variable.

Refs: [REQ R9.1] [D-06]
"""
from __future__ import annotations

from pathlib import Path

# paths.py lives at src/core/paths.py  →  parent×3 = project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_APP_DIR = _PROJECT_ROOT / ".astranotes"


def platform_data_dir() -> Path:
    """Return the default data directory (inside the project folder)."""
    return _APP_DIR


def platform_config_dir() -> Path:
    """Return the default config directory (inside the project folder)."""
    return _APP_DIR
