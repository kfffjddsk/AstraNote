# AstraNotes Sync Server — Operations Guide

This document covers the production-deployment knobs introduced in
Sprint 5A.2. The defaults are safe (HTTPS-required, rate-limited) so a
deployer only needs to set the secrets and the database URL.

## Required environment variables

| Variable | Purpose | Required? |
|----------|---------|-----------|
| `ASTRANOTES_JWT_SECRET` | HS256 signing key for bearer tokens. | **Yes** |
| `ASTRANOTES_SYNC_DATABASE_URL` | SQLAlchemy URL for the sync server's database (Postgres in production). | **Yes** in production (defaults to local SQLite for the MVP). |

If `ASTRANOTES_JWT_SECRET` is missing outside a pytest run the server
refuses to boot — see `ServerSettings.from_env()`.

## Optional environment variables

| Variable | Default | Effect |
|----------|---------|--------|
| `ASTRANOTES_SYNC_DATA_DIR` | `./astranotes_server_data` | Where the account store + audit log live. |
| `ASTRANOTES_JWT_EXPIRY_HOURS` | `24` | Bearer-token lifetime. |
| `ASTRANOTES_DEV_HTTP` | unset | When `1` / `true`, disables the HTTPS-only middleware (loopback dev only). |
| `ASTRANOTES_RATE_LIMIT_PER_MIN` | `60` | Sliding-window quota per account for `/sync/push` + `/sync/pull`. |
| `ASTRANOTES_DB_POOL_SIZE` | `10` | SQLAlchemy base pool size (Postgres only). |
| `ASTRANOTES_DB_MAX_OVERFLOW` | `20` | Extra burst connections beyond pool size. |

## HTTPS enforcement (B-92)

When `ASTRANOTES_DEV_HTTP` is **not** set, the server refuses any plain
HTTP request whose host is not `localhost`, `127.0.0.1`, or `::1`. Two
bypass paths exist:

1. The request includes `X-Forwarded-Proto: https` (TLS already
   terminated by an upstream reverse proxy such as nginx or Caddy).
2. The path is `/healthz`, so load-balancer probes still work without
   TLS.

To run a local dev server without a TLS cert, set `ASTRANOTES_DEV_HTTP=1`.
**Do not set this in production.**

## Rate limiting (B-95)

`/sync/push` and `/sync/pull` are guarded by an in-process sliding
window keyed on `account_id`. The default is 60 requests per minute per
account; tune via `ASTRANOTES_RATE_LIMIT_PER_MIN`. When exceeded the
server returns HTTP 429 with the R16.8 error envelope and a
`Retry-After` header (integer seconds).

`/auth/login` is intentionally **not** rate-limited by this layer —
`AccountStore` already enforces 5 failures → 5-minute lockout per
username (Sprint 2, B-58).

## PostgreSQL — `sslmode=require` (B-63)

`make_engine()` parses the `ASTRANOTES_SYNC_DATABASE_URL`. If the URL
points at a Postgres host other than `localhost` / `127.0.0.1` / `::1`
and the query string does **not** contain
`sslmode=require` (or `verify-ca`, `verify-full`), the server raises
`ValueError` on startup. Example production URL:

```
postgresql://astranotes_app:s3cret@db.example.com:5432/astranotes?sslmode=require
```

## PostgreSQL — least-privilege role (B-53)

Create a non-DDL role for the sync server and grant only the rights it
needs:

```sql
CREATE ROLE astranotes_app LOGIN PASSWORD 'changeme';
GRANT CONNECT ON DATABASE astranotes TO astranotes_app;
GRANT USAGE ON SCHEMA public TO astranotes_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO astranotes_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO astranotes_app;
-- No CREATE, DROP, ALTER, TRUNCATE permissions.
```

Schema migrations should be run by a separate admin role (e.g. via
Alembic from a deploy job), not by `astranotes_app`.

## Connection pool (B-93)

Postgres engines get `pool_pre_ping=True` and `pool_recycle=3600`. The
base pool size and burst overflow are taken from
`ASTRANOTES_DB_POOL_SIZE` / `ASTRANOTES_DB_MAX_OVERFLOW`. The defaults
(10 + 20 = 30 concurrent connections) satisfy the ≥10-user load test in
`tests/test_sprint5a2.py::TestConcurrentSync`.

## Health check

`GET /healthz` always returns `{"status": "ok"}`. It bypasses HTTPS
enforcement and rate limiting so it is safe to wire into any
load-balancer probe.
