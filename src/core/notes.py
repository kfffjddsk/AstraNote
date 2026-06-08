"""Backward-compat re-exports.

The Note model lives in :mod:`src.core.note`.
The DatabaseStore lives in :mod:`src.core.store`.
The Container lives in :mod:`src.core.container`.

All existing imports of the form ``from src.core.notes import X`` continue
to work unchanged.
"""
from src.core.container import (  # noqa: F401
    MAGIC,
    VERSION,
    FLAG_ENCRYPTED,
    FLAG_COMPRESSED,
    HEADER_SIZE,
    Container,
    ContainerError,
    ContainerHeader,
    ContainerValidationError,
    ValidationResult,
    ValidationSeverity,
)
from src.core.note import (  # noqa: F401
    Attachment,
    DiskFullError,
    Note,
    _utcnow,
)
from src.core.store import (  # noqa: F401
    DatabaseStore,
    _Base,
    _NoteRow,
    _RETRY_ATTEMPTS,
    _RETRY_BASE_DELAY,
    _enable_wal,
    _execute_with_retry,
    _row_to_note,
)
