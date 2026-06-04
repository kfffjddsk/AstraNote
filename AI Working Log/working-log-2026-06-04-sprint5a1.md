# AI Working Log — 2026-06-04 (Sprint 5A.1)

## Session Summary

**AI Partner:** Astra (GitHub Copilot)
**Sprint:** 5A.1 — Sync Server MVP
**Outcome:** First shipping increment of Sprint 5. FastAPI sync server, JWT bearer auth, push/pull endpoints, per-account isolation, CLI sync commands, and 40 new tests landed. Total suite **609 passed, 1 skipped**.

## What Was Delivered (Backlog B-86, B-88, B-90 CLI half, B-94)

| ID | Item | Notes |
|----|------|-------|
| B-86 | FastAPI sync server skeleton | New `src/server/` package: app factory, settings, db, models, schemas, security, routers. `POST /sync/push` + `GET /sync/pull?since=` with last-write-wins on `modified_at`. |
| B-88 | JWT bearer auth | `authlib.jose` HS256; `Authorization: Bearer …`; missing / malformed / bad-signature / expired → 401 with R16.8 error envelope. Pytest-aware secret bootstrap (`PYTEST_CURRENT_TEST` falls back to deterministic secret). |
| B-90 (CLI half) | `astranotes sync login/logout/push/pull` | New `sync` Click group; `SyncClient` httpx wrapper; on-disk token cache at `<data-dir>/.sync_token` (owner-only perms). GUI sync button still pending in 5B. |
| B-94 | Per-account data isolation | Server always overrides `NotePayload.account_id` with `claims.account_id`. Composite PK `(note_id, account_id)` lets the same UUID co-exist under different accounts. Three explicit isolation regression tests. |

## Files Touched

### New

- `src/server/__init__.py`, `app.py`, `settings.py`, `db.py`, `models.py`, `schemas.py`, `security.py`, `main.py`
- `src/server/routers/__init__.py`, `auth.py`, `sync.py`
- `src/core/sync_client.py` — sync-only httpx wrapper + token cache + `SyncError` hierarchy.
- `tests/test_sprint5a.py` — 40 tests across 8 classes.

### Modified

| File | Change |
|------|--------|
| `src/cli.py` | New `sync` command group with `login` / `logout` / `push` / `pull` subcommands. |
| `src/core/notes.py` | New helpers: `list_pending_push()`, `mark_synced()`, `max_synced_at()`, `upsert_remote()`. |
| `requirements.txt` | Added explicit `httpx` dependency. |
| `planning/backlog.md` | Sprint 5A section flipped to *In Progress*; B-86/B-88/B-94 → ✅ Done (5A.1); B-90 annotated CLI-half done. |
| `planning/traceability-metrics.md` | v2.9; NFR-4 test count 570 → 609; new Sprint 5A.1 completion note. |
| `docs/test-execution-evidence.md` | New Sprint 5A.1 evidence section with 40-test breakdown + design-decision notes. |

## Test Results

```
609 passed, 1 skipped in ~58s
```

- 569 pre-existing tests still green.
- 40 new sync-server tests (`tests/test_sprint5a.py`).
- 1 POSIX-only permission test still skipped on Windows.

## Process Notes

- Used a Senior-SDE subagent to scaffold the server package; it returned no transcript (the run hit an empty-output edge case) but left a clean, well-commented codebase including helper additions to `DatabaseStore`. Closed the gap personally: added the `sync` CLI group, `max_synced_at`, the test suite, and docs.
- **httpx 0.28** detail: `httpx.ASGITransport` is async-only. Tests inject `fastapi.testclient.TestClient` directly into `SyncClient(client=...)` — sync-compatible and hermetic.
- Pytest-aware JWT secret prevents tests from leaking a real production secret while keeping fixtures hermetic.

## Known Follow-ups (Sprint 5A.2)

1. **Postgres backend (B-44)** — Swap `DATABASE_URL` to PG; verify SQLAlchemy ORM works untouched.
2. **Least-privilege PG role (B-53)** + **`sslmode=require` (B-63)**.
3. **HTTPS/TLS middleware (B-92)** — reject HTTP unless `ASTRANOTES_DEV_HTTP=1`.
4. **Connection pool tuning + ≥10-user load test (B-93)**.
5. **Rate limiting via `slowapi` (B-95)** — 60 req/min/account.
6. **Library hygiene** — migrate `authlib.jose` → `joserfc` (vendor deprecation); replace `HTTP_422_UNPROCESSABLE_ENTITY` with `HTTP_422_UNPROCESSABLE_CONTENT` (Starlette deprecation).
7. **Alembic for server schema** — currently `Base.metadata.create_all` at startup; move to a dedicated migration chain before Sprint 5B.

## Discussion-list candidates (D-xx)

To add to `Copilot/discussion-list.md` after team review:

- **D-?**: When a 5A.2 client repeatedly fails to push (e.g. connectivity loss for hours), should the local `synced_at` watermark be reset, or should we track `failed_push_count` per note and surface it in the GUI?
- **D-?**: Should the server hold an audit log of push/pull events analogous to the local `AuditLogger`, or is local audit sufficient?
- **D-?**: Server-side encrypted-blob retention policy when an account is deleted — instant purge vs. 30-day soft-delete window?
