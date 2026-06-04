"""Application-level PID lock file for session exclusivity.

Prevents two AstraNotes GUI instances from running against the same data
directory simultaneously.  [BL B-101] [REQ R9.7] [D-13]

Lock file location: ``<data-dir>/.app.lock``
Lock file format (JSON)::

    {"pid": <int>, "launched_at": "<ISO-8601 UTC>"}

Behaviour:
- ``acquire_lock()``: write lock if none exists or PID is stale (process dead).
  Raises :exc:`SessionConflictError` if an alive process holds the lock.
- ``release_lock()``: delete the lock file.  Safe to call even if the file
  has already been removed.
"""
from __future__ import annotations

import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path


class SessionConflictError(Exception):
    """Raised when an alive process already holds the application lock."""


def _is_process_alive(pid: int) -> bool:
    """Return True if *pid* corresponds to a running process."""
    if pid <= 0:
        return False
    try:
        if platform.system() == "Windows":
            import ctypes

            PROCESS_QUERY_INFORMATION = 0x0400
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION, False, pid
            )
            if handle == 0:
                return False
            exit_code = ctypes.c_ulong(0)
            ctypes.windll.kernel32.GetExitCodeProcess(
                handle, ctypes.byref(exit_code)
            )
            ctypes.windll.kernel32.CloseHandle(handle)
            STILL_ACTIVE = 259
            return exit_code.value == STILL_ACTIVE
        else:
            os.kill(pid, 0)
            return True
    except (OSError, PermissionError):
        return False


class AppLockManager:
    """Manages a PID lock file at ``<data_dir>/.app.lock``.

    Usage::

        lock = AppLockManager(data_dir)
        lock.acquire_lock()   # raises SessionConflictError if another app is alive
        try:
            ...
        finally:
            lock.release_lock()
    """

    LOCK_FILENAME = ".app.lock"

    def __init__(self, data_dir: Path) -> None:
        self._lock_path: Path = Path(data_dir) / self.LOCK_FILENAME

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    def acquire_lock(self) -> None:
        """Acquire the application lock.

        - No lock file → create it with current PID.
        - Lock file with stale (dead) PID → overwrite silently.
        - Lock file with alive PID → raise :exc:`SessionConflictError`.

        [BL B-101] [REQ R9.7]
        """
        if self._lock_path.exists():
            try:
                with self._lock_path.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                existing_pid = int(data.get("pid", -1))
            except (json.JSONDecodeError, OSError, ValueError, KeyError):
                existing_pid = -1  # Corrupted lock → treat as stale

            if _is_process_alive(existing_pid):
                raise SessionConflictError(
                    f"AstraNotes is already running (PID {existing_pid}).  "
                    "Close the existing instance before launching a new one."
                )
            # Stale lock — fall through to overwrite

        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_data = {
            "pid": os.getpid(),
            "launched_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        with self._lock_path.open("w", encoding="utf-8") as fh:
            json.dump(lock_data, fh)

    def release_lock(self) -> None:
        """Release the lock by deleting the lock file.

        Safe to call when the file does not exist (e.g. already cleaned up).
        """
        try:
            self._lock_path.unlink()
        except FileNotFoundError:
            pass  # Already gone — that is fine
