# AI Working Log — 2026-05-21

## Session Summary

**AI Partner:** Astra (GitHub Copilot)  
**Sprint:** Sprint 2  
**Outcome:** Sprint 2 fully implemented and all tests passing.

---

## Work Completed

### New Files Created

| File | Purpose |
|------|---------|
| `src/core/auth.py` | AccountStore (bcrypt registration + auth + rate limiting), SessionManager (24h token), validate_username, AuthError, RateLimitError |
| `alembic/versions/3b7c9f2d8a1e_sprint_two_accounts.py` | Alembic migration adding `accounts` table (chained from Sprint 0 baseline) |
| `tests/test_sprint2.py` | 93 tests across 16 sections covering all Sprint 2 backlog items |

### Modified Files

| File | Change |
|------|--------|
| `src/core/notes.py` | DiskFullError, ENOSPC handling, hybrid storage (≥5 MB threshold), account_id column integration, disassociate_account(), associate_anonymous_notes(), set_note_account_id(), list() scoping fix |
| `src/cli.py` | register, login, logout, delete-account commands; add/list updated for session; DiskFullError handling |
| `requirements.txt` | Added bcrypt |
| `planning/backlog.md` | Sprint 2 section updated to Done ✅ |
| `README.md` | Status line updated to Sprint 2 complete; project structure and milestones updated |

---

## Test Results

```
233 passed, 1 skipped in 68.62s
```

- Sprint 1 tests: 140 — all still pass (zero regressions)
- Sprint 2 new tests: 93 — all pass
- Skipped: 1 (POSIX file permission test, skipped on Windows by design)

---

## Issues Fixed During Testing

1. **`CliRunner(mix_stderr=False)`** — Click version in venv does not support this kwarg; removed.
2. **`TestDatabaseUrlEnvVarOnly` docstring false-positive** — Test was scanning docstring lines as code; fixed to skip comment/docstring lines.
3. **bcrypt not installed in venv** — `pip install bcrypt` into `.venv` resolved.

---

## Architectural Decisions

- `AccountStore` uses a separate `_AuthBase` (DeclarativeBase subclass) sharing same `notes.db` file via independent `create_all()` — no foreign key constraints between tables by design (offline-first).
- Hybrid storage: encrypted notes ≥5 MB written to `<data-dir>/files/<note_id>.bin`; `payload_location` column distinguishes inline vs filesystem.
- `SessionManager.create()` calls `os.chmod()` for POSIX-only permission restriction; Windows skips silently.
- Rate limiting: 5 consecutive failures → 5-minute lockout stored in `locked_until` column (ISO-8601); resets on successful auth.
- Backward compatibility: `list()` flat format preserved when logged out, so all Sprint 1 tests pass unchanged.

---

## Session 2 (continuation — same day)

**Focus:** Auth security review, branch-coverage gap tests, None-check hardening, full Sprint 2 documentation sync.

### Auth Security Review — 3 Bugs Fixed

| Bug | Root Cause | Fix |
|---|---|---|
| `validate_username` trailing-`\n` bypass | `$` allows `\n` before end of string | Changed to `\Z` (absolute end-of-string) |
| `register()` uncaught `IntegrityError` on race condition | `UNIQUE` violation propagated as `IntegrityError` | Wrapped `commit()` in `except IntegrityError → rollback → ValueError` |
| `SessionManager.load()` corrupt file not cleaned up | `json.JSONDecodeError` handler returned `None` without deleting file | Added `path.unlink(missing_ok=True)` in except block, guarded by inner `try/except OSError` |

Bug-regression tests added in `§16`/`§17` of `tests/test_sprint2.py`.

### §18 TestBranchCoverageGaps — 8 New Tests

Added to `tests/test_sprint2.py` to reach 100% branch coverage on all core modules:

| Test | Branch covered |
|---|---|
| `test_delete_nonexistent_account_is_noop` | `auth.py:314→exit` — delete when row is None |
| `test_create_session_succeeds_when_chmod_raises` | `auth.py:373-374` — `os.chmod` `OSError` absorbed |
| `test_load_corrupt_session_returns_none_when_unlink_fails` | `auth.py:403-404` — unlink `OSError` absorbed |
| `test_sqlite_disk_io_error_raises_disk_full_error` | `notes.py:103` — `OperationalError("disk I/O error")` |
| `test_sqlite_disk_full_msg_raises_disk_full_error` | `notes.py:103` — `OperationalError("disk full")` |
| `test_add_large_encrypted_non_enospc_oserror_propagates` | `notes.py:326` — non-ENOSPC `OSError` re-raised |
| `test_get_filesystem_note_missing_payload_returns_note_with_none_blob` | `notes.py:372-373` — missing payload → `blob=None` |
| `test_delete_filesystem_note_tolerates_already_removed_payload` | `notes.py:453-454` — idempotent delete |

Also added `# pragma: no branch` on `notes.py:95` for loop (structurally unreachable normal exit).
Added `_wipe_test_db_before_session` session-scoped autouse fixture in `conftest.py`.

### None-check hardening

Added `assert <obj> is not None` before every attribute access on objects returned from `session.get()` and `store.get_by_username()` — 12 total locations across `tests/test_sprint2.py`.

### Final Test Results

```
246 passed, 1 skipped
100% branch coverage on: auth.py, notes.py, blob_codec.py, security.py, plugin_base.py, __init__.py
```

### Document Updates (Session 2)

| Document | Change |
|---|---|
| `planning/backlog.md` | B-81 ✅ Done, B-96 ✅ Done; Sprint 2 test count → 246 |
| `planning/traceability-metrics.md` | v2.5; 22 items WT→FT, 2 items WT→PT; totals FT 49→71, PT 5→7, WT 73→49; Sprint 2 completion note added; §5.1 gap analysis updated |
| `planning/design.md` | Status → Sprint 2 complete, 246 tests, 100% coverage; `[LOG 05-21]` |
| `planning/prd.md` | Version 1.3; date 2026-05-21 |

### Deferred Items (Sprint 3)

- FR-79: `--local` flag on `add` (opt-out of account association)
- FR-103: Binary note auto-export to `exports/` directory
- B-25/B-71: `AuditLogger` — audit.log written during note operations

