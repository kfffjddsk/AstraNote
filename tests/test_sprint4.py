"""Sprint 4 test suite for AstraNotes.

Coverage:
  §1   ConfigStore security_level key        [BL B-98]  [REQ R9.3–R9.5]
  §2   Plugin manifest validation            [BL B-99]  [REQ R4.11, R4.12]
  §3   Trust-tier enforcement                [BL B-100] [REQ R4.13]
  §4   AppLockManager PID lock file          [BL B-101] [REQ R9.7]
  §5   AppController startup sequence        [BL B-84]  (mocked Qt)
  §6   CLI gui command                       [BL B-84]
  §7   DesktopGUI — PassphraseDialog         [BL B-84, B-85]
  §8   DesktopGUI — NoteEditorWidget         [BL B-84, B-85]
  §9   DesktopGUI — MainWindow CRUD          [BL B-85]
  §10  DesktopGUI — idle auto-lock timer     [BL B-102] [REQ R9.8]
  §11  DesktopGUI — security_level logic     [BL B-98]
  §12  DesktopGUI — system tray              [BL B-97]
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.core.app_lock import AppLockManager, SessionConflictError, _is_process_alive
from src.core.config import ALLOWED_KEYS, DEFAULTS, ConfigStore, _VALUE_CONSTRAINTS
from src.core.notes import DatabaseStore, Note
from src.core.plugin_base import PluginBase, PluginRegistry
from tests.conftest import _TEST_ITERATIONS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> DatabaseStore:
    return DatabaseStore(tmp_path)


def _make_config(tmp_path: Path) -> ConfigStore:
    return ConfigStore(config_path=tmp_path / "config.json")


# ---------------------------------------------------------------------------
# §1  ConfigStore security_level key  [BL B-98]
# ---------------------------------------------------------------------------


class TestSecurityLevelConfig:
    """§1 — security_level config key (B-98)."""

    def test_security_level_in_allowed_keys(self):
        """§1.1  security_level is a known config key."""
        assert "security_level" in ALLOWED_KEYS

    def test_security_level_default_is_high(self, tmp_path):
        """§1.2  Default value for security_level is 'high'."""
        cfg = _make_config(tmp_path)
        assert cfg.get("security_level") == "high"

    def test_security_level_high_in_defaults(self):
        """§1.3  DEFAULTS dict contains security_level = 'high'."""
        assert DEFAULTS.get("security_level") == "high"

    def test_security_level_value_constraints_exist(self):
        """§1.4  _VALUE_CONSTRAINTS has security_level entry."""
        assert "security_level" in _VALUE_CONSTRAINTS
        assert _VALUE_CONSTRAINTS["security_level"] == frozenset({"high", "session"})

    def test_set_security_level_high(self, tmp_path):
        """§1.5  Can set security_level to 'high'."""
        cfg = _make_config(tmp_path)
        cfg.set("security_level", "high")
        assert cfg.get("security_level") == "high"

    def test_set_security_level_session(self, tmp_path):
        """§1.6  Can set security_level to 'session'."""
        cfg = _make_config(tmp_path)
        cfg.set("security_level", "session")
        assert cfg.get("security_level") == "session"

    def test_set_security_level_invalid_rejected(self, tmp_path):
        """§1.7  Invalid security_level values are rejected with ValueError."""
        cfg = _make_config(tmp_path)
        with pytest.raises(ValueError, match="security_level"):
            cfg.set("security_level", "medium")

    def test_set_security_level_invalid_uppercase_rejected(self, tmp_path):
        """§1.8  Case-sensitive: 'High' is invalid (must be lowercase)."""
        cfg = _make_config(tmp_path)
        with pytest.raises(ValueError):
            cfg.set("security_level", "High")

    def test_security_level_persists_to_disk(self, tmp_path):
        """§1.9  security_level is persisted and survives reload."""
        cfg = _make_config(tmp_path)
        cfg.set("security_level", "session")
        cfg2 = ConfigStore(config_path=tmp_path / "config.json")
        assert cfg2.get("security_level") == "session"

    def test_reset_security_level_restores_default(self, tmp_path):
        """§1.10  Resetting security_level reverts to 'high'."""
        cfg = _make_config(tmp_path)
        cfg.set("security_level", "session")
        cfg.reset("security_level")
        assert cfg.get("security_level") == "high"


# ---------------------------------------------------------------------------
# §2  Plugin manifest validation  [BL B-99]
# ---------------------------------------------------------------------------


def _write_manifest(subdir: Path, data: dict) -> None:
    subdir.mkdir(parents=True, exist_ok=True)
    (subdir / "plugin.json").write_text(json.dumps(data), encoding="utf-8")


_VALID_MANIFEST = {
    "plugin_id": "test.plugin",
    "name": "Test Plugin",
    "version": "1.0.0",
    "engines": {"astranotes": ">=4.0.0"},
    "main": "plugin.py",
}


class TestPluginManifestValidation:
    """§2 — load_manifests() validation (B-99)."""

    def test_valid_manifest_accepted(self, tmp_path):
        """§2.1  A valid manifest with all required fields is accepted."""
        _write_manifest(tmp_path / "myplugin", _VALID_MANIFEST)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert len(manifests) == 1
        assert manifests[0]["plugin_id"] == "test.plugin"

    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        """§2.2  load_manifests() on a non-existent directory returns []."""
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path / "no_such_dir")
        assert manifests == []

    def test_missing_plugin_json_skipped(self, tmp_path):
        """§2.3  Plugin subdir without plugin.json is silently skipped."""
        (tmp_path / "nomanifest").mkdir()
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert manifests == []

    def test_invalid_json_skipped(self, tmp_path):
        """§2.4  Malformed JSON in plugin.json is skipped with a warning."""
        subdir = tmp_path / "badplugin"
        subdir.mkdir()
        (subdir / "plugin.json").write_text("{not: valid json}", encoding="utf-8")
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert manifests == []

    def test_missing_required_field_plugin_id(self, tmp_path):
        """§2.5  Missing plugin_id causes manifest to be skipped."""
        data = {k: v for k, v in _VALID_MANIFEST.items() if k != "plugin_id"}
        _write_manifest(tmp_path / "myplugin", data)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert manifests == []

    def test_missing_required_field_name(self, tmp_path):
        """§2.6  Missing name causes manifest to be skipped."""
        data = {k: v for k, v in _VALID_MANIFEST.items() if k != "name"}
        _write_manifest(tmp_path / "myplugin", data)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert manifests == []

    def test_missing_required_field_version(self, tmp_path):
        """§2.7  Missing version causes manifest to be skipped."""
        data = {k: v for k, v in _VALID_MANIFEST.items() if k != "version"}
        _write_manifest(tmp_path / "myplugin", data)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert manifests == []

    def test_missing_required_field_engines(self, tmp_path):
        """§2.8  Missing engines causes manifest to be skipped."""
        data = {k: v for k, v in _VALID_MANIFEST.items() if k != "engines"}
        _write_manifest(tmp_path / "myplugin", data)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert manifests == []

    def test_missing_required_field_main(self, tmp_path):
        """§2.9  Missing main causes manifest to be skipped."""
        data = {k: v for k, v in _VALID_MANIFEST.items() if k != "main"}
        _write_manifest(tmp_path / "myplugin", data)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert manifests == []

    def test_is_official_in_manifest_rejected(self, tmp_path):
        """§2.10  Manifest containing is_official is always rejected (server-injected only)."""
        data = dict(_VALID_MANIFEST, is_official=True)
        _write_manifest(tmp_path / "evilplugin", data)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert manifests == []

    def test_is_official_false_in_manifest_also_rejected(self, tmp_path):
        """§2.11  is_official=False in manifest is also rejected (any presence forbidden)."""
        data = dict(_VALID_MANIFEST, is_official=False)
        _write_manifest(tmp_path / "evilplugin", data)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert manifests == []

    def test_multiple_valid_manifests(self, tmp_path):
        """§2.12  Multiple valid plugin subdirs all accepted."""
        for i in range(3):
            data = dict(_VALID_MANIFEST, plugin_id=f"plugin.{i}", name=f"Plugin {i}")
            _write_manifest(tmp_path / f"plugin{i}", data)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert len(manifests) == 3

    def test_mix_valid_and_invalid(self, tmp_path):
        """§2.13  Only valid manifests returned; invalid ones silently skipped."""
        _write_manifest(tmp_path / "good", _VALID_MANIFEST)
        bad = dict(_VALID_MANIFEST, is_official=True, plugin_id="evil")
        _write_manifest(tmp_path / "bad", bad)
        missing_plugin_id = {k: v for k, v in _VALID_MANIFEST.items() if k != "plugin_id"}
        _write_manifest(tmp_path / "incomplete", missing_plugin_id)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert len(manifests) == 1
        assert manifests[0]["plugin_id"] == "test.plugin"

    def test_non_subdir_files_ignored(self, tmp_path):
        """§2.14  Files directly in plugin_dir (not subdirs) are ignored."""
        # plugin.json at the top level — not in a subdir — must be ignored
        (tmp_path / "plugin.json").write_text(json.dumps(_VALID_MANIFEST), encoding="utf-8")
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert manifests == []

    def test_manifests_stored_on_registry(self, tmp_path):
        """§2.15  Accepted manifests are stored on registry._manifests."""
        _write_manifest(tmp_path / "myplugin", _VALID_MANIFEST)
        registry = PluginRegistry()
        registry.load_manifests(tmp_path)
        assert len(registry._manifests) == 1

    def test_extra_fields_in_manifest_accepted(self, tmp_path):
        """§2.16  Extra fields beyond required set are allowed (additionalProperties=True)."""
        data = dict(_VALID_MANIFEST, description="A handy plugin", author="Alice")
        _write_manifest(tmp_path / "myplugin", data)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert len(manifests) == 1
        assert manifests[0]["description"] == "A handy plugin"

    def test_empty_string_required_field_rejected(self, tmp_path):
        """§2.17  Empty string for required field fails minLength=1 constraint."""
        data = dict(_VALID_MANIFEST, plugin_id="")
        _write_manifest(tmp_path / "myplugin", data)
        registry = PluginRegistry()
        manifests = registry.load_manifests(tmp_path)
        assert manifests == []

    def test_load_manifests_replaces_previous(self, tmp_path):
        """§2.18  Calling load_manifests() twice replaces the cached manifest list."""
        _write_manifest(tmp_path / "myplugin", _VALID_MANIFEST)
        registry = PluginRegistry()
        registry.load_manifests(tmp_path)
        assert len(registry._manifests) == 1
        # Remove the only manifest and call again
        (tmp_path / "myplugin" / "plugin.json").unlink()
        registry.load_manifests(tmp_path)
        assert registry._manifests == []


# ---------------------------------------------------------------------------
# §3  Trust-tier enforcement  [BL B-100]
# ---------------------------------------------------------------------------


class _HookPlugin(PluginBase):
    """Test plugin that registers a hook."""

    name = "hookplugin"
    version = "1.0"
    hook_called = False

    def register_hooks(self, registry: PluginRegistry) -> None:
        registry.register_hook("post_add_note", self._handler)

    def _handler(self, note: Note, **kwargs) -> None:
        _HookPlugin.hook_called = True


class _HookPlugin2(_HookPlugin):
    """Second test plugin — distinct type."""

    name = "hookplugin2"


class TestTrustTierEnforcement:
    """§3 — Trust-tier enforcement in register_plugin() (B-100)."""

    def setup_method(self):
        _HookPlugin.hook_called = False
        _HookPlugin2.hook_called = False

    def test_is_official_true_allows_hooks(self, tmp_path):
        """§3.1  Official plugin (is_official=True) can register hooks."""
        registry = PluginRegistry()
        plugin = _HookPlugin()
        registry.register_plugin(plugin, is_official=True)
        assert "post_add_note" in registry._hooks
        assert len(registry._hooks["post_add_note"]) == 1

    def test_is_official_false_blocks_hooks(self, tmp_path):
        """§3.2  User-installed plugin (is_official=False) cannot register hooks."""
        registry = PluginRegistry()
        plugin = _HookPlugin()
        registry.register_plugin(plugin, is_official=False)
        assert registry._hooks.get("post_add_note", []) == []

    def test_is_official_default_true_allows_hooks(self, tmp_path):
        """§3.3  Default is_official=True — hooks allowed without explicit flag."""
        registry = PluginRegistry()
        plugin = _HookPlugin()
        registry.register_plugin(plugin)  # no is_official kwarg → default True
        assert "post_add_note" in registry._hooks
        assert len(registry._hooks["post_add_note"]) == 1

    def test_is_official_false_plugin_still_registered(self, tmp_path):
        """§3.4  User-installed plugin is still added to _plugins even when hooks blocked."""
        registry = PluginRegistry()
        plugin = _HookPlugin()
        registry.register_plugin(plugin, is_official=False)
        assert plugin in registry._plugins

    def test_is_official_false_logs_warning(self):
        """§3.5  Blocking a user-installed plugin emits a warning log."""
        with patch("src.core.plugin_base.logger") as mock_log:
            registry = PluginRegistry()
            registry.register_plugin(_HookPlugin(), is_official=False)
        mock_log.warning.assert_called_once()
        msg = mock_log.warning.call_args[0][0]
        assert "is_official=False" in msg or "user-installed" in msg

    def test_official_plugin_hook_fires(self, tmp_path):
        """§3.6  Official plugin's hook is actually called during call_hook()."""
        registry = PluginRegistry()
        plugin = _HookPlugin()
        registry.register_plugin(plugin, is_official=True)
        note = Note.create("T", "C")
        registry.call_hook("post_add_note", note)
        assert _HookPlugin.hook_called

    def test_unofficial_plugin_hook_does_not_fire(self, tmp_path):
        """§3.7  User-installed plugin hook is NOT called during call_hook()."""
        registry = PluginRegistry()
        plugin = _HookPlugin()
        registry.register_plugin(plugin, is_official=False)
        note = Note.create("T", "C")
        registry.call_hook("post_add_note", note)
        assert not _HookPlugin.hook_called

    def test_official_and_unofficial_together(self, tmp_path):
        """§3.8  Official plugin fires; unofficial plugin does not — both registered."""
        registry = PluginRegistry()
        official = _HookPlugin()
        unofficial = _HookPlugin2()
        registry.register_plugin(official, is_official=True)
        registry.register_plugin(unofficial, is_official=False)
        note = Note.create("T", "C")
        registry.call_hook("post_add_note", note)
        assert _HookPlugin.hook_called
        assert not _HookPlugin2.hook_called

    def test_duplicate_official_plugin_skipped(self, tmp_path):
        """§3.9  Registering the same official plugin type twice: second skipped."""
        registry = PluginRegistry()
        registry.register_plugin(_HookPlugin(), is_official=True)
        registry.register_plugin(_HookPlugin(), is_official=True)
        assert len(registry._plugins) == 1
        # Only one hook registered
        assert len(registry._hooks.get("post_add_note", [])) == 1


# ---------------------------------------------------------------------------
# §4  AppLockManager PID lock file  [BL B-101]
# ---------------------------------------------------------------------------


class TestIsProcessAlive:
    """§4a — _is_process_alive() helper."""

    def test_current_process_is_alive(self):
        """§4a.1  Current process PID is always alive."""
        assert _is_process_alive(os.getpid()) is True

    def test_pid_zero_not_alive(self):
        """§4a.2  PID=0 treated as not alive (sentinel)."""
        assert _is_process_alive(0) is False

    def test_negative_pid_not_alive(self):
        """§4a.3  Negative PID treated as not alive."""
        assert _is_process_alive(-1) is False

    def test_very_large_pid_not_alive(self):
        """§4a.4  Non-existent very large PID returns False."""
        assert _is_process_alive(9_999_999) is False


class TestAppLockManager:
    """§4b — AppLockManager (B-101)."""

    def test_acquire_creates_lock_file(self, tmp_path):
        """§4b.1  acquire_lock() creates the .app.lock file."""
        lm = AppLockManager(tmp_path)
        lm.acquire_lock()
        assert lm.lock_path.exists()

    def test_lock_file_contains_pid_and_timestamp(self, tmp_path):
        """§4b.2  Lock file JSON contains 'pid' and 'launched_at' keys."""
        lm = AppLockManager(tmp_path)
        lm.acquire_lock()
        data = json.loads(lm.lock_path.read_text(encoding="utf-8"))
        assert "pid" in data
        assert "launched_at" in data

    def test_lock_file_pid_matches_current_process(self, tmp_path):
        """§4b.3  pid in lock file equals os.getpid()."""
        lm = AppLockManager(tmp_path)
        lm.acquire_lock()
        data = json.loads(lm.lock_path.read_text(encoding="utf-8"))
        assert data["pid"] == os.getpid()

    def test_release_deletes_lock_file(self, tmp_path):
        """§4b.4  release_lock() removes the .app.lock file."""
        lm = AppLockManager(tmp_path)
        lm.acquire_lock()
        lm.release_lock()
        assert not lm.lock_path.exists()

    def test_release_idempotent_when_file_missing(self, tmp_path):
        """§4b.5  release_lock() on a non-existent file does not raise."""
        lm = AppLockManager(tmp_path)
        lm.release_lock()  # should not raise

    def test_acquire_with_stale_pid_overwrites_silently(self, tmp_path):
        """§4b.6  Stale lock (dead PID) is silently overwritten."""
        lm = AppLockManager(tmp_path)
        # Write a lock with a dead PID (very large, non-existent)
        stale_data = {"pid": 9_999_999, "launched_at": "2026-01-01T00:00:00+00:00"}
        lm.lock_path.write_text(json.dumps(stale_data), encoding="utf-8")
        lm.acquire_lock()  # should NOT raise
        data = json.loads(lm.lock_path.read_text(encoding="utf-8"))
        assert data["pid"] == os.getpid()

    def test_acquire_with_alive_pid_raises_conflict(self, tmp_path):
        """§4b.7  Lock held by alive process raises SessionConflictError."""
        lm = AppLockManager(tmp_path)
        # Use current process PID as "another" alive process
        alive_data = {"pid": os.getpid(), "launched_at": "2026-01-01T00:00:00+00:00"}
        lm.lock_path.write_text(json.dumps(alive_data), encoding="utf-8")
        # Now try to acquire from the "same alive PID" perspective — simulate
        # by writing same PID but patching _is_process_alive to say it's alive
        # (it IS alive — it's our process).  Acquire should detect conflict.
        lm2 = AppLockManager(tmp_path)
        # The PID in the file IS alive (os.getpid()), so acquire should raise
        with pytest.raises(SessionConflictError, match="already running"):
            lm2.acquire_lock()

    def test_conflict_error_message_contains_pid(self, tmp_path):
        """§4b.8  SessionConflictError message includes the conflicting PID."""
        lm = AppLockManager(tmp_path)
        alive_data = {"pid": os.getpid(), "launched_at": "2026-01-01T00:00:00+00:00"}
        lm.lock_path.write_text(json.dumps(alive_data), encoding="utf-8")
        with pytest.raises(SessionConflictError) as exc_info:
            AppLockManager(tmp_path).acquire_lock()
        assert str(os.getpid()) in str(exc_info.value)

    def test_acquire_with_corrupted_lock_treats_as_stale(self, tmp_path):
        """§4b.9  Corrupted lock file (invalid JSON) treated as stale, overwritten."""
        lm = AppLockManager(tmp_path)
        lm.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lm.lock_path.write_text("{corrupt json!!", encoding="utf-8")
        lm.acquire_lock()  # should not raise
        data = json.loads(lm.lock_path.read_text(encoding="utf-8"))
        assert data["pid"] == os.getpid()

    def test_lock_path_property(self, tmp_path):
        """§4b.10  lock_path property returns correct path."""
        lm = AppLockManager(tmp_path)
        assert lm.lock_path == tmp_path / ".app.lock"

    def test_acquire_creates_parent_dirs(self, tmp_path):
        """§4b.11  acquire_lock() creates parent directories if needed."""
        deep_dir = tmp_path / "deep" / "nested"
        lm = AppLockManager(deep_dir)
        lm.acquire_lock()
        assert lm.lock_path.exists()

    def test_acquire_with_missing_pid_field_treats_as_stale(self, tmp_path):
        """§4b.12  Lock file without 'pid' key treated as stale."""
        lm = AppLockManager(tmp_path)
        lm.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lm.lock_path.write_text(json.dumps({"launched_at": "2026-01-01"}), encoding="utf-8")
        lm.acquire_lock()  # should not raise
        assert json.loads(lm.lock_path.read_text())["pid"] == os.getpid()


# ---------------------------------------------------------------------------
# §5  AppController startup sequence  [BL B-84]
# ---------------------------------------------------------------------------


class TestAppControllerStartup:
    """§5 — AppController.run() startup sequence (mocked Qt)."""

    def _make_controller(self, tmp_path):
        from src.desktop.app_controller import AppController
        return AppController(
            data_dir=tmp_path,
            config_path=tmp_path / "config.json",
        )

    def test_run_acquires_lock_then_releases(self, tmp_path):
        """§5.1  run() acquires and releases the lock around the session."""
        from src.desktop.app_controller import AppController

        controller = AppController(data_dir=tmp_path, config_path=tmp_path / "config.json")
        mock_app = MagicMock()
        mock_app.exec.return_value = 0
        mock_window = MagicMock()

        with patch("src.desktop.app_controller.QApplication", return_value=mock_app) as MockQApp, \
             patch("src.desktop.app_controller.QApplication.instance", return_value=None), \
             patch("src.desktop.main_window.MainWindow", return_value=mock_window), \
             patch("src.desktop.app_controller.MainWindow", return_value=mock_window):
            MockQApp.instance.return_value = None
            exit_code = controller.run()

        # Lock should be released (file gone)
        assert not (tmp_path / ".app.lock").exists()
        assert exit_code == 0

    def test_run_resolves_data_dir_from_config(self, tmp_path):
        """§5.2  Without override, data_dir comes from ConfigStore or default."""
        from src.desktop.app_controller import AppController

        controller = AppController(config_path=tmp_path / "config.json")
        assert controller._override_data_dir is None
        controller.config = MagicMock()
        controller.config.get.return_value = str(tmp_path)
        resolved = controller._resolve_data_dir()
        assert resolved == tmp_path

    def test_resolve_data_dir_uses_override(self, tmp_path):
        """§5.3  _override_data_dir takes precedence over config."""
        from src.desktop.app_controller import AppController

        override = tmp_path / "override"
        controller = AppController(data_dir=override)
        controller.config = MagicMock()
        controller.config.get.return_value = "/some/other/path"
        assert controller._resolve_data_dir() == override

    def test_resolve_data_dir_fallback_to_platform_data_dir(self, tmp_path):
        """§5.4  When config has no data_dir set, falls back to platform_data_dir()."""
        from src.desktop.app_controller import AppController
        from src.core.paths import platform_data_dir

        controller = AppController(config_path=tmp_path / "config.json")
        controller.config = MagicMock()
        controller.config.get.return_value = None
        resolved = controller._resolve_data_dir()
        assert resolved == platform_data_dir()

    def test_run_returns_1_on_session_conflict(self, tmp_path):
        """§5.5  run() returns exit code 1 when SessionConflictError raised."""
        from src.desktop.app_controller import AppController
        from src.core.app_lock import SessionConflictError

        controller = AppController(data_dir=tmp_path, config_path=tmp_path / "config.json")
        with patch("src.desktop.app_controller.AppLockManager.acquire_lock",
                   side_effect=SessionConflictError("already running (PID 99)")):
            with patch("src.desktop.app_controller.QApplication"):
                with patch("src.desktop.app_controller.QMessageBox"):
                    exit_code = controller.run()
        assert exit_code == 1

    def test_run_loads_plugin_manifests(self, tmp_path):
        """§5.6  run() calls PluginRegistry.load_manifests() during startup."""
        from src.desktop.app_controller import AppController

        controller = AppController(data_dir=tmp_path, config_path=tmp_path / "config.json")
        mock_app = MagicMock()
        mock_app.exec.return_value = 0
        mock_window = MagicMock()

        with patch("src.desktop.app_controller.PluginRegistry") as MockRegistry, \
             patch("src.desktop.app_controller.QApplication") as MockQApp, \
             patch("src.desktop.app_controller.MainWindow", return_value=mock_window):
            MockQApp.instance.return_value = None
            MockQApp.return_value = mock_app
            mock_registry_inst = MagicMock()
            MockRegistry.return_value = mock_registry_inst
            controller.run()

        mock_registry_inst.load_manifests.assert_called_once()


# ---------------------------------------------------------------------------
# §6  CLI gui command  [BL B-84]
# ---------------------------------------------------------------------------


class TestCliGuiCommand:
    """§6 — astranotes gui CLI command."""

    def test_gui_command_exists(self):
        """§6.1  'gui' command is registered in the CLI."""
        from click.testing import CliRunner
        from src.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["gui", "--help"])
        assert result.exit_code == 0
        assert "gui" in result.output.lower() or "Launch" in result.output

    def test_gui_command_invokes_app_controller(self, tmp_path):
        """§6.2  'astranotes gui' constructs AppController and calls run()."""
        from click.testing import CliRunner
        from src.cli import cli

        runner = CliRunner()
        with patch("src.desktop.app_controller.AppController") as MockCtrl:
            mock_instance = MagicMock()
            mock_instance.run.return_value = 0
            MockCtrl.return_value = mock_instance
            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_path), "gui"],
                catch_exceptions=False,
            )
        mock_instance.run.assert_called_once()

    def test_gui_command_raises_system_exit_on_nonzero(self, tmp_path):
        """§6.3  Non-zero exit code from AppController.run() causes SystemExit."""
        from click.testing import CliRunner
        from src.cli import cli

        runner = CliRunner()
        with patch("src.desktop.app_controller.AppController") as MockCtrl:
            mock_instance = MagicMock()
            mock_instance.run.return_value = 1
            MockCtrl.return_value = mock_instance
            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_path), "gui"],
            )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# §7  PassphraseDialog  [BL B-84, B-85]
# ---------------------------------------------------------------------------

try:
    from PySide6.QtWidgets import QApplication, QDialog
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

_qt = pytest.mark.skipif(not _QT_AVAILABLE, reason="PySide6 not available")

# Global QApplication instance for the test session
_app: object = None


def _ensure_app():
    """Return (or create) a QApplication singleton for testing."""
    global _app
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if _app is None:
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication([])
    return _app


@_qt
class TestPassphraseDialog:
    """§7 — PassphraseDialog widget (B-84/B-85)."""

    def test_dialog_accepts_on_ok_with_passphrase(self):
        """§7.1  Clicking OK stores passphrase in dialog.passphrase."""
        _ensure_app()
        from src.desktop.main_window import PassphraseDialog
        dlg = PassphraseDialog()
        dlg._entry.setText("correct-horse-battery")
        dlg._on_accept()
        assert dlg.passphrase == "correct-horse-battery"
        assert dlg.result() == QDialog.DialogCode.Accepted

    def test_dialog_passphrase_empty_by_default(self):
        """§7.2  passphrase attribute starts as empty string."""
        _ensure_app()
        from src.desktop.main_window import PassphraseDialog
        dlg = PassphraseDialog()
        assert dlg.passphrase == ""

    def test_dialog_confirm_mode_mismatch_does_not_accept(self):
        """§7.3  Mismatched passphrases in confirm mode do not close the dialog."""
        _ensure_app()
        from src.desktop.main_window import PassphraseDialog
        with patch("src.desktop.main_window.QMessageBox.warning"):
            dlg = PassphraseDialog(confirm=True)
            dlg._entry.setText("passphrase1")
            dlg._confirm_entry.setText("different")
            dlg._on_accept()
        # Dialog was not accepted
        assert dlg.passphrase == ""

    def test_dialog_confirm_mode_match_accepts(self):
        """§7.4  Matching passphrases in confirm mode sets passphrase and accepts."""
        _ensure_app()
        from src.desktop.main_window import PassphraseDialog
        dlg = PassphraseDialog(confirm=True)
        dlg._entry.setText("secure-passphrase")
        dlg._confirm_entry.setText("secure-passphrase")
        dlg._on_accept()
        assert dlg.passphrase == "secure-passphrase"

    def test_entry_uses_password_echo_mode(self):
        """§7.5  Entry fields use Password echo mode (masked input)."""
        _ensure_app()
        from PySide6.QtWidgets import QLineEdit
        from src.desktop.main_window import PassphraseDialog
        dlg = PassphraseDialog()
        assert dlg._entry.echoMode() == QLineEdit.EchoMode.Password


# ---------------------------------------------------------------------------
# §8  NoteEditorWidget  [BL B-84, B-85]
# ---------------------------------------------------------------------------


@_qt
class TestNoteEditorWidget:
    """§8 — NoteEditorWidget (B-84/B-85)."""

    def test_clear_resets_all_fields(self):
        """§8.1  clear() empties title, content, and unchecks encrypted."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        w._title_edit.setText("Hello")
        w._content_edit.setPlainText("World")
        w._encrypt_check.setChecked(True)
        w.clear()
        assert w.get_title() == ""
        assert w.get_content() == ""
        assert w.is_encrypted() is False

    def test_load_unencrypted_note(self):
        """§8.2  load() populates editor from an unencrypted Note."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        note = Note.create("My Title", "My Content")
        w = NoteEditorWidget()
        w.load(note)
        assert w.get_title() == "My Title"
        assert w.get_content() == "My Content"
        assert w.is_encrypted() is False

    def test_load_encrypted_note_shows_placeholder(self):
        """§8.3  load() shows [Encrypted] for encrypted note without content."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget, _ENCRYPTED_PLACEHOLDER
        note = Note.create("Secret", "placeholder", encrypted=True, blob=b"fakeciphertext")
        w = NoteEditorWidget()
        w.load(note)
        assert w.is_encrypted() is True
        assert w.get_content() == _ENCRYPTED_PLACEHOLDER

    def test_load_encrypted_note_with_decrypted_content(self):
        """§8.4  load() shows decrypted content when provided."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        note = Note.create("Secret", "placeholder", encrypted=True, blob=b"fakeciphertext")
        w = NoteEditorWidget()
        w.load(note, decrypted_content="The real secret")
        assert w.get_content() == "The real secret"

    def test_get_title_strips_whitespace(self):
        """§8.5  get_title() strips leading and trailing whitespace."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        w._title_edit.setText("  trimmed  ")
        assert w.get_title() == "trimmed"

    def test_show_encrypted_placeholder_replaces_content(self):
        """§8.6  show_encrypted_placeholder() replaces content with [Encrypted]."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget, _ENCRYPTED_PLACEHOLDER
        w = NoteEditorWidget()
        w._content_edit.setPlainText("visible text")
        w.show_encrypted_placeholder()
        assert w.get_content() == _ENCRYPTED_PLACEHOLDER

    def test_set_encrypted_checkbox_state(self):
        """§8.7  set_encrypted() controls the encrypted checkbox."""
        _ensure_app()
        from src.desktop.main_window import NoteEditorWidget
        w = NoteEditorWidget()
        w.set_encrypted(True)
        assert w.is_encrypted() is True
        w.set_encrypted(False)
        assert w.is_encrypted() is False


# ---------------------------------------------------------------------------
# §9  MainWindow CRUD  [BL B-85]
# ---------------------------------------------------------------------------


@_qt
class TestMainWindowCRUD:
    """§9 — MainWindow note CRUD operations (B-85)."""

    def _make_window(self, tmp_path):
        _ensure_app()
        from src.desktop.main_window import MainWindow
        store = DatabaseStore(tmp_path)
        config = ConfigStore(config_path=tmp_path / "config.json")
        registry = PluginRegistry()
        return MainWindow(store=store, config=config, registry=registry), store

    def test_populate_note_list_empty(self, tmp_path):
        """§9.1  populate_note_list() works with no notes in database."""
        w, _ = self._make_window(tmp_path)
        w.populate_note_list()
        assert w._note_list.count() == 0

    def test_populate_note_list_shows_notes(self, tmp_path):
        """§9.2  populate_note_list() shows all notes from the store."""
        w, store = self._make_window(tmp_path)
        store.add(Note.create("Alpha", "content 1"))
        store.add(Note.create("Beta", "content 2"))
        w.populate_note_list()
        assert w._note_list.count() == 2

    def test_populate_note_list_encrypted_shows_lock(self, tmp_path):
        """§9.3  Encrypted notes show lock emoji prefix in list."""
        w, store = self._make_window(tmp_path)
        note = Note.create("Secret", "x", encrypted=True, blob=b"fake")
        store.add(note)
        w.populate_note_list()
        item = w._note_list.item(0)
        assert "🔒" in item.text()

    def test_on_new_note_clears_editor(self, tmp_path):
        """§9.4  _on_new_note() clears editor and resets current note."""
        w, _ = self._make_window(tmp_path)
        w._current_note = Note.create("Old", "content")
        w._editor._title_edit.setText("Old")
        w._on_new_note()
        assert w._current_note is None
        assert w._editor.get_title() == ""

    def test_on_save_new_unencrypted_note(self, tmp_path):
        """§9.5  Saving new unencrypted note adds it to the store."""
        w, store = self._make_window(tmp_path)
        w._editor._title_edit.setText("New Note")
        w._editor._content_edit.setPlainText("Some content")
        w._editor.set_encrypted(False)
        w._on_save()
        notes_acc, notes_anon = store.list()
        all_notes = notes_acc + notes_anon
        assert len(all_notes) == 1
        assert all_notes[0].title == "New Note"

    def test_on_save_empty_title_shows_warning(self, tmp_path):
        """§9.6  Saving with empty title shows warning, does not save."""
        w, store = self._make_window(tmp_path)
        w._editor._title_edit.setText("")
        with patch("src.desktop.main_window.QMessageBox.warning"):
            w._on_save()
        _, anon = store.list()
        assert len(anon) == 0

    def test_on_save_updates_existing_note(self, tmp_path):
        """§9.7  Saving when a note is selected updates that note."""
        w, store = self._make_window(tmp_path)
        note = Note.create("Original", "content")
        store.add(note)
        w._current_note = store.get(note.id)
        w._editor.load(w._current_note)
        w._editor._title_edit.setText("Updated")
        w._editor._content_edit.setPlainText("new content")
        w._on_save()
        updated = store.get(note.id)
        assert updated.title == "Updated"
        assert updated.content == "new content"

    def test_on_delete_removes_note(self, tmp_path):
        """§9.8  _on_delete() removes the current note after confirmation."""
        w, store = self._make_window(tmp_path)
        note = Note.create("To Delete", "bye")
        store.add(note)
        w._current_note = store.get(note.id)
        with patch("src.desktop.main_window.QMessageBox.question",
                   return_value=__import__("PySide6.QtWidgets",
                                           fromlist=["QMessageBox"]).QMessageBox.StandardButton.Yes):
            w._on_delete()
        assert store.get(note.id) is None

    def test_on_delete_no_selection_shows_info(self, tmp_path):
        """§9.9  _on_delete() with no current note shows info message."""
        w, _ = self._make_window(tmp_path)
        w._current_note = None
        with patch("src.desktop.main_window.QMessageBox.information") as mock_info:
            w._on_delete()
        mock_info.assert_called_once()

    def test_on_delete_cancelled_does_not_remove(self, tmp_path):
        """§9.10  Cancelling the delete dialog leaves the note intact."""
        w, store = self._make_window(tmp_path)
        note = Note.create("Keep Me", "content")
        store.add(note)
        w._current_note = store.get(note.id)
        with patch("src.desktop.main_window.QMessageBox.question",
                   return_value=__import__("PySide6.QtWidgets",
                                           fromlist=["QMessageBox"]).QMessageBox.StandardButton.No):
            w._on_delete()
        assert store.get(note.id) is not None

    def test_on_save_encrypted_placeholder_updates_title_only(self, tmp_path):
        """§9.11  Saving encrypted note with placeholder content updates title only."""
        from src.desktop.main_window import _ENCRYPTED_PLACEHOLDER
        w, store = self._make_window(tmp_path)
        note = Note.create("OldTitle", "x", encrypted=True, blob=b"blob")
        store.add(note)
        w._current_note = store.get(note.id)
        w._editor.load(w._current_note)
        w._editor._title_edit.setText("NewTitle")
        # Content is placeholder (as set by load())
        w._on_save()
        updated = store.get(note.id)
        assert updated.title == "NewTitle"

    def test_note_list_item_has_user_role_id(self, tmp_path):
        """§9.12  Each list item stores note_id as UserRole data."""
        from PySide6.QtCore import Qt
        w, store = self._make_window(tmp_path)
        note = Note.create("X", "Y")
        store.add(note)
        w.populate_note_list()
        item = w._note_list.item(0)
        assert item.data(Qt.ItemDataRole.UserRole) == note.id


# ---------------------------------------------------------------------------
# §10  Idle auto-lock timer  [BL B-102]
# ---------------------------------------------------------------------------


@_qt
class TestIdleTimer:
    """§10 — Encrypted note idle auto-lock (B-102)."""

    def _make_window(self, tmp_path):
        _ensure_app()
        from src.desktop.main_window import MainWindow
        store = DatabaseStore(tmp_path)
        config = ConfigStore(config_path=tmp_path / "config.json")
        registry = PluginRegistry()
        return MainWindow(store=store, config=config, registry=registry)

    def test_start_idle_timer_activates_timer(self, tmp_path):
        """§10.1  start_idle_timer() activates the QTimer."""
        w = self._make_window(tmp_path)
        w.start_idle_timer()
        assert w._idle_timer.isActive()

    def test_reset_idle_timer_restarts_timer(self, tmp_path):
        """§10.2  reset_idle_timer() restarts the timer (isActive=True)."""
        w = self._make_window(tmp_path)
        w.start_idle_timer()
        w.reset_idle_timer()
        assert w._idle_timer.isActive()

    def test_idle_timeout_clears_passphrase(self, tmp_path):
        """§10.3  _on_idle_timeout() clears _cached_passphrase."""
        w = self._make_window(tmp_path)
        note = Note.create("S", "x", encrypted=True, blob=b"fake")
        w._current_note = note
        w._cached_passphrase = "secret"
        w._on_idle_timeout()
        assert w._cached_passphrase is None

    def test_idle_timeout_shows_placeholder_for_encrypted_note(self, tmp_path):
        """§10.4  _on_idle_timeout() shows [Encrypted] placeholder."""
        from src.desktop.main_window import _ENCRYPTED_PLACEHOLDER
        w = self._make_window(tmp_path)
        note = Note.create("S", "x", encrypted=True, blob=b"fake")
        w._current_note = note
        w._editor._content_edit.setPlainText("decrypted content")
        w._on_idle_timeout()
        assert w._editor.get_content() == _ENCRYPTED_PLACEHOLDER

    def test_idle_timeout_no_effect_for_unencrypted_note(self, tmp_path):
        """§10.5  _on_idle_timeout() does nothing when current note is unencrypted."""
        w = self._make_window(tmp_path)
        note = Note.create("U", "content")
        w._current_note = note
        w._editor._content_edit.setPlainText("content")
        w._on_idle_timeout()
        assert w._editor.get_content() == "content"

    def test_idle_timeout_no_effect_when_no_current_note(self, tmp_path):
        """§10.6  _on_idle_timeout() is a no-op when no note is open."""
        w = self._make_window(tmp_path)
        w._current_note = None
        w._on_idle_timeout()  # should not raise

    def test_auto_close_encrypted_note_delegates_to_timeout(self, tmp_path):
        """§10.7  auto_close_encrypted_note() calls the same logic as timeout."""
        w = self._make_window(tmp_path)
        note = Note.create("S", "x", encrypted=True, blob=b"fake")
        w._current_note = note
        w._cached_passphrase = "pwd"
        w.auto_close_encrypted_note()
        assert w._cached_passphrase is None

    def test_idle_timer_interval_is_5_minutes(self, tmp_path):
        """§10.8  QTimer interval is 5 minutes (300_000 ms)."""
        from src.desktop.main_window import _IDLE_TIMEOUT_MS
        w = self._make_window(tmp_path)
        assert w._idle_timer.interval() == _IDLE_TIMEOUT_MS
        assert _IDLE_TIMEOUT_MS == 300_000


# ---------------------------------------------------------------------------
# §11  Security level passphrase handling  [BL B-98]
# ---------------------------------------------------------------------------


@_qt
class TestSecurityLevelPassphrase:
    """§11 — security_level passphrase clearing logic (B-98)."""

    def _make_window(self, tmp_path):
        _ensure_app()
        from src.desktop.main_window import MainWindow
        store = DatabaseStore(tmp_path)
        config = ConfigStore(config_path=tmp_path / "config.json")
        registry = PluginRegistry()
        return MainWindow(store=store, config=config, registry=registry), store, config

    def test_high_mode_clears_passphrase_on_navigation(self, tmp_path):
        """§11.1  security_level=high clears passphrase when navigating away."""
        w, store, config = self._make_window(tmp_path)
        config.set("security_level", "high")
        note_a = Note.create("A", "content_a")
        note_b = Note.create("B", "content_b")
        store.add(note_a)
        store.add(note_b)
        # Simulate having note_a open with a cached passphrase
        w._current_note = store.get(note_a.id)
        w._cached_passphrase = "mysecret"
        # Navigate to note_b (unencrypted — won't prompt)
        w.populate_note_list()
        item_b = w._note_list.findItems("B", __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.MatchFlag.MatchExactly)
        # Simulate selection of note_b
        w._on_note_selected(
            w._note_list.item(1) if w._note_list.count() > 1 else None,
            None,
        )
        assert w._cached_passphrase is None

    def test_session_mode_does_not_clear_passphrase_on_navigation(self, tmp_path):
        """§11.2  security_level=session retains passphrase across navigation."""
        w, store, config = self._make_window(tmp_path)
        config.set("security_level", "session")
        note_a = Note.create("A", "content_a")
        note_b = Note.create("B", "content_b")
        store.add(note_a)
        store.add(note_b)
        w.populate_note_list()
        w._current_note = store.get(note_a.id)
        w._cached_passphrase = "mysecret"
        # Simulate selecting note_b from the list
        from PySide6.QtWidgets import QListWidgetItem
        item = w._note_list.item(1) if w._note_list.count() > 1 else w._note_list.item(0)
        if item:
            w._on_note_selected(item, None)
        # Passphrase retained in session mode
        assert w._cached_passphrase == "mysecret"

    def test_cache_passphrase_stores_value(self, tmp_path):
        """§11.3  _cache_passphrase() stores the passphrase regardless of mode."""
        w, _, _ = self._make_window(tmp_path)
        w._cache_passphrase("my-passphrase")
        assert w._cached_passphrase == "my-passphrase"

    def test_try_decrypt_note_returns_none_without_passphrase(self, tmp_path):
        """§11.4  _try_decrypt_note() returns None when no passphrase cached."""
        w, _, _ = self._make_window(tmp_path)
        note = Note.create("S", "x", encrypted=True, blob=b"fake")
        result = w._try_decrypt_note(note)
        assert result is None

    def test_try_decrypt_note_returns_none_on_bad_passphrase(self, tmp_path):
        """§11.5  _try_decrypt_note() returns None on wrong passphrase (InvalidTag)."""
        w, _, _ = self._make_window(tmp_path)
        # Create a real encrypted note
        from src.core.security import KeyManager
        from src.core.blob_codec import BlobCodec
        km = KeyManager("correct-passphrase", iterations=_TEST_ITERATIONS)
        engine = km.get_engine()
        raw = BlobCodec.encode({"title": "S"}, b"secret content")
        blob = BlobCodec.encrypt(raw, engine)
        note = Note.create("S", "x", encrypted=True, blob=blob)
        w._cached_passphrase = "wrong-passphrase"
        result = w._try_decrypt_note(note)
        assert result is None


# ---------------------------------------------------------------------------
# §12  System tray  [BL B-97]
# ---------------------------------------------------------------------------


@_qt
class TestSystemTray:
    """§12 — System tray icon and context menu (B-97)."""

    def _make_window(self, tmp_path):
        _ensure_app()
        from src.desktop.main_window import MainWindow
        store = DatabaseStore(tmp_path)
        config = ConfigStore(config_path=tmp_path / "config.json")
        registry = PluginRegistry()
        return MainWindow(store=store, config=config, registry=registry)

    def test_tray_icon_created(self, tmp_path):
        """§12.1  MainWindow creates a QSystemTrayIcon."""
        from PySide6.QtWidgets import QSystemTrayIcon
        w = self._make_window(tmp_path)
        assert isinstance(w._tray, QSystemTrayIcon)

    def test_tray_has_context_menu(self, tmp_path):
        """§12.2  Tray icon has a context menu."""
        w = self._make_window(tmp_path)
        assert w._tray.contextMenu() is not None

    def test_tray_menu_has_show_hide_action(self, tmp_path):
        """§12.3  Tray context menu contains Show/Hide action."""
        w = self._make_window(tmp_path)
        actions = w._tray.contextMenu().actions()
        texts = [a.text() for a in actions]
        assert any("Show" in t or "Hide" in t for t in texts)

    def test_tray_menu_has_quit_action(self, tmp_path):
        """§12.4  Tray context menu contains Quit action."""
        w = self._make_window(tmp_path)
        actions = w._tray.contextMenu().actions()
        texts = [a.text() for a in actions]
        assert any("Quit" in t for t in texts)

    def test_toggle_visibility_hides_visible_window(self, tmp_path):
        """§12.5  _toggle_visibility() hides a visible window."""
        w = self._make_window(tmp_path)
        w.show()
        assert w.isVisible()
        w._toggle_visibility()
        assert not w.isVisible()

    def test_toggle_visibility_shows_hidden_window(self, tmp_path):
        """§12.6  _toggle_visibility() shows a hidden window."""
        w = self._make_window(tmp_path)
        w.hide()
        w._toggle_visibility()
        assert w.isVisible()

    def test_close_event_hides_to_tray(self, tmp_path):
        """§12.7  closeEvent() hides the window instead of closing when tray is available."""
        from PySide6.QtGui import QCloseEvent
        w = self._make_window(tmp_path)
        w.show()
        # close_behavior="minimize" -> hide-to-tray without opening the ask dialog
        w._config.set("close_behavior", "minimize")
        # Patch tray to indicate system tray is available
        with patch.object(w._tray, "isSystemTrayAvailable", return_value=True), \
             patch.object(w._tray, "isVisible", return_value=True):
            event = QCloseEvent()
            w.closeEvent(event)
            assert event.isAccepted() is False  # ignored = hidden to tray
