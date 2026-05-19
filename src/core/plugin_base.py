"""PluginBase ABC and PluginRegistry for AstraNotes hook-based extensibility.

Refs: [BL B-18, B-37, B-38] [REQ R4.3, R4.7] [US-4] design §3.1
"""
from __future__ import annotations

import dataclasses
import importlib.util
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class PluginBase(ABC):
    """Abstract base class for all AstraNotes plugins.

    Subclasses must implement :meth:`register_hooks`.  They may also override
    :meth:`get_commands` to expose additional CLI commands.
    """

    name: str = ""
    version: str = ""
    overrides: list[str] = dataclasses.field(default_factory=list)

    @abstractmethod
    def register_hooks(self, registry: "PluginRegistry") -> None:
        """Register this plugin's hooks with *registry*."""

    def get_commands(self) -> dict[str, Callable]:
        """Return additional CLI commands provided by this plugin.

        Keys are command names; values are Click command callables.
        """
        return {}


class PluginRegistry:
    """Central registry for plugin hooks.

    - Duplicate registrations are silently skipped with a warning.
    - Hook dispatch wraps every handler in try/except so a crashing plugin
      never kills the calling operation.  [REQ R4.7]
    - Each hook receives a read-only copy of the note (dataclasses.replace)
      to prevent plugins from mutating core state.  [REQ R15.7] [D-09]

    Refs: [BL B-18, B-38] [REQ R4.3, R4.7] design §3.1
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable]] = {}
        self._plugins: list[PluginBase] = []

    def register_plugin(self, plugin: PluginBase) -> None:
        """Register *plugin* and invoke its :meth:`~PluginBase.register_hooks`."""
        if any(type(p) is type(plugin) for p in self._plugins):
            logger.warning("Plugin %r already registered; skipping.", plugin.name)
            return
        self._plugins.append(plugin)
        plugin.register_hooks(self)

    def register_hook(self, name: str, fn: Callable) -> None:
        """Attach *fn* to the hook named *name*."""
        self._hooks.setdefault(name, []).append(fn)

    def call_hook(self, name: str, note: Any, **kwargs: Any) -> None:
        """Invoke all handlers registered for *name* with a copy of *note*.

        Individual handler exceptions are caught and logged; they never
        propagate to the caller.  [REQ R4.7]
        """
        from src.core.notes import Note  # local import to avoid circular dependency

        note_copy = dataclasses.replace(note) if isinstance(note, Note) else note
        for fn in self._hooks.get(name, []):
            try:
                fn(note_copy, **kwargs)
            except Exception:
                logger.exception("Plugin hook %r raised an exception.", name)


# ---------------------------------------------------------------------------
# Plugin auto-discovery  [BL B-37]
# ---------------------------------------------------------------------------


def discover_plugins(plugin_dir: Path, registry: PluginRegistry) -> list[PluginBase]:
    """Import every ``*.py`` file in *plugin_dir* and register :class:`PluginBase`
    subclasses found therein with *registry*.

    Rules:
    - Files whose name starts with ``_`` are skipped (e.g. ``__init__.py``).
    - Import failures are caught and logged; they never abort the process.
    - Instantiation failures are caught and logged per-class.
    - Already-registered plugin types are silently skipped (handled by
      :meth:`PluginRegistry.register_plugin`).

    Returns the list of successfully registered plugin instances.  [BL B-37]
    """
    loaded: list[PluginBase] = []
    if not plugin_dir.exists() or not plugin_dir.is_dir():
        return loaded

    for py_file in sorted(plugin_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
        if spec is None or spec.loader is None:
            logger.warning("Could not create module spec for %s; skipping.", py_file)
            continue
        try:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception:
            logger.exception("Failed to import plugin module %s; skipping.", py_file)
            continue

        for attr_name, attr in vars(module).items():
            if (
                isinstance(attr, type)
                and issubclass(attr, PluginBase)
                and attr is not PluginBase
            ):
                try:
                    instance = attr()
                    registry.register_plugin(instance)
                    loaded.append(instance)
                    logger.info("Loaded plugin %r from %s.", attr_name, py_file)
                except Exception:
                    logger.exception(
                        "Failed to instantiate plugin %s from %s; skipping.",
                        attr_name, py_file,
                    )

    return loaded
