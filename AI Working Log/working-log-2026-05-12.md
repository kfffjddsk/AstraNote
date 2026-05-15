# AstraNotes — AI Working Log
**Date:** 2026-05-12  
**Session type:** Design discussion resolution  
**AI Partner:** Astra (GitHub Copilot)

---

## Summary
Resolved D-10 (Migration Sequence Diagram) by eliminating the migration entirely. Sprint plans, backlog, and all design documents updated for the new storage strategy: SQLite (`DatabaseStore`) from Sprint 0, no JSON storage phase.

---

## Decisions Made

### D-10 — SQLite from Sprint 0; no migration needed
**Question:** Can we skip JSON storage (NoteStore) entirely and start with SQLite directly?  
**Decision:** Yes — `DatabaseStore` (SQLAlchemy/SQLite) is the only local store, used from Sprint 0.

**Consequences:**
- `NoteStore` (JSON) never implemented — `DatabaseStore` is the sole local store from day one.
- `migrate` CLI command (B-48) dropped — there is no JSON file to migrate from. B-72 and B-80 dropped as dependents.
- `BlobCodec` (B-43) moved to Sprint 0 alongside `DatabaseStore` (was Sprint 1 per D-07).
- B-42, B-51, B-74 also moved to Sprint 0.
- B-65 (Alembic schema versioning) and B-66 (WAL mode + retry) moved to Sprint 1.
- B-35 (corrupt JSON recovery) dropped — SQLite ACID replaces the JSON corruption risk entirely.
- D-10 closes as "not needed" — no migration sequence diagram ever required.
- `StoreLoadError` (corrupt-notes.json error class from D-08) retired — no JSON layer.

### Sprint Reorganization
| Sprint | Storage work |
|--------|-------------|
| Sprint 0 | `DatabaseStore` (SQLite, `create_all()`), `BlobCodec`, SQLAlchemy ORM, `title`/`format` columns — B-42, B-43, B-51, B-74 |
| Sprint 1 | Alembic schema versioning, WAL mode + retry — B-65, B-66 |
| Sprint 2 | Auth layer, PostgreSQL backend (B-41, B-44–B-47, B-57–B-60, B-63–B-64, B-75–B-79, B-81, B-96) |

---

## Files Changed

| File | Changes |
|------|---------|
| `planning/sprint-zero-plan.md` | §2: `NoteStore` → `DatabaseStore` + `BlobCodec`; Sprint 0 exit criteria updated; Sprint 1 B-35 dropped, B-65+B-66 added; Sprint 2 items cleaned (B-42/43/48/51/65/66/74/80 removed); Sprint 4 exit criteria `NoteStore` → `DatabaseStore` |
| `planning/backlog.md` | B-15 struck (replaced by B-42/43/51/74); B-35/B-48/B-72/B-80 struck (DROPPED); B-42/43/51/74 annotated Sprint 0; B-65/66 annotated Sprint 1 |
| `Copilot/discussion-list.md` | D-10 moved to Resolved section; D-06 startup sequence updated (store selector removed → always `DatabaseStore`) |
| `planning/requirements.md` | R3 section header: superseded by R14; R3.1/R3.6 retired; R1.10 N/A; R14.7 dropped; R6.2/R6.5 updated; R11.1/R11 header `NoteStore` → `DatabaseStore` |
| `planning/design.md` | §3.1: `NoteStore` → `DatabaseStore`; §3.2: `DatabaseStore` Sprint 0, `BlobCodec` Sprint 0, `StoreLoadError` retired; §4.1/§4.2: NoteStore→DatabaseStore, sprint labels Sprint 0; §4.2a: error messages updated; §4.5: store selector removed; §5.1: `notes.json` retired; ADR-02: decision + consequences updated; §9.2 T2: resolved; §9.4: B-35 dropped, BlobCodec Sprint 0; §8.1 module map: NoteStore rows updated |
| `planning/traceability-metrics.md` | FR-1–FR-22: NoteStore → DatabaseStore class evidence; FR-10: N/A (B-35 dropped); FR-19: call site resolved; FR-27: retired; FR-32: retired; FR-28–FR-34: DatabaseStore evidence; R3 section note added |
| `AI Working Log/working-log-2026-05-11.md` | Follow-up actions updated — D-10 resolved |

---

## Follow-Up Actions (D-10)
- D-11 through D-14 remain open — to be resolved before their blocking sprints begin.
- Next priority: D-11 (session validation + `ensure_store()` replacement) — blocks Sprint 2.

---

## Decisions Made (continued)

### D-11 — Session Validation Integration Point and `ensure_store()` Replacement
**Question:** (1) Where does `AuthManager.verify_session()` live in the Click CLI? (2) What replaces `ensure_store()` for passphrase caching in the multi-account architecture?

**Sub-decision 1 — Sync gating (T3):**  
`sync` commands form a dedicated Click subgroup. Its group callback calls `AuthManager.verify_session(data_dir)` — blocking. If the session is absent or expired, raises `ClickException` + exit 1 with a message directing the user to run `login`. The top-level CLI group callback (§4.5) calls `try_load_session()` — non-blocking, returns `account_id = None` on miss. Local CRUD (add/get/list/update/delete) passes through the top-level callback only; it is never blocked by session state.

**Sub-decision 2 — Note scoping:**  
Logged-out → `DatabaseStore.list(account_id=None)` returns only anonymous notes (`account_id = NULL`). Logged-in → returns own account notes + anonymous notes. No cross-user visibility (User A cannot see User B's notes regardless of DB contents).

**Sub-decision 3 — Two-section list layout:**  
`DatabaseStore.list(account_id)` returns a tuple `(account_notes: List[Note], local_notes: List[Note])`. CLI renders **"Your Notes"** then **"Local Open Notes"**. "Your Notes" section omitted entirely when logged out. When a user associates anonymous notes on login (R12.3 "Yes"), those notes receive `account_id` and appear under "Your Notes" on next list.

**Sub-decision 4 — Passphrase caching (T4):**  
`get_key_manager(ctx)` — module-level helper in `cli.py`. Checks `ctx.obj['key_manager']`; if None, prompts passphrase, constructs `KeyManager(passphrase)`, caches in `ctx.obj['key_manager']`. Within-process only — no OS keychain, no cross-invocation persistence. Each new CLI invocation (new process) re-prompts if needed.  
- `add --encrypt yes`: constructs `KeyManager` inline, not cached (single note per invocation).  
- `list`: never calls `get_key_manager()` — reads plaintext `title`/`format` columns only.  
- `get`, `update`, `delete`, `reencrypt`: call `get_key_manager(ctx)`.

**`ctx.obj` schema (finalized):**  
```python
ctx.obj = {
    'store':       DatabaseStore,   # always present
    'account_id':  str | None,      # None = logged out
    'key_manager': KeyManager | None  # lazily set by get_key_manager()
}
```

**GUI security level (B-98, Sprint 4):**  
`security_level` config key. `high` (default): clear passphrase from memory on note close, navigate away, minimize, or focus loss — always re-prompt. `session`: clear only on app close — prompt once per app launch.

---

## Files Changed (D-11)

| File | Changes |
|------|---------|
| `planning/design.md` | §3.1: `DatabaseStore.list()` → tuple signature; §3.2: same + `AuthManager` `try_load_session()`/`verify_session()` methods + BL ref drop B-48; §4.1: account_id added to ctx.obj read; §4.2: `KeyManager` inline note + account_id ctx read; §4.2a: `get_key_manager(ctx)` call + `store =` line added; §4.5: step 5 (session probe) added, `ctx.obj` dict schema, key_manager note updated, new §4.6 sync subgroup diagram title; new **§4.6**: sync group callback sequence; §9.2 T2: resolved ✅; §9.2 T3: resolved ✅; §9.2 T4: resolved ✅; §9.3 U4: fully resolved ✅ |
| `planning/requirements.md` | R1.3: two-section list description added |
| `planning/backlog.md` | B-85/B-97 line split (formatting fix); B-98 added (GUI passphrase security level, Sprint 4) |
| `Copilot/discussion-list.md` | D-11 moved from Open Items to Resolved section |

---

## Tests Performed
No code written; no tests applicable.

---

## Follow-Up Actions
- D-12 (extension manifest schema + sandboxing) — **RESOLVED below**.
- D-13 (desktop GUI startup sequence) — blocks Sprint 4.
- D-14 (sync server diagrams + conflict resolution) — blocks Sprint 5.
- Cross-check all planning docs for remaining legacy design inconsistencies (NoteStore refs, flat `List[Note]` list signatures, `TestNoteStore` unit refs, stale sprint labels).
- All commits pending — suggested groupings: (1) D-10 sprint reorganization, (2) D-11 resolution, (3) D-12/D-13/D-14 when done.

---

## Decisions Made (continued)

### D-12 — Extension Plugin Manifest Schema and Sandboxing Trust Model
**Question:** (1) Define the plugin manifest file format and all required/optional fields. (2) Define in concrete terms what each trust tier can and cannot do.

**Manifest format — JSON (`plugin.json`):**  
Located at the root of each plugin subdirectory under `plugins/`. Validated by `PluginRegistry.load_manifests()` using `jsonschema`. Malformed or missing manifests rejected with warning; plugin skipped.

**Required fields:**

| Field | Type | Notes |
|-------|------|-------|
| `plugin_id` | str | Unique namespace; must match `allowed_plugins` config key |
| `name` | str | Display name |
| `version` | str | Semver (e.g. `"1.0.0"`) |
| `engines` | str | Min AstraNotes version (e.g. `">=1.0.0"`) |
| `main` | str | Entrypoint Python module path relative to plugin root |

**Optional fields:** `supported_mime_types` (list[str]), `keywords` (list[str]), `categories` (list[str]), `repository` (str URL), `extensionDependencies` (list[str] of `plugin_id`s).

**`is_official` — server-assigned only:**  
NOT a manifest field. Any manifest containing `is_official` is rejected by `load_manifests()`. The value is injected by `PluginRegistry.register_plugin(plugin, is_official: bool)` from the backend-verified extension registry record. Sideloaded plugins always default to `is_official = False`.

**Trust tiers:**
- `is_official = True` (server-approved, pre-installed) → full `EditorProvider` + `PluginBase` API (hooks, CLI commands, read-only note copies).
- `is_official = False` (user-installed) → `EditorProvider` only. `PluginBase` hook registration blocked at `register_plugin()` time with a warning.
- Rationale: `PluginBase` hooks receive a copy of every note on `post_add_note`/`post_update_note`. Unrestricted hook access for user-installed plugins would enable silent note exfiltration. `EditorProvider` scope limits access to only notes the user actively opens in that plugin's editor.

**`EditorProvider` class changes:** `engines: str` and `main: str` added as required fields. `is_official: bool` annotation updated to "server-assigned — NOT read from plugin.json."

---

## Files Changed (D-12)

| File | Changes |
|------|---------|
| `planning/design.md` | §3.1 `EditorProvider`: added `engines`, `main` fields; `is_official` annotation updated to server-assigned; "TBD" manifest note replaced with resolved note + ADR-14 ref; §3.1 `PluginRegistry`: `register_plugin()` signature updated + trust-tier enforcement notes; `load_manifests()` added to method list; new **`plugin.json` Manifest Schema** table added; §4.5 step 4: `load_manifests()` inline comments expanded with required fields + `is_official` rejection note; ADR-14 added |
| `planning/requirements.md` | R4.11 (manifest validation), R4.12 (`is_official` server-only), R4.13 (trust-tier enforcement) added |
| `planning/backlog.md` | B-99 (manifest validation), B-100 (trust-tier enforcement) added to Sprint 4 |
| `Copilot/discussion-list.md` | D-12 moved from Open Items to Resolved section |

---

## Follow-Up Actions (D-12)
- D-13 (desktop GUI startup sequence) — blocks Sprint 4. Next priority.
- D-14 (sync server diagrams + conflict resolution) — blocks Sprint 5.

---

## Decisions Made (continued)

### D-13 — Desktop GUI Startup Sequence
**Date:** 2026-05-13  
**Question:** How should `DesktopGUI` instantiate `DatabaseStore`? When is the passphrase `QDialog` shown? How is concurrent CLI + GUI access handled? What happens on first launch?

**Sub-decision 1 — Startup orchestrator (Q1):**  
`AppController` (Option C — orchestrator) is introduced as a new class constructed in `main.py`. It owns `ConfigStore`, `DatabaseStore`, `SessionManager`, and `DesktopGUI` and wires them in order. `DesktopGUI` receives `DatabaseStore` via constructor injection — it never creates storage internally. Rationale: testability via injection + all startup wiring in one named place, scalable as more modules are added in Sprint 4+.

**Sub-decision 2 — Passphrase prompt timing (Q2):**  
Lazy — note list populates with `[Encrypted]` placeholders via `DatabaseStore.list()`; passphrase `QDialog` is shown only when the user opens a specific encrypted note. No passphrase prompt at startup.

**Sub-decision 3 — Session exclusivity + idle auto-lock (Q3):**  
Session exclusivity: only one AstraNotes session (GUI or CLI) per account. Enforced by a PID-based lock file at `<data-dir>/.app.lock`. On startup: check lock → alive PID → error dialog + exit; dead PID → overwrite (stale lock). Lock deleted on clean exit.  
Idle auto-lock: encrypted note auto-closes after 5 minutes of no user interaction. Clears passphrase from memory; redisplays `[Encrypted]` placeholder. Security feature only — not a multi-user locking mechanism. Note-level access locks across OS users were considered and dropped as out of scope for a personal app.

**Sub-decision 4 — First launch (Q4):**  
Already resolved. `DatabaseStore.__init__` calls `create_all()` transparently. No special case needed.

**Startup sequence diagram:** §4.7 added to `planning/design.md`.

---

## Files Changed (D-13)

| File | Changes |
|------|---------|
| `planning/design.md` | §4.7 `AppController` startup sequence diagram added; `AppController` and `SessionManager` class diagrams added to §3.2; T8 gap entry updated to resolved |
| `planning/requirements.md` | R9.7 (session exclusivity lock file) and R9.8 (encrypted note idle auto-lock) added |
| `planning/backlog.md` | B-101 (`AppController` + `SessionManager` session lock), B-102 (idle auto-lock timer) added to Sprint 4 |
| `planning/sprint-zero-plan.md` | Sprint 1 exit criteria: WAL mode note updated (session exclusivity is primary defense); Sprint 4 plan rewritten — decision gates (D-13 added), Items expanded (B-84 updated, B-97–B-102 added), Exit Criteria expanded (AppController, lazy passphrase, session lock, idle timer, B-98–B-100) |
| `Copilot/discussion-list.md` | D-13 moved from Open Items to Resolved section |
| `planning/traceability-metrics.md` | FR-65-R9 (R9.7), FR-66-R9 (R9.8) added to R9 section |

---

## Follow-Up Actions (D-13)
- D-14 (sync server interaction diagrams + conflict resolution) — blocks Sprint 5. Next priority.
- `SessionManager` and `AppController` class diagrams added to §3.2 (2026-05-13, prioritized to unblock Sprint 4 implementers).

