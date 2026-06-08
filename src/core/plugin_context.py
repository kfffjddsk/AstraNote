"""PluginContext — restricted API surface given to plugins on initialisation.

Plugins receive a :class:`PluginContext` via :meth:`~src.core.plugin_base.PluginBase.initialize`.
This is the *only* object they get from the host application.

What plugins CAN do through PluginContext
-----------------------------------------
- Read and write their own namespaced settings (key–value pairs).
- Write log messages.

What plugins CANNOT do through PluginContext
--------------------------------------------
- Access DatabaseStore or any note data.
- Read another plugin's settings namespace.
- Access user credentials or encryption keys.

This architectural isolation is the primary data-theft mitigation: a plugin
that only receives a PluginContext can never exfiltrate notes it was never
given.

Refs: [BL B-100] [REQ R4.13] design §3.1
"""
from __future__ import annotations

import logging
from typing import Any

from src.core.config import ConfigStore


class PluginContext:
    """Restricted host API for plugin initialisation.

    All settings are stored under the key ``plugin_<plugin_id>_<key>`` in the
    shared :class:`~src.core.config.ConfigStore`, which keeps them isolated
    from both the host application's settings and those of other plugins.
    """

    def __init__(self, plugin_id: str, config: ConfigStore) -> None:
        self._plugin_id = plugin_id
        self._config = config
        self._logger = logging.getLogger(f"plugin.{plugin_id}")

    # ------------------------------------------------------------------
    # Settings (namespaced)
    # ------------------------------------------------------------------

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Return the setting *key* for this plugin, or *default*."""
        return self._config.get(self._ns(key)) or default

    def set_setting(self, key: str, value: Any) -> None:
        """Persist *value* under *key* for this plugin."""
        self._config.set(self._ns(key), value)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(self, msg: str) -> None:
        """Emit *msg* as an INFO log line tagged with this plugin's id."""
        self._logger.info("%s", msg)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ns(self, key: str) -> str:
        return f"plugin_{self._plugin_id}_{key}"
