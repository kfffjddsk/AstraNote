"""Background sync worker — runs push/pull off the Qt UI thread.

A :class:`SyncWorker` is a :class:`QThread` subclass that wraps a single
``push``, ``pull``, or ``both`` cycle.  The UI constructs a worker, wires
its signals to slots, calls :py:meth:`QThread.start`, and forgets about
it; the worker emits progress / completion signals back on the main
thread.

The worker NEVER touches any Qt widget directly — it only emits signals.
The owning window is responsible for keeping a reference alive (so the
worker is not GC'd mid-run) and for calling :py:meth:`deleteLater` once
``finished`` fires.

Refs: [BL B-89, B-90] [REQ R16.1, R16.2, R16.3] design §3.2, §4.10
"""
from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from PySide6.QtCore import QThread, Signal

from src.core.notes import DatabaseStore
from src.core.sync_client import (  # noqa: F401  (re-exported for monkeypatch)
    AuthenticationError,
    SyncClient,
    SyncError,
)

logger = logging.getLogger(__name__)

Direction = Literal["push", "pull", "both"]


class SyncWorker(QThread):
    """Run one push/pull/both cycle in a background thread.

    Signals
    -------
    progress(str)
        Human-readable status update — UI may forward to the status bar.
    finished_ok(dict)
        Run finished without raising.  Payload::

            {
                "pushed": int,
                "skipped": int,
                "pulled": int,
                "conflicts": list[dict],
            }

        ``conflicts`` is a list of ``{note_id, local, remote}`` dicts
        (also emitted separately via :pyattr:`conflict_detected`).
    failed(str, str)
        Sync raised — payload is ``(error_class_name, message)``.
    conflict_detected(list)
        Emitted once with the full list of conflicts (if any).  The list
        is also embedded in the ``finished_ok`` summary so callers can
        choose whichever signal fits their slot wiring.
    """

    progress = Signal(str)
    finished_ok = Signal(dict)
    failed = Signal(str, str)
    conflict_detected = Signal(list)

    def __init__(
        self,
        client: SyncClient,
        token: str,
        account_id: str,
        store: DatabaseStore,
        direction: Direction = "both",
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._token = token
        self._account_id = account_id
        self._store = store
        if direction not in ("push", "pull", "both"):
            raise ValueError(
                f"direction must be 'push', 'pull', or 'both' — got {direction!r}"
            )
        self._direction = direction

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:  # noqa: D401 — Qt convention
        """Run the sync cycle in the worker thread."""
        summary: dict[str, Any] = {
            "pushed": 0,
            "skipped": 0,
            "pulled": 0,
            "conflicts": [],
        }
        try:
            if self._direction in ("push", "both"):
                self.progress.emit("Pushing local changes…")
                pushed, skipped = self._do_push()
                summary["pushed"] = pushed
                summary["skipped"] = skipped

            if self._direction in ("pull", "both"):
                self.progress.emit("Pulling remote changes…")
                pulled, conflicts = self._do_pull()
                summary["pulled"] = pulled
                summary["conflicts"] = conflicts
                if conflicts:
                    self.conflict_detected.emit(conflicts)

        except SyncError as exc:
            logger.warning("Sync failed (%s): %s", exc.__class__.__name__, exc)
            self.failed.emit(exc.__class__.__name__, str(exc))
            # finished_ok still emitted below so the UI can clear "Syncing…"
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("Unexpected sync failure")
            self.failed.emit("Exception", str(exc))

        self.finished_ok.emit(summary)

    # ------------------------------------------------------------------
    # Internal — push / pull cycles
    # ------------------------------------------------------------------

    def _do_push(self) -> tuple[int, int]:
        """Push pending local notes; return ``(pushed, skipped)``."""
        pending = list(self._store.list_pending_push(self._account_id))
        if not pending:
            return 0, 0

        # The client expects JSON-safe payloads; convert blob bytes if any.
        payloads: list[dict[str, Any]] = []
        for note in pending:
            blob = note.get("blob")
            if isinstance(blob, (bytes, bytearray)):
                # The server side accepts base64 in 5A.1 — leave conversion
                # to the existing CLI/server contract.  We pass bytes-as-is
                # here so the existing SyncClient marshalling rules apply.
                payloads.append({**note, "blob": bytes(blob)})
            else:
                payloads.append(dict(note))

        response = self._client.push(self._token, payloads)
        server_time = response.get("server_time") or ""
        accepted = response.get("accepted") or []
        skipped = response.get("skipped") or []

        for entry in accepted:
            note_id = entry.get("id") if isinstance(entry, dict) else entry
            stamp = (
                entry.get("synced_at", server_time)
                if isinstance(entry, dict)
                else server_time
            )
            if note_id:
                self._store.mark_synced(note_id, stamp or server_time)
        return len(accepted), len(skipped)

    def _do_pull(self) -> tuple[int, list[dict[str, Any]]]:
        """Pull remote notes; return ``(pulled, conflicts)``."""
        watermark = self._store.max_synced_at(self._account_id)
        response = self._client.pull(self._token, since=watermark)
        remote_notes = response.get("notes") or []

        pulled = 0
        conflicts: list[dict[str, Any]] = []

        for remote in remote_notes:
            note_id = remote.get("id")
            if not note_id:
                continue
            local = self._store.get(note_id)
            remote_modified = remote.get("modified_at") or ""
            remote_synced = remote.get("synced_at") or remote_modified

            if local is None:
                self._store.upsert_remote(
                    note_id=note_id,
                    account_id=self._account_id,
                    title=remote.get("title") or "",
                    content=remote.get("content"),
                    is_encrypted=bool(remote.get("is_encrypted")),
                    blob=remote.get("blob"),
                    created_at=remote.get("created_at") or remote_modified,
                    modified_at=remote_modified,
                    synced_at=remote_synced,
                )
                pulled += 1
                continue

            local_modified = getattr(local, "modified_at", "") or ""
            local_synced = getattr(local, "synced_at", "") or ""
            has_unsynced_local_edits = (
                not local_synced or local_synced < local_modified
            )
            remote_is_newer = remote_modified and remote_modified != local_modified

            if has_unsynced_local_edits and remote_is_newer:
                # True conflict — caller decides via MergeWindow.
                conflicts.append(
                    {
                        "note_id": note_id,
                        "local": _note_to_dict(local),
                        "remote": dict(remote),
                    }
                )
                continue

            # No local unsynced edits — accept remote if it is newer
            # (last-write-wins).  If neither side moved we skip.
            if remote_is_newer or local_synced < remote_modified:
                self._store.upsert_remote(
                    note_id=note_id,
                    account_id=self._account_id,
                    title=remote.get("title") or "",
                    content=remote.get("content"),
                    is_encrypted=bool(remote.get("is_encrypted")),
                    blob=remote.get("blob"),
                    created_at=remote.get("created_at") or remote_modified,
                    modified_at=remote_modified,
                    synced_at=remote_synced,
                )
                pulled += 1

        return pulled, conflicts


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _note_to_dict(note: Any) -> dict[str, Any]:
    """Best-effort conversion of a :class:`Note` (or dict-like) to a plain dict."""
    if isinstance(note, dict):
        return dict(note)
    keys = (
        "id",
        "title",
        "content",
        "blob",
        "encrypted",
        "is_encrypted",
        "created_at",
        "modified_at",
        "synced_at",
    )
    out: dict[str, Any] = {}
    for k in keys:
        if hasattr(note, k):
            out[k] = getattr(note, k)
    return out
