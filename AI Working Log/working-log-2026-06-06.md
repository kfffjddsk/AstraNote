# AI Working Log — 2026-06-06

## Session Summary

**AI Partner:** Claude (claude-sonnet-4-6)
**Sprint:** 5C — Installed-App Packaging
**Outcome:** All packaging / installed-app changes implemented and passing. 669 tests, 1 skipped — suite unchanged (no new tests needed; changed tests updated to match new path contract).

---

## Changes Made

### `src/core/paths.py` (NEW)

Centralised platform-appropriate directory helper:
- `platform_data_dir()` — Windows `%APPDATA%\AstraNotes`, macOS `~/Library/Application Support/AstraNotes`, Linux `$XDG_DATA_HOME/AstraNotes`
- `platform_config_dir()` — same paths as above (on POSIX uses `$XDG_CONFIG_HOME`)

Both functions use stdlib only (`os`, `platform`, `pathlib`). No new dependency.

**Why:** CLI and GUI previously used different defaults (`~/.astranotes` vs `~/astranotes`) which meant they accessed separate databases. Both now call `platform_data_dir()` — same directory every time regardless of how the app is launched.

### `src/core/config.py`

- Replaced inline `_default_config_path()` logic with `platform_config_dir() / "config.json"`.
- Removed now-unused `os` and `platform` stdlib imports.
- Docstring updated to show all three OS paths.

### `src/desktop/app_controller.py`

- `_resolve_data_dir()` fallback changed from `Path.home() / "astranotes"` → `platform_data_dir()`.
- Google credential resolution now checks three sources in order: `config.json` → `ASTRANOTES_GOOGLE_CLIENT_ID` env var → `bundled_defaults.py`.
- Added standalone `main()` entry-point function for `astranotes-gui` console script.
- Added `import os` and imports for `platform_data_dir`, `bundled_defaults`.

### `src/cli.py`

- `_validate_data_dir()` fallback changed from `Path.home() / ".astranotes"` → `platform_data_dir()` (lazy import inside function to avoid circular).

### `src/core/auth.py`

- `_SESSION_EXPIRY_HOURS`: 24 → 720 (30 days). Installed apps should not force re-login daily.

### `src/server/main.py`

- Added `server_main()` function — entry point for `astranotes-server` console script. Reads `ASTRANOTES_SYNC_HOST` / `ASTRANOTES_SYNC_PORT` env vars.
- `if __name__ == "__main__"` block now delegates to `server_main()`.

### `src/desktop/bundled_defaults.py` (NEW)

Patchable placeholder for build-time credentials:
```python
GOOGLE_CLIENT_ID: str = ""
GOOGLE_CLIENT_SECRET: str = ""
```
At packaging time, patch this file to embed credentials so end-users don't need to configure `config.json`. The `AppController` checks this as the lowest-priority fallback after config.json and env vars.

### `requirements.txt`

- Removed `authlib` (migrated to `joserfc` in Sprint 5B TD-01).
- Added `joserfc` (JWT signing/verification).
- Added `redis` (optional Redis rate-limiter backend from Sprint 5B TD-03).

### `pyproject.toml` (NEW)

Standard PEP 517/518 packaging metadata:
- `project.scripts` maps three entry points: `astranotes`, `astranotes-gui`, `astranotes-server`.
- `[project.optional-dependencies] dev` groups test tooling.
- `[tool.setuptools.packages.find]` discovers all `src.*` packages.
- `[tool.pytest.ini_options]` moves test config out of command line.

### `tests/test_sprint1.py`

- `test_data_dir_defaults_to_home_astranotes` renamed to `test_data_dir_defaults_to_platform_data_dir`. Old test patched `Path.home` which no longer controls the default; new test patches `src.core.paths.platform_data_dir`.

### `tests/test_sprint4.py`

- `test_resolve_data_dir_fallback_to_home` renamed to `test_resolve_data_dir_fallback_to_platform_data_dir`. Assertion updated to compare against `platform_data_dir()` return value.

---

## Test Results

```
669 passed, 1 skipped
```

No new tests added — all 669 existing tests pass with updated path contract.

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Use `%APPDATA%` (roaming) rather than `%LOCALAPPDATA%` on Windows | Matches the existing config.json location; consistent across the app; acceptable for a course project where multi-machine roaming is not a concern |
| Keep `src` as package name (not rename to `astranotes`) | Renaming would break every import across ~30 files; not worth the churn for a course project |
| Session 30-day expiry | Standard for installed desktop apps; users can still sign out explicitly; session file is per-data-dir so no cross-user leak |
| `bundled_defaults.py` over env-only | Allows credentials to be baked into a PyInstaller bundle without an installer-step that writes env vars; env-var override still works for CI |
