"""PluginBase ABC and PluginRegistry for AstraNotes hook-based extensibility.

Refs: [BL B-18, B-37, B-38, B-99, B-100] [REQ R4.3, R4.7, R4.11, R4.12, R4.13] [US-4] design §3.1
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from src.core.editor_protocol import EditorProtocol
    from src.core.plugin_context import PluginContext


# ---------------------------------------------------------------------------
# Pack / unpack error types
# ---------------------------------------------------------------------------


class PluginPackError(Exception):
    """Raised by :meth:`PluginBase.pack` when the input cannot be packed."""


class PluginUnpackError(Exception):
    """Raised by :meth:`PluginBase.unpack` when the bytes cannot be unpacked."""

import jsonschema

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Manifest schema for plugin.json  [BL B-99] [REQ R4.11, R4.12]
# ---------------------------------------------------------------------------

_MANIFEST_SCHEMA: dict = {
    "type": "object",
    "required": ["plugin_id", "name", "version", "engines", "main"],
    "properties": {
        "plugin_id": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "version": {"type": "string", "minLength": 1},
        "author": {"type": "string"},
        "description": {"type": "string"},
        "engines": {"type": "object"},
        "main": {"type": "string", "minLength": 1},
        # Security fields  [BL B-100] [REQ R4.13]
        "permissions": {
            "type": "array",
            "items": {"type": "string", "enum": ["network", "filesystem", "clipboard"]},
            "default": [],
        },
        "verified": {"type": "boolean", "default": False},
        "mime_types": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
    },
    "additionalProperties": True,
}


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

    def pack(self, data: Any) -> bytes:
        """Serialise *data* to raw bytes for container storage.

        The returned bytes are passed directly to :func:`~src.core.container.Container.frame`
        as the payload.  Raise :class:`PluginPackError` on failure.

        The default implementation encodes *data* as UTF-8 if it is a ``str``,
        or returns it unchanged if it is already ``bytes``.  Override for
        richer formats.
        """
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        raise PluginPackError(
            f"{type(self).__name__}.pack() received unsupported type {type(data).__name__!r}. "
            "Override pack() to handle this type."
        )

    def unpack(self, data: bytes) -> Any:
        """Deserialise *data* back to the original value.

        *data* is the raw payload bytes extracted from a container.
        Raise :class:`PluginUnpackError` on failure.

        The default implementation returns the bytes as a UTF-8 string, falling
        back to raw bytes on decode error.  Override for richer formats.
        """
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PluginUnpackError(
                f"Default unpack() could not decode payload as UTF-8: {exc}"
            ) from exc

    def mime_type(self) -> str:
        """Return the MIME type this plugin stores in the container header.

        Override to advertise a more specific type (e.g. ``"text/markdown"``).
        """
        return "text/plain"

    def create_editor(self) -> Optional["EditorProtocol"]:
        """Return a fresh editor widget instance, or ``None``.

        The returned object must satisfy :class:`~src.core.editor_protocol.EditorProtocol`:
        it must be a ``QWidget`` subclass that declares ``save_requested`` and
        ``content_changed`` Qt signals and implements ``load()`` /
        ``show_save_result()``.

        Return ``None`` (the default) to indicate that this plugin does not
        supply an editor UI; the host will fall back to
        :class:`~src.core.editor_protocol.DefaultFileEditor`.
        """
        return None

    def initialize(self, context: "PluginContext") -> None:
        """Called once after the plugin is registered, before any notes are opened.

        *context* is a :class:`~src.core.plugin_context.PluginContext` providing
        namespaced settings access and a logger.  It does **not** expose
        DatabaseStore or any note data.

        Override to perform one-time setup (e.g. reading persisted settings).
        The default implementation does nothing.
        """

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
    - Trust-tier enforcement: ``is_official=False`` plugins may only use the
      EditorProvider API; hook registration is blocked with a warning.
      [BL B-100] [REQ R4.13]

    Refs: [BL B-18, B-38, B-99, B-100] [REQ R4.3, R4.7, R4.11–R4.13] design §3.1
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable]] = {}
        self._plugins: list[PluginBase] = []
        self._manifests: list[dict] = []  # loaded plugin.json records [B-99]

    def register_plugin(self, plugin: PluginBase, *, is_official: bool = True) -> None:
        """Register *plugin* and invoke its :meth:`~PluginBase.register_hooks`.

        Trust-tier enforcement [BL B-100]:
        - ``is_official=True`` (default): plugin has full API access.
        - ``is_official=False``: only the EditorProvider API is allowed; hook
          registration is skipped with a warning.  Pass this flag explicitly when
          registering user-installed plugins loaded from the file system.
        """
        if any(type(p) is type(plugin) for p in self._plugins):
            logger.warning("Plugin %r already registered; skipping.", plugin.name)
            return
        self._plugins.append(plugin)
        if not is_official:
            logger.warning(
                "Plugin %r is user-installed (is_official=False); "
                "hook registration blocked — EditorProvider API only.  [B-100]",
                plugin.name,
            )
            # Skip register_hooks; plugin still recorded for EditorProvider use.
            return
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

    def load_manifests(self, plugin_dir: Path) -> list[dict]:
        """Read and validate ``plugin.json`` from each subdirectory of *plugin_dir*.

        Validation rules [BL B-99] [REQ R4.11, R4.12]:
        - Required fields: ``plugin_id``, ``name``, ``version``, ``engines``, ``main``.
        - Manifest must NOT contain ``is_official`` — that field is server-injected
          only and must never appear in a user-supplied manifest file.
        - Malformed JSON, missing file, schema violations, or ``is_official`` presence
          are all rejected with a warning (non-fatal); the plugin subdir is skipped.
        - Validated manifests are stored in ``self._manifests`` and returned.

        Returns the list of accepted manifest dicts.
        """
        accepted: list[dict] = []
        if not plugin_dir.is_dir():
            return accepted

        for subdir in sorted(plugin_dir.iterdir()):
            if not subdir.is_dir():
                continue
            manifest_path = subdir / "plugin.json"
            if not manifest_path.exists():
                logger.warning(
                    "Plugin subdir %s has no plugin.json; skipping.", subdir.name
                )
                continue
            try:
                with manifest_path.open(encoding="utf-8") as fh:
                    manifest = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Could not read plugin.json in %s: %s; skipping.", subdir.name, exc
                )
                continue

            # Reject is_official in manifest — server-injected only [REQ R4.13]
            if "is_official" in manifest:
                logger.warning(
                    "Plugin %s manifest contains 'is_official'; "
                    "field is server-injected only — rejecting manifest.",
                    subdir.name,
                )
                continue

            try:
                jsonschema.validate(manifest, _MANIFEST_SCHEMA)
            except jsonschema.ValidationError as exc:
                logger.warning(
                    "Plugin %s manifest failed schema validation: %s; skipping.",
                    subdir.name,
                    exc.message,
                )
                continue

            accepted.append(manifest)
            logger.info(
                "Loaded manifest for plugin %r v%s.",
                manifest["plugin_id"],
                manifest["version"],
            )

        self._manifests = accepted
        return accepted


# ---------------------------------------------------------------------------
# Plugin auto-discovery  [BL B-37]
# ---------------------------------------------------------------------------


def discover_plugins(
    plugin_dir: Path,
    registry: PluginRegistry,
    *,
    allowed_plugins: Optional[frozenset[str]] = None,
    override_check_fn: Optional[Callable[[PluginBase], bool]] = None,
) -> list[PluginBase]:
    """Import every ``*.py`` file in *plugin_dir* and register :class:`PluginBase`
    subclasses found therein with *registry*.

    Core rules:
    - Files whose name starts with ``_`` are skipped (e.g. ``__init__.py``).
    - Import failures are caught and logged; they never abort the process.
    - Instantiation failures are caught and logged per-class.
    - Already-registered plugin types are silently skipped (handled by
      :meth:`PluginRegistry.register_plugin`).

    Sprint 3 additions:
    - ``allowed_plugins``: if provided and non-empty, only plugins whose
      ``name`` attribute is in the set are registered; others are rejected with
      a warning.  [BL B-69] [REQ R4.10]
    - ``override_check_fn``: if a plugin has a non-empty ``overrides`` list,
      this callback is called with the plugin instance.  Return ``True`` to
      allow registration; ``False`` to skip.  The callback is responsible for
      user interaction and audit logging.  [BL B-24] [REQ R7]

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

                    # Allowlist check  [BL B-69] [REQ R4.10]
                    if allowed_plugins and instance.name not in allowed_plugins:
                        logger.warning(
                            "Plugin %r is not in allowed_plugins list; skipping.",
                            instance.name,
                        )
                        continue

                    # Override policy check  [BL B-24] [REQ R7]
                    if (
                        getattr(instance, "overrides", None)
                        and override_check_fn is not None
                    ):
                        if not override_check_fn(instance):
                            logger.info(
                                "Plugin %r skipped — override rejected by user.",
                                instance.name,
                            )
                            continue

                    registry.register_plugin(instance)
                    loaded.append(instance)
                    logger.info("Loaded plugin %r from %s.", attr_name, py_file)
                except Exception:
                    logger.exception(
                        "Failed to instantiate plugin %s from %s; skipping.",
                        attr_name, py_file,
                    )

    return loaded
