# AI Working Log — 2026-06-04 (Sprint 5A.2)

## Session Summary

**AI Partner:** Astra (GitHub Copilot)
**Sprint:** 5A.2 — Sync Server Hardening
**Outcome:** Production-readiness pass on top of the Sprint 5A.1 MVP. HTTPS-only middleware, in-process per-account rate limiter, PostgreSQL DSN validation + pool tuning, ops doc, and 22 new tests landed. Total suite **631 passed, 1 skipped**.

## What Was Delivered (Backlog B-44, B-53, B-63, B-92, B-93, B-95)

| ID | Item | Notes |
|----|------|-------|
| B-92 | HTTPS enforcement | New `HTTPSEnforcementMiddleware` (`src/server/middleware.py`). Pure-ASGI; rejects plain HTTP with 400 + R16.8 envelope unless scope `scheme == "https"`, `X-Forwarded-Proto: https`, loopback host, or `/healthz`. Driven by `ServerSettings.enforce_https` (default `True` in prod, `False` under pytest, flipped off by `ASTRANOTES_DEV_HTTP=1`). |
| B-95 | Rate limiting | `AccountRateLimiter` in `src/server/rate_limit.py` — stdlib-only sliding-window keyed on `account_id`. Per-bucket `deque[float]`, `threading.Lock` for thread-safety. Wired into `/sync/push` + `/sync/pull` via a `_rate_limit_check` FastAPI dependency. Returns 429 with `Retry-After`. |
| B-44 / B-63 | Postgres backend + SSL guard | `make_engine()` now branches on `postgresql://`: parses the DSN, requires `sslmode=require` / `verify-ca` / `verify-full` for any non-loopback host, raises `ValueError` otherwise. SQLite path unchanged. |
| B-93 | Connection pool + concurrent load | Postgres engines get `pool_size`, `max_overflow`, `pool_pre_ping`, `pool_recycle=3600` from new settings fields. `TestConcurrentSync` exercises 10 parallel users register→login→push→pull through `ThreadPoolExecutor`. |
| B-53 | Least-privilege role | Documented in `docs/operations.md` with verbatim SQL. (Server enforces no DDL via the role itself; nothing to wire in code.) |

## Files Touched

### New

- `src/server/middleware.py` — `HTTPSEnforcementMiddleware`.
- `src/server/rate_limit.py` — `AccountRateLimiter`, `RateLimitExceeded`.
- `docs/operations.md` — production deployment guide (env vars, HTTPS, rate limit, Postgres least-privilege SQL, SSL guard).
- `tests/test_sprint5a2.py` — 22 tests across 6 classes.
- `AI Working Log/working-log-2026-06-04-sprint5a2.md` — this file.

### Modified

| File | Change |
|------|--------|
| `src/server/settings.py` | Added `enforce_https`, `rate_limit_per_minute`, `db_pool_size`, `db_max_overflow` fields. `__post_init__` resolves `enforce_https=None` to `not _running_under_pytest()` so Sprint 5A.1 fixtures keep working. `from_env()` reads `ASTRANOTES_DEV_HTTP`, `ASTRANOTES_RATE_LIMIT_PER_MIN`, `ASTRANOTES_DB_POOL_SIZE`, `ASTRANOTES_DB_MAX_OVERFLOW`. |
| `src/server/db.py` | `make_engine()` now handles `postgresql://` URLs: enforces `sslmode=require` on non-loopback, applies pool tuning. |
| `src/server/routers/sync.py` | New `_rate_limit_check` dependency replaces `current_account` on `/sync/push` and `/sync/pull`. |
| `src/server/app.py` | Adds `HTTPSEnforcementMiddleware` before exception handlers; instantiates `app.state.rate_limiter`; replaces deprecated `HTTP_422_UNPROCESSABLE_ENTITY` with `HTTP_422_UNPROCESSABLE_CONTENT` (with version-safe fallback). |
| `planning/backlog.md` | Sprint 5A.2 section → ✅ Done; B-44/B-53/B-63/B-92/B-93/B-95 → ✅ Done. |
| `planning/traceability-metrics.md` | v2.9 → v2.10; NFR-4 test count 609 → 631; Sprint 5A.2 completion note appended; R16 sslmode (NFR-14) updated. |
| `docs/test-execution-evidence.md` | New Sprint 5A.2 evidence section. |

## Test Results

```
631 passed, 1 skipped in ~46s
```

- 609 pre-existing tests still green (no Sprint 5A.1 regressions).
- 22 new hardening tests (`tests/test_sprint5a2.py`).
- 1 POSIX-only permission test still skipped on Windows.

### Sprint 5A.2 breakdown (22 tests)

| Class | Count | Focus |
|-------|-------|-------|
| `TestHttpsEnforcement` | 5 | rejection, dev-opt-out, loopback, `X-Forwarded-Proto`, `/healthz` bypass |
| `TestRateLimit` | 5 | under-limit, over-limit + `Retry-After`, 429 envelope shape, per-account isolation, login not rate-limited |
| `TestRateLimiterUnit` | 4 | under-limit, raise-at-limit, sliding window (`monkeypatch time.time`), 20-thread × 10-call thread-safety |
| `TestPostgresDsnValidation` | 3 | localhost OK, remote without `sslmode` → `ValueError`, remote with `sslmode=require` OK |
| `TestConcurrentSync` | 1 | 10 users in parallel via `ThreadPoolExecutor`, account isolation holds |
| `TestSettingsHardening` | 4 | `enforce_https` default flip, `ASTRANOTES_DEV_HTTP`, `ASTRANOTES_RATE_LIMIT_PER_MIN`, pool field defaults |

## Design Decisions

- **In-process limiter over `slowapi`.** The mandate (B-95) said 60 req/min/account. `slowapi` would have brought Redis or in-process memory anyway, plus a new dependency, plus async-only middleware coupling, plus another set of error-envelope quirks. A 40-line stdlib `AccountRateLimiter` (`collections.deque` + `threading.Lock`) gives us deterministic monkeypatch-friendly tests, zero new requirements lines, and slots straight into the existing FastAPI dependency chain. Single-process deployments only — when we go multi-worker we'll revisit (see follow-ups).
- **Pure-ASGI HTTPS middleware over `BaseHTTPMiddleware`.** Starlette's `BaseHTTPMiddleware` has well-known interaction quirks with sync FastAPI routes (it forces request bodies into memory and changes exception propagation). A pure-ASGI class with `__call__(scope, receive, send)` is ~70 lines, free of side-effects, and writes its rejection body directly.
- **`enforce_https=None` sentinel.** Sprint 5A.1's `ServerSettings(...)` fixtures don't pass `enforce_https`. Adding a hard `True` default would have broken 40 existing tests. Resolving `None → not _running_under_pytest()` in `__post_init__` preserves backward compatibility while keeping prod safe-by-default. Explicit `True` / `False` from a test (or `from_env()`) still wins.
- **Postgres validation before driver lookup.** `make_engine()` parses the DSN with `urllib.parse.urlparse` and raises *before* calling `sqlalchemy.create_engine`, so the test suite can validate the rule without needing `psycopg2` installed. Tests use `try/except` to accept `ImportError` / `ModuleNotFoundError` from SQLAlchemy's dialect lookup while rejecting our `ValueError`.
- **`Retry-After` via existing handler.** The Sprint 5A.1 exception handler already passed `exc.headers` through. The 429 path just sets `headers={"Retry-After": str(n)}` on the `HTTPException` and the envelope falls out naturally — no handler changes required.
- **422 constant hygiene.** Starlette is mid-rename (`HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT`). Used `hasattr` chain instead of `getattr` because `getattr`'s default arg is always evaluated, which re-triggers the deprecation warning even when the new name is present. Now warning-free.

## Process Notes

- Wrote the whole hardening pass in one session; ran `pytest tests/test_sprint5a2.py` after each milestone (settings → middleware → limiter → router wiring → app glue) to catch wiring bugs early.
- One iteration was needed on the deprecation warning: `getattr(status, NEW, getattr(status, OLD, 422))` still fires the `OLD` access because Python evaluates default args eagerly. Replaced with explicit `hasattr` chain.

## Known Follow-ups

1. **Multi-worker rate limiting.** Today's `AccountRateLimiter` is per-process. When we deploy with multiple uvicorn workers we will need a shared backend (Redis or a sticky-session reverse proxy). Track as a Sprint 5C item.
2. **`authlib.jose` → `joserfc` migration.** Still emitting the `AuthlibDeprecationWarning` at import. Vendor warns of breaking changes before 2.0. Should be done before Sprint 5B's OAuth work.
3. **Alembic for server schema.** Sprint 5A still bootstraps with `Base.metadata.create_all`. The least-privilege Postgres role we documented in `docs/operations.md` explicitly *cannot* run DDL — so deployments will need a separate migration role + Alembic chain before we can ship the Postgres backend.
4. **B-93 stretch goal — locust / k6 load run.** The 10-user `ThreadPoolExecutor` test proves correctness under concurrency, not throughput. A proper load-test rig is a separate item.

## Discussion-list candidates (D-xx)

To add to `Copilot/discussion-list.md` after team review:

- **D-?**: Should `/auth/login` participate in the per-account limiter (currently exempt — relies on the `AccountStore` 5-attempt lockout)? Or stay decoupled?
- **D-?**: What's the right `Retry-After` precision — seconds (current) or `HTTP-date`? Currently always integer seconds.
- **D-?**: Single shared Postgres database vs. one per tenant once we get to billing — affects role provisioning + the `sslmode` story.
