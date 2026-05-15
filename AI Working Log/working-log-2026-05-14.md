# Working Log — 2026-05-14

## Summary
Design discussion session: resolved D-14 (Sync Server Interaction Diagrams and Conflict Resolution). Added §4.8 (push/pull sequence), §4.9 (OAuth PKCE desktop login flow), and §4.10 (pull-with-conflict and MergeWindow) to `planning/design.md`. Replaced the old `note_conflicts` 30-day retention model with a user-choice 2-pane merge window. All design gaps T5/T6/T7 now resolved. No code written.

---

## What Changed

### `planning/design.md`
- **§3.2** — Added `MergeWindow [planned]` class: `QDialog` subclass, 2-pane conflict merge UI (Sprint 5B). `[REQ R16.3]`
- **§4.8** — New: Sync server push/pull sequence. Push happy path (`POST /sync/push` → `AuthMiddleware.verify_token()` → `SyncRouter.push()` → PG UPSERT → 200 `{synced_at}`). Pull happy path (`GET /sync/pull?since=<ts>` → auth gate → `SELECT WHERE modified_at > since` → 200 `[note blobs]`). Post-pull conflict detection logic (compare `modified_at` vs `synced_at`). Resolves gap T5.
- **§4.9** — New: OAuth PKCE desktop login flow. `QDesktopServices.openUrl()` → system browser → Google consent → `astranotes://callback` redirect → `state` nonce CSRF check → `POST /auth/callback {code, verifier}` → authlib token exchange → JWT → `<data-dir>/.session` (mode 0600). Resolves gap T6.
- **§4.10** — New: Pull-with-conflict and MergeWindow. Conflict condition (both `server_modified_at` and `local_modified_at` newer than `local_synced_at`). `!` badge (yellow circle) on conflicted note row. `MergeWindow`: local read-only left pane (diffs highlighted), remote editable right pane. `[Use Local ←]` and `[Save Final]` buttons. No `note_conflicts` table. Server blob in memory only. Resolves gap T7.
- **§9.5** — T5, T6, T7 all marked resolved with cross-references to new sections.

### `planning/requirements.md`
- **R16.3** — Rewritten: removed `note_conflicts` 30-day table; replaced with 2-pane `MergeWindow` user-choice resolution. `[D-14 decided 2026-05-14]`

### `planning/backlog.md`
- **B-86** — Description updated: removed `note_conflicts` table language; added `[D-14 decided 2026-05-14]`.

### `planning/traceability-metrics.md`
- **FR-122** — Updated: new description matches R16.3 rewrite; class evidence updated to `MergeWindow` + `SyncRouter`; use case evidence updated to SD-T7 (§4.10); status changed from Not Traced → Weakly Traced.

### `planning/sprint-zero-plan.md`
- Sprint 5A/5B conflict exit criterion updated: `note_conflicts` reference removed; `MergeWindow` added.
- Sprint 5A OAuth exit criterion updated: `ephemeral localhost callback` → `astranotes://callback custom URI scheme` (ADR-12).

### `planning/user-stories.md`
- **US-12** acceptance criteria: conflict resolution updated to `MergeWindow` model.
- **US-14** acceptance criteria: conflict resolution updated to `MergeWindow` model.

### `planning/prd.md`
- Risk row "Sync conflict data loss": mitigation updated from `note_conflicts` 30-day table to `MergeWindow` user-choice resolution.

### `Copilot/discussion-list.md`
- **D-14** resolved and moved to Resolved Items. Full decision record written.
- Open Items section now shows *No open items.*

---

## Key Decisions

### D-14 — Sync Server Interaction Diagrams and Conflict Resolution (resolved 2026-05-14)

**T5 — Push/pull sequence:**
- Push: `POST /sync/push` → JWT validation → `SyncRouter.push(account_id, blobs)` → UPSERT PG `notes` (ON CONFLICT DO UPDATE) → 200 `{synced_at}`.
- Pull: `GET /sync/pull?since=<ts>` → JWT validation → `SELECT * WHERE account_id=? AND modified_at>since` → 200 `[note blobs]`.
- All queries scoped by `account_id` from JWT only (never request body). `[REQ R16.4, R16.5]`
- Post-pull desktop merge: auto-accept if only server changed; open `MergeWindow` if both sides changed since last sync.

**T6 — OAuth PKCE desktop login:**
- `code_verifier` + S256 `code_challenge` generated fresh per attempt (in memory only).
- `state` nonce generated per attempt for CSRF protection; verified on redirect.
- Custom URI scheme `astranotes://callback` — no inbound HTTP socket. `[ADR-12]`
- JWT written to `<data-dir>/.session` at mode 0600; never logged. `[REQ R9.6]`

**T7 — Conflict resolution:**
- **No `note_conflicts` table** — previous R16.3 language superseded. `[D-14 decided 2026-05-14]`
- Conflict detected desktop-side: `server_modified_at > local_synced_at` AND `local_modified_at > local_synced_at`.
- `!` badge (yellow circle) on conflicted note row in left file list.
- `MergeWindow` (`QDialog`): left = local (read-only, diff-highlighted), right = remote (editable). `[Use Local ←]` copies left → right. `[Save Final]` → write to `DatabaseStore`, clear badge, push to server.
- Server blob is in-memory only (from pull response). No persistence. App restart without resolving → next pull re-detects.

| File | Change |
|------|--------|
| `planning/design.md` | §3.2 `MergeWindow` class; §4.8 push/pull; §4.9 PKCE; §4.10 MergeWindow flow; §9.5 T5/T6/T7 resolved |
| `planning/requirements.md` | R16.3 rewritten |
| `planning/backlog.md` | B-86 updated |
| `planning/traceability-metrics.md` | FR-122 updated |
| `planning/sprint-zero-plan.md` | Sprint 5 exit criteria updated |
| `planning/user-stories.md` | US-12, US-14 conflict criteria updated |
| `planning/prd.md` | Risk row updated |
| `Copilot/discussion-list.md` | D-14 resolved; no open items |
