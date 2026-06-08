"""EncryptionEngine and KeyManager for AstraNotes.

Algorithm : AES-256-GCM with PBKDF2-HMAC-SHA256 key derivation.
Wire format: [16 B salt][12 B nonce][ciphertext + 16 B GCM tag]

Refs: [BL B-17, B-34] [REQ R2.1, R2.11] design §3.1
"""
from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionEngine:
    """AES-256-GCM cipher with PBKDF2-HMAC-SHA256 key derivation.

    A new random salt and nonce are generated on every :meth:`encrypt` call
    and embedded in the returned ciphertext.  :meth:`decrypt` extracts them
    automatically, so the caller does not need to manage salt/nonce separately.

    Refs: [REQ R2.1, R2.9] design §3.1, §5.3
    """

    SALT_LEN: int = 16
    NONCE_LEN: int = 12
    KEY_LEN: int = 32
    DEFAULT_ITERATIONS: int = 100_000

    def __init__(self, passphrase: str, *, iterations: int = DEFAULT_ITERATIONS) -> None:
        self._passphrase = passphrase
        self._iterations = iterations

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt *plaintext* and return ``[16B salt][12B nonce][ciphertext+tag]``.

        A fresh salt and nonce are generated per call.  [REQ R2.9] design §5.3
        """
        salt = os.urandom(self.SALT_LEN)
        nonce = os.urandom(self.NONCE_LEN)
        key = self._derive_key(salt)
        ct_tag = AESGCM(key).encrypt(nonce, plaintext, None)
        return salt + nonce + ct_tag

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt *data* previously produced by :meth:`encrypt`.

        Raises :class:`~cryptography.exceptions.InvalidTag` if the passphrase
        is wrong or the ciphertext is corrupt.  [REQ R2.8]
        Raises :class:`ValueError` if *data* is shorter than the minimum
        expected layout ``[salt][nonce][tag]`` (44 bytes).
        """
        _GCM_TAG_LEN = 16
        min_len = self.SALT_LEN + self.NONCE_LEN + _GCM_TAG_LEN
        if len(data) < min_len:
            raise ValueError(
                f"Ciphertext too short: need at least {min_len} bytes, got {len(data)}."
            )
        salt = data[: self.SALT_LEN]
        nonce = data[self.SALT_LEN : self.SALT_LEN + self.NONCE_LEN]
        ct_tag = data[self.SALT_LEN + self.NONCE_LEN :]
        key = self._derive_key(salt)
        return AESGCM(key).decrypt(nonce, ct_tag, None)

    def derive_key(self, salt: bytes) -> bytes:
        """Derive a 32-byte key from the passphrase and *salt*.

        Exposed for callers that need the raw key (e.g. external re-encryption).
        """
        return self._derive_key(salt)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _derive_key(self, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=SHA256(),
            length=self.KEY_LEN,
            salt=salt,
            iterations=self._iterations,
        )
        return kdf.derive(self._passphrase.encode("utf-8"))


class KeyManager:
    """Validates the passphrase and vends :class:`EncryptionEngine` instances."""

    def __init__(self, passphrase: str, *, iterations: int = EncryptionEngine.DEFAULT_ITERATIONS) -> None:
        if not passphrase or not passphrase.strip():
            raise ValueError("Passphrase must not be empty or whitespace.")
        self._passphrase = passphrase
        self._iterations = iterations

    def get_engine(self) -> EncryptionEngine:
        """Return a new :class:`EncryptionEngine` bound to the stored passphrase."""
        return EncryptionEngine(self._passphrase, iterations=self._iterations)
