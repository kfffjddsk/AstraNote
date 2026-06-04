"""MainWindow — PySide6 desktop GUI for AstraNotes (Sprint 4B redesign).

Layout:
  ┌────────────────────────────────────────────────────────────────┐
  │  MenuBar: [File] [Edit] [View]                                 │
  │  Toolbar:  [+ New] [💾 Save] [🗑 Delete]                       │
  ├──────────────────┬─────────────────────────────────────────────┤
  │  🔍 [Search…]    │  ┌──────────┬──────────┐                    │
  │  ──────────────  │  │ Note 1   │ Note 2   │                    │
  │  ── Your Notes── │  ├──────────┴──────────┤                    │
  │   🔒 note a     │  │ Alias:  [__________] │  [B-106]          │
  │    note b        │  │ Title:  [__________] │                   │
  │  ── Local ──     │  │  B  I  U  | 12 ▾     │  [B-105]          │
  │    note c        │  │ ┌──────────────────┐ │                   │
  │                  │  │ │ Rich text editor │ │                   │
  │                  │  │ └──────────────────┘ │                   │
  │                  │  │  □ Encrypted  [🔓]  │  [B-106]           │
  │                  │  └──────────────────────┘                   │
  └──────────────────┴─────────────────────────────────────────────┘

Refs:
  [BL B-103–B-112] [REQ R9.7, R9.8, R11] [US-9]
  design §3.1, §4.7 [D-13]
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QFont,
    QIcon,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QMenu,
)

from src.core.blob_codec import BlobCodec
from src.core.config import ConfigStore
from src.core.notes import DatabaseStore, Note
from src.core.plugin_base import PluginRegistry
from src.core.security import KeyManager

logger = logging.getLogger(__name__)

_IDLE_TIMEOUT_MS = 5 * 60 * 1000  # 300_000 ms  [REQ R9.8] [BL B-102]
_ENCRYPTED_PLACEHOLDER = "[Encrypted]"


# ---------------------------------------------------------------------------
# Theme stylesheets  [B-110]
# ---------------------------------------------------------------------------

DARK_STYLESHEET = """
QMainWindow, QWidget { background-color: #1e1e1e; color: #cccccc; }
QMenuBar { background-color: #3c3c3c; color: #cccccc; }
QMenuBar::item:selected { background-color: #094771; }
QMenu { background-color: #252526; color: #cccccc; border: 1px solid #454545; }
QMenu::item:selected { background-color: #094771; }
QListWidget { background-color: #252526; border: none; color: #cccccc; outline: none; }
QListWidget::item { padding: 4px 8px; }
QListWidget::item:selected { background-color: #094771; color: white; }
QListWidget::item:disabled { color: #666666; font-style: italic; }
QTextEdit, QLineEdit { background-color: #1e1e1e; color: #d4d4d4;
    border: 1px solid #3c3c3c; border-radius: 2px; }
QToolBar { background-color: #252526; border: none; spacing: 2px; }
QToolButton { background-color: transparent; color: #cccccc;
    border: 1px solid transparent; padding: 2px 6px; border-radius: 2px; }
QToolButton:checked { background-color: #094771; border-color: #007acc; }
QToolButton:hover { background-color: #3c3c3c; }
QTabBar::tab { background-color: #2d2d2d; color: #cccccc; padding: 6px 16px;
    border: none; border-right: 1px solid #1e1e1e; }
QTabBar::tab:selected { background-color: #1e1e1e; border-top: 2px solid #007acc; }
QTabBar::tab:hover { background-color: #3c3c3c; }
QTabWidget::pane { border: none; }
QPushButton { background-color: #0e639c; color: white; border: none;
    padding: 4px 14px; border-radius: 2px; }
QPushButton:hover { background-color: #1177bb; }
QPushButton:pressed { background-color: #0a4e7a; }
QDialog { background-color: #252526; color: #cccccc; }
QLabel { color: #cccccc; }
QComboBox { background-color: #3c3c3c; color: #cccccc;
    border: 1px solid #555; border-radius: 2px; padding: 2px 6px; }
QSpinBox { background-color: #3c3c3c; color: #cccccc;
    border: 1px solid #555; border-radius: 2px; padding: 2px 6px; }
QCheckBox { color: #cccccc; }
QSplitter::handle { background-color: #3c3c3c; }
"""

LIGHT_STYLESHEET = """
QMainWindow, QWidget { background-color: #f3f3f3; color: #333333; }
QMenuBar { background-color: #f3f3f3; color: #333333; }
QMenuBar::item:selected { background-color: #0078d4; color: white; }
QMenu { background-color: white; color: #333333; border: 1px solid #cccccc; }
QMenu::item:selected { background-color: #0078d4; color: white; }
QListWidget { background-color: #f3f3f3; border: none; color: #333333; outline: none; }
QListWidget::item { padding: 4px 8px; }
QListWidget::item:selected { background-color: #0078d4; color: white; }
QListWidget::item:disabled { color: #999999; font-style: italic; }
QTextEdit, QLineEdit { background-color: white; color: #333333;
    border: 1px solid #cccccc; border-radius: 2px; }
QToolBar { background-color: #f3f3f3; border-bottom: 1px solid #e0e0e0; spacing: 2px; }
QToolButton { background-color: transparent; color: #333333;
    border: 1px solid transparent; padding: 2px 6px; border-radius: 2px; }
QToolButton:checked { background-color: #0078d4; color: white; }
QToolButton:hover { background-color: #e5e5e5; }
QTabBar::tab { background-color: #ececec; color: #555555; padding: 6px 16px;
    border: none; border-right: 1px solid #d0d0d0; }
QTabBar::tab:selected { background-color: white; border-top: 2px solid #0078d4;
    color: #333333; }
QTabBar::tab:hover { background-color: #e0e0e0; }
QTabWidget::pane { border-top: 1px solid #e0e0e0; }
QPushButton { background-color: #0078d4; color: white; border: none;
    padding: 4px 14px; border-radius: 2px; }
QPushButton:hover { background-color: #106ebe; }
QPushButton:pressed { background-color: #005a9e; }
QDialog { background-color: #f3f3f3; color: #333333; }
QLabel { color: #333333; }
QComboBox { background-color: white; color: #333333;
    border: 1px solid #cccccc; border-radius: 2px; padding: 2px 6px; }
QSpinBox { background-color: white; color: #333333;
    border: 1px solid #cccccc; border-radius: 2px; padding: 2px 6px; }
QCheckBox { color: #333333; }
QSplitter::handle { background-color: #e0e0e0; }
"""


def apply_theme(app: "QApplication", theme: str, font_size: int = 12) -> None:
    """Apply theme stylesheet and font size to the QApplication.  [B-110, B-111]"""
    stylesheet = DARK_STYLESHEET if theme == "dark" else LIGHT_STYLESHEET
    app.setStyleSheet(stylesheet)
    font = app.font()
    font.setPointSize(font_size)
    app.setFont(font)


# ---------------------------------------------------------------------------
# Passphrase dialog
# ---------------------------------------------------------------------------


class PassphraseDialog(QDialog):
    """Modal dialog that prompts for a passphrase.

    Attributes:
        passphrase: The entered passphrase, or ``""`` if cancelled.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        title: str = "Passphrase Required",
        confirm: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.passphrase: str = ""

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._entry = QLineEdit()
        self._entry.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Passphrase:", self._entry)

        self._confirm_entry: Optional[QLineEdit] = None
        if confirm:
            self._confirm_entry = QLineEdit()
            self._confirm_entry.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow("Confirm:", self._confirm_entry)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        passphrase = self._entry.text()
        if self._confirm_entry is not None:
            confirm = self._confirm_entry.text()
            if passphrase != confirm:
                QMessageBox.warning(
                    self, "Mismatch", "Passphrases do not match. Please try again."
                )
                return
        self.passphrase = passphrase
        self.accept()


# ---------------------------------------------------------------------------
# Settings dialog  [B-109]
# ---------------------------------------------------------------------------


class SettingsDialog(QDialog):
    """Settings dialog exposing user-configurable options.  [BL B-109]"""

    def __init__(self, config: ConfigStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AstraNotes — Settings")
        self.setMinimumWidth(340)
        self._config = config

        layout = QFormLayout(self)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        # Theme  [B-110]
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["light", "dark"])
        self._theme_combo.setCurrentText(config.get("theme") or "light")
        layout.addRow("Theme:", self._theme_combo)

        # Font size  [B-111]
        self._font_spin = QSpinBox()
        self._font_spin.setRange(8, 32)
        try:
            self._font_spin.setValue(int(config.get("font_size") or 12))
        except (TypeError, ValueError):
            self._font_spin.setValue(12)
        layout.addRow("Font size (pt):", self._font_spin)

        # Default encrypt
        self._default_encrypt_combo = QComboBox()
        self._default_encrypt_combo.addItems(["no", "yes"])
        self._default_encrypt_combo.setCurrentText(config.get("default_encrypt") or "no")
        layout.addRow("Default encrypt:", self._default_encrypt_combo)

        # Passphrase min length
        self._passphrase_spin = QSpinBox()
        self._passphrase_spin.setRange(4, 64)
        try:
            self._passphrase_spin.setValue(int(config.get("passphrase_min_length") or 8))
        except (TypeError, ValueError):
            self._passphrase_spin.setValue(8)
        layout.addRow("Min passphrase length:", self._passphrase_spin)

        # Close behaviour  [B-97]
        self._close_behavior_combo = QComboBox()
        self._close_behavior_combo.addItems(["ask", "minimize", "quit"])
        self._close_behavior_combo.setItemData(0, "Always ask what to do", Qt.ItemDataRole.ToolTipRole)
        self._close_behavior_combo.setItemData(1, "Always minimize to tray", Qt.ItemDataRole.ToolTipRole)
        self._close_behavior_combo.setItemData(2, "Always quit", Qt.ItemDataRole.ToolTipRole)
        self._close_behavior_combo.setCurrentText(config.get("close_behavior") or "ask")
        layout.addRow("When closing:", self._close_behavior_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_accept(self) -> None:
        self._config.set("theme", self._theme_combo.currentText())
        self._config.set("font_size", self._font_spin.value())
        self._config.set("default_encrypt", self._default_encrypt_combo.currentText())
        self._config.set("passphrase_min_length", self._passphrase_spin.value())
        self._config.set("close_behavior", self._close_behavior_combo.currentText())
        self.accept()

    @property
    def theme(self) -> str:
        return self._theme_combo.currentText()

    @property
    def font_size(self) -> int:
        return self._font_spin.value()


# ---------------------------------------------------------------------------
# _CloseChoiceDialog — "minimize or quit?" prompt  [BL B-97]
# ---------------------------------------------------------------------------


class _CloseChoiceDialog(QDialog):
    """Ask the user whether to minimize to tray or quit, with a remember checkbox."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Close AstraNotes")
        self.choice: str = "quit"  # "minimize" or "quit"

        layout = QVBoxLayout(self)

        label = QLabel(
            "Would you like to minimize AstraNotes to the system tray or quit?"
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        self._remember = QCheckBox("Remember my choice")
        layout.addWidget(self._remember)

        btn_row = QHBoxLayout()
        minimize_btn = QPushButton("Minimize to Tray")
        quit_btn = QPushButton("Quit")
        btn_row.addWidget(minimize_btn)
        btn_row.addWidget(quit_btn)
        layout.addLayout(btn_row)

        minimize_btn.clicked.connect(self._choose_minimize)
        quit_btn.clicked.connect(self._choose_quit)

    def _choose_minimize(self) -> None:
        self.choice = "minimize"
        self.accept()

    def _choose_quit(self) -> None:
        self.choice = "quit"
        self.accept()

    @property
    def remember(self) -> bool:
        return self._remember.isChecked()


# ---------------------------------------------------------------------------
# _AliasPromptDialog — choose display alias when saving an encrypted note [B-106]
# ---------------------------------------------------------------------------


class _AliasPromptDialog(QDialog):
    """Ask the user to set a display alias for a newly-encrypted note.

    The alias is shown in the note list instead of the real (encrypted) title.
    """

    def __init__(self, suggested_title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Encrypted Note Alias")
        self.alias: str = "[Encrypted Note]"

        layout = QVBoxLayout(self)

        label = QLabel(
            "This note will be encrypted. Set a display alias that will appear "
            "in the note list, or leave it as the default."
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        self._alias_edit = QLineEdit()
        self._alias_edit.setPlaceholderText("[Encrypted Note]")
        self._alias_edit.setText(suggested_title)
        layout.addWidget(self._alias_edit)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save with alias")
        default_btn = QPushButton('Use "[Encrypted Note]"')
        cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(save_btn)
        btn_row.addWidget(default_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        save_btn.clicked.connect(self._on_save_alias)
        default_btn.clicked.connect(self._on_use_default)
        cancel_btn.clicked.connect(self.reject)

    def _on_save_alias(self) -> None:
        self.alias = self._alias_edit.text().strip() or "[Encrypted Note]"
        self.accept()

    def _on_use_default(self) -> None:
        self.alias = "[Encrypted Note]"
        self.accept()


# ---------------------------------------------------------------------------
# NoteEditorWidget — tab content pane  [B-105, B-106]
# ---------------------------------------------------------------------------


class NoteEditorWidget(QWidget):
    """Per-tab editor: title/alias, rich-text body, encrypt toggle, unlock button.

    Backward-compatible API (test_sprint4.py):
        clear(), load(), get_title(), get_content(), is_encrypted(),
        set_encrypted(), show_encrypted_placeholder()

    Sprint 4B additions:
        get_alias(), get_html_content(), unlock_requested signal, apply_font_size()
    """

    content_changed = Signal()
    unlock_requested = Signal()  # emitted by the Unlock button  [B-106]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # ── Title row (always visible) ───────────────────────────────
        self._title_row = QWidget()
        title_layout = QHBoxLayout(self._title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(QLabel("Title:"))
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Note title")
        self._title_edit.textChanged.connect(self.content_changed)
        title_layout.addWidget(self._title_edit)
        layout.addWidget(self._title_row)

        # ── Rich-text formatting toolbar  [B-105] ─────────────────────
        from PySide6.QtCore import QSize
        self._fmt_bar = QToolBar()
        self._fmt_bar.setMovable(False)
        self._fmt_bar.setIconSize(QSize(14, 14))

        self._bold_btn = QToolButton()
        self._bold_btn.setText("B")
        self._bold_btn.setCheckable(True)
        self._bold_btn.setToolTip("Bold (Ctrl+B)")
        self._bold_btn.setStyleSheet("font-weight: bold;")
        self._bold_btn.clicked.connect(self._toggle_bold)
        self._fmt_bar.addWidget(self._bold_btn)

        self._italic_btn = QToolButton()
        self._italic_btn.setText("I")
        self._italic_btn.setCheckable(True)
        self._italic_btn.setToolTip("Italic (Ctrl+I)")
        self._italic_btn.setStyleSheet("font-style: italic;")
        self._italic_btn.clicked.connect(self._toggle_italic)
        self._fmt_bar.addWidget(self._italic_btn)

        self._underline_btn = QToolButton()
        self._underline_btn.setText("U")
        self._underline_btn.setCheckable(True)
        self._underline_btn.setToolTip("Underline (Ctrl+U)")
        self._underline_btn.setStyleSheet("text-decoration: underline;")
        self._underline_btn.clicked.connect(self._toggle_underline)
        self._fmt_bar.addWidget(self._underline_btn)

        self._fmt_bar.addSeparator()

        self._font_size_combo = QComboBox()
        self._font_size_combo.addItems(
            [str(s) for s in [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48]]
        )
        self._font_size_combo.setCurrentText("12")
        self._font_size_combo.setFixedWidth(52)
        self._font_size_combo.setToolTip("Font size")
        self._font_size_combo.currentTextChanged.connect(self._on_font_size_changed)
        self._fmt_bar.addWidget(self._font_size_combo)

        layout.addWidget(self._fmt_bar)

        # ── Rich-text content editor  [B-105] ─────────────────────────
        self._content_edit = QTextEdit()
        self._content_edit.setAcceptRichText(True)
        self._content_edit.textChanged.connect(self.content_changed)
        self._content_edit.currentCharFormatChanged.connect(self._update_format_buttons)
        layout.addWidget(self._content_edit)

        # ── Bottom row: encrypt checkbox + unlock button  [B-106] ─────
        bottom = QHBoxLayout()
        self._encrypt_check = QCheckBox("Encrypted")
        self._encrypt_check.toggled.connect(self._on_encrypt_toggled)
        self._encrypt_check.toggled.connect(lambda _: self.content_changed.emit())
        bottom.addWidget(self._encrypt_check)
        bottom.addStretch()

        self._unlock_btn = QPushButton("🔓 Unlock")
        self._unlock_btn.setToolTip("Decrypt this note with your passphrase")
        self._unlock_btn.clicked.connect(self.unlock_requested)
        self._unlock_btn.setVisible(False)
        bottom.addWidget(self._unlock_btn)

        layout.addLayout(bottom)

    # ------------------------------------------------------------------
    # Formatting helpers  [B-105]
    # ------------------------------------------------------------------

    def _toggle_bold(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(
            QFont.Weight.Bold if self._bold_btn.isChecked() else QFont.Weight.Normal
        )
        self._content_edit.textCursor().mergeCharFormat(fmt)

    def _toggle_italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(self._italic_btn.isChecked())
        self._content_edit.textCursor().mergeCharFormat(fmt)

    def _toggle_underline(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(self._underline_btn.isChecked())
        self._content_edit.textCursor().mergeCharFormat(fmt)

    def _on_font_size_changed(self, text: str) -> None:
        try:
            size = int(text)
        except ValueError:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        cursor = self._content_edit.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            self._content_edit.setCurrentCharFormat(fmt)

    def _update_format_buttons(self, fmt: QTextCharFormat) -> None:
        self._bold_btn.setChecked(fmt.fontWeight() >= QFont.Weight.Bold)
        self._italic_btn.setChecked(fmt.fontItalic())
        self._underline_btn.setChecked(fmt.fontUnderline())
        size = fmt.fontPointSize()
        if size > 0:
            self._font_size_combo.setCurrentText(str(int(size)))

    # ------------------------------------------------------------------
    # Alias / encrypt toggle  [B-106]
    # ------------------------------------------------------------------

    def _on_encrypt_toggled(self, checked: bool) -> None:  # noqa: ARG002
        """Encrypt checkbox toggled — no visual change; alias set at save time."""
        # The title row stays visible at all times.  Alias is prompted on save.

    # ------------------------------------------------------------------
    # Public API (backward-compatible with test_sprint4.py)
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all fields to empty / unchecked state."""
        self._title_edit.clear()
        self._content_edit.clear()
        self._content_edit.setReadOnly(False)
        self._encrypt_check.setChecked(False)
        self._unlock_btn.setVisible(False)

    def load(self, note: Note, *, decrypted_content: Optional[str] = None) -> None:
        """Populate editor from *note*.

        For encrypted notes the content area shows ``[Encrypted]`` (and the
        unlock button) unless *decrypted_content* is provided.
        """
        # Title is always shown in _title_edit regardless of encryption state
        self._title_edit.setText(note.title)

        # Set checkbox without triggering _on_encrypt_toggled
        self._encrypt_check.blockSignals(True)
        self._encrypt_check.setChecked(note.encrypted)
        self._encrypt_check.blockSignals(False)

        if note.encrypted:
            if decrypted_content is not None:
                self._content_edit.setReadOnly(False)
                self._content_edit.setPlainText(decrypted_content)
                self._unlock_btn.setVisible(False)
            else:
                self._content_edit.setPlainText(_ENCRYPTED_PLACEHOLDER)
                self._content_edit.setReadOnly(True)
                self._unlock_btn.setVisible(True)
        else:
            self._content_edit.setReadOnly(False)
            self._content_edit.setPlainText(note.content or "")
            self._unlock_btn.setVisible(False)

    def get_title(self) -> str:
        """Return the note title (reads _title_edit — tests may set it directly)."""
        return self._title_edit.text().strip()

    def get_alias(self) -> str:
        """Return alias text (same value as get_title for encrypted notes)."""
        return self.get_title()

    def get_content(self) -> str:
        """Return plain-text content (backward-compatible with test_sprint4.py)."""
        return self._content_edit.toPlainText().strip()

    def get_html_content(self) -> str:
        """Return HTML content — for richer storage when supported."""
        return self._content_edit.toHtml()

    def is_encrypted(self) -> bool:
        return self._encrypt_check.isChecked()

    def set_encrypted(self, value: bool = True) -> None:
        """Set the encrypted checkbox state."""
        self._encrypt_check.setChecked(value)

    def show_encrypted_placeholder(self) -> None:
        """Replace content with placeholder — used on idle auto-lock.  [B-102]"""
        self._content_edit.setPlainText(_ENCRYPTED_PLACEHOLDER)
        self._content_edit.setReadOnly(True)
        self._unlock_btn.setVisible(True)

    def apply_font_size(self, size: int) -> None:
        """Apply global font size to the content editor.  [B-111]"""
        font = self._content_edit.font()
        font.setPointSize(size)
        self._content_edit.setFont(font)
        self._font_size_combo.setCurrentText(str(size))


# ---------------------------------------------------------------------------
# _WelcomeWidget — home/start page shown when no note is open  [B-103]
# ---------------------------------------------------------------------------


class _WelcomeWidget(QWidget):
    """Blank welcome screen with suggested actions, shown when no tab is open."""

    # Emitted when the user clicks one of the shortcut buttons
    new_note_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        inner = QVBoxLayout()
        inner.setSpacing(16)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("AstraNotes")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28pt; font-weight: bold; color: #888;")
        inner.addWidget(title)

        subtitle = QLabel("Your encrypted personal notebook")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 11pt; color: #aaa;")
        inner.addWidget(subtitle)

        spacer = QLabel("")
        spacer.setFixedHeight(24)
        inner.addWidget(spacer)

        hint = QLabel("Get started:")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size: 10pt; color: #999;")
        inner.addWidget(hint)

        new_btn = QPushButton("  ✏  New Note   (Ctrl+N)")
        new_btn.setFixedWidth(220)
        new_btn.setFixedHeight(36)
        new_btn.clicked.connect(self.new_note_requested)
        inner.addWidget(new_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        search_hint = QLabel("Or click any note in the list on the left to open it.")
        search_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_hint.setStyleSheet("font-size: 9pt; color: #888;")
        inner.addWidget(search_hint)

        outer.addLayout(inner)


# ---------------------------------------------------------------------------
# MainWindow  [B-103, B-104, B-107, B-108, B-110, B-111, B-112]
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    """VS Code-inspired AstraNotes desktop window with tab bar and search.

    [BL B-103–B-112] [REQ R9.7, R9.8, R11] [US-9]
    """

    def __init__(
        self,
        store: DatabaseStore,
        config: ConfigStore,
        registry: PluginRegistry,
        data_dir: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._config = config
        self._registry = registry
        self._data_dir = data_dir  # optional, for account-aware list [B-108]

        # State
        self._current_note: Optional[Note] = None
        self._cached_passphrase: Optional[str] = None

        self.setWindowTitle("AstraNotes")
        self.resize(1100, 680)

        self._build_menu_bar()
        self._build_toolbar()
        self._build_central_widget()
        self._build_tray()

        # Idle timer  [B-102]
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(_IDLE_TIMEOUT_MS)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_timeout)

    # ------------------------------------------------------------------
    # Builder helpers
    # ------------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        # ── File ──────────────────────────────────────────────────────
        file_menu = menu_bar.addMenu("&File")

        self._action_new = QAction("&New Note", self)
        self._action_new.setShortcut("Ctrl+N")
        self._action_new.triggered.connect(self._on_new_note)
        file_menu.addAction(self._action_new)

        self._action_save = QAction("&Save", self)
        self._action_save.setShortcut("Ctrl+S")
        self._action_save.triggered.connect(self._on_save)
        file_menu.addAction(self._action_save)

        self._action_delete = QAction("&Delete Note", self)
        self._action_delete.setShortcut("Delete")
        self._action_delete.triggered.connect(self._on_delete)
        file_menu.addAction(self._action_delete)

        file_menu.addSeparator()

        self._action_settings = QAction("⚙ &Settings…", self)
        self._action_settings.setShortcut("Ctrl+,")
        self._action_settings.triggered.connect(self._on_settings)
        file_menu.addAction(self._action_settings)

        file_menu.addSeparator()

        action_quit = QAction("&Quit", self)
        action_quit.setShortcut("Ctrl+Q")
        action_quit.triggered.connect(QApplication.instance().quit)
        file_menu.addAction(action_quit)

        # ── Edit ──────────────────────────────────────────────────────
        edit_menu = menu_bar.addMenu("&Edit")
        action_close_tab = QAction("Close &Tab", self)
        action_close_tab.setShortcut("Ctrl+W")
        action_close_tab.triggered.connect(self._on_close_current_tab)
        edit_menu.addAction(action_close_tab)

        # ── View ──────────────────────────────────────────────────────
        view_menu = menu_bar.addMenu("&View")
        action_focus_search = QAction("&Find Notes…", self)
        action_focus_search.setShortcut("Ctrl+F")
        action_focus_search.triggered.connect(self._on_focus_search)
        view_menu.addAction(action_focus_search)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction(self._action_new)
        toolbar.addAction(self._action_save)
        toolbar.addAction(self._action_delete)
        toolbar.addSeparator()
        toolbar.addAction(self._action_settings)

    def _build_central_widget(self) -> None:
        """VS Code-inspired split layout: sidebar + tab editor.  [B-103, B-104]"""
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(1)

        # ── LEFT: sidebar ─────────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Search bar  [B-107]
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("🔍  Search notes…")
        self._search_bar.setClearButtonEnabled(True)
        self._search_bar.textChanged.connect(self._on_search_changed)
        left_layout.addWidget(self._search_bar)

        # Note list  [B-108]
        self._note_list = QListWidget()
        self._note_list.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._note_list.currentItemChanged.connect(self._on_note_selected)
        left_layout.addWidget(self._note_list)

        left.setMinimumWidth(160)
        splitter.addWidget(left)

        # ── RIGHT: stacked pane (welcome page OR tab editor)  [B-103, B-104] ─
        self._right_stack = QStackedWidget()

        # Index 0 — welcome / home page
        self._welcome_widget = _WelcomeWidget()
        self._welcome_widget.new_note_requested.connect(self._on_new_note)
        self._right_stack.addWidget(self._welcome_widget)   # index 0

        # Index 1 — tab editor
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.setMovable(True)
        self._tab_widget.setDocumentMode(True)
        self._tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        self._right_stack.addWidget(self._tab_widget)       # index 1

        splitter.addWidget(self._right_stack)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([220, 880])

        self.setCentralWidget(splitter)

        # Tab tracking: note_id -> NoteEditorWidget
        self._note_editors: dict[str, NoteEditorWidget] = {}

        # Start on welcome page; no initial empty tab
        self._right_stack.setCurrentIndex(0)
        self._editor: NoteEditorWidget = NoteEditorWidget()  # off-screen placeholder

    def _show_welcome(self) -> None:
        """Switch the right pane to the welcome / home view."""
        self._right_stack.setCurrentIndex(0)
        self._current_note = None
        self._cached_passphrase = None

    def _show_editor(self) -> None:
        """Switch the right pane to the tab editor view."""
        self._right_stack.setCurrentIndex(1)

    def _build_tray(self) -> None:
        """Set up system tray icon and context menu.  [BL B-97]"""
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(QIcon.fromTheme("text-editor"))
        self._tray.setToolTip("AstraNotes")

        tray_menu = QMenu()
        show_action = QAction("Show / Hide", self)
        show_action.triggered.connect(self._toggle_visibility)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(quit_action)

        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    # ------------------------------------------------------------------
    # Tab management  [B-104]
    # ------------------------------------------------------------------

    def _open_new_tab(
        self,
        note_id: Optional[str] = None,
        label: str = "New Note",
    ) -> "NoteEditorWidget":
        """Create a new editor tab, wire signals, and make it current."""
        editor = NoteEditorWidget()
        editor.content_changed.connect(self.reset_idle_timer)
        editor.unlock_requested.connect(self._on_unlock_requested)

        # Apply current font size  [B-111]
        try:
            font_size = int(self._config.get("font_size") or 12)
        except (TypeError, ValueError):
            font_size = 12
        editor.apply_font_size(font_size)

        index = self._tab_widget.addTab(editor, label)
        # Register BEFORE setCurrentIndex so _on_tab_changed can resolve the note
        if note_id:
            self._note_editors[note_id] = editor
        self._tab_widget.setCurrentIndex(index)
        # _on_tab_changed fires here and updates self._editor
        self._show_editor()  # switch stack to tab view

        return editor

    def _get_or_open_tab(self, note: Note) -> "NoteEditorWidget":
        """Return the existing tab for *note*, or open a new one."""
        if note.id in self._note_editors:
            editor = self._note_editors[note.id]
            idx = self._tab_widget.indexOf(editor)
            if idx >= 0:
                self._tab_widget.setCurrentIndex(idx)
                self._editor = editor
                return editor
            # Tab was removed; clean up dict entry
            del self._note_editors[note.id]

        label = f"🔒 {note.title}" if note.encrypted else note.title
        editor = self._open_new_tab(note_id=note.id, label=label)
        return editor

    def _on_tab_close_requested(self, index: int) -> None:
        """Close a tab; show welcome page when no tabs remain."""
        editor = self._tab_widget.widget(index)
        for nid, ed in list(self._note_editors.items()):
            if ed is editor:
                del self._note_editors[nid]

        self._tab_widget.removeTab(index)

        if self._tab_widget.count() == 0:
            self._show_welcome()
        else:
            widget = self._tab_widget.currentWidget()
            if isinstance(widget, NoteEditorWidget):
                self._editor = widget

    def _on_tab_changed(self, index: int) -> None:
        """Sync _editor and _current_note to the active tab."""
        if index < 0:
            return
        widget = self._tab_widget.widget(index)
        if not isinstance(widget, NoteEditorWidget):
            return
        self._editor = widget
        note_id = next(
            (nid for nid, ed in self._note_editors.items() if ed is widget), None
        )
        if note_id:
            self._current_note = self._store.get(note_id)
        else:
            self._current_note = None

    def _on_close_current_tab(self) -> None:
        """Close the currently active tab.  [B-112 Ctrl+W]"""
        idx = self._tab_widget.currentIndex()
        if idx >= 0:
            self._on_tab_close_requested(idx)

    # ------------------------------------------------------------------
    # Note list population  [B-84, B-108]
    # ------------------------------------------------------------------

    def populate_note_list(self) -> None:
        """Reload note list from the database.  [BL B-84] [REQ R1.3]"""
        if not self._search_bar.text().strip():
            self._populate_note_list_items()

    def _populate_note_list_items(self) -> None:
        """Fill the list widget; use account sections when a session exists."""
        self._note_list.clear()

        # Attempt account-aware list  [B-108]
        account_id: Optional[str] = None
        if self._data_dir:
            try:
                from src.core.auth import SessionManager
                session = SessionManager(self._data_dir).load()
                if session:
                    account_id = session.account_id
            except Exception:
                pass

        account_notes, local_notes = self._store.list(account_id=account_id)

        if account_notes:
            header = QListWidgetItem("── Your Notes ──")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self._note_list.addItem(header)
            for note in account_notes:
                self._note_list.addItem(self._make_note_item(note))

        if account_notes and local_notes:
            header2 = QListWidgetItem("── Local Notes ──")
            header2.setFlags(Qt.ItemFlag.NoItemFlags)
            self._note_list.addItem(header2)

        for note in local_notes:
            self._note_list.addItem(self._make_note_item(note))

    @staticmethod
    def _make_note_item(note: Note) -> QListWidgetItem:
        display = f"🔒 {note.title}" if note.encrypted else note.title
        item = QListWidgetItem(display)
        item.setData(Qt.ItemDataRole.UserRole, note.id)
        return item

    # ------------------------------------------------------------------
    # Search  [B-107]
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        """Filter note list in real-time via DatabaseStore.search().  [B-107]"""
        self._note_list.clear()
        query = text.strip()
        if not query:
            self._populate_note_list_items()
            return
        try:
            results = self._store.search(query)
        except Exception:
            results = []
        for note in results:
            self._note_list.addItem(self._make_note_item(note))

    def _on_focus_search(self) -> None:
        """Focus the search bar.  [B-112 Ctrl+F]"""
        self._search_bar.setFocus()
        self._search_bar.selectAll()

    # ------------------------------------------------------------------
    # Settings  [B-109]
    # ------------------------------------------------------------------

    def _on_settings(self) -> None:
        """Open Settings dialog and apply changes live.  [B-109, B-112 Ctrl+,]"""
        dlg = SettingsDialog(self._config, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        app = QApplication.instance()
        if app:
            apply_theme(app, dlg.theme, dlg.font_size)
        for editor in self._note_editors.values():
            editor.apply_font_size(dlg.font_size)

    # ------------------------------------------------------------------
    # Idle timer  [BL B-102]
    # ------------------------------------------------------------------

    def start_idle_timer(self) -> None:
        """Start the 5-minute idle auto-lock timer."""
        self._idle_timer.start()

    def reset_idle_timer(self) -> None:
        """Reset the idle timer on any user interaction."""
        self._idle_timer.start()

    def _on_idle_timeout(self) -> None:
        """Auto-lock: clear passphrase and show placeholder for encrypted note."""
        if self._current_note is not None and self._current_note.encrypted:
            self._cached_passphrase = None
            self._editor.show_encrypted_placeholder()
            logger.info("Idle timeout: encrypted note auto-locked.  [B-102]")

    def auto_close_encrypted_note(self) -> None:
        """Public façade for idle timeout — also used by AppController.  [B-102]"""
        self._on_idle_timeout()

    # ------------------------------------------------------------------
    # CRUD operations  [BL B-85]
    # ------------------------------------------------------------------

    def _on_new_note(self) -> None:
        """Open a fresh editor tab for a new note.  [B-112 Ctrl+N]"""
        self._current_note = None
        self._cached_passphrase = None
        editor = self._open_new_tab(label="New Note")
        editor.clear()
        self._editor = editor
        self.reset_idle_timer()

    def _on_save(self) -> None:
        """Save the current editor state to the database.  [B-112 Ctrl+S]"""
        title = self._editor.get_title()
        content = self._editor.get_content()

        if not title:
            QMessageBox.warning(self, "Validation", "Title must not be empty.")
            return
        if not content and not self._editor.is_encrypted():
            QMessageBox.warning(self, "Validation", "Content must not be empty.")
            return

        if self._editor.is_encrypted():
            if content and content != _ENCRYPTED_PLACEHOLDER:
                # User typed new plaintext — encrypt and save
                passphrase = self._get_or_prompt_passphrase(confirm=True)
                if not passphrase:
                    return

                # Prompt for alias when the note is new OR was previously unencrypted
                is_newly_encrypted = (
                    self._current_note is None or not self._current_note.encrypted
                )
                if is_newly_encrypted:
                    alias_dlg = _AliasPromptDialog(title, self)
                    if alias_dlg.exec() != QDialog.DialogCode.Accepted:
                        return
                    alias = alias_dlg.alias
                else:
                    # Existing encrypted note: title field holds the current alias
                    alias = title

                try:
                    km = KeyManager(passphrase)
                    engine = km.get_engine()
                    raw_blob = BlobCodec.encode(
                        header={"title": title}, payload=content.encode("utf-8")
                    )
                    encrypted_blob = BlobCodec.encrypt(raw_blob, engine)
                    if self._current_note is None:
                        note = Note.create(alias, "", encrypted=True, blob=encrypted_blob)
                        self._store.add(note)
                        self._current_note = note
                        self._register_current_editor(note)
                    else:
                        self._store.update(
                            self._current_note.id, title=alias, blob=encrypted_blob
                        )
                    self._cache_passphrase(passphrase)
                    # Reflect the alias in the editor's title field
                    self._editor._title_edit.setText(alias)
                except ValueError as exc:
                    QMessageBox.critical(self, "Encryption Error", str(exc))
                    return
            else:
                # Placeholder still shown — update title/alias only
                if self._current_note is not None:
                    self._store.update(self._current_note.id, title=title)
                else:
                    QMessageBox.information(
                        self,
                        "Nothing to save",
                        "Enter content or uncheck Encrypted to save a new note.",
                    )
                    return
        else:
            if not content:
                QMessageBox.warning(self, "Validation", "Content must not be empty.")
                return
            if self._current_note is None:
                note = Note.create(title, content)
                self._store.add(note)
                self._current_note = note
                self._register_current_editor(note)
            else:
                self._store.update(self._current_note.id, title=title, content=content)

        # Update tab label after save
        if self._current_note:
            label = (
                f"🔒 {self._current_note.title}"
                if self._current_note.encrypted
                else self._current_note.title
            )
            idx = self._tab_widget.indexOf(self._editor)
            if idx >= 0:
                self._tab_widget.setTabText(idx, label)

        self.populate_note_list()

        # Close the saved tab and return to the welcome page
        save_idx = self._tab_widget.indexOf(self._editor)
        if save_idx >= 0:
            self._on_tab_close_requested(save_idx)

        self.reset_idle_timer()

    def _register_current_editor(self, note: Note) -> None:
        """Associate the current editor with a newly-saved note ID."""
        self._note_editors[note.id] = self._editor

    def _on_delete(self) -> None:
        """Delete the currently selected note after confirmation.  [B-112 Del]"""
        if self._current_note is None:
            QMessageBox.information(self, "No selection", "Select a note to delete.")
            return
        # Encrypted notes: require passphrase before deleting  [B-106]
        if self._current_note.encrypted:
            passphrase = self._get_or_prompt_passphrase()
            if not passphrase:
                return
            result = self._try_decrypt_with_passphrase(self._current_note, passphrase)
            if result is None:
                QMessageBox.warning(
                    self,
                    "Wrong Passphrase",
                    "Cannot delete: passphrase verification failed.",
                )
                return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete note '{self._current_note.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            note_id = self._current_note.id
            self._store.delete(note_id)
            # Close the tab for this note if open
            if note_id in self._note_editors:
                editor = self._note_editors.pop(note_id)
                idx = self._tab_widget.indexOf(editor)
                if idx >= 0:
                    self._tab_widget.removeTab(idx)
            if self._tab_widget.count() == 0:
                self._show_welcome()
            else:
                widget = self._tab_widget.currentWidget()
                if isinstance(widget, NoteEditorWidget):
                    self._editor = widget
            self.populate_note_list()
        self.reset_idle_timer()

    def _on_note_selected(
        self,
        current: Optional[QListWidgetItem],
        previous: Optional[QListWidgetItem],
    ) -> None:
        """Load the selected note into a tab.  [B-104]"""
        if current is None:
            return
        note_id: Optional[str] = current.data(Qt.ItemDataRole.UserRole)
        if note_id is None:
            # Header item — not selectable
            return
        note = self._store.get(note_id)
        if note is None:
            return

        # security_level: clear passphrase on navigation (high mode)  [B-98]
        security_level = self._config.get("security_level") or "high"
        if (
            security_level == "high"
            and self._current_note is not None
            and self._current_note.id != note_id
        ):
            self._cached_passphrase = None

        self._current_note = note
        editor = self._get_or_open_tab(note)

        # Try to decrypt with cached passphrase
        decrypted_content: Optional[str] = None
        if note.encrypted and self._cached_passphrase:
            result = self._try_decrypt_note(note)
            if result is not None:
                real_title, decrypted_content = result
                editor.load(note, decrypted_content=decrypted_content)
                editor._title_edit.setText(real_title)
                self.reset_idle_timer()
                return

        editor.load(note, decrypted_content=decrypted_content)
        self.reset_idle_timer()

    # ------------------------------------------------------------------
    # Unlock button handler  [B-106]
    # ------------------------------------------------------------------

    def _on_unlock_requested(self) -> None:
        """Prompt for passphrase and decrypt the current encrypted note."""
        if self._current_note is None or not self._current_note.encrypted:
            return
        passphrase = self._get_or_prompt_passphrase()
        if not passphrase:
            return
        result = self._try_decrypt_with_passphrase(self._current_note, passphrase)
        if result is None:
            QMessageBox.warning(
                self,
                "Wrong Passphrase",
                "Could not decrypt the note. Please check your passphrase.",
            )
            return
        self._cached_passphrase = passphrase
        real_title, decrypted = result
        self._editor.load(self._current_note, decrypted_content=decrypted)
        # Restore the real title (stored in blob header, not the visible alias)
        self._editor._title_edit.setText(real_title)

    # ------------------------------------------------------------------
    # Passphrase handling  [BL B-84, B-85, B-98]
    # ------------------------------------------------------------------

    def _get_or_prompt_passphrase(self, *, confirm: bool = False) -> Optional[str]:
        """Return cached passphrase or prompt the user."""
        if self._cached_passphrase:
            return self._cached_passphrase
        dlg = PassphraseDialog(self, confirm=confirm)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.passphrase or None

    def _cache_passphrase(self, passphrase: str) -> None:
        """Cache passphrase according to security_level config.  [B-98]"""
        self._cached_passphrase = passphrase

    def _try_decrypt_note(self, note: Note) -> Optional[tuple[str, str]]:
        """Attempt to decrypt *note* using the cached passphrase."""
        if not self._cached_passphrase:
            return None
        return self._try_decrypt_with_passphrase(note, self._cached_passphrase)

    def _try_decrypt_with_passphrase(self, note: Note, passphrase: str) -> Optional[tuple[str, str]]:
        """Attempt to decrypt *note* with *passphrase*.

        Returns ``(real_title, plaintext_content)`` on success, ``None`` on failure.
        The real title comes from the blob header (not the stored alias).
        """
        try:
            km = KeyManager(passphrase)
            engine = km.get_engine()
            raw_blob = BlobCodec.decrypt(note.blob, engine)
            header, payload = BlobCodec.decode(raw_blob)
            real_title = header.get("title") or note.title
            return real_title, payload.decode("utf-8")
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Tray  [BL B-97]
    # ------------------------------------------------------------------

    def _toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_visibility()

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        """Ask minimize-or-quit, or use saved preference.  [BL B-97]"""
        behavior = self._config.get("close_behavior") or "ask"

        if behavior == "minimize" and self._tray.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            return

        if behavior == "quit":
            event.accept()
            QApplication.instance().quit()
            return

        # behavior == "ask" — show the choice dialog
        if not self._tray.isSystemTrayAvailable():
            # No tray support: just quit
            event.accept()
            QApplication.instance().quit()
            return

        dlg = _CloseChoiceDialog(self)
        dlg.exec()

        if dlg.remember:
            self._config.set("close_behavior", dlg.choice)

        if dlg.choice == "minimize":
            event.ignore()
            self.hide()
        else:
            event.accept()
            QApplication.instance().quit()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.reset_idle_timer()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        self.reset_idle_timer()
        super().keyPressEvent(event)
