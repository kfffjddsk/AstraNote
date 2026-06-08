"""Container — self-describing binary envelope for AstraNotes payloads.

Wire format:
    [4B]  Magic       b'ASTR'
    [2B]  Version     uint16 LE  (currently 1)
    [2B]  Flags       uint16 LE  (FLAG_ENCRYPTED=0x01, FLAG_COMPRESSED=0x02)
    [4B]  MIME length uint32 LE
    [4B]  Payload sz  uint32 LE
    [4B]  CRC32       uint32 LE  (CRC32 of payload bytes)
    [ N]  MIME type   UTF-8 (N = mime_len bytes)
    [ M]  Payload     raw bytes  (M = payload_sz bytes)

Validation severity contract:
    ERROR   — checksum mismatch, size mismatch, truncated/corrupt magic.
              Caller must not store or display the content.
    WARNING — unknown version or unrecognised flags.
              Caller should show a warning; content is still readable.
    OK      — all checks pass.

Refs: design §3.1, §5.3
"""
from __future__ import annotations

import dataclasses
import enum
import struct
import zlib

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAGIC: bytes = b"ASTR"
VERSION: int = 1

FLAG_ENCRYPTED: int = 0x01
FLAG_COMPRESSED: int = 0x02

# Fixed header: magic(4s) version(H) flags(H) mime_len(I) payload_sz(I) crc32(I)
# = 4+2+2+4+4+4 = 20 bytes
_HEADER_STRUCT = struct.Struct("<4sHHIII")
HEADER_SIZE: int = _HEADER_STRUCT.size  # 20

_KNOWN_FLAGS: int = FLAG_ENCRYPTED | FLAG_COMPRESSED


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


class ValidationSeverity(enum.Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclasses.dataclass(frozen=True)
class ValidationResult:
    severity: ValidationSeverity
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.severity == ValidationSeverity.OK

    @property
    def is_error(self) -> bool:
        return self.severity == ValidationSeverity.ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == ValidationSeverity.WARNING


@dataclasses.dataclass(frozen=True)
class ContainerHeader:
    version: int
    flags: int
    mime_type: str
    payload_size: int
    checksum: int

    @property
    def encrypted(self) -> bool:
        return bool(self.flags & FLAG_ENCRYPTED)

    @property
    def compressed(self) -> bool:
        return bool(self.flags & FLAG_COMPRESSED)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ContainerError(ValueError):
    """Raised when a container cannot be framed or unframed (structural error)."""


class ContainerValidationError(Exception):
    """Raised when Container.validate() returns ERROR severity.

    Attributes:
        severity  ValidationSeverity (always ERROR when raised by the store)
        message   Human-readable detail suitable for QMessageBox.setDetailedText()
    """

    def __init__(self, severity: ValidationSeverity, message: str) -> None:
        super().__init__(message)
        self.severity = severity
        self.message = message


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


class Container:
    """Stateless helpers for framing, unframing, and validating containers."""

    # ------------------------------------------------------------------
    # frame
    # ------------------------------------------------------------------

    @staticmethod
    def frame(payload: bytes, mime_type: str, flags: int = 0) -> bytes:
        """Wrap *payload* in a Container envelope and return the raw bytes.

        Args:
            payload:   Arbitrary byte content produced by a packer.
            mime_type: IANA MIME type string (e.g. ``"text/plain"``).
            flags:     Bitfield; use ``FLAG_ENCRYPTED`` / ``FLAG_COMPRESSED``.
        """
        mime_bytes = mime_type.encode("utf-8")
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        header = _HEADER_STRUCT.pack(
            MAGIC, VERSION, flags, len(mime_bytes), len(payload), crc
        )
        return header + mime_bytes + payload

    # ------------------------------------------------------------------
    # unframe
    # ------------------------------------------------------------------

    @staticmethod
    def unframe(data: bytes) -> tuple[ContainerHeader, bytes]:
        """Parse *data* and return ``(ContainerHeader, payload)``.

        Raises :class:`ContainerError` if the data is structurally invalid
        (wrong magic, truncated, non-UTF-8 MIME).  Does *not* validate the
        CRC — call :meth:`validate` for that.
        """
        if len(data) < HEADER_SIZE:
            raise ContainerError(
                f"Data too short: need {HEADER_SIZE}B fixed header, got {len(data)}B."
            )

        magic, version, flags, mime_len, payload_sz, crc = _HEADER_STRUCT.unpack(
            data[:HEADER_SIZE]
        )

        if magic != MAGIC:
            raise ContainerError(
                f"Bad magic bytes: expected {MAGIC!r}, got {magic!r}. "
                "This is not an AstraNotes container."
            )

        expected_total = HEADER_SIZE + mime_len + payload_sz
        if len(data) < expected_total:
            raise ContainerError(
                f"Container truncated: header claims {expected_total}B total, "
                f"only {len(data)}B available."
            )

        offset = HEADER_SIZE
        try:
            mime_type = data[offset : offset + mime_len].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContainerError(
                f"MIME type field is not valid UTF-8: {exc}"
            ) from exc

        offset += mime_len
        payload = data[offset : offset + payload_sz]

        header = ContainerHeader(
            version=version,
            flags=flags,
            mime_type=mime_type,
            payload_size=payload_sz,
            checksum=crc,
        )
        return header, payload

    # ------------------------------------------------------------------
    # validate
    # ------------------------------------------------------------------

    @staticmethod
    def validate(header: ContainerHeader, payload: bytes) -> ValidationResult:
        """Check integrity and compatibility of a (header, payload) pair.

        Always call this after :meth:`unframe`.  For encrypted containers the
        payload passed here should be the *plaintext* payload (post-decrypt);
        the CRC was computed over the plaintext.

        Returns a :class:`ValidationResult` — never raises.
        """
        # CRC integrity — hard error
        actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
        if actual_crc != header.checksum:
            return ValidationResult(
                ValidationSeverity.ERROR,
                f"CRC32 checksum mismatch.\n"
                f"  Expected : {header.checksum:#010x}\n"
                f"  Computed : {actual_crc:#010x}\n"
                "The container payload is corrupt and cannot be trusted.",
            )

        # Payload size consistency — hard error
        if len(payload) != header.payload_size:
            return ValidationResult(
                ValidationSeverity.ERROR,
                f"Payload size mismatch.\n"
                f"  Header claims : {header.payload_size} bytes\n"
                f"  Actual        : {len(payload)} bytes",
            )

        # Unknown version — soft warning
        if header.version != VERSION:
            return ValidationResult(
                ValidationSeverity.WARNING,
                f"Container version {header.version} is not known "
                f"(current: {VERSION}). "
                "Content may not display correctly with this version of AstraNotes.",
            )

        # Unknown flags — soft warning
        unknown_flags = header.flags & ~_KNOWN_FLAGS
        if unknown_flags:
            return ValidationResult(
                ValidationSeverity.WARNING,
                f"Container has unrecognised flag bits: {unknown_flags:#06x}. "
                "A newer plugin may have written this container.",
            )

        return ValidationResult(ValidationSeverity.OK)
