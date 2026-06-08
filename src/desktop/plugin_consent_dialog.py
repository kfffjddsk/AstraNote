"""PluginConsentDialog — first-run permission consent for unverified plugins.

Shown once per plugin (keyed by ``plugin_id``) before a third-party plugin
is loaded.  Verified / bundled plugins (``"verified": true`` in their
``plugin.json``) skip this dialog entirely.

The dialog follows the Obsidian model: plugins run in-process with full
access to the note currently being edited.  The consent prompt makes this
explicit and lists any extra permissions the plugin declared.

Refs: [BL B-100] [REQ R4.13] design §3.1
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Human-readable descriptions for each permission token
_PERMISSION_DESCRIPTIONS: dict[str, str] = {
    "network": "Access the internet — can send data to external servers",
    "filesystem": "Read and write files anywhere on your computer",
    "clipboard": "Read and modify clipboard contents",
}


class PluginConsentDialog(QDialog):
    """Permission-consent dialog for an unverified plugin.

    Parameters
    ----------
    plugin_name:
        Display name from the manifest ``name`` field.
    plugin_author:
        Author string from the manifest; shown as-is (may be empty).
    permissions:
        List of permission tokens the plugin declared in its manifest
        (e.g. ``["network"]``).
    always_warn_modules:
        Module names flagged by the import scanner that require extra
        attention regardless of declared permissions (e.g. ``["subprocess"]``).
    parent:
        Optional Qt parent widget.
    """

    def __init__(
        self,
        plugin_name: str,
        plugin_author: str,
        permissions: list[str],
        always_warn_modules: list[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plugin Permission Request")
        self.setMinimumWidth(460)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header = QLabel(
            f"<b>{plugin_name}</b>"
            + (f" — by {plugin_author}" if plugin_author else "")
        )
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        # Warning banner
        banner = QLabel(
            "This plugin is <b>not verified by AstraNotes</b>.<br>"
            "It runs in the same process as the app and has access to "
            "the note you are currently editing."
        )
        banner.setTextFormat(Qt.TextFormat.RichText)
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 8px; border-radius: 4px;"
        )
        layout.addWidget(banner)

        # Permissions list
        if permissions:
            layout.addWidget(self._section_label("Permissions requested:"))
            for perm in permissions:
                desc = _PERMISSION_DESCRIPTIONS.get(perm, perm)
                row = QLabel(f"  •  {desc}")
                row.setWordWrap(True)
                layout.addWidget(row)
        else:
            layout.addWidget(QLabel("No special permissions requested."))

        # Always-warn modules
        if always_warn_modules:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            layout.addWidget(sep)
            warn = QLabel(
                "⚠  This plugin imports potentially dangerous module(s): "
                f"<b>{', '.join(always_warn_modules)}</b>.<br>"
                "These are not gated by any permission. Proceed with caution."
            )
            warn.setTextFormat(Qt.TextFormat.RichText)
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #721c24;")
            layout.addWidget(warn)

        # Footer note
        footer = QLabel(
            "By clicking <b>Allow</b> you accept responsibility for this "
            "plugin's actions. You will not be asked again for this plugin."
        )
        footer.setTextFormat(Qt.TextFormat.RichText)
        footer.setWordWrap(True)
        footer.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(footer)

        # Buttons
        buttons = QDialogButtonBox()
        allow_btn = QPushButton("Allow")
        deny_btn = QPushButton("Deny")
        buttons.addButton(allow_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(deny_btn, QDialogButtonBox.ButtonRole.RejectRole)
        allow_btn.clicked.connect(self.accept)
        deny_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(f"<b>{text}</b>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        return lbl
