"""Utility dialogs for the AstraNotes desktop GUI.

Classes
-------
PassphraseDialog      -- modal passphrase prompt
_CloseChoiceDialog    -- minimize-or-quit prompt
_AliasPromptDialog    -- alias chooser for encrypted notes
_NewNoteTypeDialog    -- format/encryption chooser for new notes
_WidgetGallery        -- developer-only QSS preview (Ctrl+Shift+G)

Refs: [BL B-97, B-106, B-109, B-112]
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# PassphraseDialog
# ---------------------------------------------------------------------------
class PassphraseDialog(QDialog):
    """Modal dialog that prompts for a passphrase.

    Attributes
    ----------
    passphrase : str
        The entered passphrase, or ``""`` if cancelled.
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
# _CloseChoiceDialog  [BL B-97]
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
# _AliasPromptDialog  [B-106]
# ---------------------------------------------------------------------------
class _AliasPromptDialog(QDialog):
    """Ask the user to set a display alias for a newly-encrypted note."""

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
# _NewNoteTypeDialog  [B-109]
# ---------------------------------------------------------------------------
class _NewNoteTypeDialog(QDialog):
    """Chooser shown when the user starts a brand-new note.

    Formats are supplied exclusively by plugins via their ``provides_formats``
    attribute.  On accept the selection is exposed via:

    * :pyattr:`note_format`  -- MIME-style format string (``"text/html"`` etc.)
    * :pyattr:`format_label` -- short human label (``"Rich text"``)
    * :pyattr:`encrypted`    -- whether to encrypt the note
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        default_encrypt: bool = False,
        plugin_formats: Optional[list[tuple[str, str, str]]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Note")
        self.setMinimumWidth(420)
        self.note_format: str = "text/html"
        self.format_label: str = "Note"
        self.encrypted: bool = default_encrypt

        layout = QVBoxLayout(self)

        choices = list(plugin_formats) if plugin_formats else []

        self._list: Optional[QListWidget] = None
        self._desc: Optional[QLabel] = None

        if choices:
            layout.addWidget(QLabel("<b>Choose a format for the new note</b>"))
            # initialise defaults from the first available format
            self.format_label, self.note_format, _first_desc = choices[0]
            self._list = QListWidget()
            for label, mime, desc in choices:
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, (label, mime, desc))
                item.setToolTip(desc)
                self._list.addItem(item)
            self._list.setCurrentRow(0)
            self._list.itemDoubleClicked.connect(self._on_accept)
            self._list.currentItemChanged.connect(self._on_selection_changed)
            layout.addWidget(self._list, stretch=1)

            self._desc = QLabel(choices[0][2])
            self._desc.setWordWrap(True)
            layout.addWidget(self._desc)

        self._enc_check = QCheckBox("Encrypt this note")
        self._enc_check.setChecked(default_encrypt)
        self._enc_check.setToolTip(
            "Protect the note with a passphrase.  You can also toggle this "
            "later from the editor."
        )
        layout.addWidget(self._enc_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_selection_changed(
        self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]
    ) -> None:  # noqa: ARG002
        if current is None or self._desc is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if data:
            self._desc.setText(data[2])

    def _on_accept(self, *_: object) -> None:
        if self._list is not None:
            item = self._list.currentItem()
            if item is not None:
                label, mime, _desc = item.data(Qt.ItemDataRole.UserRole)
                self.format_label = label
                self.note_format = mime
        self.encrypted = self._enc_check.isChecked()
        self.accept()


# ---------------------------------------------------------------------------
# _WidgetGallery  — developer-only QSS preview (Ctrl+Shift+G)
# ---------------------------------------------------------------------------
class _WidgetGallery(QDialog):
    """Shows one of every styled widget in its main visual states.

    Not wired to any user-visible menu; open with Ctrl+Shift+G.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AstraNotes -- Widget Gallery (Ctrl+Shift+G)")
        self.resize(820, 560)

        outer = QVBoxLayout(self)
        hint = QLabel(
            "Developer preview of every styled widget.  Edit "
            "<code>src/desktop/styles/dark.qss</code> or "
            "<code>light.qss</code> and (with "
            "<code>ASTRANOTES_QSS_HOTRELOAD=1</code> set) the changes "
            "appear here on file save."
        )
        hint.setWordWrap(True)
        outer.addWidget(hint)

        tabs = QTabWidget()
        tabs.addTab(self._build_inputs_tab(), "Inputs")
        tabs.addTab(self._build_lists_tab(), "Lists && Trees")
        tabs.addTab(self._build_misc_tab(), "Misc")
        outer.addWidget(tabs, stretch=1)

        bar = QStatusBar()
        bar.showMessage("Status bar message")
        l1 = QLabel("Permanent A")
        l2 = QLabel("Permanent B")
        bar.addPermanentWidget(l1)
        bar.addPermanentWidget(l2)
        outer.addWidget(bar)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        outer.addWidget(buttons)

    def _build_inputs_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        line = QLineEdit()
        line.setPlaceholderText("QLineEdit placeholder text...")
        form.addRow("Normal:", line)

        line_disabled = QLineEdit("disabled value")
        line_disabled.setEnabled(False)
        form.addRow("Disabled:", line_disabled)

        combo = QComboBox()
        combo.addItems(["Option A", "Option B", "Option C"])
        form.addRow("QComboBox:", combo)

        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(42)
        form.addRow("QSpinBox:", spin)

        chk_row = QHBoxLayout()
        c1 = QCheckBox("Unchecked")
        c2 = QCheckBox("Checked")
        c2.setChecked(True)
        c3 = QCheckBox("Disabled")
        c3.setEnabled(False)
        for c in (c1, c2, c3):
            chk_row.addWidget(c)
        chk_row.addStretch(1)
        chk_wrap = QWidget()
        chk_wrap.setLayout(chk_row)
        form.addRow("QCheckBox:", chk_wrap)

        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("Default"))
        b2 = QPushButton("Disabled")
        b2.setEnabled(False)
        btn_row.addWidget(b2)
        btn_row.addWidget(QPushButton("Long button label"))
        btn_row.addStretch(1)
        btn_wrap = QWidget()
        btn_wrap.setLayout(btn_row)
        form.addRow("QPushButton:", btn_wrap)

        text = QTextEdit()
        text.setPlaceholderText("QTextEdit placeholder")
        text.setPlainText("Some sample text.\nLine two.\nLine three.")
        text.setFixedHeight(80)
        form.addRow("QTextEdit:", text)

        return w

    def _build_lists_tab(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)

        lst = QListWidget()
        for i in range(8):
            lst.addItem(QListWidgetItem(f"List item {i + 1}"))
        lst.setCurrentRow(2)
        layout.addWidget(lst, stretch=1)

        tree = QTreeWidget()
        tree.setColumnCount(3)
        tree.setHeaderLabels(["Name", "Version", "Status"])
        for i in range(6):
            item = QTreeWidgetItem(
                [f"Plugin {i + 1}", f"1.0.{i}", "Allowed" if i % 2 else "Disabled"]
            )
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                0, Qt.CheckState.Checked if i % 2 else Qt.CheckState.Unchecked
            )
            tree.addTopLevelItem(item)
        layout.addWidget(tree, stretch=2)

        return w

    def _build_misc_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        inner_tabs = QTabWidget()
        for i in range(4):
            page = QLabel(f"Tab {i + 1} content")
            page.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner_tabs.addTab(page, f"Tab {i + 1}")
        layout.addWidget(inner_tabs)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(QLabel("Left pane"))
        split.addWidget(QLabel("Right pane"))
        split.setSizes([200, 400])
        split.setFixedHeight(50)
        layout.addWidget(split)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        tip_btn = QPushButton("Hover me for a tooltip")
        tip_btn.setToolTip("This is a styled QToolTip.")
        layout.addWidget(tip_btn)

        layout.addStretch(1)
        return w
