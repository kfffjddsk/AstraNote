"""plugin_security — static import analysis for untrusted plugins.

Security model
--------------
We scan every ``.py`` file in a plugin directory with the standard ``ast``
module *before* importing it.  Import names are compared against:

1. ``_PERMISSION_MAP`` — modules that are dangerous only if the plugin did
   not declare the matching permission in its manifest.  Declaring the
   permission lets the import through *and* triggers the consent dialog.

2. ``_ALWAYS_WARN`` — modules that are dangerous regardless of declared
   permissions (e.g. ``subprocess``).  We never block outright — the user
   still sees a consent warning — but no permission grants them.

Limitations
-----------
- Static AST analysis cannot detect dynamic imports (``importlib.import_module``,
  ``__import__``, ``exec``).  Runtime sandboxing would be needed for that.
- We inspect the *top-level module name* only; sub-packages (e.g. ``os.path``)
  are attributed to their root (``os``).
- This is a best-effort defence, not a guarantee.  Users should only install
  plugins they trust.

Refs: [BL B-100] [REQ R4.13] design §3.1
"""
from __future__ import annotations

import ast
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Modules gated by the "network" permission
_NETWORK_MODULES: frozenset[str] = frozenset({
    "requests", "httpx", "urllib", "urllib3",
    "socket", "ssl", "http", "ftplib", "smtplib",
    "aiohttp", "websocket", "websockets", "grpc",
})

# Modules gated by the "filesystem" permission.
# Note: ``os`` also covers ``os.system`` / ``os.popen`` which can spawn
# processes, so we flag it even though pure path use is harmless.
_FILESYSTEM_MODULES: frozenset[str] = frozenset({
    "os", "pathlib", "shutil", "glob", "tempfile", "fileinput",
})

# Modules that raise a warning regardless of declared permissions.
# No permission can silence these — the user must explicitly consent.
_ALWAYS_WARN: frozenset[str] = frozenset({
    "subprocess", "ctypes", "cffi", "importlib",
    "pickle", "shelve", "marshal",
})

# Maps permission name → set of modules it covers
_PERMISSION_MAP: dict[str, frozenset[str]] = {
    "network": _NETWORK_MODULES,
    "filesystem": _FILESYSTEM_MODULES,
}


def scan_plugin_imports(plugin_dir: Path) -> dict[str, list[str]]:
    """Return all top-level module names imported by any ``.py`` in *plugin_dir*.

    Returns a dict ``{module_root: [source_file, ...]}``.
    Files whose names start with ``_`` are skipped.
    Syntax errors are logged as warnings and the file is skipped.
    """
    found: dict[str, list[str]] = {}
    for py_file in sorted(plugin_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            logger.warning("Syntax error in %s during import scan: %s", py_file.name, exc)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    found.setdefault(root, []).append(py_file.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    found.setdefault(root, []).append(py_file.name)
    return found


def check_permissions(
    imports: dict[str, list[str]],
    declared_permissions: list[str],
) -> tuple[list[str], list[str]]:
    """Compare *imports* against *declared_permissions* from the manifest.

    Returns ``(blocked, always_warn)``:

    - ``blocked``: modules that require a permission the plugin did *not*
      declare.  The plugin should be refused entirely.
    - ``always_warn``: modules in :data:`_ALWAYS_WARN` present in the plugin.
      These are shown to the user in the consent dialog regardless of
      declared permissions.
    """
    # Build the set of modules granted by declared permissions
    granted: set[str] = set()
    for perm in declared_permissions:
        granted |= _PERMISSION_MAP.get(perm, frozenset())

    blocked: list[str] = []
    always_warn: list[str] = []

    for module in imports:
        if module in _ALWAYS_WARN:
            always_warn.append(module)
            continue
        for modules in _PERMISSION_MAP.values():
            if module in modules and module not in granted:
                blocked.append(module)
                break

    return blocked, always_warn
