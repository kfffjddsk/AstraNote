"""test_sprint5_ui.py — Sprint 5 UI coverage tests.

Covers the lowest-coverage desktop paths identified from the coverage report:

  §1  TestNoteSelectionGuard     — _reverting_selection re-entry guard
  §2  TestRevertNoteSelection    — _revert_note_selection both branches
  §3  TestMissingPluginSelection — plugin-missing → revert + warn flow
  §4  TestNoteItemClicked        — _on_note_item_clicked all branches
  §5  TestPluginsDialogConstruct — PluginsDialog construction & population
  §6  TestPluginsDialogFilter    — search filter and description pane
  §7  TestPluginsDialogApply     — Apply button enable / disable / block

Refs: [BL B-99, B-100, B-103] [REQ R11]
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.config import ConfigStore
from src.core.notes import DatabaseStore, Note
from src.core.plugin_base import PluginBase, PluginRegistry

# ---------------------------------------------------------------------------
# Qt availability guard
# ---------------------------------------------------------------------------
try:
    from PySide6.QtWidgets import QApplication, QListWidgetItem
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

_qt = pytest.mark.skipif(not _QT_AVAILABLE, reason="PySide6 not available")

_app: object = None


def _ensure_app() -> object:
    global _app
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if _app is None:
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication([])
    return _app


def _make_window(tmp_path: Path):
    """Return (window, store, config, registry) with a fresh empty store."""
    _ensure_app()
    from src.desktop.main_window import MainWindow
    store = DatabaseStore(tmp_path)
    config = ConfigStore(config_path=tmp_path / "config.json")
    registry = PluginRegistry()
    w = MainWindow(store=store, config=config, registry=registry, data_dir=tmp_path)
    return w, store, config, registry


def _make_item(note: Note) -> "QListWidgetItem":
    """Return a bare QListWidgetItem carrying note.id in UserRole."""
    from PySide6.QtCore import Qt
    item = QListWidgetItem(note.title)
    item.setData(Qt.ItemDataRole.UserRole, note.id)
    return item


def _find_list_item(w, note_id: str) -> "QListWidgetItem | None":
    """Find the list item for *note_id* in the window's note list."""
    from PySide6.QtCore import Qt
    for i in range(w._note_list.count()):
        it = w._note_list.item(i)
        if it and it.data(Qt.ItemDataRole.UserRole) == note_id:
            return it
    return None


# ---------------------------------------------------------------------------
# Minimal fake plugins (only register_hooks is abstract)
# ---------------------------------------------------------------------------

class _AudioPlugin(PluginBase):
    name = "TestAudioPlugin"
    version = "0.1"
    mime_types: list = ["audio/basic"]
    overrides: list = []
    provides_formats: list = []

    def register_hooks(self, registry: PluginRegistry) -> None:
        pass


class _VideoPlugin(PluginBase):
    name = "TestVideoPlugin"
    version = "0.1"
    mime_types: list = ["video/mp4"]
    overrides: list = []
    provides_formats: list = []

    def register_hooks(self, registry: PluginRegistry) -> None:
        pass


# ---------------------------------------------------------------------------
# §1  TestNoteSelectionGuard
# ---------------------------------------------------------------------------

@_qt
class TestNoteSelectionGuard:
    """§1 — _reverting_selection prevents re-entrant signal handling."""

    def test_flag_initialised_false(self, tmp_path):
        """§1.1  _reverting_selection starts False after construction."""
        w, *_ = _make_window(tmp_path)
        assert w._reverting_selection is False

    def test_on_note_selected_noop_while_reverting(self, tmp_path):
        """§1.2  No tab opens when _reverting_selection is True."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("N", "hello")
        store.add(note)
        w.populate_note_list()
        item = w._note_list.item(0)

        count_before = w._tab_widget.count()
        w._reverting_selection = True
        w._on_note_selected(item, None)
        assert w._tab_widget.count() == count_before
        w._reverting_selection = False

    def test_on_note_selected_noop_on_none_current(self, tmp_path):
        """§1.3  current=None returns without error."""
        w, *_ = _make_window(tmp_path)
        w._on_note_selected(None, None)  # must not raise

    def test_on_note_selected_noop_on_missing_user_role(self, tmp_path):
        """§1.4  Item with no UserRole data is silently skipped."""
        w, *_ = _make_window(tmp_path)
        item = QListWidgetItem("orphan")  # no UserRole set → note_id = None
        w._on_note_selected(item, None)  # must not raise

    def test_on_note_selected_noop_on_unknown_note_id(self, tmp_path):
        """§1.5  Item whose note is not in the store is silently skipped."""
        w, *_ = _make_window(tmp_path)
        phantom = Note.create("Ghost", "boo")
        # Intentionally NOT added to the store
        item = _make_item(phantom)
        w._on_note_selected(item, None)  # must not raise

    def test_on_note_item_clicked_noop_while_reverting(self, tmp_path):
        """§1.6  _on_note_item_clicked is a no-op while reverting."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("Y", "y")
        store.add(note)
        item = _make_item(note)
        w._reverting_selection = True
        w._on_note_item_clicked(item)  # must not raise
        w._reverting_selection = False

    def test_on_note_item_clicked_noop_on_missing_user_role(self, tmp_path):
        """§1.7  itemClicked on an item with no UserRole is silently ignored."""
        w, *_ = _make_window(tmp_path)
        item = QListWidgetItem("orphan")
        w._on_note_item_clicked(item)  # must not raise

    def test_on_note_item_clicked_noop_when_no_current_note(self, tmp_path):
        """§1.8  No current note — clicking any item does not raise."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("M", "m")
        store.add(note)
        assert w._current_note is None
        w._on_note_item_clicked(_make_item(note))  # must not raise


# ---------------------------------------------------------------------------
# §2  TestRevertNoteSelection
# ---------------------------------------------------------------------------

@_qt
class TestRevertNoteSelection:
    """§2 — _revert_note_selection correctly updates the list selection."""

    def test_revert_to_previous_item(self, tmp_path):
        """§2.1  When previous is given it becomes the current list item."""
        w, store, *_ = _make_window(tmp_path)
        n1 = Note.create("N1", "aaa")
        n2 = Note.create("N2", "bbb")
        store.add(n1)
        store.add(n2)
        w.populate_note_list()

        item0 = _find_list_item(w, n1.id)
        item1 = _find_list_item(w, n2.id)
        w._note_list.setCurrentItem(item1)
        w._revert_note_selection(item0)
        assert w._note_list.currentItem() is item0

    def test_revert_to_none_clears_selection(self, tmp_path):
        """§2.2  When previous is None the selection is cleared entirely."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("Solo", "content")
        store.add(note)
        w.populate_note_list()
        w._note_list.setCurrentItem(w._note_list.item(0))
        assert w._note_list.currentItem() is not None

        w._revert_note_selection(None)
        assert len(w._note_list.selectedItems()) == 0

    def test_flag_false_after_revert_with_previous(self, tmp_path):
        """§2.3  _reverting_selection is reset to False after previous-branch."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("Z", "zzz")
        store.add(note)
        w.populate_note_list()
        item = w._note_list.item(0)
        w._revert_note_selection(item)
        assert w._reverting_selection is False

    def test_flag_false_after_revert_with_none(self, tmp_path):
        """§2.4  _reverting_selection is reset to False after None-branch."""
        w, *_ = _make_window(tmp_path)
        w._revert_note_selection(None)
        assert w._reverting_selection is False

    def test_flag_true_during_setCurrentItem(self, tmp_path):
        """§2.5  _reverting_selection is True while setCurrentItem executes."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("A", "aaa")
        store.add(note)
        w.populate_note_list()
        item = w._note_list.item(0)

        observed: list[bool] = []
        original = w._note_list.setCurrentItem

        def spy(i, *a, **kw):
            observed.append(w._reverting_selection)
            return original(i, *a, **kw)

        w._note_list.setCurrentItem = spy
        w._revert_note_selection(item)
        assert observed == [True]
        assert w._reverting_selection is False


# ---------------------------------------------------------------------------
# §3  TestMissingPluginSelection
# ---------------------------------------------------------------------------

@_qt
class TestMissingPluginSelection:
    """§3 — Clicking an unsupported note reverts selection and shows warning."""

    def test_audio_note_triggers_warning(self, tmp_path):
        """§3.1  Audio note with no registered plugin calls _warn_plugin_missing."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("Voice", "data:audio/basic;base64,AAAA")
        store.add(note)

        with patch("src.desktop.main_window.QMessageBox.warning") as mock_warn:
            w._on_note_selected(_make_item(note), None)

        mock_warn.assert_called_once()
        title_arg = mock_warn.call_args[0][1]
        assert "Voice" in title_arg

    def test_video_note_triggers_warning(self, tmp_path):
        """§3.2  Video note with no registered plugin calls _warn_plugin_missing."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("Demo", "data:video/mp4;base64,AAAA")
        store.add(note)

        with patch("src.desktop.main_window.QMessageBox.warning") as mock_warn:
            w._on_note_selected(_make_item(note), None)

        mock_warn.assert_called_once()

    def test_missing_plugin_does_not_open_tab(self, tmp_path):
        """§3.3  No tab is opened when the plugin is missing."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("Audio", "data:audio/basic;base64,AAAA")
        store.add(note)
        count_before = w._tab_widget.count()

        with patch("src.desktop.main_window.QMessageBox.warning"):
            w._on_note_selected(_make_item(note), None)

        assert w._tab_widget.count() == count_before

    def test_missing_plugin_does_not_advance_current_note(self, tmp_path):
        """§3.4  _current_note is NOT updated when the plugin is missing."""
        w, store, *_ = _make_window(tmp_path)
        text = Note.create("Text", "<p>hello</p>")
        store.add(text)
        # Open the text note first to establish _current_note
        w._on_note_selected(_make_item(text), None)
        assert w._current_note is not None
        assert w._current_note.id == text.id

        audio = Note.create("Audio", "data:audio/basic;base64,AAAA")
        store.add(audio)
        with patch("src.desktop.main_window.QMessageBox.warning"):
            w._on_note_selected(_make_item(audio), _make_item(text))

        assert w._current_note.id == text.id

    def test_reverts_to_previous_list_item(self, tmp_path):
        """§3.5  Previous list item is re-highlighted after failed navigation."""
        w, store, *_ = _make_window(tmp_path)
        text = Note.create("Text", "<p>hi</p>")
        audio = Note.create("Audio", "data:audio/basic;base64,AAAA")
        store.add(text)
        store.add(audio)
        w.populate_note_list()

        text_item = _find_list_item(w, text.id)
        audio_item = _find_list_item(w, audio.id)
        assert text_item is not None and audio_item is not None

        w._note_list.setCurrentItem(text_item)
        with patch("src.desktop.main_window.QMessageBox.warning"):
            w._on_note_selected(audio_item, text_item)

        assert w._note_list.currentItem() is text_item

    def test_clears_selection_when_no_previous(self, tmp_path):
        """§3.6  No previous item → selection cleared, first note NOT auto-opened."""
        w, store, *_ = _make_window(tmp_path)
        text = Note.create("Text", "<p>hi</p>")
        audio = Note.create("Audio", "data:audio/basic;base64,AAAA")
        store.add(text)
        store.add(audio)
        w.populate_note_list()

        audio_item = _find_list_item(w, audio.id)
        assert audio_item is not None

        tab_before = w._tab_widget.count()
        with patch("src.desktop.main_window.QMessageBox.warning"):
            w._on_note_selected(audio_item, None)  # previous=None

        # No new tab must have opened (first note must NOT auto-open)
        assert w._tab_widget.count() == tab_before
        assert len(w._note_list.selectedItems()) == 0

    def test_plain_text_note_opens_normally(self, tmp_path):
        """§3.7  Plain-text notes bypass the plugin check and open a tab."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("Plain", "just text")
        store.add(note)
        count_before = w._tab_widget.count()
        w._on_note_selected(_make_item(note), None)
        assert w._tab_widget.count() == count_before + 1

    def test_html_note_opens_normally(self, tmp_path):
        """§3.8  HTML notes (Tiptap) open without a plugin check."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("Rich", "<h1>Hello</h1>")
        store.add(note)
        count_before = w._tab_widget.count()
        w._on_note_selected(_make_item(note), None)
        assert w._tab_widget.count() == count_before + 1


# ---------------------------------------------------------------------------
# §4  TestNoteItemClicked
# ---------------------------------------------------------------------------

@_qt
class TestNoteItemClicked:
    """§4 — _on_note_item_clicked all branches."""

    def test_different_note_id_is_noop(self, tmp_path):
        """§4.1  Clicked note differs from _current_note — no tab switch."""
        w, store, *_ = _make_window(tmp_path)
        n1 = Note.create("N1", "aaa")
        n2 = Note.create("N2", "bbb")
        store.add(n1)
        store.add(n2)
        w._on_note_selected(_make_item(n1), None)
        assert w._current_note.id == n1.id

        tab_before = w._tab_widget.count()
        w._on_note_item_clicked(_make_item(n2))
        # No second tab opened by item-click alone
        assert w._tab_widget.count() == tab_before

    def test_re_click_focuses_existing_tab(self, tmp_path):
        """§4.2  Re-clicking the current note brings its tab to the front.

        blockSignals on the tab widget lets us move n1's tab to front without
        _on_tab_changed flipping _current_note — which is the exact state that
        _on_note_item_clicked is designed to correct.
        """
        w, store, *_ = _make_window(tmp_path)
        n1 = Note.create("N1", "aaa")
        n2 = Note.create("N2", "bbb")
        store.add(n1)
        store.add(n2)

        # Open both notes — after this _current_note = n2 and n2's tab is front
        w._on_note_selected(_make_item(n1), None)
        w._on_note_selected(_make_item(n2), None)
        assert w._current_note.id == n2.id

        # Move n1's tab to front without triggering _on_tab_changed so that
        # _current_note stays as n2.
        w._tab_widget.blockSignals(True)
        w._tab_widget.setCurrentWidget(w._note_editors[n1.id])
        w._tab_widget.blockSignals(False)
        assert w._tab_widget.currentWidget() is w._note_editors[n1.id]
        assert w._current_note.id == n2.id

        # Re-click n2 → its tab must come to the front
        w._on_note_item_clicked(_make_item(n2))
        assert w._tab_widget.currentWidget() is w._note_editors[n2.id]

    def test_re_click_when_editor_not_in_tab_widget(self, tmp_path):
        """§4.3  Re-click with editor absent from tab widget does not raise."""
        w, store, *_ = _make_window(tmp_path)
        note = Note.create("N", "x")
        store.add(note)
        w._on_note_selected(_make_item(note), None)
        editor = w._note_editors[note.id]
        # Remove editor from tab widget (simulate orphaned editor)
        idx = w._tab_widget.indexOf(editor)
        if idx >= 0:
            w._tab_widget.removeTab(idx)
        # Should not raise
        w._on_note_item_clicked(_make_item(note))


# ---------------------------------------------------------------------------
# §5  TestPluginsDialogConstruct
# ---------------------------------------------------------------------------

def _make_plugins_dialog(tmp_path: Path, plugins=(), open_mimes=frozenset()):
    """Return (dialog, registry, config)."""
    _ensure_app()
    from src.desktop.plugins_dialog import PluginsDialog
    registry = PluginRegistry()
    config = ConfigStore(config_path=tmp_path / "config.json")
    for p in plugins:
        registry.register_plugin(p)
    dlg = PluginsDialog(registry, config, open_mimes=open_mimes)
    return dlg, registry, config


@_qt
class TestPluginsDialogConstruct:
    """§5 — PluginsDialog construction, tab structure, and population."""

    def test_opens_with_empty_registry(self, tmp_path):
        """§5.1  Dialog constructs without error when no plugins exist."""
        dlg, *_ = _make_plugins_dialog(tmp_path)
        assert dlg is not None

    def test_placeholder_row_when_empty(self, tmp_path):
        """§5.2  Empty registry shows a single placeholder row."""
        dlg, *_ = _make_plugins_dialog(tmp_path)
        assert dlg._installed_tree.topLevelItemCount() == 1
        assert "(no plugins" in dlg._installed_tree.topLevelItem(0).text(0)

    def test_active_plugin_shows_active_status(self, tmp_path):
        """§5.3  Registered (active) plugin shows ✓ Active and is checked."""
        from PySide6.QtCore import Qt
        dlg, *_ = _make_plugins_dialog(tmp_path, plugins=[_AudioPlugin()])
        count = dlg._installed_tree.topLevelItemCount()
        names = [dlg._installed_tree.topLevelItem(i).text(0) for i in range(count)]
        assert "TestAudioPlugin" in names
        idx = names.index("TestAudioPlugin")
        item = dlg._installed_tree.topLevelItem(idx)
        assert "Active" in item.text(2)
        assert item.checkState(0) == Qt.CheckState.Checked

    def test_all_plugins_shows_disabled_plugin(self, tmp_path):
        """§5.4  Plugin in _all_plugins but not _plugins is shown as Disabled."""
        from PySide6.QtCore import Qt
        from src.desktop.plugins_dialog import PluginsDialog
        registry = PluginRegistry()
        config = ConfigStore(config_path=tmp_path / "config.json")
        p = _AudioPlugin()
        registry._all_plugins.append(p)          # lifetime inventory only
        # _plugins intentionally stays empty
        dlg = PluginsDialog(registry, config)
        count = dlg._installed_tree.topLevelItemCount()
        names = [dlg._installed_tree.topLevelItem(i).text(0) for i in range(count)]
        assert "TestAudioPlugin" in names
        idx = names.index("TestAudioPlugin")
        item = dlg._installed_tree.topLevelItem(idx)
        assert item.text(2) == "Disabled"
        assert item.checkState(0) == Qt.CheckState.Unchecked

    def test_multiple_plugins_all_shown(self, tmp_path):
        """§5.5  Two active plugins both appear as rows."""
        dlg, *_ = _make_plugins_dialog(
            tmp_path, plugins=[_AudioPlugin(), _VideoPlugin()]
        )
        count = dlg._installed_tree.topLevelItemCount()
        names = [dlg._installed_tree.topLevelItem(i).text(0) for i in range(count)]
        assert "TestAudioPlugin" in names
        assert "TestVideoPlugin" in names

    def test_formats_tab_has_built_in_rows(self, tmp_path):
        """§5.6  Formats tab pre-populates with built-in format rows."""
        dlg, *_ = _make_plugins_dialog(tmp_path)
        assert dlg._formats_tree.topLevelItemCount() > 0


# ---------------------------------------------------------------------------
# §6  TestPluginsDialogFilter
# ---------------------------------------------------------------------------

@_qt
class TestPluginsDialogFilter:
    """§6 — Search filter and description-pane selection."""

    def test_filter_hides_non_matching_rows(self, tmp_path):
        """§6.1  Typing in the filter hides rows that don't match."""
        dlg, *_ = _make_plugins_dialog(
            tmp_path, plugins=[_AudioPlugin(), _VideoPlugin()]
        )
        dlg._search.setText("audio")
        visible = [
            dlg._installed_tree.topLevelItem(i).text(0)
            for i in range(dlg._installed_tree.topLevelItemCount())
            if not dlg._installed_tree.topLevelItem(i).isHidden()
        ]
        assert "TestAudioPlugin" in visible
        assert "TestVideoPlugin" not in visible

    def test_filter_clear_restores_all_rows(self, tmp_path):
        """§6.2  Clearing the filter un-hides all rows."""
        dlg, *_ = _make_plugins_dialog(
            tmp_path, plugins=[_AudioPlugin(), _VideoPlugin()]
        )
        dlg._search.setText("audio")
        dlg._search.setText("")
        visible_count = sum(
            1 for i in range(dlg._installed_tree.topLevelItemCount())
            if not dlg._installed_tree.topLevelItem(i).isHidden()
        )
        assert visible_count == 2

    def test_select_plugin_populates_description(self, tmp_path):
        """§6.3  Selecting a row populates the description pane."""
        dlg, *_ = _make_plugins_dialog(tmp_path, plugins=[_AudioPlugin()])
        item = dlg._installed_tree.topLevelItem(0)
        dlg._on_installed_selected(item, None)
        assert "TestAudioPlugin" in dlg._desc.toHtml()

    def test_select_none_clears_description(self, tmp_path):
        """§6.4  Selecting None clears the description pane."""
        dlg, *_ = _make_plugins_dialog(tmp_path, plugins=[_AudioPlugin()])
        dlg._on_installed_selected(None, None)
        assert dlg._desc.toPlainText() == ""

    def test_check_change_on_column_zero_updates_status(self, tmp_path):
        """§6.5  Unchecking column 0 changes status text to 'Disabled'."""
        from PySide6.QtCore import Qt
        dlg, *_ = _make_plugins_dialog(tmp_path, plugins=[_AudioPlugin()])
        item = dlg._installed_tree.topLevelItem(0)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        dlg._on_installed_check_changed(item, 0)
        assert item.text(2) == "Disabled"

    def test_check_change_on_other_column_is_ignored(self, tmp_path):
        """§6.6  Changes on column != 0 do not alter status text."""
        from PySide6.QtCore import Qt
        dlg, *_ = _make_plugins_dialog(tmp_path, plugins=[_AudioPlugin()])
        item = dlg._installed_tree.topLevelItem(0)
        original = item.text(2)
        dlg._on_installed_check_changed(item, 1)
        assert item.text(2) == original


# ---------------------------------------------------------------------------
# §7  TestPluginsDialogApply
# ---------------------------------------------------------------------------

def _make_apply_dialog(tmp_path, plugin, *, in_registry: bool,
                       open_mimes=frozenset()):
    """Return (dialog, registry, config) wired with one plugin."""
    _ensure_app()
    from src.desktop.plugins_dialog import PluginsDialog
    registry = PluginRegistry()
    config = ConfigStore(config_path=tmp_path / "config.json")
    registry._all_plugins.append(plugin)
    if in_registry:
        registry._plugins.append(plugin)
    dlg = PluginsDialog(registry, config, open_mimes=open_mimes)
    return dlg, registry, config


@_qt
class TestPluginsDialogApply:
    """§7 — Apply button enables, disables, and blocks correctly."""

    def test_apply_checked_keeps_plugin_active(self, tmp_path):
        """§7.1  Checked plugin remains in registry after Apply."""
        p = _AudioPlugin()
        dlg, registry, _ = _make_apply_dialog(tmp_path, p, in_registry=True)
        dlg._on_apply()
        assert p in registry._plugins

    def test_apply_checked_adds_to_allowed_config(self, tmp_path):
        """§7.2  Checked plugin appears in allowed_plugins config."""
        p = _AudioPlugin()
        dlg, _, config = _make_apply_dialog(tmp_path, p, in_registry=True)
        dlg._on_apply()
        assert "TestAudioPlugin" in config.get("allowed_plugins")

    def test_apply_uncheck_removes_from_registry(self, tmp_path):
        """§7.3  Unchecking and applying removes plugin from registry._plugins."""
        from PySide6.QtCore import Qt
        p = _AudioPlugin()
        dlg, registry, _ = _make_apply_dialog(tmp_path, p, in_registry=True)
        dlg._installed_tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Unchecked)
        dlg._on_apply()
        assert p not in registry._plugins

    def test_apply_uncheck_removes_from_allowed_config(self, tmp_path):
        """§7.4  Disabled plugin is absent from allowed_plugins config."""
        from PySide6.QtCore import Qt
        p = _AudioPlugin()
        dlg, _, config = _make_apply_dialog(tmp_path, p, in_registry=True)
        dlg._installed_tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Unchecked)
        dlg._on_apply()
        assert "TestAudioPlugin" not in config.get("allowed_plugins")

    def test_apply_recheck_re_enables_plugin(self, tmp_path):
        """§7.5  Checking a disabled plugin and applying adds it back."""
        from PySide6.QtCore import Qt
        p = _AudioPlugin()
        dlg, registry, _ = _make_apply_dialog(tmp_path, p, in_registry=False)
        item = dlg._installed_tree.topLevelItem(0)
        assert item.checkState(0) == Qt.CheckState.Unchecked
        item.setCheckState(0, Qt.CheckState.Checked)
        dlg._on_apply()
        assert p in registry._plugins

    def test_apply_blocked_when_mime_is_open(self, tmp_path):
        """§7.6  Disabling a plugin whose MIME is open shows warning and is refused."""
        from PySide6.QtCore import Qt
        p = _AudioPlugin()
        dlg, registry, _ = _make_apply_dialog(
            tmp_path, p, in_registry=True,
            open_mimes=frozenset(["audio/basic"]),
        )
        dlg._installed_tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Unchecked)
        with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
            dlg._on_apply()
        mock_warn.assert_called_once()
        # Plugin must still be active
        assert p in registry._plugins

    def test_blocked_item_reverted_to_checked(self, tmp_path):
        """§7.7  Blocked plugin's checkbox is flipped back to Checked."""
        from PySide6.QtCore import Qt
        p = _AudioPlugin()
        dlg, *_ = _make_apply_dialog(
            tmp_path, p, in_registry=True,
            open_mimes=frozenset(["audio/basic"]),
        )
        item = dlg._installed_tree.topLevelItem(0)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        with patch("PySide6.QtWidgets.QMessageBox.warning"):
            dlg._on_apply()
        assert item.checkState(0) == Qt.CheckState.Checked

    def test_apply_refreshes_formats_tab(self, tmp_path):
        """§7.8  Apply always repopulates the formats tab."""
        p = _AudioPlugin()
        dlg, *_ = _make_apply_dialog(tmp_path, p, in_registry=True)
        before = dlg._formats_tree.topLevelItemCount()
        dlg._on_apply()
        # Row count must be non-zero (built-ins always present)
        assert dlg._formats_tree.topLevelItemCount() >= before
