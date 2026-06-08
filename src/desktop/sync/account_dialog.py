"""Account dialog — local sign-in, registration, and Google PKCE OAuth.

All authentication paths are Layer 2 (local account / session).  No sync
server JWT is obtained here; that happens in ``MainWindow._on_sync()``.

Classes
-------
_OAuthCallbackHandler   -- stdlib HTTP handler that captures the redirect code
_OAuthCallbackServer    -- temporary localhost server for the OAuth redirect
SyncLoginDialog         -- tabbed dialog: Sign in / Register / Google

Refs: [BL B-87, B-89] [REQ R13.5, R13.8]
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import logging
import queue
import secrets
import threading
import urllib.parse
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_SCOPE = "openid email profile"


# ---------------------------------------------------------------------------
# _OAuthCallbackHandler / _OAuthCallbackServer  [BL B-87]
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
class SyncLoginDialog(QDialog):
    """Account dialog — sign in, register, or continue with Google.

    Tabs:
      1. Sign in    — ``AccountStore.authenticate()`` → ``SessionManager.create()``
      2. Register   — ``AccountStore.register()`` → ``SessionManager.create()``
      3. Google     — PKCE desktop flow → ``AccountStore.get_or_create_oauth_account()``
                      → ``SessionManager.create()``
    """

    def __init__(
        self,
        store: "DatabaseStore",
        data_dir: Path,
        google_client_id: str = "",
        google_client_secret: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Account")
        self.setMinimumWidth(400)
        self._store = store
        self._data_dir = data_dir
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
                raise RuntimeError(
                    f"Google token exchange failed ({resp.status_code}): {resp.text[:200]}"
                )
            tokens = resp.json()
            id_token = tokens.get("id_token", "")
            if not id_token:
                raise RuntimeError("No id_token in Google response")
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
