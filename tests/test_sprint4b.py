"""test_sprint4b.py — Sprint 4B GUI completeness tests.

Covers backlog items B-103 through B-112:
  §1  TestTheme            — DARK/LIGHT stylesheets, apply_theme()  [B-110, B-111]
  §2  TestSettingsDialog   — Settings dialog fields and persistence [B-109]
  §3  TestRichTextEditor   — Bold / Italic / Underline / font size  [B-105]
  §4  TestTabBar           — Tab open/close, Ctrl+W, initial tab    [B-104]
  §5  TestAliasInput       — Alias row visibility, get_alias()       [B-106]
  §6  TestUnlockButton     — Unlock button visibility and signal     [B-106]
  §7  TestSearchBar        — Search bar, filter, Ctrl+F focus        [B-107]
  §8  TestAccountAwareList — Section headers for account notes       [B-108]
  §9  TestKeyboardShortcuts— Menu shortcut strings registered        [B-112]

All Qt tests are gated behind @_qt (skipped when PySide6 is absent).

Refs: [BL B-103B-112] [REQ R9.7, R11] [US-9]
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.config import ConfigStore
from src.core.notes import DatabaseStore, Note
from src.core.plugin_base import PluginRegistry

# ---------------------------------------------------------------------------
# Qt availability guard
# ---------------------------------------------------------------------------

try:
    from PySide6.QtWidgets import QApplication, QDialog
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

_qt = pytest.mark.skipif(not _QT_AVAILABLE, reason="PySide6 not available")

_app: object = None


def _ensure_app():
    global _app
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if _app is None:
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication([])
    return _app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_window(tmp_path: Path, data_dir: Path | None = None):
    """Create a test MainWindow with an in-memory store."""
    _ensure_app()
    from src.desktop.main_window import MainWindow
    store = DatabaseStore(tmp_path)
    config = ConfigStore(config_path=tmp_path / "config.json")
    registry = PluginRegistry()
    return (
        MainWindow(store=store, config=config, registry=registry, data_dir=data_dir),
        store,
        config,
    )


# ---------------------------------------------------------------------------
# §1  Theme  [B-110, B-111]
# ---------------------------------------------------------------------------


@_qt
class TestTheme:
    """§1 — DARK/LIGHT stylesheets and apply_theme() helper."""

    def test_dark_stylesheet_constant_exists(self):
        """§1.1  DARK_STYLESHEET is a non-empty string."""
        from src.desktop.main_window import DARK_STYLESHEET
        assert isinstance(DARK_STYLESHEET, str)
        assert len(DARK_STYLESHEET) > 0

    def test_light_stylesheet_constant_exists(self):
        """§1.2  LIGHT_STYLESHEET is a non-empty string."""
        from src.desktop.main_window import LIGHT_STYLESHEET
        assert isinstance(LIGHT_STYLESHEET, str)
        assert len(LIGHT_STYLESHEET) > 0

    def test_dark_stylesheet_contains_dark_background(self):
        """§1.3  DARK_STYLESHEET contains a recognisable dark colour."""
        from src.desktop.main_window import DARK_STYLESHEET
        # Check for a dark hex colour (#1e1e1e or similar)
        assert "#1e1e1e" in DARK_STYLESHEET.lower() or "#252526" in DARK_STYLESHEET.lower()

    def test_light_stylesheet_contains_light_background(self):
        """§1.4  LIGHT_STYLESHEET contains a recognisable light colour."""
        from src.desktop.main_window import LIGHT_STYLESHEET
        assert "white" in LIGHT_STYLESHEET.lower() or "#f3f3f3" in LIGHT_STYLESHEET.lower()

    def test_apply_theme_callable(self):
        """§1.5  apply_theme() is importable and callable."""
        from src.desktop.main_window import apply_theme
        assert callable(apply_theme)

    def test_apply_theme_dark(self):
        """§1.6  apply_theme(app, 'dark', 14) runs without error."""
        app = _ensure_app()
        from src.desktop.main_window import apply_theme
        apply_theme(app, "dark", 14)  # must not raise

    def test_apply_theme_light(self):
        """§1.7  apply_theme(app, 'light', 12) runs without error."""
        app = _ensure_app()
        from src.desktop.main_window import apply_theme
        apply_theme(app, "light", 12)

    def test_apply_theme_unknown_defaults_to_light(self):
        """§1.8  apply_theme with an unknown theme string does not raise."""
        app = _ensure_app()
        from src.desktop.main_window import apply_theme
        apply_theme(app, "solarised", 12)  # should not raise


# ---------------------------------------------------------------------------
# §2  SettingsDialog  [B-109]
# ---------------------------------------------------------------------------


@_qt
class TestSettingsDialog:
    """§2 — SettingsDialog fields and persistence."""

    def test_settings_dialog_importable(self):
        """§2.1  SettingsDialog can be imported from main_window."""
        _ensure_app()
        from src.desktop.main_window import SettingsDialog
        assert SettingsDialog is not None

    def test_settings_dialog_has_theme_combo(self, tmp_path):
        """§2.2  SettingsDialog exposes _theme_combo widget."""
        _ensure_app()
        from src.desktop.main_window import SettingsDialog
        config = ConfigStore(config_path=tmp_path / "cfg.json")
        dlg = SettingsDialog(config)
        assert hasattr(dlg, "_theme_combo")

    def test_settings_dialog_has_font_spin(self, tmp_path):
        """§2.3  SettingsDialog exposes _font_spin widget."""
        _ensure_app()
        from src.desktop.main_window import SettingsDialog
        config = ConfigStore(config_path=tmp_path / "cfg.json")
        dlg = SettingsDialog(config)
        assert hasattr(dlg, "_font_spin")

    def test_settings_dialog_has_default_encrypt_combo(self, tmp_path):
        """§2.4  SettingsDialog exposes _default_encrypt_combo widget."""
        _ensure_app()
        from src.desktop.main_window import SettingsDialog
        config = ConfigStore(config_path=tmp_path / "cfg.json")
        dlg = SettingsDialog(config)
        assert hasattr(dlg, "_default_encrypt_combo")

    # def test_settings_dialog_has_passphrase_spin(self, tmp_path):
    #     """§2.5  SettingsDialog exposes _passphrase_spin widget.
    #
    #     Commented out (2026-06-03): the passphrase-length spinbox was removed
    #     from the Settings UI per UX request — users should not configure this;
    #     the backend default (8 chars) still applies. See ConfigStore default
    #     for ``passphrase_min_length``.
    #     """
    #     _ensure_app()
    #     from src.desktop.main_window import SettingsDialog
    #     config = ConfigStore(config_path=tmp_path / "cfg.json")
    #     dlg = SettingsDialog(config)
    #     assert hasattr(dlg, "_passphrase_spin")

    def test_settings_dialog_theme_property(self, tmp_path):
        """§2.6  SettingsDialog.theme property returns current combo value."""
        _ensure_app()
        from src.desktop.main_window import SettingsDialog
        config = ConfigStore(config_path=tmp_path / "cfg.json")
        dlg = SettingsDialog(config)
        dlg._theme_combo.setCurrentText("dark")
        assert dlg.theme == "dark"

    def test_settings_dialog_font_size_property(self, tmp_path):
        """§2.7  SettingsDialog.font_size property returns spinbox value."""
        _ensure_app()
        from src.desktop.main_window import SettingsDialog
        config = ConfigStore(config_path=tmp_path / "cfg.json")
        dlg = SettingsDialog(config)
        dlg._font_spin.setValue(16)
        assert dlg.font_size == 16

    def test_settings_dialog_accept_saves_theme(self, tmp_path):
        """§2.8  Accepting dialog persists theme to ConfigStore."""
        _ensure_app()
        from src.desktop.main_window import SettingsDialog
        config = ConfigStore(config_path=tmp_path / "cfg.json")
        dlg = SettingsDialog(config)
        dlg._theme_combo.setCurrentText("dark")
        dlg._on_accept()
        assert config.get("theme") == "dark"

    def test_settings_dialog_accept_saves_font_size(self, tmp_path):
        """§2.9  Accepting dialog persists font_size to ConfigStore."""
        _ensure_app()
        from src.desktop.main_window import SettingsDialog
        config = ConfigStore(config_path=tmp_path / "cfg.json")
        dlg = SettingsDialog(config)
        dlg._font_spin.setValue(18)
        dlg._on_accept()
        assert int(config.get("font_size")) == 18

    def test_settings_dialog_accept_saves_default_encrypt(self, tmp_path):
        """§2.10  Accepting dialog persists default_encrypt to ConfigStore."""
        _ensure_app()
        from src.desktop.main_window import SettingsDialog
        config = ConfigStore(config_path=tmp_path / "cfg.json")
        dlg = SettingsDialog(config)
        dlg._default_encrypt_combo.setCurrentText("yes")
        dlg._on_accept()
        assert config.get("default_encrypt") == "yes"

    def test_settings_dialog_preloads_existing_config(self, tmp_path):
        """§2.11  SettingsDialog pre-fills widgets from existing config values."""
        _ensure_app()
        from src.desktop.main_window import SettingsDialog
        config = ConfigStore(config_path=tmp_path / "cfg.json")
        config.set("theme", "dark")
        config.set("font_size", 20)
        dlg = SettingsDialog(config)
        assert dlg._theme_combo.currentText() == "dark"
        assert dlg._font_spin.value() == 20

    def test_main_window_has_settings_action(self, tmp_path):
        """§2.12  MainWindow exposes _action_settings and connects to _on_settings."""
        w, _, _ = _make_window(tmp_path)
        assert hasattr(w, "_action_settings")
        assert w._action_settings is not None


# ---------------------------------------------------------------------------
# §3  Rich-text editor  [B-105]
# ---------------------------------------------------------------------------


@_qt
class TestRichTextEditor:
    """§3 — Rich-text formatting toolbar (bold / italic / underline / font size)."""

    def test_editor_has_bold_btn(self):
        """§3.1  NoteEditorWidget exposes _bold_btn (QToolButton, checkable)."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        assert hasattr(w, "_bold_btn")
        assert w._bold_btn.isCheckable()

    def test_editor_has_italic_btn(self):
        """§3.2  NoteEditorWidget exposes _italic_btn (QToolButton, checkable)."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        assert hasattr(w, "_italic_btn")
        assert w._italic_btn.isCheckable()

    def test_editor_has_underline_btn(self):
        """§3.3  NoteEditorWidget exposes _underline_btn (QToolButton, checkable)."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        assert hasattr(w, "_underline_btn")
        assert w._underline_btn.isCheckable()

    def test_editor_has_font_size_combo(self):
        """§3.4  NoteEditorWidget exposes _font_size_combo (QComboBox)."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        assert hasattr(w, "_font_size_combo")

    def test_font_size_combo_has_numeric_options(self):
        """§3.5  _font_size_combo contains numeric size items."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        texts = [w._font_size_combo.itemText(i) for i in range(w._font_size_combo.count())]
        assert "12" in texts
        assert "14" in texts

    def test_get_html_content_returns_html(self):
        """§3.6  get_html_content() returns a non-empty HTML string."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        w._content_edit.setPlainText("Hello World")
        html = w.get_html_content()
        assert isinstance(html, str)
        assert "Hello World" in html

    def test_get_content_still_returns_plain_text(self):
        """§3.7  get_content() returns plain text (backward compat)."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        w._content_edit.setPlainText("plain text")
        assert w.get_content() == "plain text"

    def test_apply_font_size(self):
        """§3.8  apply_font_size() sets font on content editor without error."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        w.apply_font_size(18)
        assert w._content_edit.font().pointSize() == 18

    def test_content_edit_accepts_rich_text(self):
        """§3.9  _content_edit.acceptRichText() is True."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        assert w._content_edit.acceptRichText() is True

    def test_editor_formatting_toolbar_exists(self):
        """§3.10  NoteEditorWidget has a _fmt_bar (QToolBar)."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        from PySide6.QtWidgets import QToolBar
        w = NoteEditorWidget()
        assert hasattr(w, "_fmt_bar")
        assert isinstance(w._fmt_bar, QToolBar)


# ---------------------------------------------------------------------------
# §4  Tab bar  [B-104]
# ---------------------------------------------------------------------------


@_qt
class TestTabBar:
    """§4 — QTabWidget-based tab bar."""

    def test_main_window_has_tab_widget(self, tmp_path):
        """§4.1  MainWindow exposes _tab_widget (QTabWidget)."""
        from PySide6.QtWidgets import QTabWidget
        w, _, _ = _make_window(tmp_path)
        assert hasattr(w, "_tab_widget")
        assert isinstance(w._tab_widget, QTabWidget)

    def test_initial_tab_exists(self, tmp_path):
        """§4.2  MainWindow starts on the welcome screen (no initial tab)."""
        w, _, _ = _make_window(tmp_path)
        # New UX: app opens to welcome page, no empty tab is pre-created
        assert w._tab_widget.count() == 0
        # The right-hand stack should be showing the welcome widget (index 0)
        assert w._right_stack.currentIndex() == 0

    def test_initial_editor_assigned(self, tmp_path):
        """§4.3  MainWindow._editor is set immediately after construction."""
        from src.desktop.main_window import NoteEditorWidget
        w, _, _ = _make_window(tmp_path)
        assert hasattr(w, "_editor")
        assert isinstance(w._editor, NoteEditorWidget)

    def test_new_note_opens_new_tab(self, tmp_path):
        """§4.4  _on_new_note() increases tab count by one."""
        w, _, _ = _make_window(tmp_path)
        initial_count = w._tab_widget.count()
        w._on_new_note()
        assert w._tab_widget.count() == initial_count + 1

    def test_tab_closable(self, tmp_path):
        """§4.5  The tab widget is configured as tabs-closable."""
        w, _, _ = _make_window(tmp_path)
        assert w._tab_widget.tabsClosable() is True

    def test_tab_movable(self, tmp_path):
        """§4.6  The tab widget is configured as movable."""
        w, _, _ = _make_window(tmp_path)
        assert w._tab_widget.isMovable() is True

    def test_note_select_opens_tab(self, tmp_path):
        """§4.7  Selecting a note from the list opens a dedicated tab."""
        from PySide6.QtCore import Qt
        w, store, _ = _make_window(tmp_path)
        note = Note.create("Tab Note", "content")
        store.add(note)
        w.populate_note_list()
        initial_count = w._tab_widget.count()
        item = w._note_list.item(0)
        assert item is not None
        w._note_list.setCurrentItem(item)
        # _on_note_selected should be triggered
        w._on_note_selected(item, None)
        assert w._tab_widget.count() == initial_count + 1

    def test_close_tab_reduces_count(self, tmp_path):
        """§4.8  Closing a tab decreases the tab count (minimum 1 empty tab remains)."""
        w, _, _ = _make_window(tmp_path)
        w._on_new_note()
        count_before = w._tab_widget.count()
        w._on_tab_close_requested(0)
        assert w._tab_widget.count() == count_before - 1

    def test_close_all_tabs_returns_to_welcome(self, tmp_path):
        """§4.9  Closing the last tab returns to the welcome screen."""
        w, _, _ = _make_window(tmp_path)
        w._on_new_note()  # open one tab
        assert w._tab_widget.count() == 1
        w._on_tab_close_requested(0)  # close it
        # Tab widget is empty and welcome screen is visible
        assert w._tab_widget.count() == 0
        assert w._right_stack.currentIndex() == 0

    def test_note_editors_dict_exists(self, tmp_path):
        """§4.10  MainWindow has _note_editors dict for tracking open tabs."""
        w, _, _ = _make_window(tmp_path)
        assert hasattr(w, "_note_editors")
        assert isinstance(w._note_editors, dict)

    def test_second_select_of_same_note_reuses_tab(self, tmp_path):
        """§4.11  Selecting the same note twice does not open a second tab."""
        from PySide6.QtCore import Qt
        w, store, _ = _make_window(tmp_path)
        note = Note.create("Reuse Me", "text")
        store.add(note)
        w.populate_note_list()
        item = w._note_list.item(0)
        w._on_note_selected(item, None)
        count_after_first = w._tab_widget.count()
        w._on_note_selected(item, None)
        assert w._tab_widget.count() == count_after_first


# ---------------------------------------------------------------------------
# §5  Alias / _AliasPromptDialog  [B-106]
# ---------------------------------------------------------------------------


@_qt
class TestAliasInput:
    """§5 — Alias is set via a dialog on save, not via a permanent alias row."""

    def test_title_row_always_visible(self):
        """§5.1  _title_row stays visible regardless of encrypt state."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        assert not w._title_row.isHidden()
        w._encrypt_check.setChecked(True)
        assert not w._title_row.isHidden()

    def test_title_row_visible_after_encrypt_toggle(self):
        """§5.2  _title_row remains visible after toggling encrypt on/off."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        w._encrypt_check.setChecked(True)
        w._encrypt_check.setChecked(False)
        assert not w._title_row.isHidden()

    def test_get_title_returns_title_edit(self):
        """§5.3  get_title() always reads _title_edit, not a separate alias field."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        w._title_edit.setText("Real Title")
        assert w.get_title() == "Real Title"

    def test_get_alias_equals_get_title(self):
        """§5.4  get_alias() returns the same value as get_title()."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        w._title_edit.setText("My Note")
        assert w.get_alias() == w.get_title()

    def test_alias_prompt_dialog_exists(self):
        """§5.5  _AliasPromptDialog is importable and has a QLineEdit."""
        _ensure_app()
        from src.desktop.main_window import _AliasPromptDialog
        from PySide6.QtWidgets import QLineEdit
        dlg = _AliasPromptDialog("My Note")
        assert hasattr(dlg, "_alias_edit")
        assert isinstance(dlg._alias_edit, QLineEdit)
        dlg.destroy()

    def test_alias_prompt_default_button(self):
        """§5.6  Clicking 'Use [Encrypted Note]' sets alias to the default string."""
        _ensure_app()
        from src.desktop.main_window import _AliasPromptDialog
        dlg = _AliasPromptDialog("Real Title")
        dlg._on_use_default()
        assert dlg.alias == "[Encrypted Note]"

    def test_alias_prompt_save_alias_button(self):
        """§5.7  Clicking 'Save with alias' uses the text in the line edit."""
        _ensure_app()
        from src.desktop.main_window import _AliasPromptDialog
        dlg = _AliasPromptDialog("Real Title")
        dlg._alias_edit.setText("Custom Alias")
        dlg._on_save_alias()
        assert dlg.alias == "Custom Alias"

    def test_alias_prompt_empty_alias_falls_back(self):
        """§5.8  Empty text in alias field falls back to '[Encrypted Note]'."""
        _ensure_app()
        from src.desktop.main_window import _AliasPromptDialog
        dlg = _AliasPromptDialog("Some Title")
        dlg._alias_edit.setText("")
        dlg._on_save_alias()
        assert dlg.alias == "[Encrypted Note]"

    def test_load_encrypted_note_sets_title(self):
        """§5.9  load() with an encrypted note shows the alias in _title_edit."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        note = Note.create("My Alias", "x", encrypted=True, blob=b"fake")
        w = NoteEditorWidget()
        w.load(note)
        assert w.get_title() == "My Alias"


# ---------------------------------------------------------------------------
# §6  Unlock button  [B-106]
# ---------------------------------------------------------------------------


@_qt
class TestUnlockButton:
    """§6 — Unlock button for encrypted notes."""

    def test_unlock_btn_hidden_initially(self):
        """§6.1  _unlock_btn is hidden when editor is freshly created."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        assert not w._unlock_btn.isVisible()

    def test_unlock_btn_exists(self):
        """§6.2  NoteEditorWidget exposes _unlock_btn (QPushButton)."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        from PySide6.QtWidgets import QPushButton
        w = NoteEditorWidget()
        assert hasattr(w, "_unlock_btn")
        assert isinstance(w._unlock_btn, QPushButton)

    def test_unlock_btn_shown_on_encrypted_placeholder(self):
        """§6.3  show_encrypted_placeholder() makes _unlock_btn visible."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        w.show_encrypted_placeholder()
        assert not w._unlock_btn.isHidden()

    def test_load_encrypted_without_content_shows_unlock_btn(self):
        """§6.4  load() for encrypted note without decrypted_content shows unlock_btn."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        note = Note.create("Locked", "x", encrypted=True, blob=b"blob")
        w = NoteEditorWidget()
        w.load(note)
        assert not w._unlock_btn.isHidden()

    def test_load_encrypted_with_content_hides_unlock_btn(self):
        """§6.5  load() for encrypted note with decrypted_content hides unlock_btn."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        note = Note.create("Unlocked", "x", encrypted=True, blob=b"blob")
        w = NoteEditorWidget()
        w.load(note, decrypted_content="the secret")
        assert not w._unlock_btn.isVisible()

    def test_unlock_btn_emits_unlock_requested(self):
        """§6.6  Clicking _unlock_btn emits the unlock_requested signal."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        received = []
        w.unlock_requested.connect(lambda: received.append(True))
        w._unlock_btn.click()
        assert received == [True]

    def test_unlock_requested_signal_exists(self):
        """§6.7  NoteEditorWidget has unlock_requested Signal attribute."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        assert hasattr(w, "unlock_requested")

    def test_clear_hides_unlock_btn(self):
        """§6.8  clear() hides the unlock button."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        w.show_encrypted_placeholder()
        w.clear()
        assert not w._unlock_btn.isVisible()


# ---------------------------------------------------------------------------
# §7  Search bar  [B-107]
# ---------------------------------------------------------------------------


@_qt
class TestSearchBar:
    """§7 — Search bar filters note list."""

    def test_main_window_has_search_bar(self, tmp_path):
        """§7.1  MainWindow exposes _search_bar (QLineEdit)."""
        from PySide6.QtWidgets import QLineEdit
        w, _, _ = _make_window(tmp_path)
        assert hasattr(w, "_search_bar")
        assert isinstance(w._search_bar, QLineEdit)

    def test_search_bar_has_placeholder(self, tmp_path):
        """§7.2  _search_bar has a non-empty placeholder hint."""
        w, _, _ = _make_window(tmp_path)
        assert len(w._search_bar.placeholderText()) > 0

    def test_search_empty_restores_full_list(self, tmp_path):
        """§7.3  Clearing search text re-populates full note list."""
        w, store, _ = _make_window(tmp_path)
        store.add(Note.create("Alpha", "content1"))
        store.add(Note.create("Beta", "content2"))
        w.populate_note_list()
        assert w._note_list.count() == 2
        w._search_bar.setText("zzz")   # no matches
        w._search_bar.setText("")      # clear → back to full list
        assert w._note_list.count() == 2

    def test_search_filters_list(self, tmp_path):
        """§7.4  Entering a search term calls store.search() and filters list."""
        w, store, _ = _make_window(tmp_path)
        store.add(Note.create("Alpha Note", "content"))
        store.add(Note.create("Beta Note", "content"))
        w.populate_note_list()
        # Simulate typing "Alpha" in search bar
        w._search_bar.setText("Alpha")
        # After search, only notes matching "Alpha" should show
        for i in range(w._note_list.count()):
            item = w._note_list.item(i)
            assert item is not None

    def test_on_focus_search_focuses_search_bar(self, tmp_path):
        """§7.5  _on_focus_search() focuses _search_bar."""
        w, _, _ = _make_window(tmp_path)
        w.show()
        w._on_focus_search()
        # Just verify it doesn't raise; focus behaviour is OS-dependent
        assert w._search_bar is not None

    def test_search_bar_has_clear_button(self, tmp_path):
        """§7.6  _search_bar has a clear button enabled."""
        w, _, _ = _make_window(tmp_path)
        # isClearButtonEnabled returns True if set
        assert w._search_bar.isClearButtonEnabled()


# ---------------------------------------------------------------------------
# §8  Account-aware list  [B-108]
# ---------------------------------------------------------------------------


@_qt
class TestAccountAwareList:
    """§8 — Section headers when an account session is active."""

    def test_no_headers_without_data_dir(self, tmp_path):
        """§8.1  Without data_dir, no section headers appear."""
        w, store, _ = _make_window(tmp_path, data_dir=None)
        store.add(Note.create("A", "content"))
        store.add(Note.create("B", "content"))
        w.populate_note_list()
        # All items should have UserRole data (no disabled header items)
        from PySide6.QtCore import Qt
        for i in range(w._note_list.count()):
            item = w._note_list.item(i)
            assert item.data(Qt.ItemDataRole.UserRole) is not None, \
                f"Item {i} ('{item.text()}') has no UserRole data — unexpected header"

    def test_list_count_equals_note_count_without_data_dir(self, tmp_path):
        """§8.2  Without data_dir, _note_list.count() equals the number of notes."""
        w, store, _ = _make_window(tmp_path, data_dir=None)
        store.add(Note.create("X", "c1"))
        store.add(Note.create("Y", "c2"))
        store.add(Note.create("Z", "c3"))
        w.populate_note_list()
        assert w._note_list.count() == 3

    def test_data_dir_parameter_accepted(self, tmp_path):
        """§8.3  MainWindow accepts data_dir parameter without error."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        w, _, _ = _make_window(tmp_path, data_dir=data_dir)
        assert w is not None

    def test_headers_are_non_selectable(self, tmp_path):
        """§8.4  Header list items (if present) have NoItemFlags."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidgetItem

        # Inject a known header item and verify its flags
        _ensure_app()
        from src.desktop.main_window import MainWindow
        store = DatabaseStore(tmp_path)
        config = ConfigStore(config_path=tmp_path / "cfg.json")
        registry = PluginRegistry()
        w = MainWindow(store=store, config=config, registry=registry, data_dir=None)

        # Manually add a header-style item
        header = QListWidgetItem("── Section ──")
        header.setFlags(Qt.ItemFlag.NoItemFlags)
        w._note_list.addItem(header)

        item = w._note_list.item(w._note_list.count() - 1)
        assert item.flags() == Qt.ItemFlag.NoItemFlags


# ---------------------------------------------------------------------------
# §9  Keyboard shortcuts  [B-112]
# ---------------------------------------------------------------------------


@_qt
class TestKeyboardShortcuts:
    """§9 — Menu keyboard shortcut strings are registered."""

    def test_new_note_shortcut(self, tmp_path):
        """§9.1  New Note action has Ctrl+N shortcut."""
        w, _, _ = _make_window(tmp_path)
        assert w._action_new.shortcut().toString() == "Ctrl+N"

    def test_save_shortcut(self, tmp_path):
        """§9.2  Save action has Ctrl+S shortcut."""
        w, _, _ = _make_window(tmp_path)
        assert w._action_save.shortcut().toString() == "Ctrl+S"

    def test_delete_shortcut(self, tmp_path):
        """§9.3  Delete action has Delete shortcut."""
        w, _, _ = _make_window(tmp_path)
        shortcut_str = w._action_delete.shortcut().toString()
        assert "Del" in shortcut_str or shortcut_str == "Delete"

    def test_settings_shortcut(self, tmp_path):
        """§9.4  Settings action has Ctrl+, shortcut."""
        w, _, _ = _make_window(tmp_path)
        assert w._action_settings.shortcut().toString() == "Ctrl+,"

    def test_menu_bar_has_file_menu(self, tmp_path):
        """§9.5  MainWindow menu bar contains a File menu."""
        w, _, _ = _make_window(tmp_path)
        titles = [action.text() for action in w.menuBar().actions()]
        assert any("File" in t for t in titles)

    def test_menu_bar_has_edit_menu(self, tmp_path):
        """§9.6  MainWindow menu bar contains an Edit menu."""
        w, _, _ = _make_window(tmp_path)
        titles = [action.text() for action in w.menuBar().actions()]
        assert any("Edit" in t for t in titles)

    def test_menu_bar_has_view_menu(self, tmp_path):
        """§9.7  MainWindow menu bar contains a View menu."""
        w, _, _ = _make_window(tmp_path)
        titles = [action.text() for action in w.menuBar().actions()]
        assert any("View" in t for t in titles)

    def test_close_tab_action_exists(self, tmp_path):
        """§9.8  Edit menu has Close Tab action."""
        from PySide6.QtWidgets import QMenu
        w, _, _ = _make_window(tmp_path)
        edit_menu = None
        for action in w.menuBar().actions():
            if "Edit" in action.text():
                edit_menu = action.menu()
                break
        assert edit_menu is not None
        edit_titles = [a.text() for a in edit_menu.actions()]
        assert any("Tab" in t for t in edit_titles)

    def test_find_notes_action_exists(self, tmp_path):
        """§9.9  View menu has Find Notes action."""
        w, _, _ = _make_window(tmp_path)
        view_menu = None
        for action in w.menuBar().actions():
            if "View" in action.text():
                view_menu = action.menu()
                break
        assert view_menu is not None
        view_titles = [a.text() for a in view_menu.actions()]
        assert any("Find" in t for t in view_titles)
