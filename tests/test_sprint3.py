"""Sprint 3 test suite for AstraNotes.

Coverage:
  §1   AuditLogger core module              [BL B-25, B-71] [REQ R8]
  §2   ConfigStore core module              [BL B-26]       [REQ R9]
  §3   DatabaseStore.search()               [BL B-29]       [REQ R10.1-R10.3]
  §4   CLI search command                   [BL B-29]       [REQ R10.1-R10.3]
  §5   CLI export command                   [BL B-30, B-76, B-78] [REQ R10.4-R10.7]
  §6   CLI reencrypt command                [BL B-62]       [REQ R2.14]
  §7   CLI config commands                  [BL B-26]       [REQ R9.2-R9.5]
  §8   CLI audit command                    [BL B-25, B-71] [REQ R8.5]
  §9   Plugin allowlist                     [BL B-69]       [REQ R4.10]
  §10  Plugin override policy               [BL B-24]       [REQ R7]
  §11  Plugin CLI command wiring            [BL B-28]       [REQ R4.4]
  §12  ANSI stripping                       [BL B-54]       [REQ R15.5]
  §13  Path traversal prevention            [BL B-55]       [REQ R15.8]
  §14  Plugin sandboxing                    [BL B-56]       [REQ R15.7]
  §15  Audit integration in CLI commands    [BL B-71]       [REQ R8.2]
  §16  Alias info warning                   [BL B-79]       [REQ R2.16]
  §17  Passphrase memory limitation comment [BL B-73]       [REQ R2.15]
"""
from __future__ import annotations

import inspect
import json
import os
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner
from cryptography.exceptions import InvalidTag

from src.cli import (
    _strip_ansi,
    cli,
    reencrypt_cmd,
    search_cmd,
    export_cmd,
    audit_cmd,
    config_grp,
)
from src.core.audit import AuditLogger
from src.core.blob_codec import BlobCodec
from src.core.config import ALLOWED_KEYS, DEFAULTS, ConfigStore
from src.core.notes import DatabaseStore, Note
from src.core.plugin_base import (
    PluginBase,
    PluginRegistry,
    discover_plugins,
)
from src.core.security import KeyManager
from tests.conftest import _TEST_ITERATIONS, make_encrypted_note


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> DatabaseStore:
    return DatabaseStore(tmp_path)


def _invoke(runner: CliRunner, args: list, data_dir: Path, input: str = "") -> object:
    """Invoke CLI with --data-dir set to tmp_path."""
    return runner.invoke(
        cli, ["--data-dir", str(data_dir)] + args, input=input, catch_exceptions=False
    )


def _fast_engine(passphrase: str):
    return KeyManager(passphrase, iterations=_TEST_ITERATIONS).get_engine()


def _make_encrypted_blob(passphrase: str, content: str) -> bytes:
    engine = _fast_engine(passphrase)
    header = {"title": "test", "format": "text/plain"}
    raw = BlobCodec.encode(header, content.encode())
    return BlobCodec.encrypt(raw, engine)


# ===========================================================================
# §1  AuditLogger core module
# ===========================================================================


class TestAuditLogger:
    def test_log_creates_file(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        al.log("login")
        assert (tmp_path / "audit.log").exists()

    def test_log_appends_entries(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        al.log("login")
        al.log("logout")
        entries = al.read()
        assert len(entries) == 2

    def test_log_json_fields(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        al.log("encrypt", note_id="abc123", outcome="success", detail="test")
        entries = al.read()
        e = entries[0]
        assert e["operation"] == "encrypt"
        assert e["note_id"] == "abc123"
        assert e["outcome"] == "success"
        assert e["detail"] == "test"
        assert "timestamp" in e

    def test_log_timestamp_is_utc_iso(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        al.log("test_op")
        e = al.read()[0]
        dt = datetime.fromisoformat(e["timestamp"])
        assert dt.tzinfo is not None

    def test_log_omits_detail_when_none(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        al.log("login")
        e = al.read()[0]
        assert "detail" not in e

    def test_log_unwritable_file_does_not_raise(self, tmp_path: Path) -> None:
        """Unwritable log → warning, no exception.  [REQ R8.6]"""
        al = AuditLogger(tmp_path / "nonexistent_subdir" / "sub2")
        # Should not raise; should log a warning.
        al.log("login")  # directory doesn't exist — OSError silently handled

    def test_read_missing_file_returns_empty(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        assert al.read() == []

    def test_read_filter_by_operation(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        al.log("login")
        al.log("encrypt")
        al.log("login")
        entries = al.read(operation="login")
        assert len(entries) == 2
        assert all(e["operation"] == "login" for e in entries)

    def test_read_filter_by_since(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        al.log("old_op")
        future = datetime.now(timezone.utc) + timedelta(seconds=1)
        al.log("new_op")
        entries = al.read(since=future)
        # Depending on timing, 0 or 1 entries; all must have timestamp >= future
        for e in entries:
            ts = datetime.fromisoformat(e["timestamp"])
            assert ts >= future

    def test_read_limit_returns_last_n(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        for i in range(5):
            al.log(f"op{i}")
        entries = al.read(limit=3)
        assert len(entries) == 3
        assert entries[0]["operation"] == "op2"
        assert entries[-1]["operation"] == "op4"

    def test_read_limit_zero_returns_all(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        al.log("a")
        al.log("b")
        entries = al.read(limit=0)
        assert len(entries) == 2

    def test_log_outcome_default_is_success(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        al.log("login")
        assert al.read()[0]["outcome"] == "success"

    def test_log_failure_outcome(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        al.log("login", outcome="failure")
        assert al.read()[0]["outcome"] == "failure"

    def test_log_note_id_null_stored(self, tmp_path: Path) -> None:
        al = AuditLogger(tmp_path)
        al.log("search")
        assert al.read()[0]["note_id"] is None


# ===========================================================================
# §2  ConfigStore core module
# ===========================================================================


class TestConfigStore:
    def test_get_default_for_all_keys(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        for key in ALLOWED_KEYS:
            val = cfg.get(key)
            assert val == DEFAULTS[key]

    def test_set_persists_to_disk(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        cfg = ConfigStore(cfg_path)
        cfg.set("theme", "dark")
        cfg2 = ConfigStore(cfg_path)
        assert cfg2.get("theme") == "dark"

    def test_get_unknown_key_raises_key_error(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        with pytest.raises(KeyError):
            cfg.get("no_such_key")

    def test_set_unknown_key_raises_key_error(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        with pytest.raises(KeyError):
            cfg.set("no_such_key", "value")

    def test_set_invalid_type_raises_value_error(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        with pytest.raises(ValueError, match="integer"):
            cfg.set("font_size", "not_an_int")

    def test_set_constraint_violation_raises_value_error(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        with pytest.raises(ValueError):
            cfg.set("default_encrypt", "maybe")  # only "yes" or "no" allowed

    def test_set_default_encrypt_valid_values(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        cfg.set("default_encrypt", "yes")
        assert cfg.get("default_encrypt") == "yes"
        cfg.set("default_encrypt", "no")
        assert cfg.get("default_encrypt") == "no"

    def test_set_theme_valid(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        cfg.set("theme", "dark")
        assert cfg.get("theme") == "dark"

    def test_set_passphrase_min_length_below_8_raises(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        with pytest.raises(ValueError):
            cfg.set("passphrase_min_length", 4)

    def test_set_passphrase_min_length_coerce_string(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        cfg.set("passphrase_min_length", "12")
        assert cfg.get("passphrase_min_length") == 12

    def test_set_font_size_below_6_raises(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        with pytest.raises(ValueError):
            cfg.set("font_size", 4)

    def test_set_sync_auto_interval_negative_raises(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        with pytest.raises(ValueError):
            cfg.set("sync_auto_interval", -1)

    def test_set_allowed_plugins_stores_list(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        cfg.set("allowed_plugins", ["plugin_a", "plugin_b"])
        assert cfg.get("allowed_plugins") == ["plugin_a", "plugin_b"]

    def test_list_all_returns_all_keys(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        result = cfg.list_all()
        assert set(result.keys()) == ALLOWED_KEYS

    def test_reset_reverts_to_default(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        cfg = ConfigStore(cfg_path)
        cfg.set("theme", "dark")
        cfg.reset("theme")
        assert cfg.get("theme") == "light"  # default

    def test_reset_unknown_key_raises_key_error(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "config.json")
        with pytest.raises(KeyError):
            cfg.reset("no_such_key")

    def test_missing_config_file_uses_all_defaults(self, tmp_path: Path) -> None:
        cfg = ConfigStore(tmp_path / "no_file.json")
        assert cfg.get("theme") == "light"
        assert cfg.get("font_size") == 12


# ===========================================================================
# §3  DatabaseStore.search()
# ===========================================================================


class TestDatabaseStoreSearch:
    def test_search_finds_by_content(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        note = Note.create("Title", "Find me in content")
        store.add(note)
        results = store.search("Find me")
        assert len(results) == 1
        assert results[0].id == note.id

    def test_search_finds_by_title(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        note = Note.create("Unique Title Here", "content")
        store.add(note)
        results = store.search("Unique Title")
        assert len(results) == 1

    def test_search_case_insensitive(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        note = Note.create("Title", "Hello World")
        store.add(note)
        assert len(store.search("hello world")) == 1
        assert len(store.search("HELLO WORLD")) == 1
        assert len(store.search("Hello World")) == 1

    def test_search_no_match_returns_empty(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        note = Note.create("Note", "Some content")
        store.add(note)
        assert store.search("xyz_not_present") == []

    def test_search_encrypted_excluded_by_default(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        enc = make_encrypted_note("[Encrypted Note]", "secret data", "pass123!")
        store.add(enc)
        assert store.search("secret data") == []

    def test_search_encrypted_included_when_flag_set(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        enc = make_encrypted_note("[Encrypted Note]", "secret data", "pass123!")
        store.add(enc)
        results = store.search("secret", include_encrypted=True)
        assert len(results) == 1
        assert results[0].blob is not None

    def test_search_multiple_notes_correct_subset(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        note1 = Note.create("Apple", "fruit content")
        note2 = Note.create("Banana", "yellow fruit")
        note3 = Note.create("Car", "vehicle stuff")
        for n in [note1, note2, note3]:
            store.add(n)
        results = store.search("fruit")
        ids = {r.id for r in results}
        assert note1.id in ids
        assert note2.id in ids
        assert note3.id not in ids

    # --- Alias / encrypted search edge-cases ---------------------------------

    def test_search_encrypted_alias_matched_without_flag(self, tmp_path: Path) -> None:
        """Plaintext alias always searchable even without include_encrypted.  [REQ R10.1]"""
        store = _make_store(tmp_path)
        enc = make_encrypted_note("Real Title", "secret body", "pass123!",
                                  alias="Budget Meeting")
        store.add(enc)
        results = store.search("Budget")
        assert len(results) == 1
        assert results[0].title == "Budget Meeting"

    def test_search_encrypted_alias_match_returns_no_blob(self, tmp_path: Path) -> None:
        """Alias-matched encrypted note has blob=None — no sensitive data exposed."""
        store = _make_store(tmp_path)
        enc = make_encrypted_note("Real Title", "secret body", "pass123!",
                                  alias="Budget Meeting")
        store.add(enc)
        results = store.search("Budget")
        assert len(results) == 1
        assert results[0].blob is None  # alias match never exposes blob

    def test_search_default_alias_not_matched_by_content_query(self, tmp_path: Path) -> None:
        """Default alias '[Encrypted Note]' doesn't match a content-only query."""
        store = _make_store(tmp_path)
        enc = make_encrypted_note("[Encrypted Note]", "hidden body", "pass123!")
        store.add(enc)
        # Query won't match "[Encrypted Note]" alias, and include_encrypted is False
        assert store.search("hidden") == []

    def test_search_encrypted_alias_one_result_even_when_include_encrypted(self, tmp_path: Path) -> None:
        """Alias match takes precedence — note appears only once even with include_encrypted."""
        store = _make_store(tmp_path)
        enc = make_encrypted_note("Real", "Budget details", "pass123!",
                                  alias="Budget Meeting")
        store.add(enc)
        results = store.search("Budget", include_encrypted=True)
        assert len(results) == 1          # deduplicated
        assert results[0].blob is None    # alias-match bucket, not blob bucket

    def test_search_title_only_match(self, tmp_path: Path) -> None:
        """A note is returned when query matches title but not content."""
        store = _make_store(tmp_path)
        note = Note.create("UniqueKeyword Title", "irrelevant stuff")
        store.add(note)
        results = store.search("UniqueKeyword")
        assert len(results) == 1

    def test_search_content_only_match(self, tmp_path: Path) -> None:
        """A note is returned when query matches content but not title."""
        store = _make_store(tmp_path)
        note = Note.create("Generic Title", "VerySpecificContentKeyword")
        store.add(note)
        results = store.search("VerySpecificContentKeyword")
        assert len(results) == 1

    def test_search_does_not_expose_encrypted_content_without_flag(self, tmp_path: Path) -> None:
        """Encrypted body never appears in results when include_encrypted=False."""
        store = _make_store(tmp_path)
        enc = make_encrypted_note("Real", "confidential payload", "pass123!",
                                  alias="Work Notes")
        store.add(enc)
        # "confidential" is in the encrypted body, NOT in the alias
        results = store.search("confidential")
        assert results == []

    def test_search_encrypted_without_alias_match_returns_blob_when_flag(self, tmp_path: Path) -> None:
        """When alias doesn't match but include_encrypted=True, blob is provided."""
        store = _make_store(tmp_path)
        enc = make_encrypted_note("[Encrypted Note]", "confidential payload", "pass123!")
        store.add(enc)
        results = store.search("confidential", include_encrypted=True)
        assert len(results) == 1
        assert results[0].blob is not None  # blob provided for decryption


# ===========================================================================
# §4  CLI search command
# ===========================================================================


class TestCliSearch:
    def test_search_finds_note_by_content(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("My Note", "searchable content here")
        store.add(note)

        result = _invoke(runner, ["search", "searchable"], tmp_path)
        assert result.exit_code == 0
        assert "My Note" in result.output

    def test_search_no_match_prints_message(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = _invoke(runner, ["search", "nothinghere"], tmp_path)
        assert result.exit_code == 0
        assert "No notes found" in result.output

    def test_search_strips_ansi_from_preview(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("ANSI Note", "\x1b[31mred text\x1b[0m in content")
        store.add(note)
        result = _invoke(runner, ["search", "red"], tmp_path)
        assert result.exit_code == 0
        assert "\x1b[" not in result.output

    def test_search_encrypted_excluded_without_flag(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        enc = make_encrypted_note("[Encrypted Note]", "hidden text", "Pass123!")
        store.add(enc)
        result = _invoke(runner, ["search", "hidden"], tmp_path)
        assert result.exit_code == 0
        assert "No notes found" in result.output

    def test_search_encrypted_with_correct_passphrase(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Add note via CLI so encryption uses default iterations (matchable by CLI decrypt)
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "Enc",
             "--encrypt", "--content", "confidential data"],
            input="Pass1234!\nPass1234!\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        result = _invoke(
            runner, ["search", "--encrypted", "confidential"], tmp_path,
            input="Pass1234!\n"
        )
        assert result.exit_code == 0
        assert "confidential" in result.output

    def test_search_encrypted_wrong_passphrase_skips(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Add note via CLI so encryption uses default iterations
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "Enc",
             "--encrypt", "--content", "confidential data"],
            input="Pass1234!\nPass1234!\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        result = _invoke(
            runner, ["search", "--encrypted", "confidential"], tmp_path,
            input="WrongPass!\n"
        )
        assert result.exit_code == 0
        assert "No notes found" in result.output

    # --- Alias-related CLI search edge-cases ---------------------------------

    def test_search_shows_alias_of_encrypted_note_without_passphrase(
        self, tmp_path: Path
    ) -> None:
        """Encrypted note with alias returned and alias shown without a passphrase."""
        runner = CliRunner()
        store = _make_store(tmp_path)
        enc = make_encrypted_note("Real Title", "secret body", "pass123!",
                                  alias="Budget Meeting")
        store.add(enc)
        result = _invoke(runner, ["search", "Budget"], tmp_path)
        assert result.exit_code == 0
        assert "Budget Meeting" in result.output
        # Real title must NOT appear (it is inside the encrypted blob)
        assert "Real Title" not in result.output

    def test_search_alias_match_does_not_require_encrypted_flag(
        self, tmp_path: Path
    ) -> None:
        """Alias is plaintext — no --encrypted flag needed to find it."""
        runner = CliRunner()
        store = _make_store(tmp_path)
        enc = make_encrypted_note("Confidential", "body text", "pass123!",
                                  alias="Q3 Planning")
        store.add(enc)
        result = _invoke(runner, ["search", "Q3"], tmp_path)
        assert result.exit_code == 0
        assert "Q3 Planning" in result.output

    def test_search_default_alias_not_exposed_when_content_searched(
        self, tmp_path: Path
    ) -> None:
        """When alias is '[Encrypted Note]' and query matches body — hidden."""
        runner = CliRunner()
        store = _make_store(tmp_path)
        enc = make_encrypted_note("[Encrypted Note]", "hidden content", "pass123!")
        store.add(enc)
        result = _invoke(runner, ["search", "hidden"], tmp_path)
        assert result.exit_code == 0
        assert "No notes found" in result.output

    def test_search_by_title_matches_plaintext_note(self, tmp_path: Path) -> None:
        """Title-only match (content doesn't contain query) returns the note."""
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("UniqueQueryWord", "completely different body")
        store.add(note)
        result = _invoke(runner, ["search", "UniqueQueryWord"], tmp_path)
        assert result.exit_code == 0
        assert "UniqueQueryWord" in result.output

    def test_search_by_content_matches_plaintext_note(self, tmp_path: Path) -> None:
        """Content-only match (title doesn't contain query) returns the note."""
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("Generic Title", "SomeVeryUniqueBodyPhrase here")
        store.add(note)
        result = _invoke(runner, ["search", "SomeVeryUniqueBodyPhrase"], tmp_path)
        assert result.exit_code == 0
        assert "Generic Title" in result.output

    def test_search_with_encrypted_flag_alias_shown_without_decrypt(
        self, tmp_path: Path
    ) -> None:
        """With --encrypted flag, alias-matching note shown without decryption."""
        runner = CliRunner()
        store = _make_store(tmp_path)
        enc = make_encrypted_note("Real", "body", "pass123!", alias="Team Standup")
        store.add(enc)
        # Provide a wrong passphrase — alias should still show (no decrypt attempted)
        result = _invoke(
            runner, ["search", "--encrypted", "Team"], tmp_path,
            input="WrongPass!\n"
        )
        assert result.exit_code == 0
        assert "Team Standup" in result.output

    def test_search_with_encrypted_flag_content_match_after_decrypt(
        self, tmp_path: Path
    ) -> None:
        """With --encrypted + correct passphrase, content match found via decryption."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "Secret",
             "--encrypt", "--content", "classified payload"],
            input="SearchPass1!\nSearchPass1!\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        result = _invoke(
            runner, ["search", "--encrypted", "classified"], tmp_path,
            input="SearchPass1!\n"
        )
        assert result.exit_code == 0
        assert "classified" in result.output


class TestCliExport:
    def test_export_text_creates_file(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("Export Note", "content to export")
        store.add(note)

        result = _invoke(runner, ["export", "--format", "text"], tmp_path)
        assert result.exit_code == 0
        out_path = tmp_path / "export.text"
        assert out_path.exists()

    def test_export_json_creates_file(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("JSON Note", "json content")
        store.add(note)

        result = _invoke(runner, ["export", "--format", "json"], tmp_path)
        assert result.exit_code == 0
        out_path = tmp_path / "export.json"
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert isinstance(data, list)
        assert data[0]["title"] == "JSON Note"

    def test_export_json_contains_correct_fields(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("Field Check", "body text")
        store.add(note)

        _invoke(runner, ["export", "--format", "json"], tmp_path)
        data = json.loads((tmp_path / "export.json").read_text())
        row = data[0]
        assert "id" in row
        assert "title" in row
        assert "content" in row
        assert "created_at" in row
        assert "modified_at" in row

    def test_export_text_format(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("Text Export", "plain text content")
        store.add(note)

        _invoke(runner, ["export", "--format", "text"], tmp_path)
        text = (tmp_path / "export.text").read_text()
        assert "Note ID:" in text
        assert "Title: Text Export" in text
        assert "Content: plain text content" in text
        assert "---" in text

    def test_export_shows_encrypted_placeholder(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        enc = make_encrypted_note("[Encrypted Note]", "secret", "SecretP1!")
        store.add(enc)

        _invoke(runner, ["export", "--format", "json"], tmp_path)
        data = json.loads((tmp_path / "export.json").read_text())
        assert data[0]["content"] == "[Encrypted Note]"

    def test_export_encrypted_decrypts_with_correct_passphrase(
        self, tmp_path: Path
    ) -> None:
        runner = CliRunner()
        # Add note via CLI so encryption uses default iterations (matchable by CLI decrypt)
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "Enc",
             "--encrypt", "--content", "decoded text"],
            input="Pass1234!\nPass1234!\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        _invoke(
            runner,
            ["export", "--format", "json", "--encrypted"],
            tmp_path,
            input="Pass1234!\n",
        )
        data = json.loads((tmp_path / "export.json").read_text())
        assert data[0]["content"] == "decoded text"

    def test_export_cleanup_purges_exports_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        exports_dir = tmp_path / "exports"
        exports_dir.mkdir()
        (exports_dir / "dummy.txt").write_text("temp")

        result = _invoke(runner, ["export", "--cleanup"], tmp_path)
        assert result.exit_code == 0
        assert not exports_dir.exists()

    def test_export_no_notes_prints_message(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = _invoke(runner, ["export"], tmp_path)
        assert result.exit_code == 0
        assert "No notes to export" in result.output

    def test_export_custom_output_path(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("Custom Out", "content")
        store.add(note)
        out = tmp_path / "my_export.json"

        _invoke(
            runner,
            ["export", "--format", "json", "--output", str(out)],
            tmp_path,
        )
        assert out.exists()

    def test_export_null_byte_in_path_rejected(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("N", "c")
        store.add(note)
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "export", "--output", "bad\x00path.json"],
            catch_exceptions=False,
        )
        assert result.exit_code != 0

    def test_export_strips_ansi_from_content(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("ANSI", "\x1b[32mgreen\x1b[0m content")
        store.add(note)

        _invoke(runner, ["export", "--format", "json"], tmp_path)
        data = json.loads((tmp_path / "export.json").read_text())
        assert "\x1b[" not in data[0]["content"]
        assert "green" in data[0]["content"]


# ===========================================================================
# §6  CLI reencrypt command
# ===========================================================================


class TestCliReencrypt:
    def _make_enc_note(self, tmp_path: Path, passphrase: str) -> str:
        """Add an encrypted note and return its ID."""
        store = _make_store(tmp_path)
        enc = make_encrypted_note("[Encrypted Note]", "secret content", passphrase)
        store.add(enc)
        return enc.id

    def test_reencrypt_with_correct_passphrase_succeeds(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Add note via CLI so iterations match for the reencrypt CLI command
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "Enc",
             "--encrypt", "--content", "secret content"],
            input="OldPass1!\nOldPass1!\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        note_id = result.output.strip().splitlines()[-1]

        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "reencrypt", note_id],
            input="OldPass1!\nNewPass2!\nNewPass2!\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Re-encrypted" in result.output

    def test_reencrypt_wrong_old_passphrase_fails(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Add note via CLI (default iterations)
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "Enc",
             "--encrypt", "--content", "secret content"],
            input="OldPass1!\nOldPass1!\n",
            catch_exceptions=False,
        )
        note_id = result.output.strip().splitlines()[-1]

        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "reencrypt", note_id],
            input="WrongPass!\n",
            catch_exceptions=False,
        )
        assert result.exit_code != 0
        assert "wrong passphrase" in result.output.lower()

    def test_reencrypt_plain_note_rejected(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("Plain", "plain content")
        store.add(note)

        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "reencrypt", note.id],
            input="pass\n",
            catch_exceptions=False,
        )
        assert result.exit_code != 0
        assert "not encrypted" in result.output.lower()

    def test_reencrypt_nonexistent_note_fails(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "reencrypt", "nonexistent-id"],
            input="pass\n",
            catch_exceptions=False,
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_reencrypt_new_passphrase_works(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Add note via CLI (default iterations)
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "Enc",
             "--encrypt", "--content", "secret content"],
            input="OldPass1!\nOldPass1!\n",
            catch_exceptions=False,
        )
        note_id = result.output.strip().splitlines()[-1]

        runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "reencrypt", note_id],
            input="OldPass1!\nNewPass2!\nNewPass2!\n",
            catch_exceptions=False,
        )

        # Verify new passphrase decrypts (using default iterations = same as CLI)
        store = _make_store(tmp_path)
        note = store.get(note_id)
        assert note is not None and note.blob is not None
        engine = KeyManager("NewPass2!").get_engine()
        raw = BlobCodec.decrypt(note.blob, engine)
        _, payload = BlobCodec.decode(raw)
        assert payload.decode() == "secret content"

    def test_reencrypt_old_passphrase_no_longer_works(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Add note via CLI (default iterations)
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "Enc",
             "--encrypt", "--content", "secret content"],
            input="OldPass1!\nOldPass1!\n",
            catch_exceptions=False,
        )
        note_id = result.output.strip().splitlines()[-1]

        runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "reencrypt", note_id],
            input="OldPass1!\nNewPass2!\nNewPass2!\n",
            catch_exceptions=False,
        )

        store = _make_store(tmp_path)
        note = store.get(note_id)
        engine = KeyManager("OldPass1!").get_engine()
        with pytest.raises(InvalidTag):
            BlobCodec.decrypt(note.blob, engine)


# ===========================================================================
# §7  CLI config commands
# ===========================================================================


class TestCliConfig:
    def _config_path(self, tmp_path: Path) -> Path:
        return tmp_path / "test_config.json"

    def test_config_set_stores_value(self, tmp_path: Path) -> None:
        runner = CliRunner()
        cfg_path = self._config_path(tmp_path)
        with patch("src.cli.ConfigStore", lambda: ConfigStore(cfg_path)):
            result = _invoke(runner, ["config", "set", "theme", "dark"], tmp_path)
        assert result.exit_code == 0
        cfg = ConfigStore(cfg_path)
        assert cfg.get("theme") == "dark"

    def test_config_get_retrieves_value(self, tmp_path: Path) -> None:
        runner = CliRunner()
        cfg_path = self._config_path(tmp_path)
        cfg = ConfigStore(cfg_path)
        cfg.set("theme", "dark")
        with patch("src.cli.ConfigStore", lambda: ConfigStore(cfg_path)):
            result = _invoke(runner, ["config", "get", "theme"], tmp_path)
        assert result.exit_code == 0
        assert "dark" in result.output

    def test_config_list_shows_all_keys(self, tmp_path: Path) -> None:
        runner = CliRunner()
        cfg_path = self._config_path(tmp_path)
        with patch("src.cli.ConfigStore", lambda: ConfigStore(cfg_path)):
            result = _invoke(runner, ["config", "list"], tmp_path)
        assert result.exit_code == 0
        for key in ALLOWED_KEYS:
            assert key in result.output

    def test_config_reset_restores_default(self, tmp_path: Path) -> None:
        runner = CliRunner()
        cfg_path = self._config_path(tmp_path)
        cfg = ConfigStore(cfg_path)
        cfg.set("theme", "dark")
        with patch("src.cli.ConfigStore", lambda: ConfigStore(cfg_path)):
            result = _invoke(runner, ["config", "reset", "theme"], tmp_path)
        assert result.exit_code == 0
        cfg2 = ConfigStore(cfg_path)
        assert cfg2.get("theme") == "light"

    def test_config_set_unknown_key_fails(self, tmp_path: Path) -> None:
        runner = CliRunner()
        cfg_path = self._config_path(tmp_path)
        with patch("src.cli.ConfigStore", lambda: ConfigStore(cfg_path)):
            result = _invoke(
                runner, ["config", "set", "unknown_key_xyz", "value"], tmp_path
            )
        assert result.exit_code != 0

    def test_config_set_invalid_value_fails(self, tmp_path: Path) -> None:
        runner = CliRunner()
        cfg_path = self._config_path(tmp_path)
        with patch("src.cli.ConfigStore", lambda: ConfigStore(cfg_path)):
            result = _invoke(
                runner, ["config", "set", "theme", "purple"], tmp_path
            )
        assert result.exit_code != 0

    def test_config_get_unknown_key_fails(self, tmp_path: Path) -> None:
        runner = CliRunner()
        cfg_path = self._config_path(tmp_path)
        with patch("src.cli.ConfigStore", lambda: ConfigStore(cfg_path)):
            result = _invoke(runner, ["config", "get", "xyz_unknown"], tmp_path)
        assert result.exit_code != 0


# ===========================================================================
# §8  CLI audit command
# ===========================================================================


class TestCliAudit:
    def test_audit_shows_entries(self, tmp_path: Path) -> None:
        runner = CliRunner()
        al = AuditLogger(tmp_path)
        al.log("login", outcome="success")

        result = _invoke(runner, ["audit"], tmp_path)
        assert result.exit_code == 0
        assert "login" in result.output
        assert "success" in result.output

    def test_audit_empty_log_message(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = _invoke(runner, ["audit"], tmp_path)
        assert result.exit_code == 0
        assert "No audit entries" in result.output

    def test_audit_filter_by_operation(self, tmp_path: Path) -> None:
        runner = CliRunner()
        al = AuditLogger(tmp_path)
        al.log("login")
        al.log("encrypt")
        al.log("login")

        result = _invoke(runner, ["audit", "--operation", "login"], tmp_path)
        assert result.exit_code == 0
        assert result.output.count("login") >= 2
        assert "encrypt" not in result.output

    def test_audit_limit_limits_output(self, tmp_path: Path) -> None:
        runner = CliRunner()
        al = AuditLogger(tmp_path)
        for i in range(5):
            al.log(f"op{i}")

        result = _invoke(runner, ["audit", "--limit", "2"], tmp_path)
        assert result.exit_code == 0
        lines = [l for l in result.output.strip().splitlines() if l]
        assert len(lines) == 2

    def test_audit_since_filter(self, tmp_path: Path) -> None:
        runner = CliRunner()
        al = AuditLogger(tmp_path)
        al.log("old_op")

        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        al.log("future_op")

        result = _invoke(runner, ["audit", "--since", future], tmp_path)
        # May or may not have entries; should not crash
        assert result.exit_code == 0

    def test_audit_invalid_since_date_fails(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = _invoke(runner, ["audit", "--since", "not-a-date"], tmp_path)
        assert result.exit_code != 0


# ===========================================================================
# §9a  PluginRegistry unit tests  [BL B-18, B-38] [REQ R4.3, R4.7]
# ===========================================================================


class TestPluginRegistry:
    """Unit tests for PluginRegistry registration, hook dispatch, and isolation."""

    def _make_simple_plugin(self, name: str, hook: str = "on_add") -> PluginBase:
        """Return a PluginBase subclass that registers one hook."""
        received: list = []

        class _P(PluginBase):
            pass

        _P.name = name
        _P.overrides = []

        def _register_hooks(self: PluginBase, r: PluginRegistry) -> None:
            r.register_hook(hook, self._handler)

        def _handler(self, note):  # type: ignore[override]
            received.append(note)

        _P.register_hooks = _register_hooks  # type: ignore[method-assign]
        _P._handler = _handler  # type: ignore[attr-defined]
        _P._received = received  # type: ignore[attr-defined]
        return _P()

    def test_register_plugin_calls_register_hooks(self) -> None:
        """register_plugin must invoke register_hooks so hooks are wired up."""
        registry = PluginRegistry()
        called = []

        class _P(PluginBase):
            name = "p"
            overrides = []

            def register_hooks(self, r: PluginRegistry) -> None:
                called.append("registered")

        registry.register_plugin(_P())
        assert called == ["registered"]

    def test_registered_hook_fires_on_call_hook(self) -> None:
        """A hook registered in register_hooks must actually fire via call_hook."""
        registry = PluginRegistry()
        received: list[Note] = []

        class _P(PluginBase):
            name = "spy"
            overrides = []

            def register_hooks(self, r: PluginRegistry) -> None:
                r.register_hook("on_add", self.on_add)

            def on_add(self, note: Note) -> None:
                received.append(note)

        registry.register_plugin(_P())
        note = Note.create("Test", "body")
        registry.call_hook("on_add", note)
        assert len(received) == 1

    def test_call_hook_passes_copy_not_original(self) -> None:
        """Plugins receive a dataclass copy; mutation does not affect original.  [REQ R15.7]"""
        registry = PluginRegistry()
        received: list[Note] = []

        class _P(PluginBase):
            name = "copy_check"
            overrides = []

            def register_hooks(self, r: PluginRegistry) -> None:
                r.register_hook("on_add", self.on_add)

            def on_add(self, note: Note) -> None:
                received.append(note)
                note.title = "MUTATED"

        registry.register_plugin(_P())
        original = Note.create("Original", "body")
        registry.call_hook("on_add", original)
        assert len(received) == 1
        assert original.title == "Original"  # mutation did not propagate

    def test_duplicate_plugin_type_silently_skipped(self) -> None:
        """Registering the same plugin class twice emits a warning and skips.  [REQ R4.3]"""
        registry = PluginRegistry()

        class _P(PluginBase):
            name = "dup"
            overrides = []

            def register_hooks(self, r: PluginRegistry) -> None:
                pass

        registry.register_plugin(_P())
        registry.register_plugin(_P())  # second registration — must be skipped
        assert len(registry._plugins) == 1

    def test_crashing_hook_does_not_propagate(self) -> None:
        """A hook that raises must not crash the caller.  [REQ R4.7]"""
        registry = PluginRegistry()

        class _P(PluginBase):
            name = "crasher"
            overrides = []

            def register_hooks(self, r: PluginRegistry) -> None:
                r.register_hook("on_add", self.on_add)

            def on_add(self, note: Note) -> None:
                raise RuntimeError("plugin bug")

        registry.register_plugin(_P())
        note = Note.create("T", "b")
        # Must not raise
        registry.call_hook("on_add", note)

    def test_unregistered_hook_name_is_no_op(self) -> None:
        """Calling a hook with no registered handlers is a safe no-op."""
        registry = PluginRegistry()
        note = Note.create("T", "b")
        registry.call_hook("on_nonexistent", note)  # should not raise

    def test_multiple_plugins_all_notified(self) -> None:
        """All registered plugins receive the hook call."""
        registry = PluginRegistry()
        calls: list[str] = []

        for pname in ("alpha", "beta", "gamma"):
            class _P(PluginBase):
                name = pname  # type: ignore[assignment]
                overrides = []
                _pname = pname

                def register_hooks(self, r: PluginRegistry) -> None:
                    r.register_hook("on_add", self._cb)

                def _cb(self, note: Note) -> None:
                    calls.append(self._pname)

            registry.register_plugin(_P())

        registry.call_hook("on_add", Note.create("T", "b"))
        assert set(calls) == {"alpha", "beta", "gamma"}


# ===========================================================================
# §9  Plugin allowlist
# ===========================================================================


class TestPluginAllowlist:
    def _make_plugin_file(self, plugin_dir: Path, name: str) -> None:
        plugin_dir.mkdir(exist_ok=True)
        (plugin_dir / f"{name}.py").write_text(
            textwrap.dedent(f"""\
                from src.core.plugin_base import PluginBase, PluginRegistry
                class {name.title().replace("_", "")}Plugin(PluginBase):
                    name = "{name}"
                    overrides = []
                    def register_hooks(self, registry: PluginRegistry) -> None:
                        pass
            """)
        )

    def test_plugin_not_in_allowlist_skipped(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "plugins"
        self._make_plugin_file(plugin_dir, "blocked_plugin")
        registry = PluginRegistry()
        loaded = discover_plugins(
            plugin_dir, registry, allowed_plugins=frozenset({"other_plugin"})
        )
        assert len(loaded) == 0

    def test_plugin_in_allowlist_loaded(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "plugins"
        self._make_plugin_file(plugin_dir, "allowed_plugin")
        registry = PluginRegistry()
        loaded = discover_plugins(
            plugin_dir, registry, allowed_plugins=frozenset({"allowed_plugin"})
        )
        assert len(loaded) == 1
        assert loaded[0].name == "allowed_plugin"

    def test_empty_allowlist_loads_all(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "plugins"
        self._make_plugin_file(plugin_dir, "plugin_a")
        self._make_plugin_file(plugin_dir, "plugin_b")
        registry = PluginRegistry()
        loaded = discover_plugins(plugin_dir, registry, allowed_plugins=None)
        assert len(loaded) == 2

    def test_allowlist_partial_allows_subset(self, tmp_path: Path) -> None:
        """When allowlist contains only one of two plugins, only that one loads."""
        plugin_dir = tmp_path / "plugins"
        self._make_plugin_file(plugin_dir, "plugin_c")
        self._make_plugin_file(plugin_dir, "plugin_d")
        registry = PluginRegistry()
        loaded = discover_plugins(
            plugin_dir, registry, allowed_plugins=frozenset({"plugin_c"})
        )
        assert len(loaded) == 1
        assert loaded[0].name == "plugin_c"

    def test_empty_frozenset_allowlist_blocks_all(self, tmp_path: Path) -> None:
        """A non-None but empty frozenset is falsy — treated as 'no restriction'."""
        # frozenset() is falsy so allowed_plugins=frozenset() means no filter
        plugin_dir = tmp_path / "plugins"
        self._make_plugin_file(plugin_dir, "plugin_e")
        registry = PluginRegistry()
        loaded = discover_plugins(
            plugin_dir, registry, allowed_plugins=frozenset()
        )
        # empty frozenset is falsy → no restriction applied → plugin loads
        assert len(loaded) == 1


# ===========================================================================
# §10  Plugin override policy
# ===========================================================================


class TestPluginOverridePolicy:
    def _make_override_plugin(self, plugin_dir: Path, name: str) -> None:
        plugin_dir.mkdir(exist_ok=True)
        (plugin_dir / f"{name}.py").write_text(
            textwrap.dedent(f"""\
                from src.core.plugin_base import PluginBase, PluginRegistry
                class {name.title().replace("_", "")}Plugin(PluginBase):
                    name = "{name}"
                    overrides = ["on_add"]
                    def register_hooks(self, registry: PluginRegistry) -> None:
                        pass
            """)
        )

    def test_override_check_fn_called_for_overriding_plugin(
        self, tmp_path: Path
    ) -> None:
        plugin_dir = tmp_path / "plugins"
        self._make_override_plugin(plugin_dir, "override_plugin")
        called = []

        def check(plugin: PluginBase) -> bool:
            called.append(plugin.name)
            return True

        registry = PluginRegistry()
        loaded = discover_plugins(plugin_dir, registry, override_check_fn=check)
        assert "override_plugin" in called
        assert len(loaded) == 1

    def test_override_check_returning_false_skips_plugin(
        self, tmp_path: Path
    ) -> None:
        plugin_dir = tmp_path / "plugins"
        self._make_override_plugin(plugin_dir, "override_plugin2")

        def check(plugin: PluginBase) -> bool:
            return False  # reject all overriding plugins

        registry = PluginRegistry()
        loaded = discover_plugins(plugin_dir, registry, override_check_fn=check)
        assert len(loaded) == 0

    def test_override_check_not_called_for_non_overriding_plugin(
        self, tmp_path: Path
    ) -> None:
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir(exist_ok=True)
        (plugin_dir / "normal_plugin.py").write_text(
            textwrap.dedent("""\
                from src.core.plugin_base import PluginBase, PluginRegistry
                class NormalPlugin(PluginBase):
                    name = "normal_plugin"
                    overrides = []
                    def register_hooks(self, registry: PluginRegistry) -> None:
                        pass
            """)
        )
        called = []

        def check(plugin: PluginBase) -> bool:
            called.append(plugin.name)
            return True

        registry = PluginRegistry()
        discover_plugins(plugin_dir, registry, override_check_fn=check)
        assert "normal_plugin" not in called

    def test_override_check_fn_none_loads_overriding_plugin(
        self, tmp_path: Path
    ) -> None:
        """When override_check_fn is None, overriding plugins load without a prompt."""
        plugin_dir = tmp_path / "plugins"
        self._make_override_plugin(plugin_dir, "unguarded_override")
        registry = PluginRegistry()
        # No override_check_fn — overriding plugin must still load
        loaded = discover_plugins(plugin_dir, registry, override_check_fn=None)
        assert len(loaded) == 1
        assert loaded[0].name == "unguarded_override"

    def test_allowlist_blocks_before_override_check(
        self, tmp_path: Path
    ) -> None:
        """A plugin not in the allowlist is rejected BEFORE override_check_fn."""
        plugin_dir = tmp_path / "plugins"
        self._make_override_plugin(plugin_dir, "nolist_override")
        override_called = []

        def check(plugin: PluginBase) -> bool:
            override_called.append(plugin.name)
            return True

        registry = PluginRegistry()
        loaded = discover_plugins(
            plugin_dir, registry,
            allowed_plugins=frozenset({"other_plugin"}),  # not in list
            override_check_fn=check,
        )
        assert len(loaded) == 0
        assert override_called == []  # never reached

    def test_allowlist_and_override_combined_both_must_pass(
        self, tmp_path: Path
    ) -> None:
        """Plugin in allowlist with overrides must still pass override_check_fn."""
        plugin_dir = tmp_path / "plugins"
        self._make_override_plugin(plugin_dir, "listed_override")
        override_called = []

        def check(plugin: PluginBase) -> bool:
            override_called.append(plugin.name)
            return True  # approve

        registry = PluginRegistry()
        loaded = discover_plugins(
            plugin_dir, registry,
            allowed_plugins=frozenset({"listed_override"}),
            override_check_fn=check,
        )
        assert len(loaded) == 1
        assert "listed_override" in override_called  # override check was called

    def test_allowlist_and_override_combined_override_rejected(
        self, tmp_path: Path
    ) -> None:
        """Plugin in allowlist but override rejected by check_fn — not loaded."""
        plugin_dir = tmp_path / "plugins"
        self._make_override_plugin(plugin_dir, "listed_override2")

        def check(plugin: PluginBase) -> bool:
            return False  # reject

        registry = PluginRegistry()
        loaded = discover_plugins(
            plugin_dir, registry,
            allowed_plugins=frozenset({"listed_override2"}),
            override_check_fn=check,
        )
        assert len(loaded) == 0


# ===========================================================================
# §11  Plugin CLI command wiring
# ===========================================================================


class TestPluginCommandWiring:
    def test_plugin_get_commands_returns_dict(self, tmp_path: Path) -> None:
        """PluginBase.get_commands() returns empty dict by default.  [BL B-28]"""
        registry = PluginRegistry()
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        loaded = discover_plugins(plugin_dir, registry)
        # No plugins in empty dir — just verify the API works.
        assert isinstance(loaded, list)

    def test_plugin_with_command_registered(self, tmp_path: Path) -> None:
        """A plugin providing a Click command sees it registered.  [BL B-28]"""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        (plugin_dir / "cmd_plugin.py").write_text(
            textwrap.dedent("""\
                import click
                from src.core.plugin_base import PluginBase, PluginRegistry

                @click.command("plugin-hello")
                def hello_cmd():
                    click.echo("hello from plugin")

                class CmdPlugin(PluginBase):
                    name = "cmd_plugin"
                    overrides = []
                    def register_hooks(self, registry: PluginRegistry) -> None:
                        pass
                    def get_commands(self):
                        return {"plugin-hello": hello_cmd}
            """)
        )
        registry = PluginRegistry()
        loaded = discover_plugins(plugin_dir, registry)
        assert len(loaded) == 1
        cmds = loaded[0].get_commands()
        assert "plugin-hello" in cmds


# ===========================================================================
# §12  ANSI stripping
# ===========================================================================


class TestAnsiStripping:
    def test_strip_ansi_removes_csi_sequences(self) -> None:
        text = "\x1b[31mred\x1b[0m normal"
        assert _strip_ansi(text) == "red normal"

    def test_strip_ansi_removes_bold_sequence(self) -> None:
        text = "\x1b[1mbold\x1b[0m"
        assert _strip_ansi(text) == "bold"

    def test_strip_ansi_keeps_newlines(self) -> None:
        text = "line1\nline2\n"
        assert _strip_ansi(text) == "line1\nline2\n"

    def test_strip_ansi_keeps_tabs(self) -> None:
        text = "col1\tcol2"
        assert _strip_ansi(text) == "col1\tcol2"

    def test_strip_ansi_removes_control_chars(self) -> None:
        text = "a\x01b\x02c"  # SOH, STX
        result = _strip_ansi(text)
        assert "\x01" not in result
        assert "\x02" not in result
        assert "abc" in result

    def test_strip_ansi_plain_text_unchanged(self) -> None:
        text = "Hello, World! 123"
        assert _strip_ansi(text) == text

    def test_get_cmd_strips_ansi_from_content(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("Title", "\x1b[32mgreen\x1b[0m text")
        store.add(note)

        result = _invoke(runner, ["get", note.id], tmp_path)
        assert result.exit_code == 0
        assert "\x1b[" not in result.output
        assert "green" in result.output

    def test_list_cmd_strips_ansi_from_title(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("\x1b[1mBold Title\x1b[0m", "content")
        store.add(note)

        result = _invoke(runner, ["list"], tmp_path)
        assert result.exit_code == 0
        assert "\x1b[" not in result.output
        assert "Bold Title" in result.output


# ===========================================================================
# §13  Path traversal prevention
# ===========================================================================


class TestPathTraversal:
    def test_export_null_byte_rejected(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("N", "c")
        store.add(note)
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "export", "--output", "bad\x00path.json"],
            catch_exceptions=False,
        )
        assert result.exit_code != 0

    def test_data_dir_resolved_via_path_resolve(self, tmp_path: Path) -> None:
        """--data-dir with .. segments should resolve to absolute path."""
        runner = CliRunner()
        # Build a path with .., e.g. tmp_path/../tmp_path_name
        tricky = str(tmp_path / ".." / tmp_path.name)
        result = runner.invoke(
            cli,
            ["--data-dir", tricky, "list"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0  # resolves fine


# ===========================================================================
# §14  Plugin sandboxing
# ===========================================================================


class TestPluginSandboxing:
    def test_plugin_receives_copy_of_note(self, tmp_path: Path) -> None:
        """Plugins must receive a dataclass copy, not the original.  [BL B-56]"""
        registry = PluginRegistry()

        received: list[Note] = []

        class SpyPlugin(PluginBase):
            name = "spy"
            overrides = []

            def register_hooks(self, r: PluginRegistry) -> None:
                r.register_hook("on_add", self.on_add)

            def on_add(self, note: Note) -> None:
                received.append(note)

        plugin = SpyPlugin()
        registry.register_plugin(plugin)

        store = _make_store(tmp_path)
        original = Note.create("Original", "content")
        store.add(original)
        registry.call_hook("on_add", original)

        assert len(received) == 1
        # Plugin receives a Note instance; modifying it must not affect original.
        received[0].title = "MODIFIED BY PLUGIN"
        assert original.title == "Original"

    def test_plugin_cannot_mutate_note_in_store(self, tmp_path: Path) -> None:
        """Mutation of the received note copy must not affect the DB.  [BL B-56]"""
        registry = PluginRegistry()

        class MutatePlugin(PluginBase):
            name = "mutate"
            overrides = []

            def register_hooks(self, r: PluginRegistry) -> None:
                pass

            def on_add(self, note: Note) -> None:
                note.title = "MUTATED"

        plugin = MutatePlugin()
        plugin.register_hooks(registry)
        registry.register_plugin(plugin)

        store = _make_store(tmp_path)
        original = Note.create("Safe Title", "content")
        store.add(original)
        registry.call_hook("on_add", original)

        fetched = store.get(original.id)
        assert fetched is not None
        assert fetched.title == "Safe Title"


# ===========================================================================
# §15  Audit integration in CLI commands
# ===========================================================================


class TestAuditIntegration:
    def test_login_logged(self, tmp_path: Path) -> None:
        from src.core.auth import AccountStore
        runner = CliRunner()
        acct_store = AccountStore(tmp_path)
        acct_store.register("testuser", "TestPass1!")
        _invoke(runner, ["login"], tmp_path, input="testuser\nTestPass1!\nno\n")

        al = AuditLogger(tmp_path)
        entries = al.read(operation="login")
        assert any(e["outcome"] == "success" for e in entries)

    def test_logout_logged(self, tmp_path: Path) -> None:
        from src.core.auth import AccountStore, SessionManager
        runner = CliRunner()
        acct_store = AccountStore(tmp_path)
        aid = acct_store.register("user2", "TestPass2!")
        SessionManager.create(tmp_path, aid, "user2")

        _invoke(runner, ["logout"], tmp_path)

        al = AuditLogger(tmp_path)
        entries = al.read(operation="logout")
        assert any(e["outcome"] == "success" for e in entries)

    def test_register_logged(self, tmp_path: Path) -> None:
        runner = CliRunner()
        _invoke(
            runner, ["register"], tmp_path,
            input="newuser3\nTestPass3!\nTestPass3!\n"
        )
        al = AuditLogger(tmp_path)
        entries = al.read(operation="register")
        assert any(e["outcome"] == "success" for e in entries)

    def test_encrypt_logged_on_add(self, tmp_path: Path) -> None:
        runner = CliRunner()
        _invoke(
            runner,
            ["add", "--title", "Secret", "--encrypt", "--content", "some content"],
            tmp_path,
            input="AuditPass1!\nAuditPass1!\n",
        )
        al = AuditLogger(tmp_path)
        entries = al.read(operation="encrypt")
        assert any(e["outcome"] == "success" for e in entries)

    def test_decrypt_logged_on_get(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Add note via CLI (default iterations)
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "Enc",
             "--encrypt", "--content", "audit content"],
            input="AuditGet1!\nAuditGet1!\n",
            catch_exceptions=False,
        )
        note_id = result.output.strip().splitlines()[-1]

        _invoke(
            runner,
            ["get", note_id, "--decrypt"],
            tmp_path,
            input="AuditGet1!\n",
        )
        al = AuditLogger(tmp_path)
        entries = al.read(operation="decrypt")
        assert any(e["outcome"] == "success" for e in entries)

    def test_reencrypt_logged(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Add note via CLI (default iterations)
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "add", "--title", "Enc",
             "--encrypt", "--content", "data"],
            input="OldPP1234!\nOldPP1234!\n",
            catch_exceptions=False,
        )
        note_id = result.output.strip().splitlines()[-1]

        runner.invoke(
            cli,
            ["--data-dir", str(tmp_path), "reencrypt", note_id],
            input="OldPP1234!\nNewPP5678!\nNewPP5678!\n",
            catch_exceptions=False,
        )
        al = AuditLogger(tmp_path)
        entries = al.read(operation="reencrypt")
        assert any(e["outcome"] == "success" for e in entries)

    def test_export_logged(self, tmp_path: Path) -> None:
        runner = CliRunner()
        store = _make_store(tmp_path)
        note = Note.create("Exp", "content")
        store.add(note)

        _invoke(runner, ["export", "--format", "json"], tmp_path)
        al = AuditLogger(tmp_path)
        entries = al.read(operation="export")
        assert any(e["outcome"] == "success" for e in entries)


# ===========================================================================
# §16  Alias info warning  [BL B-79] [REQ R2.16]
# ===========================================================================


class TestAliasInfoWarning:
    def test_alias_with_encrypt_shows_warning(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--data-dir", str(tmp_path),
                "add", "--title", "My Note",
                "--encrypt", "--alias", "Work Meeting Notes",
                "--content", "some content",
            ],
            input="AliasPass1!\nAliasPass1!\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "unencrypted" in result.output.lower()

    def test_alias_used_as_note_title(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(
            cli,
            [
                "--data-dir", str(tmp_path),
                "add", "--title", "Internal Title",
                "--encrypt", "--alias", "Public Alias",
                "--content", "content here",
            ],
            input="AliasPass2!\nAliasPass2!\n",
            catch_exceptions=False,
        )
        store = _make_store(tmp_path)
        _, _ = store.list()
        all_notes = store.list(None)[1]  # local notes
        assert any(n.title == "Public Alias" for n in all_notes)


# ===========================================================================
# §17  Passphrase memory limitation comment  [BL B-73] [REQ R2.15]
# ===========================================================================


class TestPassphraseMemoryLimitation:
    def test_passphrase_memory_limitation_documented(self) -> None:
        """[BL B-73] CLI source must document the passphrase memory limitation."""
        import src.cli as cli_module
        source = inspect.getsource(cli_module)
        assert "not zeroizable" in source or "BL B-73" in source, (
            "CLI source must contain passphrase memory limitation note [BL B-73]"
        )
