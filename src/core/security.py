"""
AstraNote Core Security Module

Provides encryption and key management for notes.
This module is immutable and cannot be overridden by plugins.
"""

import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag
import base64


class EncryptionEngine:
    """
    Handles AES-256-GCM encryption/decryption with PBKDF2 key derivation.
    """

    def __init__(self, passphrase: str):
        self.passphrase = passphrase
        self.salt = os.urandom(16)  # Generate new salt per session

    def derive_key(self) -> bytes:
        """Derive a 256-bit key from passphrase using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(self.passphrase.encode())

    def encrypt(self, plaintext: bytes, associated_data: bytes = b"") -> str:
        """Encrypt plaintext and return base64-encoded ciphertext."""
        key = self.derive_key()
        iv = os.urandom(12)  # GCM nonce
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encryptor.authenticate_additional_data(associated_data)
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        tag = encryptor.tag
        # Store: salt + iv + tag + ciphertext
        encrypted_data = self.salt + iv + tag + ciphertext
        return base64.b64encode(encrypted_data).decode()

    def decrypt(self, ciphertext_b64: str, associated_data: bytes = b"") -> bytes:
        """Decrypt base64-encoded ciphertext."""
        encrypted_data = base64.b64decode(ciphertext_b64)
        salt = encrypted_data[:16]
        iv = encrypted_data[16:28]
        tag = encrypted_data[28:44]
        ciphertext = encrypted_data[44:]

        # Re-derive key with stored salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(self.passphrase.encode())

        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        decryptor.authenticate_additional_data(associated_data)
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        return plaintext


class KeyManager:
    """
    Manages user passphrases securely. Never exposes raw keys to plugins.
    """

    def __init__(self, passphrase: str):
        self.passphrase = passphrase  # In production, use secure storage

    def get_engine(self) -> EncryptionEngine:
        """Return an EncryptionEngine instance for operations."""
        return EncryptionEngine(self.passphrase)