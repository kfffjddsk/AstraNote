"""BlobCodec — length-prefixed binary blob encoder/decoder for AstraNotes.

Wire format (unencrypted blob):
    [4 B header_length (big-endian uint32)][JSON header bytes][raw payload bytes]

Wire format (encrypted blob):
    The framed blob above is fed into EncryptionEngine.encrypt(), producing:
    [16 B salt][12 B nonce][ciphertext + 16 B GCM tag]

Refs: [BL B-43] [REQ R2.9, R14.4] design §3.1, §5.3
"""
from __future__ import annotations

import json
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.security import EncryptionEngine


class BlobCodec:
    """Stateless codec for the AstraNotes sandbox binary blob format.

    All methods are static; no instance is needed.
    """

    _HEADER_STRUCT: str = ">I"   # big-endian unsigned 32-bit int
    _HEADER_PREFIX_LEN: int = 4  # bytes occupied by the length prefix
    _MAX_HEADER_LEN: int = 65_536  # 64 KiB — guards against oversized-header DoS

    # ------------------------------------------------------------------
    # Encode / Decode (plaintext framing)
    # ------------------------------------------------------------------

    @staticmethod
    def encode(header: dict, payload: bytes) -> bytes:
        """Encode *header* dict and *payload* bytes into the framed blob.

        Layout: ``[4B header_length][JSON header bytes][payload bytes]``
        [REQ R2.9] design §5.3
        """
        header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
        prefix = struct.pack(BlobCodec._HEADER_STRUCT, len(header_bytes))
        return prefix + header_bytes + payload

    @staticmethod
    def decode(blob: bytes) -> tuple[dict, bytes]:
        """Decode a framed blob into ``(header_dict, payload_bytes)``.

        Raises :class:`ValueError` if the blob is malformed or truncated.
        """
        prefix_len = BlobCodec._HEADER_PREFIX_LEN
        if len(blob) < prefix_len:
            raise ValueError(
                f"Blob too short: need at least {prefix_len} bytes, got {len(blob)}."
            )
        (header_len,) = struct.unpack(BlobCodec._HEADER_STRUCT, blob[:prefix_len])
        if header_len > BlobCodec._MAX_HEADER_LEN:
            raise ValueError(
                f"Header length {header_len} exceeds maximum allowed "
                f"{BlobCodec._MAX_HEADER_LEN} bytes — possible injection attempt."
            )
        end = prefix_len + header_len
        if len(blob) < end:
            raise ValueError(
                f"Blob truncated: header claims {header_len} bytes but only "
                f"{len(blob) - prefix_len} bytes remain."
            )
        header = json.loads(blob[prefix_len:end].decode("utf-8"))
        if not isinstance(header, dict):
            raise ValueError(
                f"Blob header must be a JSON object, got {type(header).__name__!r}."
            )
        payload = blob[end:]
        return header, payload

    # ------------------------------------------------------------------
    # Encrypt / Decrypt (delegates to EncryptionEngine)
    # ------------------------------------------------------------------

    @staticmethod
    def encrypt(blob: bytes, engine: "EncryptionEngine") -> bytes:
        """Encrypt the framed *blob* and return the ciphertext.

        The returned bytes can be stored directly in the ``encrypted_blob``
        database column.  [REQ R2.9] design §5.3
        """
        return engine.encrypt(blob)

    @staticmethod
    def decrypt(ciphertext: bytes, engine: "EncryptionEngine") -> bytes:
        """Decrypt *ciphertext* and return the raw framed blob.

        Raises :class:`~cryptography.exceptions.InvalidTag` on wrong passphrase
        or data corruption.  [REQ R2.8]
        """
        return engine.decrypt(ciphertext)
