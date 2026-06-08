"""TiptapPlugin — rich-text note editor using Tiptap + QWebEngineView.

The editor loads a Vite-built self-contained HTML bundle from:
    src/plugins/tiptap_plugin/editor/dist/index.html

If the bundle has not been built yet, create_editor() returns None so the
plugin registry falls back to RichTextPlugin, and a build hint is shown when
a tab is opened for a text/html note.

Build the bundle once with Node.js (nodejs.org):
    cd src/plugins/tiptap_plugin/editor
    npm install
    npm run build
"""
from __future__ import annotations

import base64
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineScript, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QFileDialog, QVBoxLayout, QWidget

from src.core.plugin_base import PluginBase, PluginRegistry
from src.core.plugin_context import PluginContext

_DIST_HTML = Path(__file__).parent / "editor" / "dist" / "index.html"


# ---------------------------------------------------------------------------
# EditorBridge — QWebChannel object exposed to JavaScript
# ---------------------------------------------------------------------------


class EditorBridge(QObject):
    """Bidirectional bridge between Python and the Tiptap JavaScript editor.

    Python → JS  (Qt signals the JS side listens to via QWebChannel):
        loadContent(title, html)   — fill the editor with new content
        applyTheme(theme)          — "dark" | "light"
        insertImageData(data_uri)  — base64 image to insert at cursor

    JS → Python  (Qt slots the JS side calls via QWebChannel):
        onReady()                  — editor finished initialising
        onContentChanged(t, html)  — content/title changed
        onSaveRequested(t, html)   — 💾 clicked or Ctrl+S pressed
        onDeleteRequested()        — 🗑 clicked
        onInsertImage()            — image-pick button clicked
    """

    # Signals emitted by Python, consumed by JavaScript
    loadContent = Signal(str, str)   # (title, html)
    applyTheme = Signal(str)         # "dark" | "light"
    insertImageData = Signal(str)    # base64 data-URI

    # Internal signals forwarded by TiptapEditorWidget
    _content_changed = Signal()
    _save_requested = Signal(str, str)   # (title, html)
    _delete_requested = Signal()
    _image_requested = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._title: str = ""
        self._html: str = ""
        self._ready: bool = False
        self._pending: Optional[tuple[str, str]] = None

    # ------------------------------------------------------------------
    # Slots called by JavaScript
    # ------------------------------------------------------------------

    @Slot()
    def onReady(self) -> None:
        """Called by JS when Tiptap has initialised and is ready."""
        self._ready = True
        if self._pending is not None:
            title, html = self._pending
            self._pending = None
            self.loadContent.emit(title, html)

    @Slot(str, str)
    def onContentChanged(self, title: str, html: str) -> None:
        self._title = title
        self._html = html
        self._content_changed.emit()

    @Slot(str, str)
    def onSaveRequested(self, title: str, html: str) -> None:
        self._title = title
        self._html = html
        self._save_requested.emit(title, html)

    @Slot()
    def onDeleteRequested(self) -> None:
        self._delete_requested.emit()

    @Slot()
    def onInsertImage(self) -> None:
        """JS calls this when the image-insert toolbar button is clicked."""
        self._image_requested.emit()

    # ------------------------------------------------------------------
    # Called from Python
    # ------------------------------------------------------------------

    def load(self, title: str, html: str) -> None:
        """Load content from Python.  Queues until JS reports ready."""
        self._title = title
        self._html = html
        if self._ready:
            self.loadContent.emit(title, html)
        else:
            self._pending = (title, html)

    def get_title(self) -> str:
        return self._title

    def get_html(self) -> str:
        return self._html


# ---------------------------------------------------------------------------
# TiptapEditorWidget — QWidget wrapping QWebEngineView
# ---------------------------------------------------------------------------


class TiptapEditorWidget(QWidget):
    """EditorProtocol implementation wrapping Tiptap in QWebEngineView.

    Signals (EditorProtocol):
        save_requested(title, html_content)
        content_changed()
        delete_requested()
    """

    save_requested = Signal(str, object)   # (title, html)
    content_changed = Signal()
    delete_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._current_theme: str = "dark"   # updated by apply_theme before load
        self._view = QWebEngineView(self)

        # Allow local file:// resources within the same directory
        settings = self._view.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )

        # QWebChannel must be set up BEFORE the page starts loading
        self._channel = QWebChannel(self._view.page())
        self._bridge = EditorBridge(self)
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        # Inject qwebchannel.js at DocumentCreation so it's available
        # before any page script runs.
        qwc = QWebEngineScript()
        qwc.setName("qt_webchannel_transport")
        qwc.setSourceUrl(QUrl("qrc:///qtwebchannel/qwebchannel.js"))
        qwc.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        qwc.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self._view.page().scripts().insert(qwc)

        layout.addWidget(self._view)

        # Wire bridge → widget signals
        self._bridge._content_changed.connect(self.content_changed)
        self._bridge._save_requested.connect(
            lambda title, html: self.save_requested.emit(title, html)
        )
        self._bridge._delete_requested.connect(self.delete_requested)
        self._bridge._image_requested.connect(self._on_insert_image)

        # Sync palette on first load so colors match the Qt app theme
        self._view.loadFinished.connect(self._on_load_finished)

        # Load the Vite-built bundle
        if _DIST_HTML.exists():
            self._view.load(QUrl.fromLocalFile(str(_DIST_HTML)))
        else:
            self._show_build_hint()

    def _show_build_hint(self) -> None:
        self._view.setHtml(
            "<!DOCTYPE html><html><body style='"
            "font-family:sans-serif;color:#aaa;background:#1e1e2e;"
            "display:flex;align-items:center;justify-content:center;"
            "height:100vh;margin:0;text-align:center;'>"
            "<div>"
            "<p style='font-size:15px;margin-bottom:8px'>Tiptap editor not built yet.</p>"
            "<p style='font-size:12px;color:#6c7086'>Run inside "
            "<code style='background:#313244;padding:2px 6px;border-radius:3px'>"
            "src/plugins/tiptap_plugin/editor/</code>:</p>"
            "<pre style='display:inline-block;background:#313244;padding:10px 18px;"
            "border-radius:6px;font-size:12px;margin-top:8px'>"
            "npm install &amp;&amp; npm run build</pre>"
            "</div></body></html>"
        )

    # ------------------------------------------------------------------
    # EditorProtocol interface
    # ------------------------------------------------------------------

    def as_widget(self) -> QWidget:
        return self

    def load(self, title: str, data: Any) -> None:
        html = ""
        if isinstance(data, str) and data.strip():
            html = data if data.lstrip().startswith("<") else f"<p>{data}</p>"
        self._bridge.load(title, html)

    def show_save_result(self, ok: bool, msg: str) -> None:
        pass  # could inject a status toast; omitted for now

    # ------------------------------------------------------------------
    # Extended helpers used by PluginEditorHost / MainWindow
    # ------------------------------------------------------------------

    def get_title(self) -> str:
        return self._bridge.get_title()

    def set_title(self, title: str) -> None:
        self._bridge.load(title, self._bridge.get_html())

    def get_content(self) -> str:
        """Plain-text content stripped from HTML — used for empty checks."""
        class _Strip(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.parts: list[str] = []
            def handle_data(self, data: str) -> None:
                self.parts.append(data)

        p = _Strip()
        p.feed(self._bridge.get_html())
        return "".join(p.parts).strip()

    def get_html_content(self) -> str:
        return self._bridge.get_html()

    def apply_format(self, mime: str) -> None:
        pass  # Tiptap always runs in rich-text mode

    def apply_font_size(self, size: int) -> None:
        self._view.page().runJavaScript(
            f"document.documentElement.style.setProperty('--font-size','{size}pt')"
        )

    def apply_font_family(self, family: str) -> None:
        if family:
            self._view.page().runJavaScript(
                f"document.documentElement.style.setProperty('--font-family','{family},sans-serif')"
            )

    def apply_word_wrap(self, enabled: bool) -> None:
        pass  # browser wraps by default; configurable via CSS if needed

    def apply_theme(self, theme: str) -> None:
        """Apply app theme ("dark" | "light") to the editor."""
        self._current_theme = theme
        # Set data-theme directly — works regardless of bridge readiness
        self._view.page().runJavaScript(
            f"document.documentElement.setAttribute('data-theme','{theme}')"
        )
        # Also emit through bridge so JS can react if it cares
        self._bridge.applyTheme.emit(theme)

    def _on_load_finished(self, ok: bool) -> None:
        if ok:
            # Apply the stored theme; runJavaScript is safe here since page is ready
            self._view.page().runJavaScript(
                f"document.documentElement.setAttribute('data-theme','{self._current_theme}')"
            )

    # ------------------------------------------------------------------
    # Image insertion via native file dialog
    # ------------------------------------------------------------------

    def _on_insert_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Insert Image",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp *.svg *.bmp)",
        )
        if not path:
            return
        ext = Path(path).suffix.lstrip(".").lower()
        mime_map = {"jpg": "jpeg", "svg": "svg+xml"}
        img_mime = f"image/{mime_map.get(ext, ext)}"
        with open(path, "rb") as fh:
            data_uri = f"data:{img_mime};base64,{base64.b64encode(fh.read()).decode()}"
        self._bridge.insertImageData.emit(data_uri)


# ---------------------------------------------------------------------------
# TiptapPlugin — PluginBase implementation
# ---------------------------------------------------------------------------


class TiptapPlugin(PluginBase):
    """Rich-text editor plugin powered by Tiptap + QWebEngineView.

    Handles text/html notes with full formatting support:
    headings, bullet/ordered lists, code blocks (syntax-highlighted),
    blockquotes, images, undo/redo.

    Falls back gracefully to RichTextPlugin when the Vite bundle has not
    been built yet (create_editor returns None).
    """

    name = "TiptapPlugin"
    version = "1.0.0"
    mime_types = ["text/html", "text/plain", "text/markdown"]

    provides_formats: list[tuple[str, str, str]] = [
        (
            "Rich text",
            "text/html",
            "Full-featured rich text: headings, bullet/ordered lists, "
            "code blocks with syntax highlighting, images.",
        ),
    ]

    def register_hooks(self, registry: PluginRegistry) -> None:
        pass

    def mime_type(self) -> str:
        return "text/html"

    def create_editor(self) -> Optional[TiptapEditorWidget]:
        if not _DIST_HTML.exists():
            return None  # fall through to RichTextPlugin until bundle is built
        return TiptapEditorWidget()

    def pack(self, data: Any) -> bytes:
        if isinstance(data, bytes):
            return data
        return str(data).encode("utf-8")

    def unpack(self, data: bytes) -> str:
        return data.decode("utf-8", errors="replace")

    def initialize(self, context: PluginContext) -> None:
        built = "yes" if _DIST_HTML.exists() else "no (run npm install && npm run build)"
        context.log(f"TiptapPlugin initialized — bundle built: {built}")
