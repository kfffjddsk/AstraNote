# Working Log — 2026-05-04

## Summary
Two-part session:
1. Design document creation (`docs/design.md` v1.1) — UML package diagram, class diagrams (implemented + planned), interaction diagrams, data models, 10 ADRs, full traceability matrix, and four-category gap analysis.
2. Traceability metrics formalization (`docs/traceability-metrics.md`) — quantified coverage across 121 requirement items.
3. Agile artifact chain audit — traced the full chain from Requirements → User Stories → Product Backlog → Sprint Backlog → Test Plan → Execution Evidence → Deployment Gate; identified 10 gaps and fixed all of them.

No code changed. All changes are planning, process, and documentation artifacts.

---

## What Changed

### New: `docs/design.md` (v1.1)
Full software design document containing:
- UML package diagram, implemented class diagrams, planned class diagrams
- Four component interaction diagrams (current unencrypted add, current encrypted add, planned post-blob add, plugin hook dispatch)
- Five data models (notes.json, DB schema, sandbox blob wire format, session token, audit log)
- ADR-01 through ADR-10
- Full traceability matrix (R1–R15 → module/class/test)
- §9 four-category gap analysis (bugs B1–B3, missing transitions T1–T4, underspecified U1–U5, intentional deferments)
- §10 summary table linking to `traceability-metrics.md`

### New: `docs/traceability-metrics.md`
Standalone metrics document covering:
- 121 total requirement items (R1–R15): 29 Fully Traced / 17 Partially Traced / 71 Weakly Traced / 4 Not Traced
- 5 UML elements without backing requirements
- Full per-category lists

### New: `docs/test-execution-evidence.md`
Captured Sprint Zero gate-pass evidence: 33/33 tests passing as of 2026-05-04. Includes test breakdown table and known test gaps (B-83, B-40 scenarios) to be closed in Sprint 1.

### Modified: `planning/user-stories.md`
Added US-13 (Security & Injection Prevention) covering R15.1–R15.9. Nine backlog items (B-51, B-52, B-53, B-54, B-55, B-56, B-63, B-64, and related) were previously traceable only through functional user stories (US-1, US-4, US-12). US-13 closes this gap.

### Modified: `planning/backlog.md`
- Updated User Story column for B-51, B-52, B-53, B-54, B-55, B-56, B-63, B-64 to add US-13 reference.
- Updated B-40 description to be explicit: "BDD + unit tests for new edge cases (B-31–B-39 scenarios)."
- Annotated B-18 as `Done (test debt: B-83)` — plugin base class was marked Done but has no automated test.
- Added B-83: Unit tests for PluginBase and PluginRegistry, High priority, US-4.

### Modified: `planning/sprint-zero-plan.md`
- Replaced "Next Sprint Candidates" bullets with an explanatory note: B-24, B-25, B-28 were intentionally deferred to Sprint 3 (after database/auth infrastructure in Sprint 2). Sprint 1 was reoriented to critical bug fixes first.
- Added B-83 to Sprint 1 item list to close B-18 test debt.
- Added Sprint 3 Plan section covering B-24 (Override policy), B-25 (Audit trail), B-28 (Plugin CLI commands), B-26 (Config module), and remaining injection-prevention security items (B-53–B-56, B-62, B-69–B-71, B-73, B-76).

### Modified: `docs/test_workflow.md`
Added Sprint 1 Test Plan section covering:
- 9 new BDD scenarios required (B-31, B-32, B-33, B-35, B-36, B-39)
- 6 new unit tests required (B-31, B-34, B-83 × 4)
- Sprint 1 exit criteria: total tests grow from 33 → ≥47

---

## Gaps Found and Closed

| Gap | Layer | Fix Applied |
|-----|-------|-------------|
| R15 (9 requirements) had no User Story | Req → US | Added US-13 |
| B-51/52/53/54/55/56/63/64 had no security US reference | US → Backlog | Added US-13 to each |
| B-18 marked Done with no automated test | Backlog → Test Plan | Flagged test debt; added B-83 |
| Sprint 1 item B-40 description vague ("edge cases") | Sprint → Test Plan | Clarified to "(B-31–B-39 scenarios)" |
| B-24/B-25/B-28 marked "Next Sprint Candidates" but not in Sprint 1 or Sprint 2 | Sprint Backlog gap | Added Sprint 3 plan with explicit rationale |
| Sprint 1 had no test plan entries | Sprint → Test Plan | Added Sprint 1 Test Plan to test_workflow.md |
| No captured execution evidence artifact | Test Plan → Evidence | Created test-execution-evidence.md |
| No Sprint Zero gate-pass record | Evidence → Deployment Gate | Captured in test-execution-evidence.md §Sprint Zero Gate Pass |
| R5.3 acceptance criteria missing from any US | Req → US | Noted as documented gap (R5.3 error message detail not in acceptance criteria — low risk, minor wording issue only) |
| Sprint 3 items had no sprint home (B-24, B-25, B-26, B-28 floating in backlog) | Backlog → Sprint | Added to new Sprint 3 Plan |

---

## Key Decisions

### US-13 scope
Injection prevention and security hardening are behavioral requirements visible to users ("the app must reject bad inputs and enforce secure access"). They warrant a user story, not just requirements. US-13 consolidates all R15 items under a single user-facing story.

### B-83 as Sprint 1, High Priority
The DoD requires automated test coverage for all new behavior. B-18 (PluginBase + PluginRegistry) was marked Done without any tests. B-83 is Sprint 1 priority because it closes an existing DoD violation.

### Sprint 3 deferred B-24/B-25/B-28 (not abandoned)
Sprint 1 is bug-fix focused; the override policy and audit trail require the plugin system to be stable first. Sprint 2 delivers the database and auth layer. Sprint 3 then completes the plugin hardening, override policy, and audit trail on top of that stable foundation.

### test-execution-evidence.md lifecycle
This document is updated after each sprint's gate verification. Sprint 1 and Sprint 2 rows are placeholders until those sprints complete.

---

## Follow-Up Actions
- [ ] B-83: Write PluginBase + PluginRegistry unit tests in Sprint 1
- [ ] B-40: Write the 9 new BDD scenarios before Sprint 1 items are marked Done
- [ ] Update `docs/test-execution-evidence.md` Sprint 1 section when Sprint 1 completes
- [ ] Review R5.3 ("error messages identify triggering module") — decide if it needs a dedicated acceptance criterion in US-1 or can remain as an implementation note only

---

## Continuation — GUI Architecture Redesign `[LOG 05-04]`

### Summary
User direction received: AstraNotes will ship as **two distinct product variants**:
1. **Personal version** — "simple as possible just like most of the note app on the market" — minimal GUI, single-user, shares existing core Python modules.
2. **Server version** — proper front-end / back-end separation:
   - *Client side:* browser-based SPA (cloud sync, Google OAuth / social login, offline mode)
   - *Server side:* REST API server (concurrent multi-user, OAuth token verification, per-user isolation)

This is an architectural change from the previous model where "server mode" was CLI + PostgreSQL only. No production code was changed. All changes are to planning and design documentation.

### What Changed (GUI Architecture Pass)

| File | Change |
|------|--------|
| `planning/requirements.md` | R11 expanded from 4 vague items to 12 (split R11-A Personal GUI + R11-B Server Web Client); R12 gained R12.7/R12.8; R13 gained R13.14–R13.15 (OAuth/SSO); R16 added (8 REST API Server requirements) |
| `planning/user-stories.md` | US-9 updated from deferred epic to concrete Personal GUI story with acceptance criteria; US-14 added (Server Web Client — OAuth, cloud sync, offline mode); US-11 updated with OAuth acceptance criteria |
| `planning/backlog.md` | B-27 updated (now umbrella item); B-84–B-95 added (Personal GUI Sprint 4; REST API + Web Client + OAuth Sprint 5) |
| `planning/sprint-zero-plan.md` | Sprint 4 Plan added (Personal GUI); Sprint 5 Plan added (Server REST API + Web Client — two sub-sprints with decision gates for ADR-11/12/13) |
| `docs/design.md` | Version 1.1 → 1.2; §1 updated with two-variant scope; §2 package diagram expanded (web_client + rest_api + personal_gui packages added); §3.2 planned classes: PersonalGUI, NoteRouter, AuthMiddleware added; ADR-11/12/13 added (pending decisions); §9.4 deferment table updated; §9.5 new architecture gaps T5–T8 added |
| `docs/traceability-metrics.md` | R11 section restructured (R11-A + R11-B sub-tables; 12 rows replacing 4); FR-108–FR-127 assigned; R12 gained FR-116/FR-117; R13 gained FR-118/FR-119; R16 section added (FR-120–FR-127); metrics summary updated (121 → 141 total requirements); §5.2 intentional-absences updated |
| `docs/prd.md` | Version 1.0 → 1.1; §2 Target Users updated (added Personal GUI user + Server web user personas); §6 Out of Scope updated (removed AI-flagged "Mobile or web client" — now the web client is owner-specified; added "Mobile-native app" and "Cloud sync for Personal version" as explicit out-of-scope); §7 Deferred section updated (Sprint 4 and Sprint 5 plans noted) |

### Key Architectural Decisions Made
- Personal GUI shares core Python modules (`NoteStore`, `EncryptionEngine`, `PluginRegistry`) directly — no server required.
- Server version uses REST API as the **exclusive** data interface for the web client (web client never accesses DB directly).
- OAuth 2.0 / Google OpenID Connect is the required minimum provider for web client login; extensible provider pattern required.
- Three ADRs are now "Pending" gating before Sprint 4/5 implementation: ADR-11 (REST API framework), ADR-12 (OAuth strategy), ADR-13 (GUI framework for both variants).
- CLI remains as the primary interface for Sprints 0–3 and as a secondary operator interface in server mode.

### Follow-Up Actions (new)
- [x] ADR-13: Decided — Local web server + browser SPA `[LOG 05-04 — three-layer pass]`
- [x] ADR-11: Decided — FastAPI `[LOG 05-04 — three-layer pass]`
- [x] ADR-12: Decided — authlib + Google OIDC `[LOG 05-04 — three-layer pass]`
- [ ] Design interaction diagrams for sync push/pull flow (gap T5) and OAuth token flow (gap T6) before Sprint 5
- [ ] Design cloud sync conflict resolution strategy (gap T7) before Sprint 5B
- [ ] Design Personal GUI startup sequence (gap T8) before Sprint 4 implementation

---

## Continuation — Three-Layer Architecture Simplification  `[LOG 05-04]`

**Session context:** Human team member identified that the hard "Personal mode / Server mode" split from the GUI redesign pass was over-engineered. A simpler, layered opt-in model was adopted instead.

### Architectural Decision

The forced two-product split is replaced by a **three-layer additive model**:

| Layer | Opt-in? | Mechanism |
|-------|---------|-----------|
| **1 — Local store** | Always on | SQLite at `<data-dir>/notes.db`; no config or login needed |
| **2 — Account** | Optional | `register`/`login`; `account_id` nullable FK on all notes |
| **3 — Cloud sync** | Optional (requires account) | `sync push` / `sync pull`; last-write-wins; FastAPI sync server |

Key implications:
- No first-launch mode selection prompt; no `deployment_mode` config key.
- Auth never blocks local CRUD. An expired session only prevents sync.
- `account_id = NULL` means anonymous/device-local. Set on login.
- First login on device with anonymous notes triggers a one-time association prompt.
- Logout keeps all local notes accessible; `account_id` values preserved on device.
- `delete-account` sets `account_id = NULL` locally; warns cloud copies deleted.
- REST API is a **sync endpoint** (`POST /sync/push`, `GET /sync/pull?since=`), not a CRUD proxy.
- Data directory always flat: `<data-dir>/notes.db`, `files/`, `exports/`, `audit.log`.

ADR decisions confirmed in this pass:
- **ADR-11:** FastAPI (async, Pydantic, auto OpenAPI)
- **ADR-12:** authlib + Google OIDC (framework-neutral, RFC-correct, extensible)
- **ADR-13:** Local web server + browser SPA (shared components with web client)
- **ADR-09:** Updated — flat directory, no per-user subdirs

### What Changed (Three-Layer Pass)

| File | Change |
|------|--------|
| `planning/requirements.md` | R12 rewritten (three-layer model, R12.1–R12.7); R13 rewritten (optional auth, `account_id`, new R13.8–R13.14); R14 updated (`account_id` nullable + `synced_at`, `accounts` table, flat dir); R16 rewritten (push/pull sync, not CRUD proxy) |
| `planning/user-stories.md` | US-10 rewritten ("Local-First with Opt-In Account"); US-11 rewritten ("Optional Account and Authentication"); US-12 header + body rewritten; US-14 rewritten (sync-focused, not CRUD-proxy) |
| `planning/backlog.md` | B-41 updated (association prompt); B-42 updated (account_id+synced_at); B-44 updated (sync server, not server mode); B-47 updated (account_id); B-50/B-70 marked REMOVED; B-61 updated (detach not purge); B-77 updated (flat dir); B-81 updated; B-86–B-95 fully rewritten; B-96 added (accounts table) |
| `planning/sprint-zero-plan.md` | Sprint 2 goal, items, and exit criteria rewritten; B-70 struck; Sprint 5 goal, items, and exit criteria rewritten (sync server, not REST CRUD) |
| `docs/design.md` (v1.2) | §1 scope updated; §2 package diagram `rest_api` → `sync_server`; §3.2 `AuthManager` + `SyncRouter` updated; §5.2 `notes` schema adds `account_id`+`synced_at`, `users`→`accounts`; §5.4 session token `user_id`→`account_id`; ADR-02/07/09/11/12/13 updated (11/12/13 Pending→Decided) |
| `docs/traceability-metrics.md` | R12 section rewritten (7 rows); R13 section updated (FR-88–FR-94 updated, FR-119 removed, total 15→14); R14 FR-97/FR-104/FR-107 updated; R16 section rewritten (push/pull, FastAPI decided); metrics summary 141→139 |
| `docs/prd.md` (v1.2) | §1 problem statement; §2 stakeholder table; §3.3 notes schema; §3.4 rewritten (Local-First + Opt-In); §3.5 rewritten (Optional Auth); §3.8 flat audit log; §4 NFR; §5 risks (removed mode-switch risk, added sync conflict risk); §6 removed "Cloud sync for Personal version" out-of-scope item |

### No Production Code Changes
All 33 tests continue to pass. `src/` files are untouched.

### Follow-Up Actions (three-layer pass)
- [ ] Design interaction diagrams for `sync push`/`sync pull` flow (gap T5) and OAuth token flow via authlib (gap T6)
- [ ] Design `note_conflicts` table schema and merge algorithm before Sprint 5B
- [ ] Design Personal GUI startup sequence (gap T8) before Sprint 4

---

## Continuation — PySide6 Desktop Architecture Document Update  `[LOG 05-04]`

**Session context:** The prior "GUI Architecture Redesign" pass had briefly landed on "Local web server + browser SPA (FastAPI + Svelte)" for ADR-13. The team confirmed both Sprint 4 and Sprint 5 should be a **PySide6 desktop app** — no browser surface, no Svelte, no static file serving. This pass updates all planning and design documents to reflect that final decision and identifies remaining gaps, conflicts, and vague items.

### Key Decisions Confirmed

| ADR | Decision |
|-----|----------|
| ADR-13 | **PySide6 desktop app**; single codebase; Sprint 4 = CRUD; Sprint 5 = same app + sync |
| ADR-11 | FastAPI (sync server only; no static file serving) |
| ADR-12 | authlib + Google OIDC (PKCE flow in desktop app; system browser opens for consent) |

FR-114 (IndexedDB offline cache + write queue) **dropped** — browser-only concept. Covered by FR-76 (local SQLite always on). Total requirements: 138.

### What Changed

| File | Changes |
|------|---------|
| `docs/design.md` | §1 scope; §2 package diagram (removed `web_client` box; `personal_gui` → `desktop_gui`); §3.2 `PersonalGUI` → `DesktopGUI` class block (added `on_sync()`, `show_settings()`; startup = QApplication); ADR-12 context; ADR-13 title + options + decision rewritten (PySide6); gap items T5–T8 updated; risk table Sprint 4/5 rows updated |
| `docs/traceability-metrics.md` | R11 section heading; R11-A FR-72/FR-75/FR-108/FR-109 updated (DesktopGUI, PySide6); R11-B heading → "Sync-Enabled Desktop Client (Sprint 5)"; FR-110/FR-111/FR-112/FR-115 rewritten (no web_client); changelog note updated |
| `docs/prd.md` | §2 "Logged-in web user" → "Logged-in desktop user"; §3.9 removed `deployment_mode` config key; §6 mobile out-of-scope rationale; §7 deferred Sprint 4/5 descriptions |
| `planning/requirements.md` | R9.3 `deployment_mode` removed; R11 intro; R11.5/R11.6 (PySide6 decided); R11-B heading → "Sync-Enabled Desktop Client"; R11.7–R11.10/R11.12 rewritten (desktop app, no browser); R11.11 dropped; R13.13 "web client and GUI" → "desktop app and CLI" |
| `planning/user-stories.md` | US-7 removed `deployment_mode` from config keys; US-9 GUI framework bullet (PySide6 decided); US-9 backend bullet ("personal-mode" → "local"); US-11 OAuth login method ("in GUI and web client" → "in the desktop app"); US-14 title, user statement, acceptance criteria (browser SPA bullet → PySide6 desktop bullet) |
| `planning/backlog.md` | B-27 umbrella; B-84 description (PySide6, QApplication); Sprint 5 section heading; B-89 rewritten (PySide6 sync UI); B-91 struck (superseded) |
| `planning/sprint-zero-plan.md` | Sprint 4 decision gate (PySide6 decided); Sprint 5 title/goal/duration; ADR-13 gate; Sprint 5B section heading; B-89 item; B-91 struck; exit criteria (browser SPA → desktop; OAuth in browser → desktop PKCE; offline write queue criterion removed) |

### No Production Code Changes
All 33 tests continue to pass.

### Remaining Gaps, Conflicts, and Vague Items Identified

#### Conflicts
- **FR-80 / FR-113 background sync:** R12.5 and R11.10 both say "opt-in via config" — consistent. No conflict, but the config key for enabling background sync is unspecified. `allowed_plugins` and known keys list in R9.3 does not include a background-sync toggle. **Action:** add `sync_auto_interval` (or similar) to R9.3 known keys before Sprint 5 begins.
- **US-14 source reference:** US-14 cites `[REQ R11.7–R11.12]` — R11.11 has been dropped. The source cite should be updated to `[REQ R11.7–R11.10, R11.12]`.

#### Vague Items
- **OAuth PKCE desktop redirect:** No requirement or design specifies how the desktop app listens for the redirect (ephemeral `localhost:<port>/callback` HTTP listener? custom URI scheme?). ADR-12 says "PKCE flow" but the desktop-side capture mechanism is undesigned. Flag for Sprint 5 design phase (gap T6).
- **Settings dialog contents:** `show_settings()` in design.md \u00a73.2 says "data dir, account, sync server URL, theme, etc." — the "etc." is unspecified. No requirement enumerates all settings-dialog fields. The "theme" option has no corresponding requirement.
- **System tray icon:** Mentioned as "optional Sprint 4 stretch goal" in the archived scratch file. No backlog item exists; not in any requirement. Either add a backlog item (B-97?) or explicitly drop it.
- **`sync_auto_interval` config key:** R9.3 known-keys list does not include a background-sync trigger. Required before Sprint 5 to avoid R9.3 violation when adding opt-in background sync.
- **B-91 drop visibility:** B-91 is struck in backlog.md but no corresponding ADR or decision record exists. The rationale (Layer 1 SQLite always on = no write queue needed) is in the backlog note. Sufficient for now but worth a one-line ADR amendment.

#### Deferred Design Work (unchanged from prior session)
- T5 — sync server request flow sequence diagram (Sprint 5 design phase)
- T6 — OAuth PKCE desktop callback flow diagram (Sprint 5 design phase)
- T7 — `note_conflicts` table schema + merge algorithm (Sprint 5B design phase)
- T8 — Desktop GUI startup sequence diagram (Sprint 4 design phase)
