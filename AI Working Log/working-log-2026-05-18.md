# Working Log — 2026-05-18

## Summary
Sprint 1 full implementation session. All Sprint 1 backlog items delivered, 113 new tests written, all 159 tests passing (46 Sprint 0 + 113 Sprint 1). Root-caused and fixed a subtle Alembic/environment-variable bug. Applied defensive test improvements requested during review. Sprint 1 committed and ready to push.

---

## What Changed

### `src/cli.py` *(new)*
- Click CLI with `add`, `get`, `list`, `update`, `delete` commands.
- `--data-dir` global option + `ASTRANOTES_DATA_DIR` env var. [B-19]
- `_validate_data_dir`: creates dir if missing, write-probe, is-dir check. [B-36]
- `_check_title` / `_check_content`: null byte + control-char rejection at CLI boundary. [B-52]
- `add --encrypt`: `click.prompt(hide_input=True, confirmation_prompt=True)`. [B-32]
- All error paths call `sys.exit(1)`. [B-23]
- Friendly OSError/PermissionError messages. [B-39]
- Auto-discovers plugins from `plugins/` directory on startup. [B-37]

### `src/core/notes.py`
- WAL journal mode via `event.listen(engine, "connect", _enable_wal)`. [B-66]
- `_execute_with_retry(fn)`: up to 5 attempts, exponential back-off, retries only on "database is locked". [B-66]
- All five store methods (`add`, `get`, `update`, `delete`, `list`) wrapped in retry.

### `src/core/plugin_base.py`
- `discover_plugins(plugin_dir, registry)`: scans `*.py`, skips `_`-prefixed files, imports via `importlib.util`, registers all `PluginBase` subclasses. Import/instantiation errors are logged and skipped. [B-37]

### `alembic/` + `alembic.ini` *(new)*
- `alembic init alembic` scaffold. [B-65]
- `env.py`: imports `_Base` from `src.core.notes`; `ASTRANOTES_DB_URL` env var overrides URL for CI/test injection; uses `create_engine(url)` directly (avoids `engine_from_config` quirks on Windows).
- Migration `e2f2634ce4f7_sprint_zero_baseline.py`: creates all columns of the `notes` table.

### `tests/test_sprint1.py` *(new)*
- 113 tests across 13 sections covering all Sprint 1 backlog items plus edge/corner/rare cases.
- §1 WAL + retry; §2 PluginBase/PluginRegistry; §3 plugin discovery; §4 input validation; §5 --data-dir; §6–10 all five CLI commands; §11 exit-code sweep; §12 passphrase confirmation; §13 Alembic.

### `tests/test_sprint1.py` *(test quality fixes)*
- Added `None` guard + clear assertion message before `fetchone()` index in `test_wal_mode_enabled`.
- Added `None` guard before `.title` access in `test_cli_update_title`.
- Added `None` guard before `.content` access in `test_cli_update_content`.

### `pytest.ini`
- Added `cli: CLI integration tests using CliRunner` marker.

---

## Key Decisions / Root Causes

### Alembic Python API silently skipping migrations
`alembic_cmd.upgrade(cfg, "head")` was creating no DB file and emitting no "Running upgrade" log. Root cause: `ASTRANOTES_DB_URL` was set as a persistent Windows environment variable (left over from a prior manual debug session). `alembic/env.py` overrides `sqlalchemy.url` with this env var, so every in-process test was migrating against the wrong (already-at-head) database. Fix:
- `monkeypatch.delenv("ASTRANOTES_DB_URL", raising=False)` at the top of both Alembic migration tests — makes them immune to stale shell state.
- Switched `env.py` from `engine_from_config()` to `create_engine(url)` for simplicity.

### Click 8.3.x `CliRunner` — no `mix_stderr`
`CliRunner(mix_stderr=False)` raises `TypeError` in Click 8.3.x (parameter removed). Use `CliRunner()` with no kwargs; stderr is merged into `result.output`.

### KDF iterations mismatch in encrypt/decrypt CLI tests
Notes created via `make_encrypted_note()` use `_TEST_ITERATIONS=1_000`; CLI decrypts with `DEFAULT_ITERATIONS=100_000` → different key → `InvalidTag`. Fix: encrypt/decrypt round-trip tests go entirely through the CLI (consistent iterations on both sides).

---

## Test Counts
| Suite | Tests | Status |
|---|---|---|
| Sprint 0 (`test_core.py`) | 46 | ✅ all pass |
| Sprint 1 (`test_sprint1.py`) | 113 | ✅ all pass |
| **Total** | **159** | ✅ |
*(1 `@pytest.mark.stress` test deselected by default)*

---

## ⚠️ TODO — Review Sprint 1 Implementation Before Next Session

Before closing out Sprint 1 as "Done", the following should be reviewed:

1. **`src/cli.py` full review** — verify all five commands handle all edge cases cleanly, error messages are user-friendly, and the plugin hook call sites are correct.
2. **`alembic/env.py`** — confirm the `ASTRANOTES_DB_URL` override priority is intentional and documented; add a comment warning that setting this env var in a dev shell will redirect all in-process migrations.
3. **`_execute_with_retry` back-off timing** — current base delay is `0.05 s`; confirm this is acceptable for production (may want to make it configurable).
4. **Plugin discovery in CLI startup** — `discover_plugins` is called unconditionally; if `plugins/` dir doesn't exist it returns `[]` silently, but confirm the log output is acceptable.
5. **Definition of Done checklist** — walk through `Copilot/Definition of Done.md` item by item for Sprint 1 before marking backlog items closed.

---

## Commits This Session
- `dd25eba` — docs: update sprint-zero-plan checkboxes (prior session)
- `3dda7a9` — docs: reorganize backlog.md by sprint (prior session)
- `3c7c3aa` — feat(sprint-1): implement CLI, WAL mode, plugin discovery, Alembic
- `bd02181` — test: add None guards before attribute access on store.get() results
