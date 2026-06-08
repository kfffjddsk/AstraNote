"""NoteEditorWidget, PluginEditorHost, and _WelcomeWidget.

NoteEditorWidget — legacy per-tab editor (kept for test backward-compat).
PluginEditorHost — drop-in replacement that wraps any EditorProtocol plugin.
_WelcomeWidget   — blank screen shown when no tab is open.

Refs: [BL B-103, B-105, B-106, B-111]
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QTextCharFormat
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from src.core.notes import Note

_ENCRYPTED_PLACEHOLDER = "[Encrypted]"


# ---------------------------------------------------------------------------
# NoteEditorWidget  [B-105, B-106]
# ---------------------------------------------------------------------------
class NoteEditorWidget(QWidget):
    """Per-tab editor: title/alias, rich-text body, encrypt toggle, unlock button.

    Backward-compatible API (test_sprint4.py):
        clear(), load(), get_title(), get_content(), is_encrypted(),
        set_encrypted(), show_encrypted_placeholder()
    Sprint 4B additions:
        get_alias(), get_html_content(), unlock_requested signal, apply_font_size()
    Sprint 5C additions:
        save_requested, delete_requested signals; 💾 and 🗑 toolbar buttons
    """

    content_changed = Signal()
    unlock_requested = Signal()   # emitted by the 🔓 Unlock button  [B-106]
    save_requested = Signal()     # emitted by the 💾 button in the editor bar
    delete_requested = Signal()   # emitted by the 🗑 button in the editor bar

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Title row (always visible)
        self._title_row = QWidget()
        title_layout = QHBoxLayout(self._title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(QLabel("Title:"))
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Note title")
        self._title_edit.textChanged.connect(self.content_changed)
        title_layout.addWidget(self._title_edit)
        layout.addWidget(self._title_row)

        # Rich-text formatting toolbar  [B-105]
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
        self._font_size_combo.setFixedWidth(72)
        self._font_size_combo.setToolTip("Font size")
        self._font_size_combo.currentTextChanged.connect(self._on_font_size_changed)
        self._fmt_bar.addWidget(self._font_size_combo)

        self._fmt_bar.addSeparator()

        # Flexible spacer pushes save/delete to the right.
        fmt_spacer = QWidget()
        fmt_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._fmt_bar.addWidget(fmt_spacer)

        self._fmt_save_btn = QToolButton()
        self._fmt_save_btn.setText("\U0001f4be")
        self._fmt_save_btn.setToolTip("Save  (Ctrl+S)")
        self._fmt_save_btn.clicked.connect(self.save_requested)
        self._fmt_bar.addWidget(self._fmt_save_btn)

        self._fmt_delete_btn = QToolButton()
        self._fmt_delete_btn.setText("\U0001f5d1")
        self._fmt_delete_btn.setToolTip("Delete Note")
        self._fmt_delete_btn.clicked.connect(self.delete_requested)
        self._fmt_bar.addWidget(self._fmt_delete_btn)

        layout.addWidget(self._fmt_bar)

        # Rich-text content editor  [B-105]
        self._content_edit = QTextEdit()
        self._content_edit.setAcceptRichText(True)
        self._content_edit.textChanged.connect(self.content_changed)
        self._content_edit.currentCharFormatChanged.connect(self._update_format_buttons)
        layout.addWidget(self._content_edit)

        # Bottom row: encrypt checkbox + unlock button  [B-106]
        bottom = QHBoxLayout()
        self._encrypt_check = QCheckBox("Encrypted")
        self._encrypt_check.toggled.connect(self._on_encrypt_toggled)
        self._encrypt_check.toggled.connect(lambda _: self.content_changed.emit())
        bottom.addWidget(self._encrypt_check)
        bottom.addStretch()
        self._unlock_btn = QPushButton("\U0001f513 Unlock")
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

    def load(self, note: "Note", *, decrypted_content: Optional[str] = None) -> None:
        """Populate editor from *note*.

        For encrypted notes the content area shows ``[Encrypted]`` (and the
        unlock button) unless *decrypted_content* is provided.
        """
        self._title_edit.setText(note.title)
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

    def apply_font_family(self, family: str) -> None:
        """Apply a font family to the content editor."""
        if not family:
            return
        font = self._content_edit.font()
        font.setFamily(family)
        self._content_edit.setFont(font)

    def apply_word_wrap(self, enabled: bool) -> None:
        """Toggle long-line wrapping in the editor."""
        mode = (
            QTextEdit.LineWrapMode.WidgetWidth
            if enabled
            else QTextEdit.LineWrapMode.NoWrap
        )
        self._content_edit.setLineWrapMode(mode)

    def apply_format(self, mime: str) -> None:
        """Configure the editor for a specific note format.

        - ``text/plain`` / ``text/markdown``: source mode (no rich-text paste).
        - ``text/html`` (or anything else): rich-text mode.
        """
        accept_rich = mime not in ("text/plain", "text/markdown")
        self._content_edit.setAcceptRichText(accept_rich)
        for btn in (self._bold_btn, self._italic_btn, self._underline_btn):
            btn.setVisible(accept_rich)


# ---------------------------------------------------------------------------
# _NoEditorWidget — fallback when no plugin provides an editor
# ---------------------------------------------------------------------------

class _NoEditorWidget(QWidget):
    """Lightweight EditorProtocol fallback used when no plugin is loaded.

    In production TiptapPlugin is always available; this widget exists so
    tests that construct MainWindow without a plugin registry still have a
    functional editor they can interact with via _title_edit / _content_edit.
    """

    save_requested = Signal(str, object)
    content_changed = Signal()
    delete_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Note title")
        self._title_edit.textChanged.connect(self.content_changed)
        layout.addWidget(self._title_edit)
        self._content_edit = QTextEdit()
        self._content_edit.textChanged.connect(self.content_changed)
        layout.addWidget(self._content_edit)

    def as_widget(self) -> QWidget:
        return self

    def load(self, title: str, data: Any) -> None:
        self._title_edit.blockSignals(True)
        self._content_edit.blockSignals(True)
        self._title_edit.setText(str(title) if title else "")
        if isinstance(data, str) and data.lstrip().startswith("<"):
            self._content_edit.setHtml(data)
        else:
            self._content_edit.setPlainText(str(data) if data else "")
        self._title_edit.blockSignals(False)
        self._content_edit.blockSignals(False)

    def show_save_result(self, ok: bool, msg: str) -> None:
        pass

    def get_title(self) -> str:
        return self._title_edit.text().strip()

    def get_content(self) -> str:
        return self._content_edit.toPlainText().strip()

    def get_html_content(self) -> str:
        return self._content_edit.toHtml()


# ---------------------------------------------------------------------------
# PluginEditorHost  [B-103, B-105, B-106]
# ---------------------------------------------------------------------------


class PluginEditorHost(QWidget):
    """Tab-level host that wraps any EditorProtocol plugin widget.

    Provides the same public API as :class:`NoteEditorWidget` so that
    :class:`~src.desktop.main_window.MainWindow` can use it as a drop-in
    replacement.

    Responsibilities
    ----------------
    - Embed the plugin editor widget (``editor.as_widget()``).
    - Manage the encrypted / locked overlay (hides the plugin widget and shows
      a ``[Encrypted]`` placeholder when the note is locked).
    - Own the ``Encrypted`` checkbox and ``🔓 Unlock`` button — the plugin
      knows nothing about encryption.
    - Forward ``content_changed``, ``save_requested``, ``delete_requested``,
      and ``unlock_requested`` signals to ``MainWindow``.

    Parameters
    ----------
    editor:
        An object satisfying :class:`~src.core.editor_protocol.EditorProtocol`.
        When ``None`` a minimal no-op placeholder is shown.
    """

    content_changed = Signal()
    unlock_requested = Signal()
    save_requested = Signal()    # no-args, for MainWindow._on_save() compat
    delete_requested = Signal()

    def __init__(
        self,
        editor: Any = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        if editor is None:
            editor = _NoEditorWidget()
        self._plugin_editor = editor
        # Routing MIME of the editor this host wraps; set by MainWindow when the
        # tab is opened.  Used to re-route the tab to the correct editor after an
        # encrypted note is decrypted (the real MIME is only known post-decrypt).
        self._routing_mime: str = "text/html"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Content area: stacked between locked placeholder and live editor ──
        self._stack = QStackedWidget()

        # Page 0 — live plugin editor
        self._stack.addWidget(editor.as_widget())

        # Page 1 — locked placeholder (shown when encrypted + not yet unlocked)
        locked_page = QWidget()
        locked_layout = QVBoxLayout(locked_page)
        locked_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._locked_label = QLabel(_ENCRYPTED_PLACEHOLDER)
        self._locked_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._locked_label.setStyleSheet("color: #888; font-size: 16pt;")
        locked_layout.addWidget(self._locked_label)
        self._stack.addWidget(locked_page)

        layout.addWidget(self._stack, stretch=1)

        # ── Bottom row: encrypt checkbox + unlock button ──────────────────────
        bottom = QHBoxLayout()
        bottom.setContentsMargins(6, 2, 6, 4)
        self._encrypt_check = QCheckBox("Encrypted")
        self._encrypt_check.toggled.connect(self._on_encrypt_toggled)
        bottom.addWidget(self._encrypt_check)
        bottom.addStretch()
        self._unlock_btn = QPushButton("\U0001f513 Unlock")
        self._unlock_btn.setToolTip("Decrypt this note with your passphrase")
        self._unlock_btn.clicked.connect(self.unlock_requested)
        self._unlock_btn.setVisible(False)
        bottom.addWidget(self._unlock_btn)
        layout.addLayout(bottom)

        # ── Wire plugin signals ───────────────────────────────────────────────
        editor.content_changed.connect(self.content_changed)
        # save_requested on the plugin carries (title, content) — strip to no-args
        editor.save_requested.connect(lambda *_: self.save_requested.emit())
        # delete_requested is optional (not in EditorProtocol)
        if hasattr(editor, "delete_requested"):
            editor.delete_requested.connect(self.delete_requested)

    # ------------------------------------------------------------------
    # NoteEditorWidget-compatible API
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self._plugin_editor.load("", "")
        self._stack.setCurrentIndex(0)
        self._encrypt_check.blockSignals(True)
        self._encrypt_check.setChecked(False)
        self._encrypt_check.blockSignals(False)
        self._unlock_btn.setVisible(False)

    def load(self, note: "Note", *, decrypted_content: Optional[str] = None) -> None:
        self._encrypt_check.blockSignals(True)
        self._encrypt_check.setChecked(note.encrypted)
        self._encrypt_check.blockSignals(False)
        if note.encrypted and decrypted_content is None:
            self._stack.setCurrentIndex(1)   # show locked overlay
            self._unlock_btn.setVisible(True)
        else:
            self._stack.setCurrentIndex(0)   # show live editor
            self._unlock_btn.setVisible(False)
            self._plugin_editor.load(
                note.title,
                decrypted_content if decrypted_content is not None else (note.content or ""),
            )

    def get_title(self) -> str:
        return getattr(self._plugin_editor, "get_title", lambda: "")()

    def set_title(self, title: str) -> None:
        if hasattr(self._plugin_editor, "set_title"):
            self._plugin_editor.set_title(title)

    def get_content(self) -> str:
        if self._stack.currentIndex() == 1:   # locked overlay is visible
            return _ENCRYPTED_PLACEHOLDER
        return getattr(self._plugin_editor, "get_content", lambda: "")()

    def get_alias(self) -> str:
        return self.get_title()

    def get_html_content(self) -> str:
        if self._stack.currentIndex() == 1:
            return _ENCRYPTED_PLACEHOLDER
        return getattr(self._plugin_editor, "get_html_content", self.get_content)()

    def is_encrypted(self) -> bool:
        return self._encrypt_check.isChecked()

    def set_encrypted(self, value: bool = True) -> None:
        self._encrypt_check.setChecked(value)

    def show_encrypted_placeholder(self) -> None:
        self._stack.setCurrentIndex(1)
        self._unlock_btn.setVisible(True)

    def lock(self) -> None:
        """Re-lock a previously-decrypted encrypted note.

        Discards the decrypted content from the wrapped editor widget (so it is
        not left in memory or revealed when the tab is shown again), stops any
        media playback, and shows the locked overlay.  Used when navigating away
        from an encrypted note in high-security mode.
        """
        try:
            self._plugin_editor.load("", "")
        except Exception:
            pass
        self._stack.setCurrentIndex(1)
        self._unlock_btn.setVisible(True)
        self._encrypt_check.blockSignals(True)
        self._encrypt_check.setChecked(True)
        self._encrypt_check.blockSignals(False)

    def apply_font_size(self, size: int) -> None:
        getattr(self._plugin_editor, "apply_font_size", lambda s: None)(size)

    def apply_font_family(self, family: str) -> None:
        getattr(self._plugin_editor, "apply_font_family", lambda f: None)(family)

    def apply_word_wrap(self, enabled: bool) -> None:
        getattr(self._plugin_editor, "apply_word_wrap", lambda e: None)(enabled)

    def apply_format(self, mime: str) -> None:
        getattr(self._plugin_editor, "apply_format", lambda m: None)(mime)

    def apply_theme(self, theme: str) -> None:
        getattr(self._plugin_editor, "apply_theme", lambda t: None)(theme)

    # ------------------------------------------------------------------
    # Internal-attribute proxies (test backward-compat)
    # Tests that previously accessed NoteEditorWidget._title_edit /
    # _content_edit directly continue to work through these proxies.
    # ------------------------------------------------------------------

    @property
    def _title_edit(self) -> Any:
        return getattr(self._plugin_editor, "_title_edit", None)

    @property
    def _content_edit(self) -> Any:
        return getattr(self._plugin_editor, "_content_edit", None)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_encrypt_toggled(self, _checked: bool) -> None:
        self.content_changed.emit()


# ---------------------------------------------------------------------------
# _WelcomeWidget  [B-103]
# ---------------------------------------------------------------------------
class _WelcomeWidget(QWidget):
    """Blank welcome screen with suggested actions, shown when no tab is open."""

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

        new_btn = QPushButton("  ✓ New Note   (Ctrl+N)")
        new_btn.setFixedWidth(220)
        new_btn.setFixedHeight(36)
        new_btn.clicked.connect(self.new_note_requested)
        inner.addWidget(new_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        search_hint = QLabel("Or click any note in the list on the left to open it.")
        search_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_hint.setStyleSheet("font-size: 9pt; color: #888;")
        inner.addWidget(search_hint)

        outer.addLayout(inner)
