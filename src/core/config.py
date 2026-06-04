"""Configuration module for AstraNotes.

Settings stored at the OS-standard path:
  Windows : ``%APPDATA%\\astranotes\\config.json``
  POSIX   : ``~/.config/astranotes/config.json``

Config is separate from ``data_dir``; moving ``--data-dir`` does not move
the config file.  ``DATABASE_URL`` is never stored here — accepted from
environment variable only.  [D-06] [REQ R9.1, R9.6]

Refs: [BL B-26, B-69] [REQ R9.1–R9.6] [US-7]
"""
from __future__ import annotations

import json
import logging
import os
import platform
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known configuration keys  [REQ R9.3]
# ---------------------------------------------------------------------------

ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "allowed_plugins",
        "close_behavior",
        "data_dir",
        "default_encrypt",
        "font_size",
        "passphrase_min_length",
        "plugin_dir",
        "security_level",
        "sync_auto_interval",
        "sync_server_url",
        "theme",
    }
)

# Expected Python type for each key (used for value validation).  [REQ R9.4]
_TYPE_MAP: dict[str, type] = {
    "allowed_plugins": list,
    "close_behavior": str,
    "data_dir": str,
    "default_encrypt": str,
    "font_size": int,
    "passphrase_min_length": int,
    "plugin_dir": str,
    "security_level": str,
    "sync_auto_interval": int,
    "sync_server_url": str,
    "theme": str,
}

# Default value for each key.  [REQ R9.5]
DEFAULTS: dict[str, Any] = {
    "allowed_plugins": [],
    "close_behavior": "ask",
    "data_dir": None,
    "default_encrypt": "no",
    "font_size": 12,
    "passphrase_min_length": 8,
    "plugin_dir": None,
    "security_level": "high",
    "sync_auto_interval": 0,
    "sync_server_url": None,
    "theme": "light",
}

# Keys with restricted allowed values (enum-style validation).
_VALUE_CONSTRAINTS: dict[str, frozenset] = {
    "default_encrypt": frozenset({"yes", "no"}),
    "security_level": frozenset({"high", "session"}),  # B-98 [REQ R9.8]
    "theme": frozenset({"light", "dark"}),
}


def _default_config_path() -> Path:
    """Return the OS-standard config file path.  [REQ R9.1] [D-06]"""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA") or str(
            Path.home() / "AppData" / "Roaming"
        )
        return Path(appdata) / "astranotes" / "config.json"
    return Path.home() / ".config" / "astranotes" / "config.json"


class ConfigStore:
    """Persistent key/value configuration backed by a JSON file.

    - Known keys only; free-form keys rejected with ``KeyError``.  [REQ R9.3]
    - Wrong value type → ``ValueError``.  [REQ R9.4]
    - Missing config file → all defaults returned; file created on first
      ``set()`` call.  [REQ R9.5]
    - ``DATABASE_URL`` never stored here.  [REQ R9.6]

    Refs: [BL B-26] [REQ R9.1–R9.6]
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._path: Path = config_path or _default_config_path()
        self._data: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Disk I/O
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load config from disk.  Missing file → empty dict (all defaults)."""
        if not self._path.exists():
            return
        try:
            with self._path.open(encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self._data = loaded
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Could not read config %s: %s — using defaults.", self._path, exc
            )
            self._data = {}

    def _save(self) -> None:
        """Write config to disk, creating parent directories as needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any:
        """Return the stored value for *key*, or its default.

        Raises :exc:`KeyError` if *key* is not a known config key.
        [REQ R9.3]
        """
        if key not in ALLOWED_KEYS:
            raise KeyError(
                f"Unknown config key {key!r}. Known keys: {sorted(ALLOWED_KEYS)}"
            )
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        """Store *value* for *key* and persist to disk.

        Raises :exc:`KeyError` if *key* is unknown.
        Raises :exc:`ValueError` if *value* fails type or constraint checks.
        [REQ R9.3, R9.4]
        """
        if key not in ALLOWED_KEYS:
            raise KeyError(
                f"Unknown config key {key!r}. Known keys: {sorted(ALLOWED_KEYS)}"
            )

        expected_type = _TYPE_MAP[key]

        # Coerce string → int for integer keys (CLI args are always strings).
        if isinstance(value, str) and expected_type is int:
            try:
                value = int(value)
            except ValueError:
                raise ValueError(
                    f"Key {key!r} expects an integer value; got {value!r}."
                )

        # Type check after coercion.
        if not isinstance(value, expected_type):
            raise ValueError(
                f"Key {key!r} expects {expected_type.__name__!r}, "
                f"got {type(value).__name__!r}."
            )

        # Enum-style value constraints.
        if key in _VALUE_CONSTRAINTS and value not in _VALUE_CONSTRAINTS[key]:
            allowed = sorted(_VALUE_CONSTRAINTS[key])
            raise ValueError(
                f"Key {key!r} must be one of {allowed}; got {value!r}."
            )

        # Additional numeric constraints.
        if key == "passphrase_min_length" and value < 8:
            raise ValueError("passphrase_min_length must be at least 8.")
        if key == "font_size" and value < 6:
            raise ValueError("font_size must be at least 6.")
        if key == "sync_auto_interval" and value < 0:
            raise ValueError(
                "sync_auto_interval must be 0 (disabled) or a positive integer."
            )

        self._data[key] = value
        self._save()

    def list_all(self) -> dict[str, Any]:
        """Return all known keys with their current (or default) values."""
        return {
            key: self._data.get(key, DEFAULTS.get(key))
            for key in sorted(ALLOWED_KEYS)
        }

    def reset(self, key: str) -> None:
        """Remove *key* from stored config, reverting it to its default.

        Raises :exc:`KeyError` if *key* is not a known config key.
        """
        if key not in ALLOWED_KEYS:
            raise KeyError(
                f"Unknown config key {key!r}. Known keys: {sorted(ALLOWED_KEYS)}"
            )
        if key in self._data:
            del self._data[key]
            self._save()
