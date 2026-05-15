# Working Log — 2026-05-11

## Summary
Design maintenance and decision session. Fixed stale content in `docs/design.md` left over from Sprint 0 code removal. Identified and documented all open design gaps as discussion items D-06 through D-14. Added VS Code extension system research directions to plugin-related items. Fully resolved D-06 (CLI startup sequence + ConfigStore location), D-07 (`Note.title` dual-field state machine — Option C adopted), D-08 (error flows in interaction diagrams), and D-09 (`PluginRegistry` allowlist + note isolation). Fixed `Note.metadata: dict` permanently in design, traceability, and sprint-zero-plan. Moved `prd.md`, `design.md`, `traceability-metrics.md` from `docs/` to `planning/`. Performed DoD cross-check after each decision. No code written.

---

## What Changed

### `planning/design.md` (moved from `docs/design.md`)
- **§1** — Replaced stale "Two design layers (Sprint Zero / Planned)" paragraph with a "Design status (updated 2026-05-11)" note: Sprint 0 removed, Sprint 1 starts clean, all designs are planned, gaps tracked in discussion list.
- **§3.1 heading** — Changed "Sprint Zero Classes" to "Sprint 1 Classes". `[D-07]`
- **§3.1 Note class** — Removed `encrypted_title: str|None` field; added `blob: bytes | None` (encrypted sandbox blob; `None` for unencrypted). `[D-07]`
- **§3.1 state table** — Replaced dual-field state table with Option C three-state table: unencrypted (`blob=None`, plaintext fields); encrypted+no key (`blob=bytes`, title=`"[Encrypted Note]"`, content=`""`); encrypted+correct key (`blob=bytes`, title/content populated in-memory from `BlobCodec.decode()`). `[D-07]`
- **§3.2 BlobCodec** — Changed `[planned]` to `[Sprint 1]`. `[D-07]`
- **§4.2** — Replaced separate `EncryptionEngine.encrypt(content)` + `EncryptionEngine.encrypt(title)` calls with `BlobCodec.encode()` + `BlobCodec.encrypt()` flow. Updated heading to "Sprint 1, uses BlobCodec". `[D-07]`
- **§4.5** — Corrected startup sequence diagram: `ConfigStore` now loads from fixed OS-standard path. Corrected startup order: ConfigStore → resolve `data_dir` → store selection → plugin manifest loading (eager) + activation (lazy). `[D-06]`
- **§5.1 heading** — Changed "pre-migration, Sprint Zero" to "pre-migration, Sprint 1". `[D-07]`
- **§5.1 JSON example** — Removed `"metadata": {}` field; replaced `"encrypted_title"` with `"blob"` for both unencrypted (`null`) and encrypted (base64 blob) examples. `[D-07]`
- **§7 traceability preamble** — Updated to state Sprint 0 source was deleted; all entries are unimplemented; paths are Sprint 1+ targets.
- **§8 directory structure** — Replaced stale Sprint Zero target tree with actual current workspace layout.
- **§9.1 B3 pitfall** — Updated "unchanged notes write their stored `encrypted_title` / `content` ciphertext verbatim" → "unchanged notes write their stored `blob` bytes verbatim". `[D-07]`
- **§9.2 T1** — Marked resolved, referencing §4.5 and D-06.
- **§9.2 T2** — Updated: with Option C, Sprint 1 JSON already uses `BlobCodec` blobs; JSON→SQLite migration is a structural copy. Noted remaining gap is the sequence diagram. `[D-07]`
- **§9.3 ConfigStore** — `config_path: Path` annotated with OS-standard path and "NOT inside data_dir" note.
- **§9.3 U1** — Marked resolved with Option C description. `[D-07]`
- **§9.3 U4** — Marked partially resolved: NoteStore call sites decided for Sprint 1; `migrate` call site (T2) remains open. `[D-07]`
- **§3.2 `StoreLoadError`** — new planned class added: `StoreLoadError(Exception)` with `path: Path` field. Raised by `NoteStore.load()` when `json.JSONDecodeError` is caught; caught by CLI startup callback. `[D-08]`
- **§4.1** — heading updated "Sprint Zero" → "Sprint 1"; added `StoreLoadError` and `OSError` error branches; added empty-input validation branch. `[D-08]`
- **§4.2** — added passphrase-mismatch `ClickException` branch (was just "print error, abort"); added `StoreLoadError` and `OSError` error branches. `[D-08]`
- **§4.2a** — new diagram added: Get/Update/Delete encrypted note error flows — `None` return from `get()` → `ClickException`; `InvalidTag` → `ClickException`; `OSError` on save → `ClickException`. `[D-08]`
- **§4.5** — error flows block added below `ctx.obj['store'] = store`: `StoreLoadError` → `ClickException`; `OSError` on unwritable `data_dir` → `ClickException`. `[D-08]`
- **§9.3 U2** — marked resolved with decision table. `[D-08]`

### `planning/design.md` (D-09 + metadata fix)
- **§3.1 `Note.metadata` note** — Strengthened: `metadata: dict` is permanently removed; future per-note fields must be typed `Note` fields decoded from blob header by `BlobCodec.decode()` — never a freeform dict. `[metadata fix]`
- **§3.1 `PluginRegistry` class diagram** — Added `_allowed: frozenset[str]` field; updated `call_hook` signature to show `dataclasses.replace(note)` copy; added annotations for allowlist check and mutable-field copy rule. `[D-09]`
- **§4.4 hook-dispatch diagram** — Replaced bare `fn(note_copy)` with explicit `dataclasses.replace(note)` step; added comment on mutable-field rule; noted only allowlisted plugins reach this point. `[D-09]`
- **ADR-05** — Updated decision text from "deep copy" to `dataclasses.replace(note)`; added mutable-field copy rule; added allowlist-at-registration-time note. `[D-09]`
- **§9.3 U3** — Marked resolved. `[D-09]`
- **§9.4 deferment table** — Updated BlobCodec row from "Sprint Zero scope" to "moved to Sprint 1". `[D-07]`

### `planning/prd.md` (moved from `docs/prd.md`)
- **R9.1 reference** — Updated "Settings stored in `<data-dir>/config.json`" to reflect fixed OS-standard path. `[D-06]`

### `planning/traceability-metrics.md` (moved from `docs/traceability-metrics.md`)
- Cross-references updated from `docs/design.md` → `planning/design.md`.
- **Orphan table** — `Note.encrypted_title: Optional[str]` row updated: removed by D-07; `Note.blob: bytes | None` is now the authoritative field for encrypted notes. `[D-07]`
- **FR-19/FR-98 gap #4** — BlobCodec call site marked partially resolved: `NoteStore` sprint 1 pattern decided. `[D-07]`
- **FR-101 gap #5** — Updated: Option C eliminates format-conversion concern; migration is now a structural copy; sequence diagram still missing. `[D-07]`

### `planning/user-stories.md`
- **US-7** — `<data-dir>/config.json` → fixed OS-standard path per D-06. `[D-06]`

### `planning/sprint-zero-plan.md`
- Three references updated from `docs/design.md` → `planning/design.md`.

### `planning/backlog.md`
- **B-43** — Annotated with Sprint 1 scope and `NoteStore` call pattern per D-07 decision. `[D-07]`

### `Copilot/discussion-list.md`
- Added open items **D-06 through D-14** covering all design gaps from `docs/design.md` §9 (T1–T8, U1–U5, extension manifest).
- Added **VS Code extension system research directions** to D-06, D-09, D-12.
- **D-06 resolved** and moved to Resolved Items section.
- **D-07 resolved** and moved to Resolved Items section. `[D-07]`
- **D-10 updated** — Removed U4 sub-item (call site resolved by D-07); narrowed to T2 (migration sequence diagram); noted Option C simplifies migration to a structural copy. `[D-07]`

---

## Key Decisions

### D-06 — CLI Startup: Store Factory and ConfigStore Integration (resolved 2026-05-11)
- **ConfigStore location:** Fixed OS-standard path (`%APPDATA%\astranotes\config.json` on Windows; `~/.config/astranotes/config.json` on Linux/macOS). Not inside `data_dir`. Moving `--data-dir` does not move the config file.
- **`data_dir` resolution:** Read from `config["data_dir"]`; `--data-dir` CLI flag overrides at runtime.
- **Startup order:** (1) `ConfigStore.load()` from OS path; (2) resolve `data_dir`; (3) store selection (`notes.db` → `DatabaseStore`, else `NoteStore`); (4) `PluginRegistry.load_manifests()` eagerly, activation deferred to first relevant note open (VS Code activation-events model).
- **Code location:** Single Click group callback in `src/cli.py`. `--help`/`--version` short-circuit before it.

### D-07 — `Note.title` Dual-Field State Machine (resolved 2026-05-11)
- **Decision — Option C:** `encrypted_title` removed from `Note`. `Note.blob: bytes | None` is the sole authoritative storage for encrypted notes. `BlobCodec` moved to Sprint 1.
- **`NoteStore` call pattern:** `BlobCodec.encode() + encrypt()` in `add()`; `BlobCodec.decrypt() + decode()` in `load()` and `get()` when a key is present.
- **State machine:** Unencrypted (`blob=None`, plaintext fields); Encrypted+no key (`blob=bytes`, title=`"[Encrypted Note]"`, content=`""`); Encrypted+correct key (`blob=bytes`, title/content populated in-memory from blob).
- **`migrate` simplification:** With Option C, Sprint 1 JSON already uses blobs; JSON→SQLite migration is a structural copy, not a format conversion. T2 design gap (sequence diagram) remains open — tracked in D-10.
- **Files updated:** `planning/design.md` (§3.1, §3.2, §4.2, §5.1, §9.1–§9.4), `planning/traceability-metrics.md`, `Copilot/discussion-list.md`, `planning/backlog.md`.

### D-09 — `PluginRegistry` Allowlist and Read-Only Copy Call Sites (resolved 2026-05-11)
- **Allowlist check location:** `register_plugin()` — VS Code install-time validation model. Plugin not in `config["allowed_plugins"]` → logged as warning, skipped, never enters registry. `[REQ R4.10]`
- **Note isolation:** `dataclasses.replace(note)` — safe for current all-primitive `Note` fields. Rule: future mutable fields (e.g. `tags: list[str]`) must be explicitly shallow-copied at the call site.
- **Rationale over `copy.deepcopy`:** 20× faster for same result on current `Note`; `deepcopy` would only matter if `Note` contained deeply nested mutable objects, which the blob-header typed-field rule prevents.
- **Files updated:** `planning/design.md` (§3.1 `PluginRegistry` diagram, §4.4, ADR-05, §9.3 U3), `Copilot/discussion-list.md`.

### `Note.metadata: dict` — Permanent Removal (2026-05-11)
- `Note.metadata: dict` permanently removed. Rationale: a freeform dict would contradict R2.9 (all metadata inside blob), recreate the dual-source problem D-07 resolved, and bypass BlobCodec validation.
- Rule codified: future per-note fields must be **typed `Note` fields** decoded from the blob JSON header by `BlobCodec.decode()`.
- **Files updated:** `planning/design.md` §3.1 note, `planning/traceability-metrics.md` orphan table, `planning/sprint-zero-plan.md` checklist.

---
- **Wrong passphrase** (`InvalidTag`): propagates from `BlobCodec.decrypt()` through `NoteStore.get()`; CLI catches as `ClickException("[NoteStore] Wrong passphrase — note <id> could not be decrypted.")` → exit 1. (Option B)
- **Note not found**: `NoteStore.get()` returns `None`; CLI checks return value, raises `ClickException("Note <id> not found.")` → exit 1. (Option A)
- **Disk full / `OSError`**: `NoteStore.save()` lets `OSError` propagate; CLI catches as `ClickException("[NoteStore] Save failed: <msg>")` → exit 1. (Option A)
- **Corrupt `notes.json`**: `NoteStore.load()` catches `json.JSONDecodeError`, wraps in `StoreLoadError(path)`; CLI startup callback catches as `ClickException("[NoteStore] notes.json corrupt: <path>. Restore from backup.")` → exit 1. (Option B)
- **New class**: `StoreLoadError(Exception)` with `path: Path` field — only exception class introduced by this decision.
- **Files updated**: `planning/design.md` (§3.2, §4.1, §4.2, §4.2a [new], §4.5, §9.3 U2), `Copilot/discussion-list.md`.

---
- After D-06: Checked `requirements.md`, `prd.md`, `docs/design.md`, `planning/backlog.md`, `Copilot/discussion-list.md`. Found and fixed R9.1 conflict (`<data-dir>/config.json` → OS-standard path); fixed `§3.2 ConfigStore.config_path` annotation; no conflicts in `backlog.md`.
- After D-07: Checked `requirements.md`, `prd.md`, `user-stories.md`, `traceability-metrics.md` for `encrypted_title` references. All instances updated or marked resolved. No unresolved conflicts.
- After D-08: Checked `requirements.md`, `prd.md`, `traceability-metrics.md` for R5.2/R5.3 coverage. All already reference `ClickException` + exit 1 pattern. `StoreLoadError` is a new internal class; no requirement update needed. No conflicts.
- After D-09: Checked all planning files for `deepcopy` references — none found. Checked `allowed_plugins` references — all consistent with check-at-registration decision. Checked `Note.metadata` — cleaned in design.md, traceability-metrics.md, sprint-zero-plan.md. No remaining conflicts.

---

## Tests Performed
No code written; no tests applicable.

---

## Follow-Up Actions
- ~~D-10 through D-14 remain open — to be resolved before their blocking sprints begin.~~
- ~~Next priority: D-10 (migration sequence diagram) — blocks Sprint 2.~~
- **D-10 resolved 2026-05-12** — Sprint reorganization: SQLite (`DatabaseStore`) from Sprint 0. No JSON storage phase. `migrate` command (B-48), B-72, B-80 dropped. B-42, B-43, B-51, B-74 moved to Sprint 0; B-65, B-66 moved to Sprint 1. D-11 through D-14 remain open.
