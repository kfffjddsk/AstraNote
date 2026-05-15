"""Shared pytest fixtures for AstraNotes tests.

Available to all test files and BDD step definitions via normal pytest
fixture injection.

Refs: planning/sprint-zero-plan.md §4 (Testing Infrastructure)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.blob_codec import BlobCodec
from src.core.notes import DatabaseStore, Note
from src.core.security import EncryptionEngine, KeyManager

# ---------------------------------------------------------------------------
# Speed constant — lower iteration count for tests keeps the suite fast
# without changing the production default.
# ---------------------------------------------------------------------------
_TEST_ITERATIONS = 1_000


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_store(tmp_path: Path) -> DatabaseStore:
    """Fresh DatabaseStore backed by a temp directory."""
    return DatabaseStore(tmp_path)


@pytest.fixture()
def passphrase() -> str:
    return "SecretPass1"


@pytest.fixture()
def alt_passphrase() -> str:
    return "WrongPass999"


@pytest.fixture()
def key_manager(passphrase: str) -> KeyManager:
    return KeyManager(passphrase, iterations=_TEST_ITERATIONS)


@pytest.fixture()
def enc_engine(key_manager: KeyManager) -> EncryptionEngine:
    return key_manager.get_engine()


# ---------------------------------------------------------------------------
# BDD shared context
# ---------------------------------------------------------------------------


@pytest.fixture()
def context(tmp_path: Path) -> dict:
    """Mutable dict shared across all steps of a single BDD scenario."""
    return {"tmp_path": tmp_path}


# ---------------------------------------------------------------------------
# Helper used by both unit and BDD tests
# ---------------------------------------------------------------------------


def make_encrypted_note(
    title: str,
    content: str,
    passphrase: str,
    *,
    alias: str = "[Encrypted Note]",
    iterations: int = _TEST_ITERATIONS,
) -> Note:
    """Build an encrypted Note with a BlobCodec-encoded blob.

    *alias* is the plaintext title stored in the DB for fast listing.
    """
    engine = KeyManager(passphrase, iterations=iterations).get_engine()
    header = {"title": title, "format": "text/plain"}
    payload = content.encode("utf-8")
    raw_blob = BlobCodec.encode(header, payload)
    encrypted_blob = BlobCodec.encrypt(raw_blob, engine)
    return Note.create(alias, content, encrypted=True, blob=encrypted_blob)
