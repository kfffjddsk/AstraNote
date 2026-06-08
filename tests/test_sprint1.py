"""Sprint 1 unit and CLI integration tests for AstraNotes.

Coverage:
  §1  DatabaseStore WAL mode + locked-DB retry  [BL B-66]
  §2  PluginBase / PluginRegistry contract  [BL B-83]
  §3  Plugin auto-discovery from filesystem — valid plugin, dunder skipped,
       broken import skipped, instantiation error skipped, multiple classes,
       spec_from_file_location returns None, no-subclasses file  [BL B-37]
  §4  CLI input-validation helpers  [BL B-52]
  §5  --data-dir validation — created if missing, must be directory, env var,
       defaults to ~/.astranotes, not writable  [BL B-36, B-39]
  §6  CLI ``add`` command — UUID, persistence, validation, empty/whitespace
       content, encrypted alias stored as placeholder  [BL B-19, B-23, B-32, B-52]
  §7  CLI ``get`` command
  §8  CLI ``list`` command — empty store, all notes with IDs, [enc] marker,
       mixed plain+encrypted, alias after update  [BL B-74]
  §9  CLI ``update`` command — plain title/content/both, no-fields error,
       null-byte rejection (title + content), encrypted title-only (no passphrase),
       encrypted content re-encryption (correct passphrase), encrypted wrong passphrase
  §10 CLI ``delete`` command — plain note, not-found, no-other-notes-affected,
       encrypted correct passphrase, encrypted wrong passphrase
  §11 CLI non-zero exit codes on every error path  [BL B-23]
  §12 CLI passphrase confirmation on encrypt  [BL B-32]
  §13 Alembic baseline migration  [BL B-65]

Refs: [BL B-19, B-23, B-32, B-36, B-37, B-39, B-40, B-52, B-65, B-66, B-83]
"""
from __future__ import annotations

import importlib.util
import os
import textwrap
import time
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from cryptography.exceptions import InvalidTag
from sqlalchemy.exc import OperationalError

from src.cli import (
    _check_content,
    _check_title,
    _validate_data_dir,
    cli,
)
from src.core.notes import DatabaseStore, Note, _execute_with_retry
from src.core.plugin_base import PluginBase, PluginRegistry, discover_plugins
from src.core.security import KeyManager
from tests.conftest import _TEST_ITERATIONS, make_encrypted_note

import click

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _runner(tmp_path: Path) -> tuple[CliRunner, list[str]]:
    """Return a CliRunner and the base --data-dir args pointing at *tmp_path*."""
    return CliRunner(), ["--data-dir", str(tmp_path)]


def _plain(title: str = "T", content: str = "C") -> Note:
    return Note.create(title, content)


# ===========================================================================
# §1  DatabaseStore WAL mode + retry  [BL B-66]
# ===========================================================================


@pytest.mark.unit
def test_wal_mode_enabled(tmp_path: Path) -> None:
    """A fresh DatabaseStore must use WAL journal mode.  [BL B-66]"""
    store = DatabaseStore(tmp_path)
    with store._engine.connect() as conn:
        result = conn.exec_driver_sql("PRAGMA journal_mode").fetchone()
    assert result is not None, "PRAGMA journal_mode returned no rows"
    assert result[0].upper() == "WAL"


@pytest.mark.unit
def test_execute_with_retry_succeeds_on_first_attempt() -> None:
    """_execute_with_retry returns the function value on immediate success."""
    assert _execute_with_retry(lambda: 42) == 42


@pytest.mark.unit
def test_execute_with_retry_raises_non_locked_error_immediately() -> None:
    """Non-'database is locked' OperationalError must not be retried."""
    calls = []

    def _fail():
        calls.append(1)
        raise OperationalError("stmt", {}, Exception("table not found"))

    with pytest.raises(OperationalError, match="table not found"):
        _execute_with_retry(_fail)

    assert len(calls) == 1  # no retries


@pytest.mark.unit
def test_execute_with_retry_retries_on_locked_then_succeeds() -> None:
    """When a 'database is locked' error is followed by success, the value is returned."""
    attempts = []

    def _flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise OperationalError("stmt", {}, Exception("database is locked"))
        return "ok"

    # Patch the sleep to keep the test fast.
    with patch("src.core.store.time.sleep"):
        result = _execute_with_retry(_flaky)

    assert result == "ok"
    assert len(attempts) == 3


@pytest.mark.unit
def test_execute_with_retry_gives_up_after_max_attempts() -> None:
    """After _RETRY_ATTEMPTS failures, the OperationalError propagates."""
    from src.core.notes import _RETRY_ATTEMPTS

    calls = []

    def _always_locked():
        calls.append(1)
        raise OperationalError("stmt", {}, Exception("database is locked"))

    with patch("src.core.store.time.sleep"), pytest.raises(OperationalError):
        _execute_with_retry(_always_locked)

    assert len(calls) == _RETRY_ATTEMPTS


# ===========================================================================
# §2  PluginBase / PluginRegistry  [BL B-83]
# ===========================================================================


class _GoodPlugin(PluginBase):
    name = "good"
    version = "1.0"
    calls: list[str] = []

    def register_hooks(self, registry: PluginRegistry) -> None:
        registry.register_hook("on_add", self._on_add)

    def _on_add(self, note: Note) -> None:
        self.__class__.calls.append(note.id)


class _CrashPlugin(PluginBase):
    name = "crash"
    version = "1.0"

    def register_hooks(self, registry: PluginRegistry) -> None:
        registry.register_hook("on_add", self._on_add)

    def _on_add(self, note: Note) -> None:
        raise RuntimeError("intentional crash in hook")


class _AbstractSubclass(PluginBase):
    """Concrete subclass that does nothing — just verifies ABC is satisfied."""
    name = "noop"

    def register_hooks(self, registry: PluginRegistry) -> None:
        pass


@pytest.mark.unit
def test_plugin_base_cannot_be_instantiated_directly() -> None:
    """PluginBase is abstract and must not be instantiatable."""
    with pytest.raises(TypeError):
        PluginBase()  # type: ignore[abstract]


@pytest.mark.unit
def test_plugin_registry_register_and_call_hook(tmp_store: DatabaseStore) -> None:
    """Registered hook is called with a copy of the note.  [BL B-83]"""
    registry = PluginRegistry()
    _GoodPlugin.calls.clear()
    registry.register_plugin(_GoodPlugin())
    note = _plain()
    tmp_store.add(note)
    registry.call_hook("on_add", note)
    assert note.id in _GoodPlugin.calls


@pytest.mark.unit
def test_plugin_registry_hook_receives_copy_not_original() -> None:
    """call_hook must pass a copy so plugins can't mutate core state.  [REQ R15.7]"""
    received: list[Note] = []
    registry = PluginRegistry()
    registry.register_hook("on_add", received.append)
    note = _plain("Original", "Data")
    registry.call_hook("on_add", note)
    assert len(received) == 1
    assert received[0] is not note          # copy, not the original


@pytest.mark.unit
def test_plugin_registry_crashing_hook_does_not_propagate() -> None:
    """A hook that raises must not crash the caller.  [REQ R4.7]"""
    registry = PluginRegistry()
    registry.register_plugin(_CrashPlugin())
    note = _plain()
    # Should not raise
    registry.call_hook("on_add", note)


@pytest.mark.unit
def test_plugin_registry_crashing_hook_does_not_stop_other_hooks() -> None:
    """After a crashing handler, remaining handlers still execute."""
    results: list[str] = []
    registry = PluginRegistry()
    registry.register_plugin(_CrashPlugin())
    registry.register_hook("on_add", lambda n: results.append("after"))
    note = _plain()
    registry.call_hook("on_add", note)
    assert "after" in results


@pytest.mark.unit
def test_plugin_registry_duplicate_registration_skipped() -> None:
    """Registering the same plugin type twice must be a no-op.  [BL B-83]"""
    registry = PluginRegistry()
    p1 = _AbstractSubclass()
    p2 = _AbstractSubclass()
    registry.register_plugin(p1)
    registry.register_plugin(p2)
    assert len(registry._plugins) == 1


@pytest.mark.unit
def test_plugin_registry_call_hook_with_no_handlers_is_noop() -> None:
    """call_hook on an unregistered hook name must be a no-op."""
    registry = PluginRegistry()
    note = _plain()
    registry.call_hook("nonexistent_hook", note)   # must not raise


@pytest.mark.unit
def test_plugin_get_commands_returns_empty_dict_by_default() -> None:
    """PluginBase.get_commands() default implementation returns {}."""
    plugin = _AbstractSubclass()
    assert plugin.get_commands() == {}


# ===========================================================================
# §3  Plugin auto-discovery  [BL B-37]
# ===========================================================================


@pytest.mark.unit
def test_discover_plugins_empty_dir(tmp_path: Path) -> None:
    """discover_plugins on an empty directory returns [] with no errors."""
    registry = PluginRegistry()
    result = discover_plugins(tmp_path, registry)
    assert result == []


@pytest.mark.unit
def test_discover_plugins_nonexistent_dir(tmp_path: Path) -> None:
    """discover_plugins on a non-existent path returns [] with no errors."""
    registry = PluginRegistry()
    result = discover_plugins(tmp_path / "missing", registry)
    assert result == []


@pytest.mark.unit
def test_discover_plugins_loads_valid_plugin(tmp_path: Path) -> None:
    """A .py file containing a PluginBase subclass is discovered and registered."""
    plugin_code = textwrap.dedent("""\
        from src.core.plugin_base import PluginBase, PluginRegistry

        class HelloPlugin(PluginBase):
            name = "hello"
            version = "0.1"

            def register_hooks(self, registry: PluginRegistry) -> None:
                pass
    """)
    (tmp_path / "hello_plugin.py").write_text(plugin_code)
    registry = PluginRegistry()
    result = discover_plugins(tmp_path, registry)
    assert len(result) == 1
    assert result[0].name == "hello"


@pytest.mark.unit
def test_discover_plugins_skips_dunder_files(tmp_path: Path) -> None:
    """Files starting with '_' (e.g. __init__.py) are skipped."""
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / "_private.py").write_text("")
    registry = PluginRegistry()
    result = discover_plugins(tmp_path, registry)
    assert result == []


@pytest.mark.unit
def test_discover_plugins_skips_file_when_spec_is_none(tmp_path: Path) -> None:
    """discover_plugins skips files for which spec_from_file_location returns None."""
    (tmp_path / "no_spec.py").write_text("pass")
    registry = PluginRegistry()
    with patch(
        "src.core.plugin_base.importlib.util.spec_from_file_location",
        return_value=None,
    ):
        result = discover_plugins(tmp_path, registry)
    assert result == []


@pytest.mark.unit
def test_discover_plugins_broken_import_skipped(tmp_path: Path) -> None:
    """A plugin file with a syntax / import error is skipped; others load."""
    (tmp_path / "broken.py").write_text("this is not valid python !!!")
    plugin_code = textwrap.dedent("""\
        from src.core.plugin_base import PluginBase, PluginRegistry

        class GoodPlugin(PluginBase):
            name = "good"
            def register_hooks(self, r): pass
    """)
    (tmp_path / "good.py").write_text(plugin_code)
    registry = PluginRegistry()
    result = discover_plugins(tmp_path, registry)
    # broken.py must not abort discovery; good.py must still load.
    assert len(result) == 1
    assert result[0].name == "good"


@pytest.mark.unit
def test_discover_plugins_instantiation_error_skipped(tmp_path: Path) -> None:
    """If instantiating a plugin class raises, that class is skipped."""
    plugin_code = textwrap.dedent("""\
        from src.core.plugin_base import PluginBase, PluginRegistry

        class BadInit(PluginBase):
            name = "bad"
            def __init__(self):
                raise RuntimeError("cannot init")
            def register_hooks(self, r): pass
    """)
    (tmp_path / "bad_init.py").write_text(plugin_code)
    registry = PluginRegistry()
    result = discover_plugins(tmp_path, registry)
    assert result == []


@pytest.mark.unit
def test_discover_plugins_multiple_classes_in_one_file(tmp_path: Path) -> None:
    """All PluginBase subclasses in a single file are registered."""
    plugin_code = textwrap.dedent("""\
        from src.core.plugin_base import PluginBase, PluginRegistry

        class Alpha(PluginBase):
            name = "alpha"
            def register_hooks(self, r): pass

        class Beta(PluginBase):
            name = "beta"
            def register_hooks(self, r): pass
    """)
    (tmp_path / "multi.py").write_text(plugin_code)
    registry = PluginRegistry()
    result = discover_plugins(tmp_path, registry)
    names = {p.name for p in result}
    assert names == {"alpha", "beta"}


@pytest.mark.unit
def test_discover_plugins_no_subclasses_in_file_returns_empty(tmp_path: Path) -> None:
    """A valid Python file with no PluginBase subclasses contributes nothing.  [BL B-37]"""
    (tmp_path / "no_plugins.py").write_text("x = 42\n")
    registry = PluginRegistry()
    result = discover_plugins(tmp_path, registry)
    assert result == []


# ===========================================================================
# §4  CLI input-validation helpers  [BL B-52]
# ===========================================================================


@pytest.mark.unit
def test_check_title_accepts_normal_text() -> None:
    _check_title("My note title")   # must not raise


@pytest.mark.unit
def test_check_title_rejects_null_byte() -> None:
    with pytest.raises(click.UsageError, match=r"U\+0000"):
        _check_title("bad\x00title")


@pytest.mark.unit
def test_check_title_rejects_other_control_chars() -> None:
    for cp in [0x01, 0x08, 0x0B, 0x0C, 0x0E, 0x1F, 0x7F]:
        with pytest.raises(click.UsageError):
            _check_title(f"bad{chr(cp)}title")


@pytest.mark.unit
def test_check_content_accepts_normal_text() -> None:
    _check_content("Line one\nLine two\tTabbed")   # must not raise


@pytest.mark.unit
def test_check_content_rejects_null_byte() -> None:
    with pytest.raises(click.UsageError, match=r"U\+0000"):
        _check_content("null\x00byte")


@pytest.mark.unit
def test_check_content_rejects_rare_control_chars() -> None:
    for cp in [0x01, 0x02, 0x0B, 0x0C, 0x0E, 0x1F, 0x7F]:
        with pytest.raises(click.UsageError):
            _check_content(f"bad{chr(cp)}content")


@pytest.mark.unit
def test_check_content_allows_newline_tab_cr() -> None:
    _check_content("line1\nline2\r\ntabbed\there")  # must not raise


# ===========================================================================
# §5  --data-dir validation  [BL B-36]
# ===========================================================================


@pytest.mark.cli
def test_data_dir_created_if_missing(tmp_path: Path) -> None:
    """--data-dir that doesn't exist yet should be created transparently."""
    new_dir = tmp_path / "new_subdir"
    runner, _ = _runner(tmp_path)
    result = runner.invoke(cli, ["--data-dir", str(new_dir), "list"])
    assert new_dir.is_dir()
    assert result.exit_code == 0


@pytest.mark.cli
def test_data_dir_must_be_directory(tmp_path: Path) -> None:
    """--data-dir pointing at a regular file should fail with exit code 2."""
    file_path = tmp_path / "not_a_dir"
    file_path.touch()
    runner, _ = _runner(tmp_path)
    result = runner.invoke(cli, ["--data-dir", str(file_path), "list"])
    assert result.exit_code == 2
    # On Windows, mkdir on an existing file raises FileExistsError ("cannot create");
    # on Linux/Mac it raises NotADirectoryError ("not a directory").
    assert "cannot create" in result.output.lower() or "not a directory" in result.output.lower()


@pytest.mark.cli
def test_data_dir_defaults_to_platform_data_dir(tmp_path: Path) -> None:
    """Omitting --data-dir resolves to platform_data_dir() (monkeypatched)."""
    fake_data_dir = tmp_path / "platform_data"
    runner = CliRunner()
    with patch("src.core.paths.platform_data_dir", return_value=fake_data_dir):
        result = runner.invoke(cli, ["list"])
    assert fake_data_dir.is_dir()
    assert result.exit_code == 0


@pytest.mark.cli
def test_data_dir_env_var_respected(tmp_path: Path) -> None:
    """ASTRANOTES_DATA_DIR env var is used when --data-dir is not supplied."""
    env_dir = tmp_path / "env_store"
    runner = CliRunner()
    result = runner.invoke(
        cli, ["list"], env={"ASTRANOTES_DATA_DIR": str(env_dir)}
    )
    assert env_dir.is_dir()
    assert result.exit_code == 0


@pytest.mark.cli
def test_cli_data_dir_not_writable_exits_nonzero(tmp_path: Path) -> None:
    """--data-dir with no write permission exits 2.  [BL B-39]"""
    probe_dir = tmp_path / "ro_dir"
    probe_dir.mkdir()
    runner = CliRunner()
    # Patch Path.touch to simulate a non-writable directory without relying on
    # OS-level chmod (which is unreliable on Windows).
    with patch("pathlib.Path.touch", side_effect=PermissionError("Access is denied")):
        result = runner.invoke(cli, ["--data-dir", str(probe_dir), "list"])
    assert result.exit_code == 2
    assert "not writable" in result.output.lower()


# ===========================================================================
# §6  CLI ``add`` command  [BL B-19, B-23, B-52]
# ===========================================================================


@pytest.mark.cli
def test_cli_add_plain_note_returns_uuid(tmp_path: Path) -> None:
    """``add`` on a plain note prints the new note ID and exits 0."""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["add", "--title", "Hello", "--content", "World"])
    assert result.exit_code == 0
    note_id = result.output.strip()
    # Should be a valid UUID
    import uuid
    uuid.UUID(note_id)


@pytest.mark.cli
def test_cli_add_note_persisted_in_store(tmp_path: Path) -> None:
    """After ``add``, the note is retrievable from the store."""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["add", "--title", "Persist", "--content", "Data"])
    note_id = result.output.strip()
    store = DatabaseStore(tmp_path)
    note = store.get(note_id)
    assert note is not None
    assert note.title == "Persist"
    assert note.content == "Data"


@pytest.mark.cli
def test_cli_add_missing_title_exits_nonzero(tmp_path: Path) -> None:
    """``add`` without --title should fail with exit code 2 (missing option)."""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["add", "--content", "No title"])
    assert result.exit_code == 2


@pytest.mark.cli
def test_cli_add_empty_title_exits_nonzero(tmp_path: Path) -> None:
    """``add`` with an empty title string should fail and exit 1."""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["add", "--title", "", "--content", "body"])
    assert result.exit_code == 1


@pytest.mark.cli
def test_cli_add_whitespace_title_exits_nonzero(tmp_path: Path) -> None:
    """``add`` with a whitespace-only title should fail and exit 1."""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["add", "--title", "   ", "--content", "body"])
    assert result.exit_code == 1


@pytest.mark.cli
def test_cli_add_null_byte_in_title_exits_nonzero(tmp_path: Path) -> None:
    """Null byte in title must be caught at CLI boundary.  [BL B-52]"""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["add", "--title", "bad\x00title", "--content", "ok"])
    assert result.exit_code == 1
    assert "U+0000" in result.output or "null" in result.output.lower()


@pytest.mark.cli
def test_cli_add_null_byte_in_content_exits_nonzero(tmp_path: Path) -> None:
    """Null byte in content must be caught at CLI boundary.  [BL B-52]"""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["add", "--title", "T", "--content", "bad\x00content"])
    assert result.exit_code == 1


@pytest.mark.cli
def test_cli_add_control_char_in_title_exits_nonzero(tmp_path: Path) -> None:
    """Control character (0x01) in title must be rejected.  [BL B-52]"""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["add", "--title", "bad\x01title", "--content", "ok"])
    assert result.exit_code == 1


@pytest.mark.cli
def test_cli_add_content_allows_newline(tmp_path: Path) -> None:
    """Newlines in content are permitted."""
    runner, args = _runner(tmp_path)
    result = runner.invoke(
        cli, args + ["add", "--title", "Multi", "--content", "line1\nline2"]
    )
    assert result.exit_code == 0


@pytest.mark.cli
def test_cli_add_empty_content_exits_nonzero(tmp_path: Path) -> None:
    """``add`` with no --content (empty stdin) exits 1.  [REQ R1.6]"""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["add", "--title", "T"], input="")
    assert result.exit_code == 1


@pytest.mark.cli
def test_cli_add_whitespace_content_exits_nonzero(tmp_path: Path) -> None:
    """``add`` with whitespace-only content exits 1.  [REQ R1.6]"""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["add", "--title", "T", "--content", "   "])
    assert result.exit_code == 1


@pytest.mark.cli
def test_cli_add_encrypt_stores_placeholder_alias(tmp_path: Path) -> None:
    """``add --encrypt`` stores '[Encrypted Note]' as the list alias, not the real title.  [REQ R2.7]"""
    runner, args = _runner(tmp_path)
    result = runner.invoke(
        cli, args + ["add", "--title", "My Real Title", "--content", "secret", "--encrypt"],
        input="StrongPass1\nStrongPass1\n",
    )
    assert result.exit_code == 0
    list_result = runner.invoke(cli, args + ["list"])
    assert "My Real Title" not in list_result.output
    assert "[Encrypted Note]" in list_result.output
    assert "[enc]" in list_result.output


# ===========================================================================
# §7  CLI ``get`` command
# ===========================================================================


@pytest.mark.cli
def test_cli_get_existing_plain_note(tmp_path: Path) -> None:
    """``get`` on a plain note prints title and content; exits 0."""
    runner, args = _runner(tmp_path)
    add_result = runner.invoke(
        cli, args + ["add", "--title", "GetMe", "--content", "content here"]
    )
    note_id = add_result.output.strip()
    result = runner.invoke(cli, args + ["get", note_id])
    assert result.exit_code == 0
    assert "GetMe" in result.output
    assert "content here" in result.output


@pytest.mark.cli
def test_cli_get_nonexistent_note_exits_nonzero(tmp_path: Path) -> None:
    """``get`` with an unknown ID must exit 1.  [BL B-23]"""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["get", "does-not-exist"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


@pytest.mark.cli
def test_cli_get_encrypted_note_without_decrypt_shows_placeholder(tmp_path: Path) -> None:
    """``get`` on an encrypted note without --decrypt shows '[encrypted]'."""
    store = DatabaseStore(tmp_path)
    note = make_encrypted_note("Sec", "secret", "SecretPass1")
    store.add(note)
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["get", note.id])
    assert result.exit_code == 0
    assert "[encrypted]" in result.output


@pytest.mark.cli
def test_cli_get_encrypted_note_with_correct_passphrase(tmp_path: Path) -> None:
    """``get --decrypt`` with the correct passphrase shows the plaintext."""
    runner, args = _runner(tmp_path)
    # Add the note through the CLI so encryption uses production iterations,
    # then decrypt through the CLI (same iterations) — no mismatch.
    add_result = runner.invoke(
        cli, args + ["add", "--title", "Sec", "--content", "my secret content", "--encrypt"],
        input="GoodPass1\nGoodPass1\n",
    )
    assert add_result.exit_code == 0, f"add failed: {add_result.output!r}"
    note_id = add_result.output.strip().splitlines()[-1].strip()
    result = runner.invoke(
        cli, args + ["get", "--decrypt", note_id],
        input="GoodPass1\n",
    )
    assert result.exit_code == 0, f"get failed: {result.output!r}"
    assert "my secret content" in result.output


@pytest.mark.cli
def test_cli_get_encrypted_note_wrong_passphrase_exits_nonzero(tmp_path: Path) -> None:
    """``get --decrypt`` with wrong passphrase exits 1 with an error.  [BL B-23]"""
    runner, args = _runner(tmp_path)
    # Add note via CLI so iterations match during decryption.
    add_r = runner.invoke(
        cli, args + ["add", "--title", "Sec", "--content", "secret", "--encrypt"],
        input="RightPass1\nRightPass1\n",
    )
    note_id = add_r.output.strip().splitlines()[-1].strip()
    result = runner.invoke(
        cli, args + ["get", "--decrypt", note_id],
        input="WrongPass1\n",
    )
    assert result.exit_code == 1
    assert "wrong passphrase" in result.output.lower()


# ===========================================================================
# §8  CLI ``list`` command
# ===========================================================================


@pytest.mark.cli
def test_cli_list_empty_store(tmp_path: Path) -> None:
    """``list`` on an empty store prints 'No notes found.' and exits 0."""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["list"])
    assert result.exit_code == 0
    assert "no notes found" in result.output.lower()


@pytest.mark.cli
def test_cli_list_shows_all_notes(tmp_path: Path) -> None:
    """``list`` shows all note IDs and titles."""
    runner, args = _runner(tmp_path)
    runner.invoke(cli, args + ["add", "--title", "First", "--content", "a"])
    runner.invoke(cli, args + ["add", "--title", "Second", "--content", "b"])
    result = runner.invoke(cli, args + ["list"])
    assert result.exit_code == 0
    assert "First" in result.output
    assert "Second" in result.output


@pytest.mark.cli
def test_cli_list_marks_encrypted_notes(tmp_path: Path) -> None:
    """``list`` appends '[enc]' suffix to encrypted notes."""
    store = DatabaseStore(tmp_path)
    note = make_encrypted_note("Sec", "secret", "SecretPass1")
    store.add(note)
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["list"])
    assert "[enc]" in result.output


@pytest.mark.cli
def test_cli_list_shows_note_id(tmp_path: Path) -> None:
    """``list`` output contains the note ID on the same line as the title."""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(cli, args + ["add", "--title", "IDCheck", "--content", "body"])
    note_id = add_r.output.strip()
    result = runner.invoke(cli, args + ["list"])
    assert result.exit_code == 0
    assert note_id in result.output


@pytest.mark.cli
def test_cli_list_mixed_plain_and_encrypted(tmp_path: Path) -> None:
    """``list`` shows plain notes without [enc] and encrypted notes with [enc]."""
    runner, args = _runner(tmp_path)
    runner.invoke(cli, args + ["add", "--title", "PlainNote", "--content", "visible"])
    runner.invoke(
        cli, args + ["add", "--title", "SecNote", "--content", "secret", "--encrypt"],
        input="StrongPass1\nStrongPass1\n",
    )
    result = runner.invoke(cli, args + ["list"])
    assert result.exit_code == 0
    assert "PlainNote" in result.output
    assert "[Encrypted Note]" in result.output
    assert "[enc]" in result.output
    for line in result.output.splitlines():
        if "PlainNote" in line:
            assert "[enc]" not in line


@pytest.mark.cli
def test_cli_list_shows_encrypted_alias_after_update(tmp_path: Path) -> None:
    """After updating an encrypted note's alias, ``list`` shows the new alias with [enc].  [REQ R2.4]"""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(
        cli, args + ["add", "--title", "HiddenTitle", "--content", "secret", "--encrypt"],
        input="StrongPass1\nStrongPass1\n",
    )
    note_id = add_r.output.strip().splitlines()[-1].strip()
    runner.invoke(cli, args + ["update", note_id, "--title", "PublicAlias"])
    result = runner.invoke(cli, args + ["list"])
    assert result.exit_code == 0
    assert "PublicAlias" in result.output
    assert "[enc]" in result.output


# ===========================================================================
# §9  CLI ``update`` command
# ===========================================================================


@pytest.mark.cli
def test_cli_update_title(tmp_path: Path) -> None:
    """``update --title`` changes the note title; exits 0."""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(cli, args + ["add", "--title", "Old", "--content", "body"])
    note_id = add_r.output.strip()
    result = runner.invoke(cli, args + ["update", note_id, "--title", "New"])
    assert result.exit_code == 0
    assert "Updated" in result.output
    store = DatabaseStore(tmp_path)
    fetched = store.get(note_id)
    assert fetched is not None, "note was not persisted after update"
    assert fetched.title == "New"


@pytest.mark.cli
def test_cli_update_content(tmp_path: Path) -> None:
    """``update --content`` changes the content; exits 0."""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(cli, args + ["add", "--title", "T", "--content", "old body"])
    note_id = add_r.output.strip()
    result = runner.invoke(cli, args + ["update", note_id, "--content", "new body"])
    assert result.exit_code == 0
    store = DatabaseStore(tmp_path)
    fetched = store.get(note_id)
    assert fetched is not None, "note was not persisted after update"
    assert fetched.content == "new body"


@pytest.mark.cli
def test_cli_update_title_and_content_together(tmp_path: Path) -> None:
    """``update`` with both --title and --content changes both fields atomically."""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(cli, args + ["add", "--title", "OldTitle", "--content", "old body"])
    note_id = add_r.output.strip()
    result = runner.invoke(
        cli, args + ["update", note_id, "--title", "NewTitle", "--content", "new body"]
    )
    assert result.exit_code == 0
    store = DatabaseStore(tmp_path)
    fetched = store.get(note_id)
    assert fetched is not None
    assert fetched.title == "NewTitle"
    assert fetched.content == "new body"


@pytest.mark.cli
def test_cli_update_nonexistent_note_exits_nonzero(tmp_path: Path) -> None:
    """``update`` with an unknown ID exits 1.  [BL B-23]"""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["update", "ghost-id", "--title", "x"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


@pytest.mark.cli
def test_cli_update_no_fields_exits_nonzero(tmp_path: Path) -> None:
    """``update`` without --title or --content exits 1.  [BL B-23]"""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(cli, args + ["add", "--title", "T", "--content", "C"])
    note_id = add_r.output.strip()
    result = runner.invoke(cli, args + ["update", note_id])
    assert result.exit_code == 1


@pytest.mark.cli
def test_cli_update_null_byte_in_title_exits_nonzero(tmp_path: Path) -> None:
    """Null byte in updated title is rejected at CLI boundary.  [BL B-52]"""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(cli, args + ["add", "--title", "T", "--content", "C"])
    note_id = add_r.output.strip()
    result = runner.invoke(cli, args + ["update", note_id, "--title", "bad\x00title"])
    assert result.exit_code == 1


@pytest.mark.cli
def test_cli_update_null_byte_in_content_exits_nonzero(tmp_path: Path) -> None:
    """Null byte in updated content is rejected at CLI boundary.  [BL B-52]"""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(cli, args + ["add", "--title", "T", "--content", "C"])
    note_id = add_r.output.strip()
    result = runner.invoke(cli, args + ["update", note_id, "--content", "bad\x00content"])
    assert result.exit_code == 1


@pytest.mark.cli
def test_cli_update_encrypted_note_title_only_no_passphrase(tmp_path: Path) -> None:
    """Updating the title alias of an encrypted note requires no passphrase.  [REQ R2.4]"""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(
        cli, args + ["add", "--title", "SecNote", "--content", "secret", "--encrypt"],
        input="StrongPass1\nStrongPass1\n",
    )
    assert add_r.exit_code == 0
    note_id = add_r.output.strip().splitlines()[-1].strip()
    result = runner.invoke(cli, args + ["update", note_id, "--title", "NewAlias"])
    assert result.exit_code == 0
    assert "Updated" in result.output
    store = DatabaseStore(tmp_path)
    fetched = store.get(note_id)
    assert fetched is not None
    assert fetched.title == "NewAlias"


@pytest.mark.cli
def test_cli_update_encrypted_note_content_with_correct_passphrase(tmp_path: Path) -> None:
    """Updating content of encrypted note re-encrypts with correct passphrase.  [REQ R2.4]"""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(
        cli, args + ["add", "--title", "Enc", "--content", "old secret", "--encrypt"],
        input="StrongPass1\nStrongPass1\n",
    )
    assert add_r.exit_code == 0
    note_id = add_r.output.strip().splitlines()[-1].strip()
    upd_r = runner.invoke(
        cli, args + ["update", note_id, "--content", "new secret"],
        input="StrongPass1\n",
    )
    assert upd_r.exit_code == 0, f"update failed: {upd_r.output!r}"
    # Verify the new content is readable with the same passphrase.
    get_r = runner.invoke(
        cli, args + ["get", "--decrypt", note_id],
        input="StrongPass1\n",
    )
    assert get_r.exit_code == 0
    assert "new secret" in get_r.output


@pytest.mark.cli
def test_cli_update_encrypted_note_content_wrong_passphrase_exits_nonzero(tmp_path: Path) -> None:
    """Wrong passphrase when updating encrypted note content exits 1.  [REQ R2.4]"""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(
        cli, args + ["add", "--title", "Enc", "--content", "secret", "--encrypt"],
        input="StrongPass1\nStrongPass1\n",
    )
    assert add_r.exit_code == 0
    note_id = add_r.output.strip().splitlines()[-1].strip()
    result = runner.invoke(
        cli, args + ["update", note_id, "--content", "new secret"],
        input="WrongPass1\n",
    )
    assert result.exit_code == 1
    assert "wrong passphrase" in result.output.lower()


# ===========================================================================
# §10  CLI ``delete`` command
# ===========================================================================


@pytest.mark.cli
def test_cli_delete_existing_note(tmp_path: Path) -> None:
    """``delete`` removes the note; exits 0 with confirmation message."""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(cli, args + ["add", "--title", "ToDelete", "--content", "bye"])
    note_id = add_r.output.strip()
    result = runner.invoke(cli, args + ["delete", note_id])
    assert result.exit_code == 0
    assert "Deleted" in result.output
    store = DatabaseStore(tmp_path)
    assert store.get(note_id) is None


@pytest.mark.cli
def test_cli_delete_nonexistent_note_exits_nonzero(tmp_path: Path) -> None:
    """``delete`` with an unknown ID exits 1.  [BL B-23]"""
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + ["delete", "no-such-id"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


@pytest.mark.cli
def test_cli_delete_does_not_affect_other_notes(tmp_path: Path) -> None:
    """Deleting one note must not remove any other note.  [REQ R2.12]"""
    runner, args = _runner(tmp_path)
    r1 = runner.invoke(cli, args + ["add", "--title", "Keep", "--content", "k"])
    r2 = runner.invoke(cli, args + ["add", "--title", "Remove", "--content", "r"])
    keep_id = r1.output.strip()
    remove_id = r2.output.strip()
    runner.invoke(cli, args + ["delete", remove_id])
    store = DatabaseStore(tmp_path)
    assert store.get(keep_id) is not None
    assert store.get(remove_id) is None


@pytest.mark.cli
def test_cli_delete_encrypted_note_with_correct_passphrase(tmp_path: Path) -> None:
    """``delete`` on encrypted note succeeds with correct passphrase.  [REQ R2.5]"""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(
        cli, args + ["add", "--title", "SecToDel", "--content", "secret", "--encrypt"],
        input="StrongPass1\nStrongPass1\n",
    )
    assert add_r.exit_code == 0
    note_id = add_r.output.strip().splitlines()[-1].strip()
    result = runner.invoke(cli, args + ["delete", note_id], input="StrongPass1\n")
    assert result.exit_code == 0
    assert "Deleted" in result.output
    store = DatabaseStore(tmp_path)
    assert store.get(note_id) is None


@pytest.mark.cli
def test_cli_delete_encrypted_note_wrong_passphrase_exits_nonzero(tmp_path: Path) -> None:
    """Wrong passphrase on encrypted note delete exits 1; note is preserved.  [REQ R2.5]"""
    runner, args = _runner(tmp_path)
    add_r = runner.invoke(
        cli, args + ["add", "--title", "SecToDel", "--content", "secret", "--encrypt"],
        input="StrongPass1\nStrongPass1\n",
    )
    assert add_r.exit_code == 0
    note_id = add_r.output.strip().splitlines()[-1].strip()
    result = runner.invoke(cli, args + ["delete", note_id], input="WrongPass1\n")
    assert result.exit_code == 1
    assert "wrong passphrase" in result.output.lower()
    # Note must still exist — wrong passphrase must not delete it.
    store = DatabaseStore(tmp_path)
    assert store.get(note_id) is not None


# ===========================================================================
# §11  Non-zero exit codes — comprehensive sweep  [BL B-23]
# ===========================================================================


@pytest.mark.cli
@pytest.mark.parametrize("bad_subcommand,extra_args,stdin,expect_code", [
    # get: note not found
    ("get",    ["does-not-exist"],                      None, 1),
    # update: note not found
    ("update", ["does-not-exist", "--title", "x"],      None, 1),
    # update: no fields
    ("update", ["some-id"],                             None, 1),
    # delete: note not found
    ("delete", ["does-not-exist"],                      None, 1),
])
def test_nonzero_exit_codes(
    tmp_path: Path,
    bad_subcommand: str,
    extra_args: list[str],
    stdin: str | None,
    expect_code: int,
) -> None:
    runner, args = _runner(tmp_path)
    result = runner.invoke(cli, args + [bad_subcommand] + extra_args, input=stdin)
    assert result.exit_code == expect_code, (
        f"Expected exit {expect_code}, got {result.exit_code}: {result.output!r}"
    )


# ===========================================================================
# §12  Passphrase confirmation on encrypt  [BL B-32]
# ===========================================================================


@pytest.mark.cli
def test_cli_add_encrypt_passphrase_confirmed(tmp_path: Path) -> None:
    """``add --encrypt`` with matching confirmation stores an encrypted note."""
    runner, args = _runner(tmp_path)
    # CliRunner feeds the passphrase twice (prompt + confirmation).
    result = runner.invoke(
        cli, args + ["add", "--title", "Secret", "--content", "hidden", "--encrypt"],
        input="StrongPass1\nStrongPass1\n",
    )
    assert result.exit_code == 0, f"output: {result.output!r}"
    # output contains prompt lines + UUID last line
    note_id = result.output.strip().splitlines()[-1].strip()
    store = DatabaseStore(tmp_path)
    note = store.get(note_id)
    assert note is not None
    assert note.encrypted is True
    assert note.blob is not None


@pytest.mark.cli
def test_cli_add_encrypt_passphrase_mismatch_aborts(tmp_path: Path) -> None:
    """``add --encrypt`` with mismatched confirmation must fail.  [BL B-32]"""
    runner, args = _runner(tmp_path)
    result = runner.invoke(
        cli, args + ["add", "--title", "Secret", "--content", "hidden", "--encrypt"],
        input="StrongPass1\nDifferentPass2\n",
    )
    # Click's confirmation_prompt aborts with a non-zero exit on mismatch.
    assert result.exit_code != 0


@pytest.mark.cli
def test_cli_add_encrypt_short_passphrase_accepted(tmp_path: Path) -> None:
    """Passphrases of any length are accepted (no minimum enforced)."""
    runner, args = _runner(tmp_path)
    result = runner.invoke(
        cli, args + ["add", "--title", "S", "--content", "C", "--encrypt"],
        input="short\nshort\n",
    )
    assert result.exit_code == 0


# ===========================================================================
# §13  Alembic baseline migration  [BL B-65]
# ===========================================================================


@pytest.mark.unit
def test_alembic_ini_exists() -> None:
    """alembic.ini must exist at the project root.  [BL B-65]"""
    root = Path(__file__).parent.parent
    assert (root / "alembic.ini").exists()


@pytest.mark.unit
def test_alembic_versions_dir_has_migration() -> None:
    """At least one migration file must exist in alembic/versions/.  [BL B-65]"""
    root = Path(__file__).parent.parent
    versions = list((root / "alembic" / "versions").glob("*.py"))
    assert len(versions) >= 1, "No migration scripts found in alembic/versions/"


@pytest.mark.unit
def test_alembic_baseline_migration_applies_to_fresh_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running ``alembic upgrade head`` on a fresh DB creates the notes table."""
    from alembic.config import Config
    from alembic import command as alembic_cmd
    import sqlalchemy

    # Prevent a stale ASTRANOTES_DB_URL in the shell env from overriding the URL.
    monkeypatch.delenv("ASTRANOTES_DB_URL", raising=False)

    db_path = tmp_path / "migration_test.db"
    # Use forward slashes in the URL — backslashes confuse SQLite on Windows.
    url = "sqlite:///" + db_path.as_posix()
    root = Path(__file__).parent.parent

    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    alembic_cmd.upgrade(cfg, "head")

    engine = sqlalchemy.create_engine(url)
    with engine.connect() as conn:
        result = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notes'"
        ).fetchone()
    engine.dispose()
    assert result is not None, "notes table not created by migration"


@pytest.mark.unit
def test_alembic_current_head_matches_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After upgrade, alembic_version table records the expected head revision."""
    from alembic.config import Config
    from alembic import command as alembic_cmd
    import sqlalchemy

    # Prevent a stale ASTRANOTES_DB_URL in the shell env from overriding the URL.
    monkeypatch.delenv("ASTRANOTES_DB_URL", raising=False)

    db_path = tmp_path / "head_check.db"
    url = "sqlite:///" + db_path.as_posix()
    root = Path(__file__).parent.parent

    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    alembic_cmd.upgrade(cfg, "head")

    # Read the stored revision directly from the alembic_version table.
    engine = sqlalchemy.create_engine(url)
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    engine.dispose()

    assert row is not None, "alembic_version table is empty after upgrade"
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(cfg)
    expected_head = script.get_current_head()
    assert row[0] == expected_head, f"DB at {row[0]!r}, head is {expected_head!r}"
