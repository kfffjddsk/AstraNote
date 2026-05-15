"""PluginBase ABC and PluginRegistry for AstraNotes hook-based extensibility.

Refs: [BL B-18, B-38] [REQ R4.3, R4.7] [US-4] design §3.1
"""
from __future__ import annotations

import dataclasses
import logging
from abc import ABC, abstractmethod
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
