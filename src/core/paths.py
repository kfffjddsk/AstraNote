"""Platform-appropriate data and config directory helpers.

Used by ConfigStore, AppController, and the CLI to locate user data on every
supported OS without any third-party dependency.

  Windows : ``%APPDATA%\\AstraNotes``
  macOS   : ``~/Library/Application Support/AstraNotes``
  Linux   : ``$XDG_DATA_HOME/AstraNotes`` (default ``~/.local/share/AstraNotes``)

Refs: [REQ R9.1] [D-06]
"""
from __future__ import annotations

import os
import platform
from pathlib import Path

_APP_NAME = "AstraNotes"


def platform_data_dir() -> Path:
    """Return the OS-standard user data directory for AstraNotes."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / _APP_NAME
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / _APP_NAME
    xdg = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(xdg) / _APP_NAME


def platform_config_dir() -> Path:
    """Return the OS-standard config directory for AstraNotes.

    Matches the path used by :func:`~src.core.config._default_config_path`.
    On Windows config and data share the same ``%APPDATA%\\AstraNotes`` folder.
    """
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / _APP_NAME
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / _APP_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / _APP_NAME
