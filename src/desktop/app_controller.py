"""AppController — startup orchestrator for the AstraNotes desktop GUI.

Startup sequence [BL B-84] [D-13]:
  1. ConfigStore.load()
  2. DatabaseStore(data_dir)
  3. AppLockManager.acquire_lock()   → SessionConflictError → error dialog + exit(1)
  4. PluginRegistry.load_manifests()
  5. QApplication + MainWindow
  6. populate_note_list()
  7. start_idle_timer()
  8. app.exec()

Refs: [BL B-84, B-101] [REQ R9.7, R11] [US-9] design §3.1, §4.5, §4.7
"""
from __future__ import annotations

import signal
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication, QMessageBox

from src.core.app_lock import AppLockManager, SessionConflictError
from src.core.config import ConfigStore
from src.core.notes import DatabaseStore
from src.core.plugin_base import PluginRegistry
from src.desktop.main_window import MainWindow, apply_theme


class AppController:
    """Orchestrates desktop application startup and lifecycle.

    Parameters
    ----------
    data_dir:
        Override for the data directory.  When *None* the value is read from
        :class:`~src.core.config.ConfigStore` (``data_dir`` key).
    config_path:
        Override for the config file path.  When *None* the OS default is used.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        config_path: Optional[Path] = None,
    ) -> None:
        self._override_data_dir: Optional[Path] = data_dir
        self._config_path: Optional[Path] = config_path

        # Populated during run()
        self.config: Optional[ConfigStore] = None
        self.store: Optional[DatabaseStore] = None
        self.lock_mgr: Optional[AppLockManager] = None
        self.registry: Optional[PluginRegistry] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Execute the full startup sequence and enter the Qt event loop.

        Returns the process exit code (0 = normal exit).
        """
        # ── Step 1: Load configuration ────────────────────────────────
        self.config = ConfigStore(config_path=self._config_path)

        # ── Step 2: Resolve data_dir ───────────────────────────────────
        data_dir = self._resolve_data_dir()

        # ── Step 3: Create DatabaseStore ─────────────────────────────
        self.store = DatabaseStore(data_dir)

        # ── Step 4: Acquire PID lock ─────────────────────────────────
        self.lock_mgr = AppLockManager(data_dir)
        try:
            self.lock_mgr.acquire_lock()
        except SessionConflictError as exc:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "AstraNotes — Session Conflict", str(exc))
            return 1

        try:
            # ── Step 5: Validate plugin manifests ────────────────────
            self.registry = PluginRegistry()
            plugin_dir_cfg = self.config.get("plugin_dir")
            plugin_dir = (
                Path(plugin_dir_cfg) if plugin_dir_cfg else data_dir / "plugins"
            )
            self.registry.load_manifests(plugin_dir)

            # ── Step 6: Create Qt application and main window ────────
            app = QApplication.instance() or QApplication(sys.argv)
            # Allow Ctrl+C in the terminal to quit cleanly
            signal.signal(signal.SIGINT, lambda *_: app.quit())
            theme = self.config.get("theme") or "light"
            try:
                font_size = int(self.config.get("font_size") or 12)
            except (TypeError, ValueError):
                font_size = 12
            font_family = self.config.get("font_family") or ""
            accent = self.config.get("accent_color") or "purple"
            apply_theme(app, theme, font_size, font_family, accent)
            try:
                auto_interval = int(self.config.get("sync_auto_interval") or 0)
            except (TypeError, ValueError):
                auto_interval = 0
            window = MainWindow(
                store=self.store,
                config=self.config,
                registry=self.registry,
                data_dir=data_dir,
                sync_url=self.config.get("sync_server_url") or "",
                sync_auto_interval=auto_interval,
            )
            window.show()

            # ── Step 7: Populate note list and start timers ──────────
            window.populate_note_list()
            window.start_idle_timer()
            window.start_auto_sync_timer()

            # ── Step 8: Enter event loop ──────────────────────────────
            return app.exec()

        finally:
            # Always release the lock on exit
            if self.lock_mgr is not None:
                self.lock_mgr.release_lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_data_dir(self) -> Path:
        """Return the data directory, preferring the constructor override."""
        if self._override_data_dir is not None:
            return Path(self._override_data_dir)
        cfg_val = self.config.get("data_dir") if self.config else None
        if cfg_val:
            return Path(cfg_val)
        # Fall back to OS default: ~/astranotes
        return Path.home() / "astranotes"
