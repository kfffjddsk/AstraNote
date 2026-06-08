"""PluginsDialog — read-only inspector for discovered plugins.

Inspired by Notepad++ PluginsAdminDlg.  Two tabs:
  * Installed       — every Python plugin discovered by PluginRegistry
  * Supported formats — file kinds the current install can render

Refs: [BL B-99, B-100]
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.config import ConfigStore
from src.core.plugin_base import PluginRegistry

logger = logging.getLogger(__name__)


def registry_manifests(registry: PluginRegistry) -> list[dict]:
    """Safely return the manifests list of *registry* (may be empty)."""
    return getattr(registry, "_manifests", []) or []


class PluginsDialog(QDialog):
    """Read-only inspector for plugins discovered by :class:`PluginRegistry`."""

    def __init__(
        self,
        registry: PluginRegistry,
        config: ConfigStore,
        parent: Optional[QWidget] = None,
        *,
        open_mimes: frozenset = frozenset(),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("AstraNotes — Plugins Admin")
        self.setMinimumSize(720, 460)
        self._registry = registry
        self._config = config
        self._open_mimes = open_mimes

        layout = QVBoxLayout(self)

        # Search bar
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍  Filter:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Type to filter the list below...")
        self._search.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search, stretch=1)
        layout.addLayout(search_row)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_installed_tab(), "Installed")
        self._tabs.addTab(self._build_formats_tab(), "Supported formats")
        layout.addWidget(self._tabs, stretch=1)

        # Description pane
        self._desc = QTextEdit()
        self._desc.setReadOnly(True)
        self._desc.setFixedHeight(110)
        self._desc.setPlaceholderText("Select a row to see details...")
        layout.addWidget(self._desc)

        # Bottom buttons — Apply commits pending changes; Close dismisses
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close
        )
        apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn is not None:
            apply_btn.clicked.connect(self._on_apply)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)

        self._populate_installed()
        self._populate_formats()

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------
    def _build_installed_tab(self) -> QWidget:
        self._installed_tree = QTreeWidget()
        self._installed_tree.setColumnCount(4)
        self._installed_tree.setHeaderLabels(["Name", "Version", "Status", "Source"])
        header = self._installed_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._installed_tree.setRootIsDecorated(False)
        self._installed_tree.setAlternatingRowColors(True)
        self._installed_tree.currentItemChanged.connect(self._on_installed_selected)
        self._installed_tree.itemChanged.connect(self._on_installed_check_changed)
        return self._installed_tree

    def _build_formats_tab(self) -> QWidget:
        self._formats_tree = QTreeWidget()
        self._formats_tree.setColumnCount(3)
        self._formats_tree.setHeaderLabels(["Format", "Source", "Notes"])
        header = self._formats_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._formats_tree.setRootIsDecorated(False)
        self._formats_tree.setAlternatingRowColors(True)
        return self._formats_tree

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def _populate_installed(self) -> None:
        self._installed_tree.blockSignals(True)
        self._installed_tree.clear()
        allowed_raw = self._config.get("allowed_plugins") or []
        allowed: set[str] = set(allowed_raw) if isinstance(allowed_raw, list) else set()
        manifests = {
            m.get("plugin_id") or m.get("name"): m
            for m in registry_manifests(self._registry)
        }
        for plugin in self._registry._plugins:
            name = getattr(plugin, "name", type(plugin).__name__) or type(plugin).__name__
            version = getattr(plugin, "version", "") or "-"
            manifest = manifests.get(name)
            source = manifest.get("main", "<builtin>") if manifest else "<builtin>"
            status = "✓ Allowed" if (not allowed or name in allowed) else "Disabled"
            item = QTreeWidgetItem([name, version, status, source])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                0,
                Qt.CheckState.Checked
                if (not allowed or name in allowed)
                else Qt.CheckState.Unchecked,
            )
            item.setData(0, Qt.ItemDataRole.UserRole, plugin)
            item.setData(1, Qt.ItemDataRole.UserRole, manifest)
            self._installed_tree.addTopLevelItem(item)
        if self._installed_tree.topLevelItemCount() == 0:
            placeholder = QTreeWidgetItem(["(no plugins discovered)", "", "", ""])
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._installed_tree.addTopLevelItem(placeholder)
        self._installed_tree.blockSignals(False)

    def _populate_formats(self) -> None:
        rows = [
            ("Plain text (.txt)", "built-in", "Native Qt text rendering."),
            ("Markdown (.md)", "built-in", "Rendered as rich text by the editor."),
            ("Rich text (HTML)", "built-in", "Stored as HTML inside the note blob."),
            ("Images (PNG, JPG, GIF, WebP, BMP)", "built-in", "Decoded via QImageReader."),
            ("SVG", "built-in", "Requires QtSvg — included in PySide6."),
            ("PDF", "plugin", "Install a PDF viewer plugin to preview inline."),
            ("Audio / Video", "plugin", "Requires a QMediaPlayer-backed media plugin."),
            ("Office (.docx, .xlsx, .pptx)", "plugin", "Renderer plugin required."),
            ("Archives (.zip, .7z, .tar)", "plugin", "Browser plugin required."),
            ("Anything else (any binary)", "blob", "Stored encrypted; viewer plugin optional."),
        ]
        for plugin in self._registry._plugins:
            overrides = getattr(plugin, "overrides", None) or []
            for fmt in overrides:
                rows.append((str(fmt), f"plugin: {plugin.name}", "Handled by this plugin."))
        self._formats_tree.clear()
        for fmt, src, note in rows:
            self._formats_tree.addTopLevelItem(QTreeWidgetItem([fmt, src, note]))

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _on_installed_selected(
        self,
        current: Optional[QTreeWidgetItem],
        _previous: Optional[QTreeWidgetItem],
    ) -> None:
        if current is None:
            self._desc.clear()
            return
        plugin = current.data(0, Qt.ItemDataRole.UserRole)
        manifest = current.data(1, Qt.ItemDataRole.UserRole)
        if plugin is None:
            self._desc.clear()
            return
        lines = [
            f"<b>{getattr(plugin, 'name', '?')}</b> &nbsp; v{getattr(plugin, 'version', '?')}",
            f"<i>class</i>: {type(plugin).__module__}.{type(plugin).__name__}",
        ]
        if manifest:
            lines.append(f"<i>plugin_id</i>: {manifest.get('plugin_id', '')}")
            engines = manifest.get("engines", {})
            if engines:
                lines.append(f"<i>engines</i>: {engines}")
            if manifest.get("description"):
                lines.append(f"<br>{manifest['description']}")
        overrides = getattr(plugin, "overrides", None) or []
        if overrides:
            lines.append(f"<br><i>handles</i>: {', '.join(map(str, overrides))}")
        self._desc.setHtml("<br>".join(lines))

    def _on_installed_check_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return
        if item.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        checked = item.checkState(0) == Qt.CheckState.Checked
        item.setText(2, "✓ Allowed" if checked else "Disabled")

    def _on_apply(self) -> None:
        """Commit pending enable/disable changes to the live registry and config."""
        blocked: list[str] = []
        allowed: list[str] = []
        self._installed_tree.blockSignals(True)
        try:
            for i in range(self._installed_tree.topLevelItemCount()):
                item = self._installed_tree.topLevelItem(i)
                if item is None:
                    continue
                plugin = item.data(0, Qt.ItemDataRole.UserRole)
                if plugin is None:
                    continue
                name = getattr(plugin, "name", type(plugin).__name__)
                checked = item.checkState(0) == Qt.CheckState.Checked
                in_registry = plugin in self._registry._plugins
                if checked:
                    allowed.append(name)
                    if not in_registry:
                        self._registry.register_plugin(plugin)
                else:
                    plugin_mimes = set(getattr(plugin, "mime_types", None) or [])
                    if plugin_mimes & self._open_mimes:
                        # A note of this type is open — refuse to disable mid-session
                        blocked.append(name)
                        allowed.append(name)
                        item.setCheckState(0, Qt.CheckState.Checked)
                        item.setText(2, "✓ Allowed")
                    elif in_registry:
                        self._registry.unregister_plugin(name)
        finally:
            self._installed_tree.blockSignals(False)

        if blocked:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Plugin In Use",
                f"Cannot disable: {', '.join(blocked)}\n\n"
                "A note of this type is currently open. "
                "Close the note tab first, then apply the change.",
            )
        try:
            self._config.set("allowed_plugins", allowed)
        except (KeyError, ValueError) as exc:
            logger.warning("Could not update allowed_plugins: %s", exc)
        self._populate_formats()

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        tree = (
            self._installed_tree
            if self._tabs.currentIndex() == 0
            else self._formats_tree
        )
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            if item is None:
                continue
            if not needle:
                item.setHidden(False)
                continue
            row_text = " ".join(
                item.text(c) for c in range(tree.columnCount())
            ).lower()
            item.setHidden(needle not in row_text)
