"""plugin_loader — secure discovery, consent, and registration of plugins.

This module is the single entry point for loading plugins from a directory
of plugin sub-packages (each containing a ``plugin.json`` manifest and at
least one ``.py`` file).

Loading pipeline for each plugin sub-directory
-----------------------------------------------
1. Read and validate ``plugin.json`` (schema check via PluginRegistry).
2. Scan all non-underscore ``.py`` files for imports (AST analysis).
3. Compare imports against declared permissions:
   - Undeclared dangerous import → block plugin, warn user (if UI available).
   - Always-warn module (subprocess, ctypes, …) → note for consent dialog.
4. Verified plugins (``"verified": true``) skip the consent dialog.
   Unverified plugins: check stored consent in ConfigStore; show
   :class:`~src.desktop.plugin_consent_dialog.PluginConsentDialog` if not yet
   consented; persist consent on Allow.
5. Import the plugin's ``main`` Python file via ``importlib``.
6. Instantiate any :class:`~src.core.plugin_base.PluginBase` subclasses found.
7. Call ``plugin.initialize(PluginContext)`` once.
8. Register with the :class:`~src.core.plugin_base.PluginRegistry`
   (``is_official=verified``).

Security note
-------------
Even after a plugin passes consent, its editor widget only ever receives
the content of the *current* note via ``EditorProtocol.load()``.  It never
holds a reference to ``DatabaseStore`` or the note list.

Refs: [BL B-99, B-100] [REQ R4.11, R4.12, R4.13] design §3.1
"""
from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from typing import Any, Optional

import jsonschema

from src.core.config import ConfigStore
from src.core.plugin_base import PluginBase, PluginRegistry, _MANIFEST_SCHEMA
from src.core.plugin_context import PluginContext
from src.core.plugin_security import check_permissions, scan_plugin_imports

logger = logging.getLogger(__name__)

_CONSENT_KEY_PREFIX = "plugin_consent_"


def load_plugins(
    plugin_dir: Path,
    registry: PluginRegistry,
    config: ConfigStore,
    *,
    parent_widget: Optional[Any] = None,
) -> list[PluginBase]:
    """Discover, verify, consent, and register all plugins under *plugin_dir*.

    Parameters
    ----------
    plugin_dir:
        Directory whose immediate subdirectories are plugin packages.
    registry:
        The application's :class:`PluginRegistry`; plugins are registered here.
    config:
        :class:`ConfigStore` used to read/write consent records and plugin
        settings.
    parent_widget:
        Optional ``QWidget`` used as parent for consent and error dialogs.
        When ``None``, unverified plugins without prior consent are skipped
        silently (headless mode).

    Returns the list of successfully loaded and registered plugin instances.
    """
    if not plugin_dir.is_dir():
        logger.debug("Plugin dir %s does not exist; skipping.", plugin_dir)
        return []

    loaded: list[PluginBase] = []

    for subdir in sorted(plugin_dir.iterdir()):
        if not subdir.is_dir():
            continue
        plugin = _load_one(subdir, registry, config, parent_widget=parent_widget)
        if plugin is not None:
            loaded.append(plugin)

    return loaded


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_one(
    subdir: Path,
    registry: PluginRegistry,
    config: ConfigStore,
    *,
    parent_widget: Optional[Any],
) -> Optional[PluginBase]:
    """Attempt to load a single plugin from *subdir*.  Returns None on failure."""

    # ── Step 1: Read and validate manifest ──────────────────────────────
    manifest_path = subdir / "plugin.json"
    if not manifest_path.exists():
        logger.debug("No plugin.json in %s; skipping.", subdir.name)
        return None

    try:
        with manifest_path.open(encoding="utf-8") as fh:
            manifest: dict = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read plugin.json in %s: %s", subdir.name, exc)
        return None

    # is_official must never come from the manifest file [REQ R4.13]
    if "is_official" in manifest:
        logger.warning(
            "Plugin %s manifest contains 'is_official'; rejecting.", subdir.name
        )
        return None

    try:
        jsonschema.validate(manifest, _MANIFEST_SCHEMA)
    except jsonschema.ValidationError as exc:
        logger.warning(
            "Plugin %s manifest schema error: %s; skipping.", subdir.name, exc.message
        )
        return None

    plugin_id: str = manifest.get("plugin_id") or subdir.name
    verified: bool = bool(manifest.get("verified", False))
    permissions: list[str] = list(manifest.get("permissions") or [])

    # ── Step 2: Import scan ──────────────────────────────────────────────
    imports = scan_plugin_imports(subdir)
    blocked, always_warn = check_permissions(imports, permissions)

    if blocked:
        logger.warning(
            "Plugin %r blocked: undeclared dangerous imports %s.", plugin_id, blocked
        )
        _show_blocked_dialog(plugin_id, blocked, parent_widget)
        return None

    # ── Step 3: Consent (unverified plugins only) ────────────────────────
    if not verified:
        consent_key = f"{_CONSENT_KEY_PREFIX}{plugin_id}"
        if config.get(consent_key) != "yes":
            if parent_widget is None:
                logger.info(
                    "Skipping unverified plugin %r — no UI available for consent.",
                    plugin_id,
                )
                return None
            if not _ask_consent(manifest, always_warn, parent_widget):
                logger.info("User denied consent for plugin %r.", plugin_id)
                return None
            config.set(consent_key, "yes")

    # ── Step 4: Import the plugin Python module ─────────────────────────
    main_file: str = manifest.get("main") or ""
    py_file = subdir / main_file if main_file else _find_main_py(subdir)
    if py_file is None:
        logger.warning("No Python entry point found for plugin %r.", plugin_id)
        return None

    spec = importlib.util.spec_from_file_location(
        f"astranotes_plugin.{plugin_id}", py_file
    )
    if spec is None or spec.loader is None:
        logger.warning("Cannot create module spec for %s.", py_file)
        return None

    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception:
        logger.exception("Failed to import plugin %r from %s.", plugin_id, py_file)
        return None

    # ── Step 5: Find, instantiate, initialise, and register ─────────────
    for attr in vars(module).values():
        if (
            isinstance(attr, type)
            and issubclass(attr, PluginBase)
            and attr is not PluginBase
        ):
            try:
                instance = attr()
            except Exception:
                logger.exception("Failed to instantiate %s for plugin %r.", attr, plugin_id)
                continue

            try:
                context = PluginContext(plugin_id, config)
                instance.initialize(context)
            except Exception:
                logger.exception(
                    "Plugin %r initialize() raised; loading anyway.", plugin_id
                )

            # Respect the allowed_plugins whitelist.  A non-empty list means the
            # user has explicitly configured which plugins may be active.
            allowed_raw = config.get("allowed_plugins")
            if isinstance(allowed_raw, list) and allowed_raw:
                inst_name = getattr(instance, "name", None) or plugin_id
                if inst_name not in allowed_raw:
                    logger.info(
                        "Plugin %r excluded by allowed_plugins config; skipping registration.",
                        inst_name,
                    )
                    return None

            registry.register_plugin(instance, is_official=verified)
            # Append manifest for PluginsDialog (user plugins only — bundled
            # manifests are pre-loaded via registry.load_manifests in AppController)
            if not verified:
                registry._manifests.append(manifest)
            logger.info("Loaded plugin %r v%s.", plugin_id, manifest.get("version", "?"))
            return instance

    logger.warning("No PluginBase subclass found in plugin %r.", plugin_id)
    return None


def _find_main_py(subdir: Path) -> Optional[Path]:
    """Return the first non-underscore .py file in *subdir*, or None."""
    for py_file in sorted(subdir.glob("*.py")):
        if not py_file.name.startswith("_"):
            return py_file
    return None


def _show_blocked_dialog(
    plugin_id: str, blocked: list[str], parent_widget: Optional[Any]
) -> None:
    if parent_widget is None:
        return
    try:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            parent_widget,
            f"Plugin Blocked — {plugin_id}",
            f"Plugin '{plugin_id}' was blocked because it imports modules "
            f"not declared in its permissions manifest:\n\n"
            f"  {', '.join(blocked)}\n\n"
            "The plugin was not loaded.",
        )
    except Exception:
        logger.exception("Could not show blocked-plugin dialog.")


def _ask_consent(
    manifest: dict,
    always_warn: list[str],
    parent_widget: Any,
) -> bool:
    """Show consent dialog and return True if the user clicked Allow."""
    try:
        from src.desktop.plugin_consent_dialog import PluginConsentDialog
        from PySide6.QtWidgets import QDialog

        dlg = PluginConsentDialog(
            plugin_name=manifest.get("name") or manifest.get("plugin_id") or "Unknown",
            plugin_author=manifest.get("author") or "",
            permissions=list(manifest.get("permissions") or []),
            always_warn_modules=always_warn,
            parent=parent_widget,
        )
        return dlg.exec() == QDialog.DialogCode.Accepted
    except Exception:
        logger.exception("Could not show consent dialog.")
        return False
