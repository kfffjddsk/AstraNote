"""MainWindow — PySide6 desktop GUI for AstraNotes.

This module now contains only the ``MainWindow`` class and the
``_IDLE_TIMEOUT_MS`` constant.  All other classes that previously lived
here have been extracted into focused sub-modules:

  * theme.py          — stylesheet constants, apply_theme, hot-reload
  * note_editor.py    — NoteEditorWidget, _WelcomeWidget
  * dialogs.py        — PassphraseDialog, _CloseChoiceDialog, _AliasPromptDialog,
                        _NewNoteTypeDialog, _WidgetGallery
  * account_dialog.py — SyncLoginDialog, _OAuthCallbackServer/Handler
  * settings_dialog.py — SettingsDialog
  * plugins_dialog.py — PluginsDialog, registry_manifests

Backward-compat re-exports are provided at the bottom of this file so
that existing tests importing from ``src.desktop.main_window`` continue
to work without modification.

Refs: [BL B-103..B-112] [REQ R9.7, R9.8, R11] [US-9]
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QFont,
    QIcon,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.blob_codec import BlobCodec
from src.core.config import ConfigStore
from src.core.container import (
    Container,
    ContainerValidationError,
    FLAG_ENCRYPTED,
)
from src.core.notes import DatabaseStore, Note
from src.core.plugin_base import PluginRegistry
from src.core.security import KeyManager
from src.core.sync_client import (
    SyncClient,
    delete_cached_token,
    load_cached_token,
)
from src.desktop.sync import MergeWindow, SyncWorker

# Sub-module imports — used directly by MainWindow
from src.desktop.theme import (
    DARK_STYLESHEET,
    LIGHT_STYLESHEET,
    ACCENT_COLORS,
    _QSS_WATCHER,
    _stylesheet_with_accent,
    _install_qss_hotreload,
    apply_theme,
)
from src.desktop.note_editor import (
    PluginEditorHost,
    _WelcomeWidget,
    _ENCRYPTED_PLACEHOLDER,
)
from src.desktop.dialogs import (
    PassphraseDialog,
    _CloseChoiceDialog,
    _AliasPromptDialog,
    _NewNoteTypeDialog,
    _WidgetGallery,
)
from src.desktop.sync.account_dialog import (
    SyncLoginDialog,
    _OAuthCallbackHandler,
    _OAuthCallbackServer,
    _GOOGLE_AUTH_URL,
    _GOOGLE_SCOPE,
)
from src.desktop.settings_dialog import SettingsDialog
from src.desktop.plugins_dialog import PluginsDialog, registry_manifests

logger = logging.getLogger(__name__)

_IDLE_TIMEOUT_MS = 5 * 60 * 1000  # 300_000 ms  [REQ R9.8] [BL B-102]


# ---------------------------------------------------------------------------
# MainWindow  [B-103, B-104, B-107, B-108, B-110, B-111, B-112]
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """VS Code-inspired AstraNotes desktop window with tab bar and search."""

    def __init__(
        self,
        store: DatabaseStore,
        config: ConfigStore,
        registry: PluginRegistry,
        data_dir: Optional[Path] = None,
        parent: Optional[QWidget] = None,
        sync_url: str = "",
        sync_auto_interval: int = 0,
        google_client_id: str = "",
        google_client_secret: str = "",
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._config = config
        self._registry = registry
        self._data_dir = data_dir
        self._sync_url = sync_url
        self._sync_auto_interval = sync_auto_interval
        self._google_client_id = google_client_id
        self._google_client_secret = google_client_secret
        # State
        self._current_note: Optional[Note] = None
        self._cached_passphrase: Optional[str] = None
        self._sync_worker: Optional[SyncWorker] = None
        self._auto_sync_timer: Optional[QTimer] = None
        self.setWindowTitle("AstraNotes")
        self.resize(1100, 680)
        self._build_menu_bar()
        self._build_toolbar()
        self._build_central_widget()
        self._build_status_bar()
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
        self._action_settings = QAction("⚙Settings", self)
        self._action_settings.setShortcut("Ctrl+,")
        self._action_settings.triggered.connect(self._on_settings)

        file_menu = menu_bar.addMenu("&File")
        self._action_new = QAction("&New Note", self)
        self._action_new.setShortcut("Ctrl+N")
        self._action_new.triggered.connect(self._on_new_note_prompt)
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
        action_quit = QAction("&Quit", self)
        action_quit.setShortcut("Ctrl+Q")
        action_quit.triggered.connect(QApplication.quit)
        file_menu.addAction(action_quit)

        edit_menu = menu_bar.addMenu("&Edit")
        action_close_tab = QAction("Close &Tab", self)
        action_close_tab.setShortcut("Ctrl+W")
        action_close_tab.triggered.connect(self._on_close_current_tab)
        edit_menu.addAction(action_close_tab)

        view_menu = menu_bar.addMenu("&View")
        action_focus_search = QAction("&Find Notes...", self)
        action_focus_search.setShortcut("Ctrl+F")
        action_focus_search.triggered.connect(self._on_focus_search)
        view_menu.addAction(action_focus_search)

        plugins_menu = menu_bar.addMenu("&Plugins")
        self._action_plugins = QAction("Plugins &Admin...", self)
        self._action_plugins.setShortcut("Ctrl+Shift+P")
        self._action_plugins.triggered.connect(self._on_plugins)
        plugins_menu.addAction(self._action_plugins)

        self._action_widget_gallery = QAction("Widget Gallery", self)
        self._action_widget_gallery.setShortcut("Ctrl+Shift+G")
        self._action_widget_gallery.triggered.connect(self._on_widget_gallery)
        self.addAction(self._action_widget_gallery)

        self._action_sync_now = QAction("Sync Now", self)
        self._action_sync_now.setShortcut("Ctrl+Shift+S")
        self._action_sync_now.triggered.connect(self._on_sync)
        self.addAction(self._action_sync_now)
        self._action_sync_signin = QAction("Sign In...", self)
        self._action_sync_signin.triggered.connect(self._on_sync_login)
        self._action_sync_signout = QAction("Sign Out", self)
        self._action_sync_signout.triggered.connect(self._on_sync_logout)

        menu_bar.addAction(self._action_settings)

    def _build_toolbar(self) -> None:
        """Account controls pinned to the top-right corner of the menu bar."""
        self._toolbar_sync_btn = QToolButton()
        self._toolbar_sync_btn.setText("⟳  Sync")
        self._toolbar_sync_btn.setToolTip("Sync now  (Ctrl+Shift+S)")
        self._toolbar_sync_btn.clicked.connect(self._on_sync)
        self._toolbar_sync_btn.setVisible(False)

        self._user_menu = QMenu(self)
        self._toolbar_user_btn = QToolButton()
        self._toolbar_user_btn.setText("\U0001f464  Guest")
        self._toolbar_user_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._toolbar_user_btn.setMenu(self._user_menu)

        # Stored as instance attr — prevents C++ GC of the PySide6 wrapper
        self._account_corner = QWidget()
        corner_layout = QHBoxLayout(self._account_corner)
        corner_layout.setContentsMargins(0, 0, 4, 0)
        corner_layout.setSpacing(2)
        corner_layout.addWidget(self._toolbar_sync_btn)
        corner_layout.addWidget(self._toolbar_user_btn)
        self.menuBar().setCornerWidget(self._account_corner, Qt.Corner.TopRightCorner)

    def _build_central_widget(self) -> None:
        """VS Code-inspired split layout: sidebar + tab editor.  [B-103, B-104]"""
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("\U0001f50d  Search notes...")
        self._search_bar.setClearButtonEnabled(True)
        self._search_bar.textChanged.connect(self._on_search_changed)
        left_layout.addWidget(self._search_bar)

        self._new_note_list_btn = QPushButton("+")
        self._new_note_list_btn.setToolTip("New Note  (Ctrl+N)")
        self._new_note_list_btn.setFixedHeight(40)
        _nn_font = self._new_note_list_btn.font()
        _nn_font.setPointSize(18)
        self._new_note_list_btn.setFont(_nn_font)
        self._new_note_list_btn.clicked.connect(self._on_new_note_prompt)
        left_layout.addWidget(self._new_note_list_btn)

        self._note_list = QListWidget()
        self._note_list.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._note_list.currentItemChanged.connect(self._on_note_selected)
        self._note_list.itemClicked.connect(
            lambda item: self._on_note_selected(item, None)
        )
        left_layout.addWidget(self._note_list)
        left.setMinimumWidth(160)
        splitter.addWidget(left)

        self._right_stack = QStackedWidget()
        self._welcome_widget = _WelcomeWidget()
        self._welcome_widget.new_note_requested.connect(self._on_new_note_prompt)
        self._right_stack.addWidget(self._welcome_widget)   # index 0

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

        self._note_editors: dict[str, PluginEditorHost] = {}
        self._right_stack.setCurrentIndex(0)
        self._editor: PluginEditorHost = PluginEditorHost()  # off-screen placeholder
        # Tab the user is currently viewing; used to re-lock encrypted notes when
        # navigating away (high-security mode).
        self._active_editor: Optional[PluginEditorHost] = None
        # Most-recently-used order of open editor tabs (oldest → newest).  When a
        # tab closes (e.g. after Save) we return to the most recent remaining tab
        # instead of an arbitrary positional neighbour ("the note under it").
        self._tab_history: list[PluginEditorHost] = []

        self._install_webengine_warmup()

    def _install_webengine_warmup(self) -> None:
        """Embed a 1x1 QWebEngineView inside this window before it is shown.

        Why: the first QWebEngineView added to an *already-shown* top-level
        window forces Qt 6 to destroy and recreate the window's native backing
        store (to support a native child window).  The user sees this as the
        whole app "reloading itself" — a visible flash when the first Tiptap
        editor opens.

        Pre-realizing a native web view as a child of this window *before*
        show() means the MainWindow is created native-child-aware from the
        start, so later Tiptap tabs embed without any window recreation.
        The view is 1x1 and lowered behind the central widget, so it is
        never visible to the user.  It is kept alive for the app's lifetime.
        """
        self._webengine_warmup = None
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView

            view = QWebEngineView(self)
            view.setFixedSize(1, 1)
            view.move(0, 0)
            view.load(QUrl("about:blank"))
            view.lower()  # keep behind the central widget — never visible
            self._webengine_warmup = view
        except Exception:
            # Headless / CI environments without a GPU surface — skip silently.
            self._webengine_warmup = None

    def _show_welcome(self) -> None:
        self._right_stack.setCurrentIndex(0)
        self._current_note = None
        self._cached_passphrase = None
        self._update_status_bar()

    def _show_editor(self) -> None:
        self._right_stack.setCurrentIndex(1)

    def _build_status_bar(self) -> None:
        bar = QStatusBar(self)
        bar.setSizeGripEnabled(False)
        self._status_note_label = QLabel("No note selected")
        self._status_lock_label = QLabel("...")
        self._status_count_label = QLabel("0 notes")

        def _sep() -> QFrame:
            line = QFrame()
            line.setFrameShape(QFrame.Shape.VLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            return line

        self._status_account_label = QLabel("\U0001f464 Guest")
        self._status_sync_label = QLabel("● Not synced")
        bar.addPermanentWidget(self._status_account_label)
        bar.addPermanentWidget(_sep())
        bar.addPermanentWidget(self._status_sync_label)
        bar.addPermanentWidget(_sep())
        bar.addPermanentWidget(self._status_note_label)
        bar.addPermanentWidget(_sep())
        bar.addPermanentWidget(self._status_lock_label)
        bar.addPermanentWidget(_sep())
        bar.addPermanentWidget(self._status_count_label)
        self.setStatusBar(bar)
        self._status_bar = bar

    def _update_status_bar(self) -> None:
        if not hasattr(self, "_status_note_label"):
            return
        note = self._current_note
        if note is not None:
            title = (note.title or "Untitled").strip() or "Untitled"
            if len(title) > 40:
                title = title[:37] + "..."
            self._status_note_label.setText(title)
            self._status_lock_label.setText(
                "\U0001f512 Encrypted" if note.encrypted else "\U0001f513 Plain"
            )
        else:
            self._status_note_label.setText("No note selected")
            self._status_lock_label.setText("...")
        try:
            count = sum(
                1
                for row in range(self._note_list.count())
                if self._note_list.item(row)
                and self._note_list.item(row).data(Qt.ItemDataRole.UserRole)
            )
        except Exception:
            count = 0
        self._status_count_label.setText(f"{count} note{'s' if count != 1 else ''}")

    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(QIcon.fromTheme("text-editor"))
        self._tray.setToolTip("AstraNotes")
        tray_menu = QMenu()
        show_action = QAction("Show / Hide", self)
        show_action.triggered.connect(self._toggle_visibility)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
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
        mime_type: str = "text/plain",
    ) -> PluginEditorHost:
        plugin_editor = self._find_editor_for_mime(mime_type)
        # Apply current theme before wrapping so it's stored before loadFinished fires
        theme = self._config.get("theme") or "dark"
        if plugin_editor is not None and hasattr(plugin_editor, "apply_theme"):
            plugin_editor.apply_theme(theme)
        editor = PluginEditorHost(plugin_editor)
        editor._routing_mime = mime_type   # remembered for post-decrypt re-routing
        editor.content_changed.connect(self.reset_idle_timer)
        editor.unlock_requested.connect(self._on_unlock_requested)
        editor.save_requested.connect(lambda ed=editor: self._on_save_for(ed))
        editor.delete_requested.connect(lambda ed=editor: self._on_delete_for(ed))
        try:
            font_size = int(self._config.get("font_size") or 12)
        except (TypeError, ValueError):
            font_size = 12
        editor.apply_font_size(font_size)
        editor.apply_font_family(self._config.get("font_family") or "")
        editor.apply_word_wrap((self._config.get("word_wrap") or "yes") == "yes")
        # Register BEFORE addTab: adding the first tab auto-fires currentChanged
        # → _on_tab_changed, which looks the editor up in _note_editors to set
        # _current_note.  Registering first ensures that lookup succeeds.
        if note_id:
            self._note_editors[note_id] = editor
        index = self._tab_widget.addTab(editor, label)
        self._tab_widget.setCurrentIndex(index)
        self._show_editor()
        return editor

    def _get_or_open_tab(self, note: Note) -> Optional[PluginEditorHost]:
        if note.id in self._note_editors:
            editor = self._note_editors[note.id]
            idx = self._tab_widget.indexOf(editor)
            if idx >= 0:
                self._tab_widget.setCurrentIndex(idx)
                self._editor = editor
                return editor
            del self._note_editors[note.id]
        label = f"\U0001f512 {note.title}" if note.encrypted else note.title
        if note.encrypted:
            # Content is empty until decrypted; always open with the rich editor
            mime_type = "text/html"
        else:
            mime_type = self._mime_for_content(note.content or "")
        # For media notes, verify a plugin is available before opening a tab.
        if mime_type.startswith("audio/") or mime_type.startswith("video/"):
            if self._find_editor_for_mime(mime_type) is None:
                self._warn_plugin_missing(note.title, mime_type)
                return None
        return self._open_new_tab(note_id=note.id, label=label, mime_type=mime_type)

    def _warn_plugin_missing(self, note_title: str, mime_type: str) -> None:
        """Show an error when no plugin is available to open a media note."""
        plugin_name: Optional[str] = None
        for m in getattr(self._registry, "_manifests", []) or []:
            if mime_type in (m.get("mime_types") or []):
                plugin_name = m.get("name") or m.get("plugin_id")
                break
        if plugin_name:
            body = (
                f"{plugin_name} is disabled.\n"
                "Enable it in Plugins Admin and try again."
            )
        else:
            body = (
                f"No plugin is available for {mime_type} content.\n"
                "Enable the required plugin in Plugins Admin and try again."
            )
        QMessageBox.warning(
            self,
            f"Cannot open \"{note_title}\"",
            body,
        )

    @staticmethod
    def _mime_for_content(content: str) -> str:
        """Infer the editor routing MIME from a note's stored content.

        Media notes store their payload as a base64 data URI; the prefix tells
        us which editor to route back to.  HTML (Tiptap) starts with a tag;
        everything else is plain text.
        """
        stripped = content.lstrip()
        if stripped.startswith("data:audio/"):
            return "audio/basic"   # VoicePlugin routing MIME
        if stripped.startswith("data:video/"):
            return "video/mp4"     # VideoPlugin routing MIME
        if stripped.startswith("<"):
            return "text/html"
        return "text/plain"

    @staticmethod
    def _mime_family(mime: str) -> str:
        """Group MIME types by the editor that handles them.

        ``text/plain`` and ``text/html`` are both Tiptap, so they share a
        family; audio and video each have their own.
        """
        if mime.startswith("audio/"):
            return "audio"
        if mime.startswith("video/"):
            return "video"
        return "text"

    def _retarget_tab_editor(
        self, note: Note, current: PluginEditorHost, target_mime: str
    ) -> Optional[PluginEditorHost]:
        """Ensure *current*'s tab uses the editor for *target_mime*.

        Encrypted notes always open in the Tiptap host (the real MIME is unknown
        until decryption).  Once decrypted, if the content is actually audio or
        video we swap the tab to the matching media editor so it plays instead
        of showing a raw data URI.  Returns the editor host to load into, or
        None if the required plugin is unavailable (error dialog already shown).
        """
        cur_mime = getattr(current, "_routing_mime", "text/html")
        if self._mime_family(cur_mime) == self._mime_family(target_mime):
            return current
        # For media MIMEs, verify a plugin is available before replacing the tab.
        if target_mime.startswith(("audio/", "video/")):
            if self._find_editor_for_mime(target_mime) is None:
                self._warn_plugin_missing(note.title, target_mime)
                return None
        idx = self._tab_widget.indexOf(current)
        label = (
            self._tab_widget.tabText(idx)
            if idx >= 0
            else (f"\U0001f512 {note.title}" if note.encrypted else note.title)
        )
        for nid, ed in list(self._note_editors.items()):
            if ed is current:
                del self._note_editors[nid]
        if idx >= 0:
            self._tab_widget.removeTab(idx)
        new_editor = self._open_new_tab(
            note_id=note.id, label=label, mime_type=target_mime
        )
        self._editor = new_editor
        return new_editor

    def _on_tab_close_requested(self, index: int) -> None:
        editor = self._tab_widget.widget(index)
        for nid, ed in list(self._note_editors.items()):
            if ed is editor:
                del self._note_editors[nid]
        self._tab_history = [e for e in self._tab_history if e is not editor]
        # If closing the active tab, switch to the most-recently-used remaining
        # tab FIRST (so we return to where the user was, not an arbitrary
        # positional neighbour — "the note under it"), then remove the now-
        # inactive tab so Qt does not re-select for us.
        if index == self._tab_widget.currentIndex():
            target = next(
                (
                    e for e in reversed(self._tab_history)
                    if e is not editor and self._tab_widget.indexOf(e) >= 0
                ),
                None,
            )
            if target is not None:
                self._tab_widget.setCurrentWidget(target)
        self._tab_widget.removeTab(index)
        if self._tab_widget.count() == 0:
            self._show_welcome()
        else:
            widget = self._tab_widget.currentWidget()
            if isinstance(widget, PluginEditorHost):
                self._editor = widget

    def _on_tab_changed(self, index: int) -> None:
        if index < 0:
            self._active_editor = None
            return
        widget = self._tab_widget.widget(index)
        if not isinstance(widget, PluginEditorHost):
            return
        # Re-lock the tab we are leaving: in high-security mode an encrypted note
        # must not stay decrypted in a background tab (otherwise auto-switching to
        # it later — e.g. after closing another tab — would reveal it).
        prev = self._active_editor
        if prev is not None and prev is not widget:
            security_level = self._config.get("security_level") or "high"
            if security_level == "high":
                prev_note = self._note_for_editor(prev)
                if prev_note is not None and prev_note.encrypted:
                    prev.lock()
                # Forget the passphrase whenever the active tab changes so it can
                # never silently unlock a *different* note that happens to share
                # the same passphrase (e.g. after saving/closing the last note,
                # clicking Unlock on the tab we land on must re-prompt).
                self._cached_passphrase = None
        self._active_editor = widget
        self._editor = widget
        # Record MRU order: drop stale/closed editors, move this one to newest.
        self._tab_history = [
            e for e in self._tab_history
            if e is not widget and self._tab_widget.indexOf(e) >= 0
        ]
        self._tab_history.append(widget)
        note_id = next(
            (nid for nid, ed in self._note_editors.items() if ed is widget), None
        )
        if note_id:
            self._current_note = self._store.get(note_id)
            self._sync_note_list_selection(note_id)
        else:
            self._current_note = None
        self._update_status_bar()

    def _note_for_editor(self, editor: PluginEditorHost) -> Optional[Note]:
        """Return the Note backing *editor*'s tab, or None for an unsaved tab."""
        note_id = next(
            (nid for nid, ed in self._note_editors.items() if ed is editor), None
        )
        return self._store.get(note_id) if note_id else None

    def _sync_note_list_selection(self, note_id: str) -> None:
        self._note_list.blockSignals(True)
        found = False
        for row in range(self._note_list.count()):
            item = self._note_list.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == note_id:
                self._note_list.setCurrentItem(item)
                self._note_list.scrollToItem(item)
                found = True
                break
        if not found:
            self._note_list.clearSelection()
        self._note_list.blockSignals(False)

    def _on_close_current_tab(self) -> None:
        idx = self._tab_widget.currentIndex()
        if idx >= 0:
            self._on_tab_close_requested(idx)

    # ------------------------------------------------------------------
    # Note list population  [B-84, B-108]
    # ------------------------------------------------------------------
    def populate_note_list(self) -> None:
        if not self._search_bar.text().strip():
            self._populate_note_list_items()
        self._update_status_bar()
        self._update_account_label()

    def _update_account_label(self) -> None:
        session = None
        if self._data_dir:
            try:
                from src.core.auth import SessionManager
                session = SessionManager.load(self._data_dir)
            except Exception:
                pass

        if session:
            username = session["username"]
            self._status_account_label.setText(f"\U0001f464 {username}")
        else:
            self._status_account_label.setText("\U0001f464 Guest")

        if not hasattr(self, "_user_menu"):
            return
        self._user_menu.clear()
        if session:
            username = session["username"]
            header = self._user_menu.addAction(f"Signed in as {username}")
            header.setEnabled(False)
            self._user_menu.addSeparator()
            self._user_menu.addAction(self._action_sync_signout)
            self._toolbar_sync_btn.setVisible(True)
            self._toolbar_user_btn.setText(f"\U0001f464  {username}")
        else:
            self._user_menu.addAction(self._action_sync_signin)
            self._toolbar_sync_btn.setVisible(False)
            self._toolbar_user_btn.setText("\U0001f464  Guest")
        # Force the menu bar to reclaim / release space for the corner widget
        # after its contents change — Qt does not reflow it automatically.
        self._account_corner.adjustSize()
        self.menuBar().setCornerWidget(self._account_corner, Qt.Corner.TopRightCorner)

    def _current_account_id(self) -> Optional[str]:
        if not self._data_dir:
            return None
        try:
            from src.core.auth import SessionManager
            session = SessionManager.load(self._data_dir)
            return session["account_id"] if session else None
        except Exception:
            return None

    def _populate_note_list_items(self) -> None:
        # Block signals during the rebuild: clear()/addItem() make Qt move the
        # current row, which would fire currentItemChanged → _on_note_selected
        # and spuriously switch the active tab to whichever note shifted into the
        # old row (e.g. after Save, "the note under it").  Selection is restored
        # afterwards via _sync_note_list_selection.
        self._note_list.blockSignals(True)
        try:
            self._note_list.clear()
            account_id = self._current_account_id()
            account_notes, local_notes = self._store.list(account_id=account_id)
            if account_notes:
                self._note_list.addItem(self._make_section_header("Your Notes"))
                for note in account_notes:
                    self._note_list.addItem(self._make_note_item(note))
            if account_notes and local_notes:
                self._note_list.addItem(self._make_section_header("Guest Notes"))
            for note in local_notes:
                self._note_list.addItem(self._make_note_item(note))
        finally:
            self._note_list.blockSignals(False)

    @staticmethod
    def _make_note_item(note: Note) -> QListWidgetItem:
        display = f"\U0001f512 {note.title}" if note.encrypted else note.title
        item = QListWidgetItem(display)
        item.setData(Qt.ItemDataRole.UserRole, note.id)
        return item

    @staticmethod
    def _make_section_header(text: str) -> QListWidgetItem:
        item = QListWidgetItem(f"  {text}")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = item.font()
        font.setBold(True)
        font.setItalic(True)
        item.setFont(font)
        item.setForeground(QColor("#888888"))
        return item

    # ------------------------------------------------------------------
    # Search  [B-107]
    # ------------------------------------------------------------------
    def _on_search_changed(self, text: str) -> None:
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
        self._search_bar.setFocus()
        self._search_bar.selectAll()

    # ------------------------------------------------------------------
    # Settings  [B-109]
    # ------------------------------------------------------------------
    def _on_settings(self) -> None:
        dlg = SettingsDialog(self._config, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        app = QApplication.instance()
        accent = self._config.get("accent_color") or "purple"
        if app:
            apply_theme(app, dlg.theme, dlg.font_size, dlg.font_family, accent)
        for editor in self._note_editors.values():
            editor.apply_font_size(dlg.font_size)
            editor.apply_font_family(dlg.font_family)
            editor.apply_word_wrap(dlg.word_wrap)
            editor.apply_theme(dlg.theme)

    def _on_plugins(self) -> None:
        open_mimes: set[str] = set()
        for i in range(self._tab_widget.count()):
            widget = self._tab_widget.widget(i)
            if isinstance(widget, PluginEditorHost):
                mime = getattr(widget, "_routing_mime", None)
                if mime:
                    open_mimes.add(mime)
        dlg = PluginsDialog(self._registry, self._config, self, open_mimes=frozenset(open_mimes))
        dlg.exec()

    def _on_widget_gallery(self) -> None:
        dlg = _WidgetGallery(self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Idle timer  [BL B-102]
    # ------------------------------------------------------------------
    def start_idle_timer(self) -> None:
        self._idle_timer.start()

    def start_auto_sync_timer(self) -> None:
        if self._sync_auto_interval <= 0 or not self._sync_url:
            return
        self._auto_sync_timer = QTimer(self)
        self._auto_sync_timer.setInterval(self._sync_auto_interval * 60 * 1000)
        self._auto_sync_timer.timeout.connect(self._on_sync)
        self._auto_sync_timer.start()

    def reset_idle_timer(self) -> None:
        self._idle_timer.start()

    def _on_idle_timeout(self) -> None:
        if self._current_note is not None and self._current_note.encrypted:
            self._cached_passphrase = None
            self._editor.show_encrypted_placeholder()
            logger.info("Idle timeout: encrypted note auto-locked.  [B-102]")

    def auto_close_encrypted_note(self) -> None:
        self._on_idle_timeout()

    # ------------------------------------------------------------------
    # Sync  [BL B-89, B-90]
    # ------------------------------------------------------------------
    def _account_dialog(self) -> SyncLoginDialog:
        data_dir = self._data_dir or Path(".")
        return SyncLoginDialog(
            store=self._store,
            data_dir=data_dir,
            google_client_id=self._google_client_id,
            google_client_secret=self._google_client_secret,
            parent=self,
        )

    def _on_sync(self) -> None:
        if not self._sync_url:
            QMessageBox.information(
                self,
                "Sync not configured",
                "Configure a sync server URL in Settings first.",
            )
            return
        if self._sync_worker is not None and self._sync_worker.isRunning():
            return

        data_dir = self._data_dir or Path(".")
        from src.core.auth import SessionManager
        if SessionManager.load(data_dir) is None:
            if self._account_dialog().exec() != QDialog.DialogCode.Accepted:
                return
            self.populate_note_list()

        token_data = load_cached_token(data_dir)
        if token_data is None:
            QMessageBox.warning(
                self,
                "Sync server authentication needed",
                "You are signed in locally but not yet authenticated with the "
                "sync server.\n\nSign out and sign back in while the sync "
                "server is running to enable sync.",
            )
            return

        client = SyncClient(base_url=self._sync_url)
        worker = SyncWorker(
            client=client,
            token=token_data["access_token"],
            account_id=token_data["account_id"],
            store=self._store,
            direction="both",
        )
        worker.progress.connect(self._on_sync_progress)
        worker.finished_ok.connect(self._on_sync_finished)
        worker.failed.connect(self._on_sync_failed)
        worker.conflict_detected.connect(self._on_conflict_detected)
        self._sync_worker = worker
        self._status_sync_label.setText("● Syncing…")
        worker.start()

    def _on_sync_login(self) -> None:
        self._account_dialog().exec()
        self.populate_note_list()

    def _on_sync_logout(self) -> None:
        from src.core.auth import SessionManager
        data_dir = self._data_dir or Path(".")

        # Close tabs that belong to the signed-out user before wiping the session.
        account_id = self._current_account_id()
        if account_id:
            user_notes, _ = self._store.list(account_id=account_id)
            user_note_ids = {n.id for n in user_notes}
            # Collect in reverse-index order so removals don't shift remaining indices.
            indices_to_close = sorted(
                (
                    self._tab_widget.indexOf(editor)
                    for nid, editor in list(self._note_editors.items())
                    if nid in user_note_ids
                ),
                reverse=True,
            )
            for idx in indices_to_close:
                if idx >= 0:
                    self._on_tab_close_requested(idx)
            if self._current_note is not None and self._current_note.id in user_note_ids:
                self._current_note = None
                self._cached_passphrase = None

        SessionManager.delete(data_dir)
        delete_cached_token(data_dir)
        if self._auto_sync_timer is not None:
            self._auto_sync_timer.stop()
        self._status_sync_label.setText("● Not synced")
        self.populate_note_list()

    def _on_sync_progress(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 0)

    def _on_sync_finished(self, summary: dict) -> None:  # noqa: ARG002
        self._status_sync_label.setText("● Synced")
        self.statusBar().clearMessage()
        self.populate_note_list()
        if self._sync_worker is not None:
            self._sync_worker.deleteLater()
            self._sync_worker = None

    def _on_sync_failed(self, err_class: str, msg: str) -> None:
        self._status_sync_label.setText("● Sync failed")
        self.statusBar().clearMessage()
        QMessageBox.warning(self, f"Sync failed ({err_class})", msg)
        if self._sync_worker is not None:
            self._sync_worker.deleteLater()
            self._sync_worker = None

    def _on_conflict_detected(self, conflicts: list) -> None:
        for item in conflicts:
            local_note = item.get("local") or {}
            remote_note = item.get("remote") or {}
            dlg = MergeWindow(local_note=local_note, remote_note=remote_note, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._on_merge_accepted(item, dlg.resolved_content())

    def _on_merge_accepted(self, conflict_item: dict, content: str) -> None:
        note_id = conflict_item.get("note_id") or ""
        remote = conflict_item.get("remote") or {}
        now = datetime.now(timezone.utc).isoformat()
        remote_modified_at = remote.get("modified_at") or now
        data_dir = self._data_dir or Path(".")
        token_data = load_cached_token(data_dir)
        account_id = (token_data or {}).get("account_id") or ""
        self._store.upsert_remote(
            note_id=note_id,
            account_id=account_id,
            title=remote.get("title") or "",
            content=content,
            is_encrypted=bool(remote.get("is_encrypted")),
            blob=remote.get("blob"),
            created_at=remote.get("created_at") or remote_modified_at,
            modified_at=now,
            synced_at=remote_modified_at,
        )
        self.populate_note_list()

    # ------------------------------------------------------------------
    # Plugin editor resolution
    # ------------------------------------------------------------------
    def _find_editor_for_mime(self, mime_type: str = "text/plain") -> Optional[object]:
        """Return a fresh EditorProtocol instance for *mime_type*, or None.

        Search order:
        1. Plugins that explicitly advertise *mime_type* in ``provides_formats``
           (these are the "primary" editors for that format).
        2. Plugins that list *mime_type* in ``mime_types`` but don't advertise
           it in ``provides_formats`` (fallback/legacy editors).
        3. First plugin that returns a non-None editor (any mime).
        4. None — PluginEditorHost falls back to a bare RichTextEditor.
        """
        plugins = getattr(self._registry, "_plugins", None) or []

        # Tier 1: plugins that explicitly advertise this MIME in provides_formats
        for plugin in plugins:
            advertised = {m for _, m, _ in (getattr(plugin, "provides_formats", None) or [])}
            if mime_type in advertised:
                ed = plugin.create_editor()
                if ed is not None:
                    return ed

        # Tier 2: plugins that support the MIME but don't advertise it
        for plugin in plugins:
            advertised = {m for _, m, _ in (getattr(plugin, "provides_formats", None) or [])}
            if mime_type in advertised:
                continue  # already tried in tier 1
            if mime_type in (getattr(plugin, "mime_types", None) or []):
                ed = plugin.create_editor()
                if ed is not None:
                    return ed

        # Tier 3: fallback to any plugin — text-family MIMEs only.
        # For audio/video MIMEs, returning an arbitrary text editor would silently
        # render raw base64 data.  Return None instead so the caller can show a
        # "plugin missing" error.
        if not (mime_type.startswith("audio/") or mime_type.startswith("video/")):
            for plugin in plugins:
                ed = plugin.create_editor()
                if ed is not None:
                    return ed

        return None

    # ------------------------------------------------------------------
    # CRUD operations  [BL B-85]
    # ------------------------------------------------------------------
    def _on_new_note(self, mime_type: str = "text/plain") -> None:
        self._current_note = None
        self._cached_passphrase = None
        editor = self._open_new_tab(label="New Note", mime_type=mime_type)
        editor.clear()
        self._editor = editor
        self._note_list.blockSignals(True)
        self._note_list.clearSelection()
        self._note_list.setCurrentRow(-1)
        self._note_list.blockSignals(False)
        self.reset_idle_timer()

    def _on_new_note_prompt(self) -> None:
        plugin_formats: list[tuple[str, str, str]] = []
        for plugin in getattr(self._registry, "_plugins", []) or []:
            for entry in getattr(plugin, "provides_formats", None) or []:
                try:
                    label, mime, desc = entry
                    plugin_formats.append((str(label), str(mime), str(desc)))
                except (TypeError, ValueError):
                    continue
        default_encrypt = (self._config.get("default_encrypt") or "no") == "yes"
        dlg = _NewNoteTypeDialog(
            self,
            default_encrypt=default_encrypt,
            plugin_formats=plugin_formats or None,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._on_new_note(mime_type=dlg.note_format)
        if dlg.encrypted:
            self._editor.set_encrypted(True)
        idx = self._tab_widget.indexOf(self._editor)
        if idx >= 0:
            prefix = "\U0001f512 " if dlg.encrypted else ""
            self._tab_widget.setTabText(idx, f"{prefix}New {dlg.format_label}")

    def _on_save(self) -> None:
        title = self._editor.get_title()
        # plain_text used for empty / placeholder guards; html_content is what gets stored
        plain_text = self._editor.get_content()
        html_content = self._editor.get_html_content()
        if not title:
            QMessageBox.warning(self, "Validation", "Title must not be empty.")
            return
        if not plain_text and not self._editor.is_encrypted():
            QMessageBox.warning(self, "Validation", "Content must not be empty.")
            return
        if self._editor.is_encrypted():
            if plain_text and plain_text != _ENCRYPTED_PLACEHOLDER:
                passphrase = self._get_or_prompt_passphrase(confirm=True)
                if not passphrase:
                    return
                is_newly_encrypted = (
                    self._current_note is None or not self._current_note.encrypted
                )
                if is_newly_encrypted:
                    alias_dlg = _AliasPromptDialog(title, self)
                    if alias_dlg.exec() != QDialog.DialogCode.Accepted:
                        return
                    alias = alias_dlg.alias
                else:
                    alias = title
                try:
                    km = KeyManager(passphrase)
                    engine = km.get_engine()
                    inner = json.dumps(
                        {"title": title, "content": html_content}, ensure_ascii=False
                    ).encode("utf-8")
                    raw_container = Container.frame(
                        inner, "application/x-astranotes-text", FLAG_ENCRYPTED
                    )
                    hdr, pld = Container.unframe(raw_container)
                    val = Container.validate(hdr, pld)
                    if val.is_error:
                        self._show_container_dialog(
                            "Save Failed — Container Error",
                            "The note could not be packaged for encryption.",
                            val.message,
                            error=True,
                        )
                        return
                    if val.is_warning:
                        if not self._show_container_dialog(
                            "Save Warning",
                            "The note container has warnings. Save anyway?",
                            val.message,
                            error=False,
                            ask_continue=True,
                        ):
                            return
                    encrypted_blob = BlobCodec.encrypt(raw_container, engine)
                    if self._current_note is None:
                        note = Note.create(alias, "", encrypted=True, blob=encrypted_blob)
                        self._store.add(note, account_id=self._current_account_id())
                        self._current_note = note
                        self._register_current_editor(note)
                    else:
                        # Pass encrypted=True so a plain→encrypted conversion
                        # actually flips the row and drops the cleartext.
                        self._current_note = self._store.update(
                            self._current_note.id,
                            title=alias,
                            blob=encrypted_blob,
                            encrypted=True,
                        )
                    self._cache_passphrase(passphrase)
                    self._editor.set_title(alias)
                except ContainerValidationError as exc:
                    self._show_container_dialog(
                        "Save Failed — Container Error",
                        "The note container is invalid and was not saved.",
                        exc.message,
                        error=True,
                    )
                    return
                except ValueError as exc:
                    QMessageBox.critical(self, "Encryption Error", str(exc))
                    return
            else:
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
            if not plain_text:
                QMessageBox.warning(self, "Validation", "Content must not be empty.")
                return
            if self._current_note is None:
                note = Note.create(title, html_content)
                self._store.add(note, account_id=self._current_account_id())
                self._current_note = note
                self._register_current_editor(note)
            else:
                if self._current_note.encrypted:
                    if plain_text == _ENCRYPTED_PLACEHOLDER.strip():
                        QMessageBox.warning(
                            self,
                            "Unlock first",
                            "Click Unlock to decrypt the note before removing encryption.",
                        )
                        return
                    self._current_note = self._store.update(
                        self._current_note.id,
                        title=title,
                        content=html_content,
                        encrypted=False,
                    )
                    self._cached_passphrase = None
                else:
                    self._current_note = self._store.update(
                        self._current_note.id, title=title, content=html_content
                    )
        if self._current_note:
            label = (
                f"\U0001f512 {self._current_note.title}"
                if self._current_note.encrypted
                else self._current_note.title
            )
            idx = self._tab_widget.indexOf(self._editor)
            if idx >= 0:
                self._tab_widget.setTabText(idx, label)
        save_idx = self._tab_widget.indexOf(self._editor)
        self.populate_note_list()
        if save_idx >= 0:
            self._on_tab_close_requested(save_idx)
        self.reset_idle_timer()

    def _on_save_for(self, editor: "PluginEditorHost") -> None:
        """Sync self._editor/self._current_note to `editor`, then save.

        Used when save_requested fires from an editor-specific signal (e.g. the
        Tiptap QWebChannel bridge is async — by the time the message arrives
        self._editor may already point to a different tab).
        """
        self._editor = editor
        note_id = next(
            (nid for nid, e in self._note_editors.items() if e is editor), None
        )
        self._current_note = self._store.get(note_id) if note_id else None
        self._on_save()
        # Re-sync to whichever tab is actually current now (may have changed if
        # _on_save closed the saved tab).
        current_idx = self._tab_widget.currentIndex()
        if current_idx >= 0:
            widget = self._tab_widget.widget(current_idx)
            if isinstance(widget, PluginEditorHost):
                self._editor = widget

    def _on_delete_for(self, editor: "PluginEditorHost") -> None:
        """Sync self._editor/self._current_note to `editor`, then delete.

        Mirrors :meth:`_on_save_for` so the 🗑 button always targets its own
        tab, even when the signal arrives asynchronously (Tiptap's QWebChannel
        bridge) and self._editor has since moved to another tab.
        """
        self._editor = editor
        note_id = next(
            (nid for nid, e in self._note_editors.items() if e is editor), None
        )
        self._current_note = self._store.get(note_id) if note_id else None
        self._on_delete()
        current_idx = self._tab_widget.currentIndex()
        if current_idx >= 0:
            widget = self._tab_widget.widget(current_idx)
            if isinstance(widget, PluginEditorHost):
                self._editor = widget

    def _register_current_editor(self, note: Note) -> None:
        self._note_editors[note.id] = self._editor

    def _on_delete(self) -> None:
        if self._current_note is None:
            # Unsaved new note — there is nothing persisted to delete, so
            # "delete" simply discards it by closing its tab.
            idx = self._tab_widget.indexOf(self._editor)
            if idx >= 0:
                self._on_tab_close_requested(idx)
            else:
                self._show_welcome()
            self.reset_idle_timer()
            return
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
            if note_id in self._note_editors:
                editor = self._note_editors.pop(note_id)
                idx = self._tab_widget.indexOf(editor)
                if idx >= 0:
                    self._tab_widget.removeTab(idx)
            if self._tab_widget.count() == 0:
                self._show_welcome()
            else:
                widget = self._tab_widget.currentWidget()
                if isinstance(widget, PluginEditorHost):
                    self._editor = widget
            self.populate_note_list()
        self.reset_idle_timer()

    def _on_note_selected(
        self,
        current: Optional[QListWidgetItem],
        previous: Optional[QListWidgetItem],
    ) -> None:
        if current is None:
            return
        note_id: Optional[str] = current.data(Qt.ItemDataRole.UserRole)
        if note_id is None:
            return
        note = self._store.get(note_id)
        if note is None:
            return
        security_level = self._config.get("security_level") or "high"
        if (
            security_level == "high"
            and self._current_note is not None
            and self._current_note.id != note_id
        ):
            self._cached_passphrase = None
        self._current_note = note
        editor = self._get_or_open_tab(note)
        if editor is None:
            return
        decrypted_content: Optional[str] = None
        if note.encrypted and self._cached_passphrase:
            result = self._try_decrypt_note(note)
            if result is not None:
                real_title, decrypted_content = result
                target_mime = self._mime_for_content(decrypted_content or "")
                editor = self._retarget_tab_editor(note, editor, target_mime)
                if editor is None:
                    return
                editor.load(note, decrypted_content=decrypted_content)
                editor.set_title(real_title)
                self.reset_idle_timer()
                return
        editor.load(note, decrypted_content=decrypted_content)
        self.reset_idle_timer()

    # ------------------------------------------------------------------
    # Unlock button handler  [B-106]
    # ------------------------------------------------------------------
    def _on_unlock_requested(self) -> None:
        editor = self._tab_widget.currentWidget()
        if not isinstance(editor, PluginEditorHost):
            return
        note_id = next(
            (nid for nid, ed in self._note_editors.items() if ed is editor), None
        )
        note = self._store.get(note_id) if note_id is not None else self._current_note
        if note is None or not note.encrypted:
            return
        passphrase = self._get_or_prompt_passphrase()
        if not passphrase:
            return
        result = self._try_decrypt_with_passphrase(note, passphrase)
        if result is None:
            QMessageBox.warning(
                self,
                "Wrong Passphrase",
                "Could not decrypt the note. Please check your passphrase.",
            )
            return
        self._cached_passphrase = passphrase
        real_title, decrypted = result
        target_mime = self._mime_for_content(decrypted or "")
        editor = self._retarget_tab_editor(note, editor, target_mime)
        if editor is None:
            return
        editor.load(note, decrypted_content=decrypted)
        editor.set_title(real_title)

    # ------------------------------------------------------------------
    # Passphrase handling  [BL B-84, B-85, B-98]
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Container error dialogs  [design §5.3]
    # ------------------------------------------------------------------

    def _show_container_dialog(
        self,
        title: str,
        text: str,
        detail: str,
        *,
        error: bool,
        ask_continue: bool = False,
    ) -> bool:
        """Show a QMessageBox with a 'Show Details…' button for *detail*.

        Returns True if the caller should continue, False if it should abort.
        When *ask_continue* is True a Save/Cancel button pair is shown;
        otherwise only OK is shown and the return value is always False.
        """
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setDetailedText(detail)
        if error:
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            return False
        msg.setIcon(QMessageBox.Icon.Warning)
        if ask_continue:
            msg.setStandardButtons(
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel
            )
            return msg.exec() == QMessageBox.StandardButton.Save
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        return False

    # ------------------------------------------------------------------
    # Passphrase handling  [BL B-84, B-85, B-98]
    # ------------------------------------------------------------------

    def _get_or_prompt_passphrase(self, *, confirm: bool = False) -> Optional[str]:
        if self._cached_passphrase:
            return self._cached_passphrase
        dlg = PassphraseDialog(self, confirm=confirm)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.passphrase or None

    def _cache_passphrase(self, passphrase: str) -> None:
        self._cached_passphrase = passphrase

    def _try_decrypt_note(self, note: Note) -> Optional[tuple[str, str]]:
        if not self._cached_passphrase:
            return None
        return self._try_decrypt_with_passphrase(note, self._cached_passphrase)

    def _try_decrypt_with_passphrase(
        self, note: Note, passphrase: str
    ) -> Optional[tuple[str, str]]:
        try:
            if note.blob is None:
                return None
            km = KeyManager(passphrase)
            engine = km.get_engine()
            raw_container = BlobCodec.decrypt(note.blob, engine)
            hdr, payload = Container.unframe(raw_container)
            val = Container.validate(hdr, payload)
            if val.is_error:
                self._show_container_dialog(
                    "Load Failed — Container Error",
                    f"Note '{note.title}' could not be loaded: the container is corrupt.",
                    val.message,
                    error=True,
                )
                return None
            if val.is_warning:
                self.statusBar().showMessage(
                    f"Warning loading '{note.title}': {val.message}", 6000
                )
            data = json.loads(payload.decode("utf-8"))
            real_title = data.get("title") or note.title
            return real_title, data.get("content", "")
        except ContainerValidationError as exc:
            self._show_container_dialog(
                "Load Failed — Container Error",
                f"Note '{note.title}' could not be loaded.",
                exc.message,
                error=True,
            )
            return None
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
        behavior = self._config.get("close_behavior") or "ask"
        if behavior == "minimize" and self._tray.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            return
        if behavior == "quit":
            event.accept()
            QApplication.quit()
            return
        if not self._tray.isSystemTrayAvailable():
            event.accept()
            QApplication.quit()
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
            QApplication.quit()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.reset_idle_timer()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        self.reset_idle_timer()
        super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Backward-compat re-exports
# Tests and other callers that do:
#   from src.desktop.main_window import <name>
# continue to work without change.
# ---------------------------------------------------------------------------
__all__ = [
    # constants
    "_IDLE_TIMEOUT_MS",
    "_ENCRYPTED_PLACEHOLDER",
    # theme
    "DARK_STYLESHEET",
    "LIGHT_STYLESHEET",
    "ACCENT_COLORS",
    "_QSS_WATCHER",
    "_stylesheet_with_accent",
    "_install_qss_hotreload",
    "apply_theme",
    # note_editor
    "PluginEditorHost",
    "_WelcomeWidget",
    # dialogs
    "PassphraseDialog",
    "_CloseChoiceDialog",
    "_AliasPromptDialog",
    "_NewNoteTypeDialog",
    "_WidgetGallery",
    # account_dialog
    "SyncLoginDialog",
    "_OAuthCallbackHandler",
    "_OAuthCallbackServer",
    "_GOOGLE_AUTH_URL",
    "_GOOGLE_SCOPE",
    # settings_dialog
    "SettingsDialog",
    # plugins_dialog
    "PluginsDialog",
    "registry_manifests",
    # main window
    "MainWindow",
]
