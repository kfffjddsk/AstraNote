"""Shared pytest fixtures for AstraNotes tests.

Available to all test files and BDD step definitions via normal pytest
fixture injection.

Isolation strategy:
  Both ``tmp_store`` and ``tmp_path`` save files under
  ``.test_db/<sanitised_test_name>/`` so every database created during a run
  survives on disk and can be opened with a GUI tool (e.g. DB Browser for
  SQLite, SQLite Viewer VS Code extension).  The directory is wiped *before*
  the test starts so stale data never leaks between runs.

  ``tmp_store`` — returns a ready ``DatabaseStore``; used by unit tests that
    need direct store access.
  ``tmp_path``  — returns the raw ``Path``; used by CLI tests and BDD steps
    that pass the directory to the CLI via ``--data-dir``.

Refs: planning/sprint-zero-plan.md §4 (Testing Infrastructure)
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import time
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


def _force_rmtree(path: Path, *, retries: int = 5, delay: float = 0.3) -> None:
    """Remove *path* tree robustly on Windows where open handles block deletion.

    On Windows, SQLite journal files and database handles held by a previous
    (possibly killed) pytest process cause ``shutil.rmtree`` to raise
    ``PermissionError``.  The ``onerror`` handler flips the read-only bit and
    retries; if the path is still locked we sleep briefly and try the whole
    rmtree again up to *retries* times.
    """
    def _handle_error(
        func: object, failing_path: str, excinfo: object
    ) -> None:
        # Make the file/dir writable and retry the removal call.
        try:
            os.chmod(failing_path, stat.S_IWRITE)
            func(failing_path)  # type: ignore[operator]
        except OSError:
            pass  # will be retried at the top level

    for attempt in range(retries):
        try:
            shutil.rmtree(path, onerror=_handle_error)
            return  # success
        except OSError:
            if attempt < retries - 1:
                time.sleep(delay)
    # Final attempt — let it propagate if still locked
    shutil.rmtree(path, onerror=_handle_error)


@pytest.fixture(scope="session", autouse=True)
def _wipe_test_db_before_session() -> None:
    """Remove the entire .test_db/ tree at the start of each test session.

    Individual test directories are also wiped inside ``_safe_test_dir``
    before each test, but this session-level fixture guarantees a fully
    clean slate on every ``pytest`` run — no stale databases from a
    previous session can survive.

    Uses ``_force_rmtree`` so that Windows file-handle locks left by a
    previously killed pytest process do not cause 500+ PermissionErrors.
    """
    test_db_root = Path(".test_db")
    if test_db_root.exists():
        _force_rmtree(test_db_root)
    test_db_root.mkdir(parents=True, exist_ok=True)


def _safe_test_dir(request: pytest.FixtureRequest) -> Path:
    """Return a per-test path under .test_db/, wiped clean before the test."""
    safe_name = re.sub(r"[^\w\-]", "_", request.node.name)[:80]
    test_dir = Path(".test_db") / safe_name
    if test_dir.exists():
        _force_rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture()
def tmp_path(request: pytest.FixtureRequest) -> Path:  # type: ignore[override]
    """Override of pytest's built-in ``tmp_path``.

    Saves to ``.test_db/<sanitised_test_name>/`` so any database created by a
    CLI test or BDD step survives the run for GUI inspection, instead of being
    deleted automatically by pytest.
    """
    return _safe_test_dir(request)


@pytest.fixture()
def tmp_store(request: pytest.FixtureRequest) -> DatabaseStore:
    """Fresh DatabaseStore in an isolated sub-directory under .test_db/.

    Each test gets its own ``notes.db`` named after the test node, so tests
    never share rows and any DB file can be opened in a GUI tool after the run.
    The directory is wiped *before* the test starts (stale data from a
    previous run does not leak in), but left on disk afterwards for inspection.
    """
    return DatabaseStore(_safe_test_dir(request))


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
