"""SettingsDialog — category-panel preferences dialog.

Layout: category list on the left, stacked sub-panels on the right
(Notepad++ ``PreferenceDlg`` pattern).

Categories:  Appearance | Editor | Behaviour | Files

Refs: [BL B-109] [REQ R9.1–R9.6]
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.config import ConfigStore


class SettingsDialog(QDialog):
    """Settings dialog with a category list on the left and stacked sub-panels
    on the right.

    All widget attribute names are preserved from the previous form-based
    version so existing tests keep working unchanged.
    """

    def __init__(self, config: ConfigStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(640, 420)
        self._config = config
        self._original_gpu_accel = (config.get("gpu_acceleration") or "no") == "yes"

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._category_list = QListWidget()
        self._category_list.setObjectName("SettingsCategory")
        self._category_list.setFixedWidth(160)
        self._category_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        outer.addWidget(self._category_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        self._pages = QStackedWidget()
        right_layout.addWidget(self._pages, stretch=1)

        self._build_page_appearance(config)
        self._build_page_editor(config)
        self._build_page_behaviour(config)
        self._build_page_files(config)

        self._category_list.currentRowChanged.connect(self._pages.setCurrentIndex)
        self._category_list.setCurrentRow(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)
        outer.addWidget(right, stretch=1)

    # ------------------------------------------------------------------
    # Sub-panel builders
    # ------------------------------------------------------------------
    def _add_page(self, title: str, page: QWidget) -> None:
        self._category_list.addItem(title)
        self._pages.addWidget(page)

    def _build_page_appearance(self, config: ConfigStore) -> None:
        page = QWidget()
        form = QFormLayout(page)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["light", "dark"])
        self._theme_combo.setCurrentText(config.get("theme") or "light")
        self._theme_combo.setMinimumWidth(220)
        form.addRow("Theme:", self._theme_combo)

        self._font_family_combo = QFontComboBox()
        current_family = config.get("font_family") or ""
        if current_family:
            self._font_family_combo.setCurrentText(current_family)
        self._font_family_combo.setMinimumWidth(220)
        form.addRow("Font family:", self._font_family_combo)

        self._font_spin = QSpinBox()
        self._font_spin.setRange(8, 32)
        try:
            self._font_spin.setValue(int(config.get("font_size") or 12))
        except (TypeError, ValueError):
            self._font_spin.setValue(12)
        self._font_spin.setMinimumWidth(220)
        form.addRow("Font size (pt):", self._font_spin)

        self._word_wrap_check = QCheckBox("Wrap long lines in the editor")
        self._word_wrap_check.setChecked((config.get("word_wrap") or "yes") == "yes")
        wrap_holder = QWidget()
        wrap_layout = QHBoxLayout(wrap_holder)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.addWidget(self._word_wrap_check)
        wrap_layout.addStretch(1)
        form.addRow("Word wrap:", wrap_holder)

        self._accent_combo = QComboBox()
        self._accent_combo.addItems(["purple", "pink", "cyan", "green", "orange"])
        self._accent_combo.setCurrentText(config.get("accent_color") or "purple")
        self._accent_combo.setMinimumWidth(220)
        form.addRow("Accent colour:", self._accent_combo)

        self._add_page("Appearance", page)

    def _build_page_editor(self, config: ConfigStore) -> None:
        page = QWidget()
        form = QFormLayout(page)

        self._default_encrypt_combo = QComboBox()
        self._default_encrypt_combo.addItems(["no", "yes"])
        self._default_encrypt_combo.setCurrentText(config.get("default_encrypt") or "no")
        form.addRow("Default encrypt new notes:", self._default_encrypt_combo)

        hint = QLabel(
            "<i>Any passphrase length is accepted; longer passphrases "
            "provide stronger encryption.</i>"
        )
        hint.setWordWrap(True)
        form.addRow(hint)

        self._add_page("Editor", page)

    def _build_page_behaviour(self, config: ConfigStore) -> None:
        page = QWidget()
        form = QFormLayout(page)

        self._close_behavior_combo = QComboBox()
        self._close_behavior_combo.addItems(["ask", "minimize", "quit"])
        self._close_behavior_combo.setItemData(
            0, "Always ask what to do", Qt.ItemDataRole.ToolTipRole
        )
        self._close_behavior_combo.setItemData(
            1, "Always minimize to tray", Qt.ItemDataRole.ToolTipRole
        )
        self._close_behavior_combo.setItemData(
            2, "Always quit", Qt.ItemDataRole.ToolTipRole
        )
        self._close_behavior_combo.setCurrentText(config.get("close_behavior") or "ask")
        form.addRow("When closing window:", self._close_behavior_combo)

        self._auto_login_check = QCheckBox("Keep me signed in when the app restarts")
        self._auto_login_check.setChecked((config.get("auto_login") or "no") == "yes")
        auto_login_holder = QWidget()
        hl = QHBoxLayout(auto_login_holder)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self._auto_login_check)
        hl.addStretch(1)
        form.addRow("Auto login:", auto_login_holder)

        self._gpu_accel_check = QCheckBox(
            "Use GPU acceleration for the rich text editor"
        )
        self._gpu_accel_check.setChecked((config.get("gpu_acceleration") or "no") == "yes")
        gpu_holder = QWidget()
        gpu_hl = QHBoxLayout(gpu_holder)
        gpu_hl.setContentsMargins(0, 0, 0, 0)
        gpu_hl.addWidget(self._gpu_accel_check)
        gpu_hl.addStretch(1)
        form.addRow("Hardware acceleration:", gpu_holder)

        gpu_note = QLabel("<i>Takes effect after restarting AstraNotes.</i>")
        form.addRow("", gpu_note)

        self._add_page("Behaviour", page)

    def _build_page_files(self, config: ConfigStore) -> None:  # noqa: ARG002
        """Supported Formats panel — analogous to Notepad++ File Association."""
        page = QWidget()
        layout = QVBoxLayout(page)

        heading = QLabel("<b>Supported file formats</b>")
        layout.addWidget(heading)

        body = QLabel(
            "Notes are stored as opaque encrypted <i>blobs</i>, so AstraNotes "
            "can hold any file kind.  Rendering / editing the content, however, "
            "depends on what your environment supports:"
            "<ul>"
            "<li><b>Plain text &amp; rich text</b> — supported out of the box.</li>"
            "<li><b>Markdown</b> — supported out of the box (rendered as rich text).</li>"
            "<li><b>Images</b> (PNG, JPG, GIF, WebP, SVG) — supported via Qt.</li>"
            "<li><b>Audio &amp; video</b> — requires a media plugin "
            "(<code>QMediaPlayer</code> backend installed).</li>"
            "<li><b>PDF / Office / archives / any other binary</b> — stored "
            "as a blob; rendering requires a matching <b>plugin</b>.</li>"
            "</ul>"
            "Open <b>Plugins → Plugins Admin...</b> to see what's currently "
            "installed and what file kinds each plugin handles."
        )
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(body)
        layout.addStretch(1)

        self._add_page("Files", page)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _on_accept(self) -> None:
        self._config.set("theme", self._theme_combo.currentText())
        self._config.set("font_family", self._font_family_combo.currentFont().family())
        self._config.set("font_size", self._font_spin.value())
        self._config.set("word_wrap", "yes" if self._word_wrap_check.isChecked() else "no")
        self._config.set("accent_color", self._accent_combo.currentText())
        self._config.set("default_encrypt", self._default_encrypt_combo.currentText())
        self._config.set("close_behavior", self._close_behavior_combo.currentText())
        self._config.set("auto_login", "yes" if self._auto_login_check.isChecked() else "no")
        gpu_on = self._gpu_accel_check.isChecked()
        self._config.set("gpu_acceleration", "yes" if gpu_on else "no")
        gpu_changed = gpu_on != self._original_gpu_accel
        self.accept()
        if gpu_changed:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self.parentWidget(),
                "Restart Required",
                "Hardware acceleration setting will take effect after restarting AstraNotes.",
            )

    @property
    def theme(self) -> str:
        return self._theme_combo.currentText()

    @property
    def font_size(self) -> int:
        return self._font_spin.value()

    @property
    def font_family(self) -> str:
        return self._font_family_combo.currentFont().family()

    @property
    def word_wrap(self) -> bool:
        return self._word_wrap_check.isChecked()
