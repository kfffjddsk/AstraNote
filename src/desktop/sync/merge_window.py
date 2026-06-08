"""MergeWindow — two-pane conflict-merge dialog for desktop sync.

Per design §4.10 (resolves gap T7 — D-14 decided 2026-05-14): when a
pull surfaces a local-vs-remote conflict, the desktop client opens a
modal :class:`MergeWindow` showing the local copy (read-only, left)
beside the remote copy (editable, right).  The user edits the right
pane to produce a final merged content, optionally clicks
``[← Use Local]`` to overwrite the right pane with the local text, then
clicks ``[Save Final]`` to accept the dialog.

The dialog does **not** write to the database.  The caller pulls the
merged content via :py:meth:`resolved_content` and decides how to
persist it (typically ``DatabaseStore.upsert_remote`` with a fresh
server-time stamp).

Refs: [BL B-86, B-89] [REQ R16.3 — FR-122] design §4.10
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class MergeWindow(QDialog):
    """Two-pane modal dialog for resolving a sync conflict.

    Parameters
    ----------
    local_note:
        Mapping with at least ``title`` and ``content``.  Rendered into
        the read-only left pane.
    remote_note:
        Mapping with at least ``content``.  Pre-populates the editable
        right pane.  ``modified_at`` is captured for the caller.
    parent:
        Optional parent widget.
    """

    def __init__(
        self,
        local_note: Mapping[str, Any],
        remote_note: Mapping[str, Any],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._local_note: dict[str, Any] = dict(local_note)
        self._remote_note: dict[str, Any] = dict(remote_note)

        # Expose useful identifiers to the caller so it knows how to
        # write the resolved content back to the DB.
        self.local_id: Optional[str] = (
            self._local_note.get("id") or self._local_note.get("note_id")
        )
        self.remote_modified_at: Optional[str] = self._remote_note.get(
            "modified_at"
        )

        title = self._local_note.get("title") or self._remote_note.get("title") or "Untitled"
        self.setWindowTitle(f"Conflict — {title}")
        self.setModal(True)
        self.resize(900, 600)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        panes = QHBoxLayout()
        panes.setSpacing(8)

        # Left — local, read-only
        left = QVBoxLayout()
        left.addWidget(QLabel("<b>Local (yours)</b>"))
        self._local_edit = QTextEdit()
        self._local_edit.setReadOnly(True)
        self._local_edit.setPlainText(str(self._local_note.get("content") or ""))
        left.addWidget(self._local_edit, stretch=1)

        # Right — remote, editable
        right = QVBoxLayout()
        right.addWidget(QLabel("<b>Remote (server)</b>"))
        self._remote_edit = QTextEdit()
        self._remote_edit.setReadOnly(False)
        self._remote_edit.setPlainText(str(self._remote_note.get("content") or ""))
        right.addWidget(self._remote_edit, stretch=1)

        panes.addLayout(left, stretch=1)
        panes.addLayout(right, stretch=1)
        outer.addLayout(panes, stretch=1)

        # Action row — [← Use Local] [Save Final]
        action_row = QHBoxLayout()
        self._use_local_btn = QPushButton("← Use Local")
        self._use_local_btn.setToolTip(
            "Copy the left pane content into the right pane (discards remote text)."
        )
        self._use_local_btn.clicked.connect(self._on_use_local)
        action_row.addWidget(self._use_local_btn)

        action_row.addStretch(1)

        self._save_final_btn = QPushButton("Save Final")
        self._save_final_btn.setDefault(True)
        self._save_final_btn.clicked.connect(self.accept)
        action_row.addWidget(self._save_final_btn)
        outer.addLayout(action_row)

        # Standard Cancel button row (Cancel only — Save is the action above)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        button_box.rejected.connect(self.reject)
        outer.addWidget(button_box, alignment=Qt.AlignmentFlag.AlignRight)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_use_local(self) -> None:
        """Copy the read-only local content into the editable remote pane."""
        self._remote_edit.setPlainText(self._local_edit.toPlainText())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def resolved_content(self) -> str:
        """Return the merged content as currently shown in the right pane."""
        return self._remote_edit.toPlainText()

    @property
    def local_note(self) -> dict[str, Any]:
        return dict(self._local_note)

    @property
    def remote_note(self) -> dict[str, Any]:
        return dict(self._remote_note)
