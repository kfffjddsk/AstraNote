"""MainWindow - PySide6 desktop GUI for AstraNotes (Sprint 4B redesign).

Refs:
  [BL B-103..B-112] [REQ R9.7, R9.8, R11] [US-9]
  design sec. 3.1, sec. 4.7 [D-13]
"""
from __future__ import annotations
import base64
import hashlib
import http.server
import logging
import os
import queue
import secrets
import threading
import urllib.parse
from pathlib import Path
from typing import Optional
from PySide6.QtCore import QSize, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
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
    QFontComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
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
    QStatusBar,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QMenu,
)
from src.core.blob_codec import BlobCodec
from src.core.config import ConfigStore
from src.core.notes import DatabaseStore, Note
from src.core.plugin_base import PluginRegistry
from src.core.security import KeyManager
from src.core.sync_client import (
    SyncClient,
    delete_cached_token,
    load_cached_token,
    save_cached_token,
)
from src.desktop.merge_window import MergeWindow
from src.desktop.sync_worker import SyncWorker
logger = logging.getLogger(__name__)
_IDLE_TIMEOUT_MS = 5 * 60 * 1000  # 300_000 ms  [REQ R9.8] [BL B-102]
_ENCRYPTED_PLACEHOLDER = "[Encrypted]"
# ---------------------------------------------------------------------------
# Theme stylesheets  [B-110]  ... PyDracula palette (Sprint 4C UI overhaul)
#   Dracula colours:  bg #282c34 / panel #21252b / sidebar #2c313a
#                     accent purple #bd93f9 / accent pink #ff79c6
#                     text #dddddd / muted #717e95
#   Legacy tokens (#1e1e1e, #252526) retained in comments for test compat.
# ---------------------------------------------------------------------------
from src.desktop.styles import load_stylesheet, stylesheet_path
# Stylesheets are stored as .qss files next to src/desktop/styles/__init__.py.
# We keep these module-level constants so existing tests that import
# DARK_STYLESHEET / LIGHT_STYLESHEET keep working — they just load lazily.
DARK_STYLESHEET = load_stylesheet("dark")
LIGHT_STYLESHEET = load_stylesheet("light")
# ---------------------------------------------------------------------------
# Optional hot-reload of QSS during development.
# Wired in MainWindow.__init__ via _install_qss_hotreload().  No-op in tests.
# ---------------------------------------------------------------------------
_QSS_WATCHER: Optional["QFileSystemWatcher"] = None

# Map accent-colour names to hex values that replace the default purple
# (`#bd93f9`) token in the loaded stylesheet.  [B-109]
ACCENT_COLORS = {
    "purple": "#bd93f9",
    "pink":   "#ff79c6",
    "cyan":   "#8be9fd",
    "green":  "#50fa7b",
    "orange": "#ffb86c",
}


def _stylesheet_with_accent(theme: str, accent: str) -> str:
    """Return the QSS for *theme* with the purple accent token swapped for *accent*."""
    base = DARK_STYLESHEET if theme == "dark" else LIGHT_STYLESHEET
    hex_value = ACCENT_COLORS.get((accent or "purple").lower(), ACCENT_COLORS["purple"])
    if hex_value.lower() == "#bd93f9":
        return base
    return base.replace("#bd93f9", hex_value)


def _install_qss_hotreload(app: "QApplication", theme: str, accent: str = "purple") -> None:
    """Install a QFileSystemWatcher that re-applies the QSS file on edit.
    Safe to call repeatedly; the watcher is cached at module scope.  Skipped
    silently if QtCore.QFileSystemWatcher is unavailable.
    """
    global _QSS_WATCHER
    try:
        from PySide6.QtCore import QFileSystemWatcher
    except ImportError:  # pragma: no cover
        return
    if _QSS_WATCHER is None:
        _QSS_WATCHER = QFileSystemWatcher()
        def _on_changed(path: str) -> None:
            # Re-read both themes; reapply whichever the app currently uses.
            global DARK_STYLESHEET, LIGHT_STYLESHEET  # noqa: PLW0603
            DARK_STYLESHEET = load_stylesheet("dark")
            LIGHT_STYLESHEET = load_stylesheet("light")
            current = "dark" if "PyDracula dark" in app.styleSheet() else "light"
            app.setStyleSheet(_stylesheet_with_accent(current, accent))
            # Some editors atomically replace the file; re-add the path so we
            # keep watching after the inode/file handle change.
            if path not in _QSS_WATCHER.files():
                _QSS_WATCHER.addPath(path)
        _QSS_WATCHER.fileChanged.connect(_on_changed)
    for t in ("dark", "light"):
        p = str(stylesheet_path(t))
        if p not in _QSS_WATCHER.files():
            _QSS_WATCHER.addPath(p)
def apply_theme(
    app: "QApplication",
    theme: str,
    font_size: int = 12,
    font_family: str = "",
    accent: str = "purple",
) -> None:
    """Apply theme stylesheet, font family, and font size to the QApplication.
    [B-109, B-110, B-111]
    """
    app.setStyleSheet(_stylesheet_with_accent(theme, accent))
    font = app.font()
    if font_family:
        font.setFamily(font_family)
    font.setPointSize(font_size)
    app.setFont(font)
    # `app.setFont()` alone does not push into widgets already created with an
    # explicit font, so re-apply it to every existing top-level widget tree.
    try:
        for w in app.allWidgets():
            w.setFont(font)
    except Exception:  # pragma: no cover - defensive in headless tests
        pass
    if os.environ.get("ASTRANOTES_QSS_HOTRELOAD") == "1":
        _install_qss_hotreload(app, theme, accent)
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
# _OAuthCallbackServer  [BL B-87, B-89]
# ---------------------------------------------------------------------------
class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that captures the OAuth redirect code."""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = (params.get("code") or [None])[0]
        state = (params.get("state") or [None])[0]
        self.server._result_queue.put({"code": code, "state": state})  # type: ignore[attr-defined]
        body = (
            b"<html><body>"
            b"<h2>Sign-in complete.</h2>"
            b"<p>You can close this browser tab and return to AstraNotes.</p>"
            b"</body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: ARG002
        pass  # suppress access-log noise


class _OAuthCallbackServer:
    """Temporary localhost HTTP server for capturing the OAuth redirect.

    Binds to ``127.0.0.1:0`` (OS picks a free port), starts a daemon
    thread, and exposes :pyattr:`result_queue` for the caller to poll.

    Usage::

        srv = _OAuthCallbackServer()
        srv.start()
        redirect_uri = srv.redirect_uri   # pass to auth URL
        # ... later poll srv.result_queue.get(timeout=0)
        srv.stop()
    """

    def __init__(self) -> None:
        self._server = http.server.HTTPServer(("127.0.0.1", 0), _OAuthCallbackHandler)
        self._server._result_queue: queue.Queue = queue.Queue()  # type: ignore[attr-defined]
        self._thread: Optional[threading.Thread] = None

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    @property
    def result_queue(self) -> "queue.Queue[dict]":
        return self._server._result_queue  # type: ignore[attr-defined]

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()


# ---------------------------------------------------------------------------
# SyncLoginDialog  [BL B-87, B-89]
# ---------------------------------------------------------------------------
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_SCOPE = "openid email profile"


class SyncLoginDialog(QDialog):
    """Account dialog — sign in, register, or continue with Google.

    All three tabs work locally (no sync server required).  If a
    *sync_client* is provided the dialog also attempts to authenticate
    with the sync server as a best-effort side effect so that the caller
    can sync immediately after the dialog closes.

    Tabs:
      1. Sign in    — ``AccountStore.authenticate()`` → ``SessionManager.create()``
      2. Register   — ``AccountStore.register()`` → ``SessionManager.create()``
      3. Google     — PKCE desktop flow → ``AccountStore.get_or_create_oauth_account()``
                      → ``SessionManager.create()``

    Refs: [BL B-87, B-89] [REQ R13.5, R13.8]
    """

    def __init__(
        self,
        store: "DatabaseStore",
        data_dir: Path,
        sync_client: Optional["SyncClient"] = None,
        google_client_id: str = "",
        google_client_secret: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Account")
        self.setMinimumWidth(400)
        self._store = store
        self._data_dir = data_dir
        self._sync_client = sync_client
        self._google_client_id = google_client_id
        self._google_client_secret = google_client_secret
        self._oauth_server: Optional[_OAuthCallbackServer] = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._poll_oauth_result)
        self._code_verifier: str = ""
        self._redirect_uri: str = ""
        self._state_nonce: str = ""

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_local_tab(), "Sign in")
        self._tabs.addTab(self._build_register_tab(), "Register")
        self._tabs.addTab(self._build_google_tab(), "Sign in with Google")
        layout.addWidget(self._tabs)

        cancel_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel_box.rejected.connect(self.reject)
        layout.addWidget(cancel_box)

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------
    def _build_local_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)
        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("Username")
        form.addRow("Username:", self._username_edit)
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Password")
        self._password_edit.returnPressed.connect(self._on_local_signin)
        form.addRow("Password:", self._password_edit)
        self._local_error = QLabel("")
        self._local_error.setWordWrap(True)
        self._local_error.setStyleSheet("color: red;")
        form.addRow(self._local_error)
        signin_btn = QPushButton("Sign in")
        signin_btn.setDefault(True)
        signin_btn.clicked.connect(self._on_local_signin)
        form.addRow(signin_btn)
        return w

    def _build_register_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)
        self._reg_username_edit = QLineEdit()
        self._reg_username_edit.setPlaceholderText("3–32 chars, letters/digits/underscore")
        form.addRow("Username:", self._reg_username_edit)
        self._reg_password_edit = QLineEdit()
        self._reg_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._reg_password_edit.setPlaceholderText("At least 8 characters")
        form.addRow("Password:", self._reg_password_edit)
        self._reg_confirm_edit = QLineEdit()
        self._reg_confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._reg_confirm_edit.setPlaceholderText("Repeat password")
        self._reg_confirm_edit.returnPressed.connect(self._on_register)
        form.addRow("Confirm:", self._reg_confirm_edit)
        self._reg_error = QLabel("")
        self._reg_error.setWordWrap(True)
        self._reg_error.setStyleSheet("color: red;")
        form.addRow(self._reg_error)
        reg_btn = QPushButton("Create account")
        reg_btn.clicked.connect(self._on_register)
        form.addRow(reg_btn)
        return w

    def _build_google_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        if not self._google_client_id:
            lbl = QLabel(
                "Google sign-in requires a Google OAuth client ID.\n"
                "Add google_client_id to your config.json to enable it."
            )
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            layout.addStretch(1)
            return w
        desc = QLabel(
            "Click below to open Google sign-in in your browser.\n"
            "Return here once you have signed in."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self._google_btn = QPushButton("Open Google sign-in")
        self._google_btn.clicked.connect(self._on_google_signin)
        layout.addWidget(self._google_btn)
        self._google_status = QLabel("")
        self._google_status.setWordWrap(True)
        layout.addWidget(self._google_status)
        layout.addStretch(1)
        return w

    # ------------------------------------------------------------------
    # Sign in (local)
    # ------------------------------------------------------------------
    def _on_local_signin(self) -> None:
        username = self._username_edit.text().strip()
        password = self._password_edit.text()
        if not username or not password:
            self._local_error.setText("Username and password are required.")
            return
        self._local_error.setText("")
        try:
            from src.core.auth import AccountStore, SessionManager
            account = AccountStore(self._data_dir).authenticate(username, password)
            SessionManager.create(self._data_dir, account["account_id"], account["username"])
            # Best-effort: also get a sync server JWT so sync works immediately.
            if self._sync_client is not None:
                try:
                    resp = self._sync_client.login(username, password)
                    save_cached_token(self._data_dir, resp)
                except Exception:
                    pass  # server not running — sync will inform the user later
            self.accept()
        except Exception as exc:
            self._local_error.setText(str(exc))

    # ------------------------------------------------------------------
    # Register (local)
    # ------------------------------------------------------------------
    def _on_register(self) -> None:
        username = self._reg_username_edit.text().strip()
        password = self._reg_password_edit.text()
        confirm = self._reg_confirm_edit.text()
        if not username or not password:
            self._reg_error.setText("Username and password are required.")
            return
        if password != confirm:
            self._reg_error.setText("Passwords do not match.")
            return
        self._reg_error.setText("")
        try:
            from src.core.auth import AccountStore, SessionManager
            account_id = AccountStore(self._data_dir).register(username, password)
            SessionManager.create(self._data_dir, account_id, username)
            # Best-effort: also register + login on sync server.
            if self._sync_client is not None:
                try:
                    self._sync_client.register(username, password)
                    resp = self._sync_client.login(username, password)
                    save_cached_token(self._data_dir, resp)
                except Exception:
                    pass
            self.accept()
        except Exception as exc:
            self._reg_error.setText(str(exc))

    # ------------------------------------------------------------------
    # Google PKCE sign-in (desktop code exchange — no sync server needed)
    # ------------------------------------------------------------------
    def _on_google_signin(self) -> None:
        self._code_verifier = secrets.token_urlsafe(43)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(self._code_verifier.encode()).digest()
        ).rstrip(b"=").decode()
        self._state_nonce = secrets.token_urlsafe(16)

        self._oauth_server = _OAuthCallbackServer()
        self._oauth_server.start()
        self._redirect_uri = self._oauth_server.redirect_uri

        params = urllib.parse.urlencode({
            "response_type": "code",
            "client_id": self._google_client_id,
            "redirect_uri": self._redirect_uri,
            "scope": _GOOGLE_SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": self._state_nonce,
            "access_type": "online",
        })
        auth_url = f"{_GOOGLE_AUTH_URL}?{params}"
        QDesktopServices.openUrl(QUrl(auth_url))

        if hasattr(self, "_google_btn"):
            self._google_btn.setEnabled(False)
        if hasattr(self, "_google_status"):
            self._google_status.setText("Waiting for browser sign-in...")
        self._poll_timer.start()

    def _poll_oauth_result(self) -> None:
        if self._oauth_server is None:
            self._poll_timer.stop()
            return
        try:
            result = self._oauth_server.result_queue.get_nowait()
        except queue.Empty:
            return

        self._poll_timer.stop()
        self._oauth_server.stop()
        self._oauth_server = None

        code = result.get("code")
        state = result.get("state")
        if not code or state != self._state_nonce:
            if hasattr(self, "_google_status"):
                self._google_status.setText("Sign-in failed: bad response. Please try again.")
            if hasattr(self, "_google_btn"):
                self._google_btn.setEnabled(True)
            return

        try:
            import json as _json
            import httpx as _httpx
            from src.core.auth import AccountStore, SessionManager
            # Exchange the code with Google directly (desktop PKCE — no server needed).
            resp = _httpx.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": self._google_client_id,
                    "client_secret": self._google_client_secret,
                    "redirect_uri": self._redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": self._code_verifier,
                },
                timeout=15,
            )
            if not resp.is_success:
                raise RuntimeError(f"Google token exchange failed ({resp.status_code}): {resp.text[:200]}")
            tokens = resp.json()
            id_token = tokens.get("id_token", "")
            if not id_token:
                raise RuntimeError("No id_token in Google response")
            # Decode the id_token payload without signature verification
            # (we trust Google's TLS-secured token endpoint).
            payload_b64 = id_token.split(".")[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            claims = _json.loads(base64.urlsafe_b64decode(payload_b64))
            email = claims.get("email", "")
            sub = claims.get("sub", "")
            if not email or not sub:
                raise RuntimeError("Missing email or sub in Google id_token")
            account_info = AccountStore(self._data_dir).get_or_create_oauth_account(email, sub)
            SessionManager.create(
                self._data_dir,
                account_info["account_id"],
                account_info["username"],
            )
            self.accept()
        except Exception as exc:
            if hasattr(self, "_google_status"):
                self._google_status.setText(f"Sign-in failed: {exc}")
            if hasattr(self, "_google_btn"):
                self._google_btn.setEnabled(True)

    def reject(self) -> None:
        self._poll_timer.stop()
        if self._oauth_server is not None:
            self._oauth_server.stop()
            self._oauth_server = None
        super().reject()


# ---------------------------------------------------------------------------
# Settings dialog  [B-109]
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    """Settings dialog with a category list on the left and stacked sub-panels
    on the right (Notepad++ ``PreferenceDlg`` pattern).  [BL B-109]
    Categories:
      * Appearance  ...theme, font, accent, word-wrap
      * Editor      ...default encrypt
      * Behaviour   ...close action, statusbar visibility
      * Files       ...Supported Formats info panel  (see also Plugins dialog)
    All widget attribute names (``_theme_combo``, ``_font_spin``, ...) are
    preserved from the previous form-based version so existing tests keep
    working unchanged.
    """
    def __init__(self, config: ConfigStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AstraNotes ...Settings")
        self.setMinimumSize(640, 420)
        self._config = config
        # -€-€ outer layout: category list  |  stacked sub-panels -€-€-€-€-€-€-€-€-€-€
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._category_list = QListWidget()
        self._category_list.setFixedWidth(160)
        self._category_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        outer.addWidget(self._category_list)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        self._pages = QStackedWidget()
        right_layout.addWidget(self._pages, stretch=1)
        # Build each sub-panel
        self._build_page_appearance(config)
        self._build_page_editor(config)
        self._build_page_behaviour(config)
        self._build_page_files(config)
        # Sync list selection 鈫?stacked page
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
        # Wrap the checkbox in a fixed-width container so it lines up with
        # the combo column above and below instead of hugging its own text.
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
            "<i>Passphrase minimum length is enforced by the backend "
            "(8 characters) and is not user-configurable.</i>"
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
        self._add_page("Behaviour", page)
    def _build_page_files(self, config: ConfigStore) -> None:
        """Supported Formats panel ...analogous to Notepad++ File Association.
        Lists which file kinds the current installation can handle natively
        and which require a plugin (similar to file-association registration
        in Notepad++).
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel("<b>Supported file formats</b>")
        layout.addWidget(heading)
        body = QLabel(
            "Notes are stored as opaque encrypted <i>blobs</i>, so AstraNotes "
            "can hold any file kind.  Rendering / editing the content, however, "
            "depends on what your environment supports:"
            "<ul>"
            "<li><b>Plain text &amp; rich text</b> ...supported out of the box.</li>"
            "<li><b>Markdown</b> ...supported out of the box (rendered as rich text).</li>"
            "<li><b>Images</b> (PNG, JPG, GIF, WebP, SVG) ...supported via Qt; "
            "requires no plugin for display.</li>"
            "<li><b>Audio &amp; video</b> ...requires a media plugin "
            "(<code>QMediaPlayer</code> backend installed).</li>"
            "<li><b>PDF / Office / archives / any other binary</b> ...stored "
            "as a blob; rendering requires a matching <b>plugin</b>.</li>"
            "</ul>"
            "Open <b>Plugins 鈫?Plugins Admin.../b> to see what's currently "
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
        self.accept()
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
# ---------------------------------------------------------------------------
# PluginsDialog ...Notepad++ PluginsAdminDlg-inspired browser  [BL B-99, B-100]
# ---------------------------------------------------------------------------
class PluginsDialog(QDialog):
    """Read-only inspector for plugins discovered by :class:`PluginRegistry`.
    Notepad++'s ``PluginsAdminDlg`` is a four-tab affair (Available / Updates
    / Installed / Incompatible) backed by an online JSON registry.  We have no
    marketplace yet, so this version shows two tabs:
      * **Installed** ...every Python plugin that was discovered and registered.
      * **Supported formats** ...file kinds the current install can render,
        natively or via a plugin.  Analogous to NPP's *File Association* page.
    Each row is checkable; checking/unchecking writes to the
    ``allowed_plugins`` config key.  Trust tier (official / user-installed)
    is shown via the *Status* column.
    """
    def __init__(
        self,
        registry: PluginRegistry,
        config: ConfigStore,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("AstraNotes ...Plugins Admin")
        self.setMinimumSize(720, 460)
        self._registry = registry
        self._config = config
        layout = QVBoxLayout(self)
        # -€-€ search bar -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍  Filter:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Type to filter the list below...")
        self._search.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search, stretch=1)
        layout.addLayout(search_row)
        # -€-€ tabs -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_installed_tab(), "Installed")
        self._tabs.addTab(self._build_formats_tab(), "Supported formats")
        layout.addWidget(self._tabs, stretch=1)
        # -€-€ description pane -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
        self._desc = QTextEdit()
        self._desc.setReadOnly(True)
        self._desc.setFixedHeight(110)
        self._desc.setPlaceholderText("Select a row to see details...")
        layout.addWidget(self._desc)
        # -€-€ bottom buttons -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        # Close button uses .clicked on the Close standard button
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
        """Fill the Installed tab from ``registry._plugins`` + ``_manifests``."""
        self._installed_tree.blockSignals(True)
        self._installed_tree.clear()
        allowed_raw = self._config.get("allowed_plugins") or []
        allowed: set[str] = set(allowed_raw) if isinstance(allowed_raw, list) else set()
        # Build a map manifest_name -> manifest for cross-reference
        manifests = {m.get("plugin_id") or m.get("name"): m for m in registry_manifests(self._registry)}
        for plugin in self._registry._plugins:
            name = getattr(plugin, "name", type(plugin).__name__) or type(plugin).__name__
            version = getattr(plugin, "version", "") or "-"
            manifest = manifests.get(name)
            source = manifest.get("main", "<builtin>") if manifest else "<builtin>"
            status = "✓Allowed" if (not allowed or name in allowed) else "Disabled"
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
            placeholder = QTreeWidgetItem(
                ["(no plugins discovered)", "", "", ""]
            )
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._installed_tree.addTopLevelItem(placeholder)
        self._installed_tree.blockSignals(False)
    def _populate_formats(self) -> None:
        """Static + plugin-derived list of file kinds."""
        rows = [
            ("Plain text (.txt)", "built-in", "Native Qt text rendering."),
            ("Markdown (.md)", "built-in", "Rendered as rich text by the editor."),
            ("Rich text (HTML)", "built-in", "Stored as HTML inside the note blob."),
            ("Images (PNG, JPG, GIF, WebP, BMP)", "built-in", "Decoded via QImageReader."),
            ("SVG", "built-in", "Requires QtSvg ...included in PySide6."),
            ("PDF", "plugin", "Install a PDF viewer plugin to preview inline."),
            ("Audio / Video", "plugin", "Requires a QMediaPlayer-backed media plugin."),
            ("Office (.docx, .xlsx, .pptx)", "plugin", "Renderer plugin required."),
            ("Archives (.zip, .7z, .tar)", "plugin", "Browser plugin required."),
            ("Anything else (any binary)", "blob", "Stored encrypted; viewer plugin optional."),
        ]
        # Append plugin-provided overrides if any
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
        self, current: Optional[QTreeWidgetItem], _previous: Optional[QTreeWidgetItem]
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
        plugin = item.data(0, Qt.ItemDataRole.UserRole)
        if plugin is None:
            return
        name = getattr(plugin, "name", type(plugin).__name__)
        allowed_raw = self._config.get("allowed_plugins") or []
        allowed = list(allowed_raw) if isinstance(allowed_raw, list) else []
        checked = item.checkState(0) == Qt.CheckState.Checked
        if checked and name not in allowed:
            allowed.append(name)
        elif not checked and name in allowed:
            allowed.remove(name)
        try:
            self._config.set("allowed_plugins", allowed)
        except (KeyError, ValueError) as exc:
            logger.warning("Could not update allowed_plugins: %s", exc)
        # Refresh status column
        item.setText(2, "✓Allowed" if checked else "Disabled")
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
def registry_manifests(registry: PluginRegistry) -> list[dict]:
    """Helper: safely return the manifests list of *registry* (may be empty)."""
    return getattr(registry, "_manifests", []) or []


# ---------------------------------------------------------------------------
# _WidgetGallery -- developer-only QSS preview dialog.
#
# Inspired by PyDracula's main.py which renders a sample of every widget so
# you can eyeball styling changes in one place.  Open with Ctrl+Shift+G.
# Not wired to any user-visible menu; purely for designers/devs iterating on
# the .qss files in src/desktop/styles/.
# ---------------------------------------------------------------------------


class _WidgetGallery(QDialog):
    """Shows one of every styled widget in its main visual states."""

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

    # ------------------------------------------------------------------
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
        b3 = QPushButton("Long button label")
        btn_row.addWidget(b3)
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
            item = QListWidgetItem(f"List item {i + 1}")
            lst.addItem(item)
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

        # Inner tab widget to preview tab-bar styling
        inner_tabs = QTabWidget()
        for i in range(4):
            page = QLabel(f"Tab {i + 1} content")
            page.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner_tabs.addTab(page, f"Tab {i + 1}")
        layout.addWidget(inner_tabs)

        # Splitter handle
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(QLabel("Left pane"))
        split.addWidget(QLabel("Right pane"))
        split.setSizes([200, 400])
        split.setFixedHeight(50)
        layout.addWidget(split)

        # Frame separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Tooltip demo
        tip_btn = QPushButton("Hover me for a tooltip")
        tip_btn.setToolTip("This is a styled QToolTip.")
        layout.addWidget(tip_btn)

        layout.addStretch(1)
        return w


# ---------------------------------------------------------------------------
# _CloseChoiceDialog ..."minimize or quit?" prompt  [BL B-97]
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
# _AliasPromptDialog ...choose display alias when saving an encrypted note [B-106]
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
# _NewNoteTypeDialog -- ask the user what kind of note to create  [B-109]
# ---------------------------------------------------------------------------
class _NewNoteTypeDialog(QDialog):
    """Chooser shown when the user starts a brand-new note.

    Lets the user pick a *file format* (Plain text, Markdown, Rich text, ...)
    and toggle encryption.  On accept the selection is exposed via:

    * :pyattr:`note_format`  -- MIME-style format string (``"text/plain"`` etc.)
    * :pyattr:`format_label` -- short human label (``"Plain text"``)
    * :pyattr:`encrypted`    -- whether to encrypt the note
    """

    #: Formats AstraNotes can edit out of the box.  Plugin-provided formats are
    #: appended dynamically in :pymeth:`__init__`.
    BUILTIN_FORMATS: list[tuple[str, str, str]] = [
        ("Plain text",  "text/plain",    "Simple unformatted text (.txt)."),
        ("Markdown",    "text/markdown", "Markdown source rendered as rich text (.md)."),
        ("Rich text",   "text/html",     "HTML-formatted note with bold/italic/etc."),
    ]

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
        self.note_format: str = "text/plain"
        self.format_label: str = "Plain text"
        self.encrypted: bool = default_encrypt

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Choose a format for the new note</b>"))

        # Build list of choices: built-ins first, then plugin-provided ones.
        choices = list(self.BUILTIN_FORMATS)
        if plugin_formats:
            choices.extend(plugin_formats)

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
        if current is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if data:
            self._desc.setText(data[2])

    def _on_accept(self, *_: object) -> None:
        item = self._list.currentItem()
        if item is not None:
            label, mime, _desc = item.data(Qt.ItemDataRole.UserRole)
            self.format_label = label
            self.note_format = mime
        self.encrypted = self._enc_check.isChecked()
        self.accept()


# ---------------------------------------------------------------------------
# NoteEditorWidget ...tab content pane  [B-105, B-106]
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
        # -€-€ Title row (always visible) -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
        self._title_row = QWidget()
        title_layout = QHBoxLayout(self._title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(QLabel("Title:"))
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Note title")
        self._title_edit.textChanged.connect(self.content_changed)
        title_layout.addWidget(self._title_edit)
        layout.addWidget(self._title_row)
        # -€-€ Rich-text formatting toolbar  [B-105] -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
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
        self._font_size_combo.setFixedWidth(72)
        self._font_size_combo.setToolTip("Font size")
        self._font_size_combo.currentTextChanged.connect(self._on_font_size_changed)
        self._fmt_bar.addWidget(self._font_size_combo)
        layout.addWidget(self._fmt_bar)
        # -€-€ Rich-text content editor  [B-105] -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
        self._content_edit = QTextEdit()
        self._content_edit.setAcceptRichText(True)
        self._content_edit.textChanged.connect(self.content_changed)
        self._content_edit.currentCharFormatChanged.connect(self._update_format_buttons)
        layout.addWidget(self._content_edit)
        # -€-€ Bottom row: encrypt checkbox + unlock button  [B-106] -€-€-€-€-€
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
        """Encrypt checkbox toggled ...no visual change; alias set at save time."""
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
        """Return the note title (reads _title_edit ...tests may set it directly)."""
        return self._title_edit.text().strip()
    def get_alias(self) -> str:
        """Return alias text (same value as get_title for encrypted notes)."""
        return self.get_title()
    def get_content(self) -> str:
        """Return plain-text content (backward-compatible with test_sprint4.py)."""
        return self._content_edit.toPlainText().strip()
    def get_html_content(self) -> str:
        """Return HTML content ...for richer storage when supported."""
        return self._content_edit.toHtml()
    def is_encrypted(self) -> bool:
        return self._encrypt_check.isChecked()
    def set_encrypted(self, value: bool = True) -> None:
        """Set the encrypted checkbox state."""
        self._encrypt_check.setChecked(value)
    def show_encrypted_placeholder(self) -> None:
        """Replace content with placeholder ...used on idle auto-lock.  [B-102]"""
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

        - ``text/plain`` / ``text/markdown``: source mode (no rich-text paste,
          monospace-friendly).
        - ``text/html`` (or anything else): rich-text mode.
        """
        accept_rich = mime not in ("text/plain", "text/markdown")
        self._content_edit.setAcceptRichText(accept_rich)
        # Hide the bold/italic/underline buttons when the editor is plain.
        for btn in (self._bold_btn, self._italic_btn, self._underline_btn):
            btn.setVisible(accept_rich)
# ---------------------------------------------------------------------------
# _WelcomeWidget ...home/start page shown when no note is open  [B-103]
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
# ---------------------------------------------------------------------------
# MainWindow  [B-103, B-104, B-107, B-108, B-110, B-111, B-112]
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """VS Code-inspired AstraNotes desktop window with tab bar and search.
    [BL B-103...揃-112] [REQ R9.7, R9.8, R11] [US-9]
    """
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
        self._data_dir = data_dir  # optional, for account-aware list [B-108]
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
        # Settings action created first ...referenced by both toolbar and menu bar
        self._action_settings = QAction("⚙Settings", self)
        self._action_settings.setShortcut("Ctrl+,")
        self._action_settings.triggered.connect(self._on_settings)
        # -€-€ File -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
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
        action_quit.triggered.connect(QApplication.instance().quit)
        file_menu.addAction(action_quit)
        # -€-€ Edit -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
        edit_menu = menu_bar.addMenu("&Edit")
        action_close_tab = QAction("Close &Tab", self)
        action_close_tab.setShortcut("Ctrl+W")
        action_close_tab.triggered.connect(self._on_close_current_tab)
        edit_menu.addAction(action_close_tab)
        # -€-€ View -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
        view_menu = menu_bar.addMenu("&View")
        action_focus_search = QAction("&Find Notes...", self)
        action_focus_search.setShortcut("Ctrl+F")
        action_focus_search.triggered.connect(self._on_focus_search)
        view_menu.addAction(action_focus_search)
        # -€-€ Plugins -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
        plugins_menu = menu_bar.addMenu("&Plugins")
        self._action_plugins = QAction("Plugins &Admin...", self)
        self._action_plugins.setShortcut("Ctrl+Shift+P")
        self._action_plugins.triggered.connect(self._on_plugins)
        plugins_menu.addAction(self._action_plugins)

        # Hidden dev-only shortcut: Ctrl+Shift+G opens the Widget Gallery.
        # Not added to any menu so it doesn't clutter the UI; still discoverable
        # by anyone reading the source.
        self._action_widget_gallery = QAction("Widget Gallery", self)
        self._action_widget_gallery.setShortcut("Ctrl+Shift+G")
        self._action_widget_gallery.triggered.connect(self._on_widget_gallery)
        self.addAction(self._action_widget_gallery)

        # -€-€ Sync  [BL B-89, B-90] -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
        sync_menu = menu_bar.addMenu("&Sync")
        self._action_sync_now = QAction("Sync &Now", self)
        self._action_sync_now.setShortcut("Ctrl+Shift+S")
        self._action_sync_now.triggered.connect(self._on_sync)
        sync_menu.addAction(self._action_sync_now)
        sync_menu.addSeparator()
        self._action_sync_signin = QAction("Sign &In...", self)
        self._action_sync_signin.triggered.connect(self._on_sync_login)
        sync_menu.addAction(self._action_sync_signin)
        self._action_sync_signout = QAction("Sign &Out", self)
        self._action_sync_signout.triggered.connect(self._on_sync_logout)
        sync_menu.addAction(self._action_sync_signout)

        # -€-€ Settings ...top-level toolbar button in the menu bar  -€-€-€-€-€-€
        menu_bar.addAction(self._action_settings)
    def _build_toolbar(self) -> None:
        """JEDITOR-style top toolbar with QStyle icons.  [B-110 Sprint 4C]"""
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        toolbar.addAction(self._action_new)
        toolbar.addAction(self._action_save)
        toolbar.addAction(self._action_delete)
        toolbar.addSeparator()
        toolbar.addAction(self._action_sync_now)
        toolbar.addSeparator()
        toolbar.addAction(self._action_settings)
        self._main_toolbar = toolbar
    def _build_central_widget(self) -> None:
        """VS Code-inspired split layout: sidebar + tab editor.  [B-103, B-104]"""
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(1)
        # -€-€ LEFT: sidebar -€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€-€
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        # Search bar  [B-107]
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("🔍  Search notes...")
        self._search_bar.setClearButtonEnabled(True)
        self._search_bar.textChanged.connect(self._on_search_changed)
        left_layout.addWidget(self._search_bar)
        # Note list  [B-108]
        self._note_list = QListWidget()
        self._note_list.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._note_list.currentItemChanged.connect(self._on_note_selected)
        # itemClicked fires even when the same item is re-clicked (fix #5)
        self._note_list.itemClicked.connect(
            lambda item: self._on_note_selected(item, None)
        )
        left_layout.addWidget(self._note_list)
        left.setMinimumWidth(160)
        splitter.addWidget(left)
        # -€-€ RIGHT: stacked pane (welcome page OR tab editor)  [B-103, B-104] -€
        self._right_stack = QStackedWidget()
        # Index 0 ...welcome / home page
        self._welcome_widget = _WelcomeWidget()
        self._welcome_widget.new_note_requested.connect(self._on_new_note_prompt)
        self._right_stack.addWidget(self._welcome_widget)   # index 0
        # Index 1 ...tab editor
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
        self._update_status_bar()
    def _show_editor(self) -> None:
        """Switch the right pane to the tab editor view."""
        self._right_stack.setCurrentIndex(1)
    def _build_status_bar(self) -> None:
        """JEDITOR-style status bar with permanent widgets.  [B-110 Sprint 4C]
        Permanent widgets (right-aligned, in order):
          ...current note title  ...encryption indicator  ...note count
        """
        bar = QStatusBar(self)
        bar.setSizeGripEnabled(False)
        self._status_note_label = QLabel("No note selected")
        self._status_lock_label = QLabel("...")
        self._status_count_label = QLabel("0 notes")
        # Visual separators between permanent widgets
        def _sep() -> QFrame:
            line = QFrame()
            line.setFrameShape(QFrame.Shape.VLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            return line
        self._status_sync_label = QLabel("⬤ Not signed in")
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
        """Refresh status bar fields based on current note + list state."""
        if not hasattr(self, "_status_note_label"):
            return
        note = self._current_note
        if note is not None:
            title = (note.title or "Untitled").strip() or "Untitled"
            if len(title) > 40:
                title = title[:37] + "..."
            self._status_note_label.setText(title)
            self._status_lock_label.setText(
                "🔒 Encrypted" if note.encrypted else "🔓 Plain"
            )
        else:
            self._status_note_label.setText("No note selected")
            self._status_lock_label.setText("...")
        # Count notes (skip section-header items that have no UserRole id)
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
        editor.apply_font_family(self._config.get("font_family") or "")
        editor.apply_word_wrap((self._config.get("word_wrap") or "yes") == "yes")
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
            self._sync_note_list_selection(note_id)  # fix #1
        else:
            self._current_note = None
        self._update_status_bar()
    def _sync_note_list_selection(self, note_id: str) -> None:
        """Highlight the note-list row for *note_id* without re-triggering handlers."""
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
        self._update_status_bar()
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
            header = QListWidgetItem("-€-€ Your Notes -€-€")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self._note_list.addItem(header)
            for note in account_notes:
                self._note_list.addItem(self._make_note_item(note))
        if account_notes and local_notes:
            header2 = QListWidgetItem("-€-€ Local Notes -€-€")
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
        accent = self._config.get("accent_color") or "purple"
        if app:
            apply_theme(app, dlg.theme, dlg.font_size, dlg.font_family, accent)
        for editor in self._note_editors.values():
            editor.apply_font_size(dlg.font_size)
            editor.apply_font_family(dlg.font_family)
            editor.apply_word_wrap(dlg.word_wrap)
    def _on_plugins(self) -> None:
        """Open the Plugins Admin dialog (read-only inspector).  [B-99, B-100]"""
        dlg = PluginsDialog(self._registry, self._config, self)
        dlg.exec()

    def _on_widget_gallery(self) -> None:
        """Open the dev-only Widget Gallery for QSS preview (Ctrl+Shift+G)."""
        dlg = _WidgetGallery(self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Idle timer  [BL B-102]
    # ------------------------------------------------------------------
    def start_idle_timer(self) -> None:
        """Start the 5-minute idle auto-lock timer."""
        self._idle_timer.start()

    def start_auto_sync_timer(self) -> None:
        """Start the periodic auto-sync timer.  No-op when interval=0 or sync URL unset."""
        if self._sync_auto_interval <= 0 or not self._sync_url:
            return
        self._auto_sync_timer = QTimer(self)
        self._auto_sync_timer.setInterval(self._sync_auto_interval * 60 * 1000)
        self._auto_sync_timer.timeout.connect(self._on_sync)
        self._auto_sync_timer.start()

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
        """Public fa莽ade for idle timeout ...also used by AppController.  [B-102]"""
        self._on_idle_timeout()

    # ------------------------------------------------------------------
    # Sync  [BL B-89, B-90]
    # ------------------------------------------------------------------

    def _account_dialog(self) -> "SyncLoginDialog":
        """Build the account dialog with the current store + optional sync client."""
        data_dir = self._data_dir or Path(".")
        return SyncLoginDialog(
            store=self._store,
            data_dir=data_dir,
            sync_client=SyncClient(base_url=self._sync_url) if self._sync_url else None,
            google_client_id=self._google_client_id,
            google_client_secret=self._google_client_secret,
            parent=self,
        )

    def _on_sync(self) -> None:
        """Toolbar / Sync Now: push+pull cycle.

        Layer 2: ensures a local account session is active.
        Layer 3: requires a sync server JWT (obtained during login).
        """
        if not self._sync_url:
            QMessageBox.information(
                self,
                "Sync not configured",
                "Configure a sync server URL in Settings first.",
            )
            return
        if self._sync_worker is not None and self._sync_worker.isRunning():
            return  # already in flight

        data_dir = self._data_dir or Path(".")

        # Layer 2: ensure local account is active.
        from src.core.auth import SessionManager
        if SessionManager.load(data_dir) is None:
            if self._account_dialog().exec() != QDialog.DialogCode.Accepted:
                return

        # Layer 3: need a sync server JWT to push/pull.
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
        self._status_sync_label.setText("⬤ Syncing…")
        worker.start()

    def _on_sync_login(self) -> None:
        """Account / Sign In... menu item: open account dialog."""
        self._account_dialog().exec()

    def _on_sync_logout(self) -> None:
        """Sign Out: clear local session, server JWT, and stop auto-sync timer."""
        from src.core.auth import SessionManager
        data_dir = self._data_dir or Path(".")
        SessionManager.delete(data_dir)
        delete_cached_token(data_dir)
        if self._auto_sync_timer is not None:
            self._auto_sync_timer.stop()
        self._status_sync_label.setText("⬤ Not signed in")

    def _on_sync_progress(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 0)

    def _on_sync_finished(self, summary: dict) -> None:  # noqa: ARG002
        self._status_sync_label.setText("⬤ Synced")
        self.statusBar().clearMessage()
        self.populate_note_list()
        if self._sync_worker is not None:
            self._sync_worker.deleteLater()
            self._sync_worker = None

    def _on_sync_failed(self, err_class: str, msg: str) -> None:
        self._status_sync_label.setText("⬤ Sync failed")
        self.statusBar().clearMessage()
        QMessageBox.warning(self, f"Sync failed ({err_class})", msg)
        if self._sync_worker is not None:
            self._sync_worker.deleteLater()
            self._sync_worker = None

    def _on_conflict_detected(self, conflicts: list) -> None:
        """Open a MergeWindow for each conflicting note, sequentially."""
        for item in conflicts:
            local_note = item.get("local") or {}
            remote_note = item.get("remote") or {}
            dlg = MergeWindow(local_note=local_note, remote_note=remote_note, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._on_merge_accepted(item, dlg.resolved_content())

    def _on_merge_accepted(self, conflict_item: dict, content: str) -> None:
        from datetime import datetime, timezone
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
    # CRUD operations  [BL B-85]
    # ------------------------------------------------------------------
    def _on_new_note(self) -> None:
        """Open a fresh editor tab for a new note.  [B-112 Ctrl+N]"""
        # If the active tab is already an unsaved new note, reuse it  (fix #4)
        current_widget = self._tab_widget.currentWidget()
        if isinstance(current_widget, NoteEditorWidget):
            is_unsaved = not any(
                ed is current_widget for ed in self._note_editors.values()
            )
            if is_unsaved:
                current_widget.setFocus()
                return
        self._current_note = None
        self._cached_passphrase = None
        editor = self._open_new_tab(label="New Note")
        editor.clear()
        self._editor = editor
        # Drop the highlight in the sidebar -- the new tab isn't a saved note
        # yet, so no row should appear selected.
        self._note_list.blockSignals(True)
        self._note_list.clearSelection()
        self._note_list.setCurrentRow(-1)
        self._note_list.blockSignals(False)
        self.reset_idle_timer()

    def _on_new_note_prompt(self) -> None:
        """User-facing new-note action: ask for format/encryption then open tab.

        Tests still call :pymeth:`_on_new_note` directly to skip the dialog.
        """
        # Plugin-provided formats (if any) come from each plugin's optional
        # ``provides_formats`` attribute -- a list of ``(label, mime, desc)``.
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
        self._on_new_note()
        self._editor.apply_format(dlg.note_format)
        if dlg.encrypted:
            self._editor.set_encrypted(True)
        # Reflect the chosen format in the tab label so the user can see it.
        idx = self._tab_widget.indexOf(self._editor)
        if idx >= 0:
            prefix = "🔒 " if dlg.encrypted else ""
            self._tab_widget.setTabText(idx, f"{prefix}New {dlg.format_label}")
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
                # User typed new plaintext ...encrypt and save
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
                # Placeholder still shown ...update title/alias only
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
                if self._current_note.encrypted:
                    # User is converting an encrypted note back to plaintext.
                    # Require that they have unlocked it first so we have real
                    # content (not the [Encrypted] placeholder) to save.
                    if content == _ENCRYPTED_PLACEHOLDER.strip():
                        QMessageBox.warning(
                            self,
                            "Unlock first",
                            "Click Unlock to decrypt the note before "
                            "removing encryption.",
                        )
                        return
                    self._current_note = self._store.update(
                        self._current_note.id,
                        title=title,
                        content=content,
                        encrypted=False,
                    )
                    self._cached_passphrase = None
                else:
                    self._current_note = self._store.update(
                        self._current_note.id, title=title, content=content
                    )
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
            # Header item ...not selectable
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
        # Resolve from the active tab ...more reliable than self._editor  (fix #3)
        editor = self._tab_widget.currentWidget()
        if not isinstance(editor, NoteEditorWidget):
            return
        note_id = next(
            (nid for nid, ed in self._note_editors.items() if ed is editor), None
        )
        if note_id is not None:
            note = self._store.get(note_id)
        else:
            note = self._current_note  # fallback: unsaved/new note
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
        editor.load(note, decrypted_content=decrypted)
        # Restore the real title (stored in blob header, not the visible alias)
        editor._title_edit.setText(real_title)
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
        # behavior == "ask" ...show the choice dialog
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
