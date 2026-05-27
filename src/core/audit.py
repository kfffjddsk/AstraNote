"""Append-only JSON audit log for AstraNotes.

Log file: ``<data-dir>/audit.log`` — one JSON object per line.

Unwritable file → warning logged, operation not blocked.  [REQ R8.6]

Operations covered: encrypt, decrypt, passphrase_attempt, override, plugin_load,
login, logout, register, delete_account, mode_switch, migrate, export, reencrypt,
search.  [REQ R8.2]

Refs: [BL B-25, B-71] [REQ R8.1–R8.6] [US-6]
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """Append-only audit trail for security operations.

    Writes one JSON record per line to ``<data_dir>/audit.log``.
    Missing parent directory is created on first write.

    File unwritable → ``logging.warning`` only; calling operation continues.
    [REQ R8.6]

    Refs: [BL B-25, B-71] [REQ R8.1–R8.6]
    """

    def __init__(self, data_dir: Path) -> None:
        self._log_path = Path(data_dir) / "audit.log"

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def log(
        self,
        operation: str,
        *,
        note_id: Optional[str] = None,
        outcome: str = "success",
        detail: Optional[str] = None,
    ) -> None:
        """Append a single JSON record to the audit log.

        Fields: timestamp (ISO 8601 UTC), operation, note_id (nullable),
        outcome, detail (omitted when ``None``).  [REQ R8.1]

        File unwritable → warning emitted; calling operation not blocked.
        [REQ R8.6]
        """
        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "note_id": note_id,
            "outcome": outcome,
        }
        if detail is not None:
            entry["detail"] = detail

        line = json.dumps(entry, ensure_ascii=False) + "\n"
        try:
            with self._log_path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError as exc:
            logger.warning(
                "Audit log at %s is unwritable (%s) — continuing without logging.",
                self._log_path,
                exc,
            )

    # ------------------------------------------------------------------
    # Read / filter
    # ------------------------------------------------------------------

    def read(
        self,
        *,
        limit: Optional[int] = None,
        operation: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Return audit entries matching the given filters.

        Filters applied in order:
          ``operation`` — exact match on the ``operation`` field.
          ``since``     — only entries with ``timestamp >= since``.
          ``limit``     — return only the *last* N entries (after filtering).

        Missing / unreadable log file → returns ``[]``.  [REQ R8.5]
        """
        entries: list[dict] = []
        try:
            with self._log_path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if operation is not None and entry.get("operation") != operation:
                        continue

                    if since is not None:
                        try:
                            ts = datetime.fromisoformat(entry["timestamp"])
                            # Ensure both are tz-aware before comparing.
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            if ts < since:
                                continue
                        except (KeyError, ValueError):
                            continue

                    entries.append(entry)

        except FileNotFoundError:
            return []
        except OSError as exc:
            logger.warning("Could not read audit log: %s", exc)
            return []

        if limit is not None and limit > 0:
            entries = entries[-limit:]

        return entries
