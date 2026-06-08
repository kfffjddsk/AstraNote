"""EditorProtocol — structural interface for plugin-provided note editors.

Every plugin that wants to supply a note editing UI must return an object
satisfying this protocol from :meth:`~src.core.plugin_base.PluginBase.create_editor`.

Data flow
---------
Save path (plugin → app):
    1. User edits in the plugin widget.
    2. Widget emits ``save_requested(title, raw_content)`` signal.
    3. App receives title, calls ``plugin.pack(raw_content)`` → bytes.
    4. App wraps bytes in a Container, stores it.
    5. App calls ``editor.show_save_result(ok, msg)`` to report outcome.

Load path (app → plugin):
    1. App unpacks the container bytes via ``plugin.unpack(data)``.
    2. App calls ``editor.load(real_title, unpacked_content)``.
    3. Plugin renders the content in its widget.

Security note
-------------
The plugin widget only ever sees the content of the *current* note passed
via ``load()``.  It never holds a reference to DatabaseStore or the note list.

Refs: [BL B-99, B-100] [REQ R4.11, R4.12, R4.13] design §3.1
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


@runtime_checkable
class EditorProtocol(Protocol):
    """Structural protocol all plugin editor widgets must satisfy.

    Implementations must:
    - Subclass ``QWidget``
    - Declare ``save_requested = Signal(str, object)`` and
      ``content_changed = Signal()`` as class-level Qt signals
    - Implement the three methods below
    """

    # Qt signals — declared as Any because Signal descriptors are not
    # representable in typing.Protocol without introducing a PySide6 dep.
    save_requested: Any   # Signal(str, object) — (title, raw_content)
    content_changed: Any  # Signal()

    def as_widget(self) -> "QWidget":
        """Return the QWidget to embed in the tab area."""
        ...

    def load(self, title: str, data: Any) -> None:
        """Populate the editor from app-supplied *title* and *data*.

        *data* is the value returned by ``plugin.unpack()``.
        For plain text this is a ``str``; for binary formats it may be
        ``bytes`` or any richer type the plugin understands.
        """
        ...

    def show_save_result(self, ok: bool, msg: str) -> None:
        """Report the outcome of a save back to the editor UI.

        *ok* is True on success.  *msg* carries an error description on
        failure so the editor can display inline feedback.
        """
        ...


class DefaultFileEditor:
    """Fallback editor shown when no plugin claims a MIME type.

    Displays a 'no editor available' message and a file-upload button so
    the user can still replace the binary payload manually.

    Implements :class:`EditorProtocol` as a concrete class (not a Protocol
    subclass) to keep Qt imports out of this module.  The actual QWidget is
    built lazily on first call to :meth:`as_widget`.
    """

    def __init__(self, mime_type: str = "") -> None:
        self._mime_type = mime_type
        self._widget: Optional[Any] = None  # QWidget, created lazily
        self._on_save: Optional[Any] = None
        self._on_change: Optional[Any] = None

    # -- EditorProtocol interface --

    @property
    def save_requested(self) -> Any:  # noqa: D401
        return self._ensure_widget().save_requested

    @property
    def content_changed(self) -> Any:  # noqa: D401
        return self._ensure_widget().content_changed

    def as_widget(self) -> "QWidget":
        return self._ensure_widget()

    def load(self, title: str, data: Any) -> None:
        self._ensure_widget().load(title, data)

    def show_save_result(self, ok: bool, msg: str) -> None:
        self._ensure_widget().show_save_result(ok, msg)

    # -- Internal --

    def _ensure_widget(self) -> Any:
        if self._widget is None:
            self._widget = _DefaultFileEditorWidget(self._mime_type)
        return self._widget


class _DefaultFileEditorWidget:
    """Concrete QWidget implementation for DefaultFileEditor.

    Defined here to defer the PySide6 import until the widget is first used.
    """

    def __new__(cls, mime_type: str = "") -> Any:  # type: ignore[misc]
        from PySide6.QtCore import Signal as _Signal
        from PySide6.QtWidgets import (
            QFileDialog,
            QLabel,
            QPushButton,
            QVBoxLayout,
            QWidget,
        )

        class _Widget(QWidget):
            save_requested = _Signal(str, object)
            content_changed = _Signal()

            def __init__(self, mime_type: str) -> None:
                super().__init__()
                self._mime_type = mime_type
                self._title = ""
                self._data: Any = None

                layout = QVBoxLayout(self)
                self._label = QLabel(
                    f"No editor available for MIME type: {mime_type or 'unknown'}\n\n"
                    "You can upload a replacement file below."
                )
                self._label.setWordWrap(True)
                layout.addWidget(self._label)

                self._upload_btn = QPushButton("Upload file...")
                self._upload_btn.clicked.connect(self._on_upload)
                layout.addWidget(self._upload_btn)

                self._status = QLabel("")
                layout.addWidget(self._status)
                layout.addStretch()

            def as_widget(self) -> QWidget:
                return self

            def load(self, title: str, data: Any) -> None:
                self._title = title
                self._data = data
                self._status.setText("")

            def show_save_result(self, ok: bool, msg: str) -> None:
                self._status.setText("Saved" if ok else f"Error: {msg}")

            def _on_upload(self) -> None:
                path, _ = QFileDialog.getOpenFileName(self, "Select file")
                if not path:
                    return
                import pathlib
                raw = pathlib.Path(path).read_bytes()
                self.save_requested.emit(self._title, raw)

        return _Widget(mime_type)
