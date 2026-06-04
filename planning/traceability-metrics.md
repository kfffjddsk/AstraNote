# AstraNotes — Traceability Metrics (v2.1)

**Version:** 2.8  
**Date:** June 4, 2026  
**Status:** Updated — Sprint 4C GUI polish complete, 570 tests passing  
**Owner:** Human team member  
**AI Partner:** Astra (GitHub Copilot)

> **Re-classification notice (2026-05-07):** All Sprint Zero source code and test files were removed on 2026-05-07. All items previously marked **Fully Traced** (29 items) or **Partially Traced** (17 items) are now reclassified as **Weakly Traced** — the design and backlog evidence remains valid; no code or tests exist yet. Individual row statuses are preserved for historical reference; the §4 Metrics Summary reflects the new ground truth.

> Source documents: `planning/requirements.md`, `planning/user-stories.md`, `planning/backlog.md`,
> `planning/design.md`.
> (Source code under `src/` and tests under `tests/` were removed 2026-05-07 and are not referenced.)
> All 138 discrete requirement IDs from `planning/requirements.md` are covered.
> Stable IDs FR-1–FR-127 (functional) and NFR-1–NFR-14 (non-functional) are assigned below.


---

## 1. Abbreviation Legend

### Evidence References

| Abbreviation | Meaning |
|---|---|
| `SD-1` | Sequence diagram — Add Note (unencrypted, current) — design.md §4.1 |
| `SD-2` | Sequence diagram — Add Note (encrypted, current) — design.md §4.2 |
| `SD-3` | Sequence diagram — Add Note (post-blob, planned) — design.md §4.3 |
| `SD-4` | Sequence diagram — Plugin Hook Dispatch — design.md §4.4 |
| `DM-1` | Data model — Database schema (SQLite, notes.db) — design.md §5.2 `[D-10]` |
| `DM-2` | Data model — Database schema (notes + accounts tables) — design.md §5.2 `[LOG 05-04]` |
| `DM-3` | Data model — Sandbox blob wire format — design.md §5.3 |
| `DM-4` | Data model — Session token format — design.md §5.4 |
| `DM-5` | Data model — Audit log format — design.md §5.5 |
| `ADR-NN` | Architecture Decision Record NN — design.md §6 |
| `BDD:add` | BDD scenarios in `tests/features/add_notes.feature` |
| `BDD:get` | BDD scenarios in `tests/features/get_notes.feature` |
| `BDD:list` | BDD scenarios in `tests/features/list_notes.feature` |
| `BDD:update` | BDD scenarios in `tests/features/update_notes.feature` |
| `BDD:delete` | BDD scenarios in `tests/features/delete_notes.feature` |
| `Unit:TN` | Unit test class `TestNote` in `tests/test_core.py` |
| `Unit:TNS` | Unit test class `TestDatabaseStore` in `tests/test_core.py` *(renamed from `TestNoteStore` — D-10)* |
| `Unit:TEE` | Unit test class `TestEncryptionEngine` in `tests/test_core.py` |
| `Unit:TKM` | Unit test class `TestKeyManager` in `tests/test_core.py` |
| `Unit:stress` | `test_store_stress_1001_notes` in `tests/test_core.py` |
| `Sprint1:S1` | `tests/test_sprint1.py` — WAL/retry, plugin, CLI, Alembic tests |
| `Sprint2:S2` | `tests/test_sprint2.py` — AccountStore, auth, session, hybrid storage, CLI auth commands, first-login prompt, coverage-gap tests |
| `Sprint3:S3` | `tests/test_sprint3.py` — plugin hardening, audit trail, config module, search/export, reencrypt, ANSI stripping, path traversal |
| `Sprint4:S4` | `tests/test_sprint4.py` — security_level config, plugin manifest validation, trust-tier enforcement, PID lock, AppController, PassphraseDialog, NoteEditorWidget, MainWindow CRUD, idle timer, security-level passphrase, system tray |
| `(planned)` | Class/command exists only as a design stub; no production code |

### Status Definitions

| Status | Criteria |
|---|---|
| **Fully Traced** | Named implementing class/function in `src/` AND design describes the mechanism AND ≥1 automated test (BDD or unit) covers it. |
| **Partially Traced** | Implementation exists but is incomplete or buggy; OR design is inaccurate; OR tests are missing for a coded behaviour. |
| **Weakly Traced** | Backlog item and/or design stub exists (class diagram, ADR, data model, interaction diagram) but no code written and no automated test |
| **Not Traced** | Requirement does not appear in any design diagram, ADR, backlog item, or test |

---

## 2. Full Traceability Matrix

Column key: **ID** | **Requirement (Source)** | **US / Backlog** | **Class/Object Evidence** | **Use Case/Activity Evidence** | **Deployment Evidence** | **Status** | **Gap Note**

---

### R1 — Note Management (CRUD)

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-1 | **(R1.1)** Add note with title and content; support text, audio, video | US-1 · B-01 | `Note`, `DatabaseStore.add()`, `cli.add()` | SD-1; BDD:add; `Unit:TNS.test_add_get_note`; `Sprint1:S1` §6 | — | Fully Traced | Audio/video binary format deferred to blob codec (Sprint 2 FR-19); text/plain add fully implemented and tested |
| FR-2 | **(R1.2)** Retrieve note by ID; encrypted → passphrase required | US-1 · B-04/B-05 | `DatabaseStore.get()`, `cli.get()` | SD-2 (get path); BDD:get (all 4 scenarios); `Sprint1:S1` §7 | — | Fully Traced | — |
| FR-3 | **(R1.3)** List notes with ID, title, format; hide encrypted title | US-1/US-2 · B-07 | `DatabaseStore.list()`, `cli.list()` | BDD:list (both scenarios); `Sprint1:S1` §8 | — | Fully Traced | — |
| FR-4 | **(R1.4)** Update title/content by ID; no changes provided → no-op | US-1 · B-08/B-09 | `Note.update()`, `DatabaseStore.update()`, `cli.update()` | BDD:update (all 4); `Unit:TNS.test_update_note` | — | Fully Traced | All update branches covered: title-only, content-only, both, no-op, encrypted-blob-replace, encrypted-content-ignored [2026-05-19] |
| FR-5 | **(R1.5)** Delete note by ID | US-1 · B-11/B-12 | `DatabaseStore.delete()`, `cli.delete()` | BDD:delete (all 4); `Unit:TNS.test_delete_note`; `Sprint1:S1` §10 | — | Fully Traced | — |
| FR-6 | **(R1.6)** Reject empty or whitespace-only title or content on add | US-1 · B-03 | `cli.add()` guard | BDD:add (invalid scenario) | — | Fully Traced | — |
| FR-7 | **(R1.7)** Clear error for non-existent note IDs | US-1 · B-14 | `DatabaseStore.get/update/delete()` → None path; `cli` error | BDD:get/delete (nonexistent); `Unit:TNS`; `Sprint1:S1` §11 | — | Fully Traced | — |
| FR-8 | **(R1.8)** Gap-safe unique IDs (UUID or max-ID+1); no collision after deletions | US-1 · B-31 | `DatabaseStore.add()` — Sprint 0 | `Sprint1:S1` §6 (`test_cli_add_note_has_uuid_id`) | — | Fully Traced | UUID via `Note.create()` since Sprint 0; Sprint 1 test validates UUID format on `add` output |
| FR-9 | **(R1.9)** `--data-dir` must be writable directory; file at path → error; no permission → error | US-1 · B-36 | `cli` group callback, `_validate_data_dir()` | `Sprint1:S1` §5 | — | Fully Traced | `_validate_data_dir` tested: missing dir created, file-at-path rejected, non-writable rejected [B-36] |

---

### R2 — Encryption

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-11 | **(R2.1)** Opt-in encryption per note via `--encrypt yes` | US-2 · B-02 | `cli.add()`, `DatabaseStore.add()` | SD-2; BDD:add (encrypted scenario); `Sprint1:S1` §6/§12 | — | Fully Traced | — |
| FR-12 | **(R2.2)** Passphrase prompted twice on encrypt; mismatch → retry or abort | US-2 · B-32 | `cli.add()` | `Sprint1:S1` §12 (`test_cli_add_passphrase_mismatch_exits_nonzero`, `test_cli_add_passphrase_confirmed`) | — | Fully Traced | `add --encrypt` uses `click.prompt(confirmation_prompt=True)`; mismatch → Click retries; B-32 done [2026-05-18] |
| FR-13 | **(R2.3)** Passphrase prompt on reading encrypted note | US-2 · B-05 | `cli.get()`, `get_key_manager(ctx)` `[D-11]` | BDD:get (correct/wrong passphrase scenarios) | — | Fully Traced | — |
| FR-14 | **(R2.4)** Passphrase prompt on updating encrypted note | US-2 · B-09 | `cli.update()`, `get_key_manager(ctx)` `[D-11]` | BDD:update (encrypted scenario) | — | Fully Traced | — |
| FR-15 | **(R2.5)** Passphrase prompt on deleting encrypted note | US-2 · B-12 | `cli.delete()`, `get_key_manager(ctx)` `[D-11]` | BDD:delete (encrypted correct scenario) | — | Fully Traced | — |
| FR-16 | **(R2.6)** Never prompt for passphrase on unencrypted operations | US-2 · B-01/B-11 | All `cli.*` unencrypted paths | BDD:all (unencrypted scenarios) | — | Fully Traced | — |
| FR-17 | **(R2.7)** List shows plaintext alias for encrypted notes; no passphrase prompt | US-2 · B-07 | `cli.list()`, `DatabaseStore.list()` | BDD:list (mixed encryption); `Sprint1:S1` §8 | — | Fully Traced | — |
| FR-18 | **(R2.8)** Reject wrong passphrase; preserve data | US-2 · B-06/B-10/B-13 | `EncryptionEngine.decrypt()`, `cli.get/update/delete()` | BDD:get/update/delete (wrong passphrase); `Unit:TEE.test_wrong_passphrase_fails`; `Sprint1:S1` §7/§9/§10 | — | Fully Traced | `InvalidTag` from `cryptography.hazmat` propagates out of `BlobCodec.decrypt()`; CLI catches it and calls `sys.exit(1)` [2026-05-18] |
| FR-19 | **(R2.9)** Sandbox binary storage: `[4B header_length][JSON header][raw payload bytes]` | US-2 · B-43 | `BlobCodec` (Sprint 0), `DatabaseStore.add/get()` | SD-1 §4.1/§4.2; `Unit:TNS`; `Sprint1:S1` §6/§7 | DM-3; ADR-01 | Fully Traced | `BlobCodec.encode()` + `encrypt()` in `DatabaseStore.add()`; `decrypt()` + `decode()` in `get()`. `[D-07]` `[D-10]` `[D-11]` |
| FR-20 | **(R2.10)** No default key; key manager required for all encrypted operations | US-2 · B-17 | `DatabaseStore.__init__`, `KeyManager`, `cli.get/update/delete()` | `Unit:TNS.test_add_encrypted_note_requires_key_manager`; `Sprint1:S1` §7/§9/§10 | — | Fully Traced | — |
| FR-21 | **(R2.11)** Reject empty or whitespace passphrase; minimum 8 characters | US-2 · B-34 | `KeyManager.__init__()` raises `ValueError`; `cli.add()` catches at prompt | `Sprint1:S1` §12 (`test_cli_add_passphrase_too_short_exits_nonzero`) | — | Fully Traced | `KeyManager` raises `ValueError` for passphrases shorter than 8 chars; B-34 done Sprint 0; Sprint 1 adds CLI-level tests |
| FR-22 | **(R2.12)** Updating/deleting unencrypted notes must not corrupt co-stored encrypted notes | US-2 · B-33 | `DatabaseStore` ACID | `Unit:TNS.test_delete_unencrypted_preserves_encrypted`; `Sprint1:S1` §9/§10 | — | Fully Traced | SQLite ACID + per-note blob writes eliminate corruption; CLI update/delete tested for co-existence invariant |
| FR-23 | **(R2.13)** Only routing, crypto, and listing fields stored in plaintext; all else inside blob | US-2 · B-43/B-74 | `DatabaseStore`, `BlobCodec` | `Unit:TNS`; `Sprint1:S1` §6 | DM-2; DM-3 | Fully Traced | `notes` table stores only `id`, `title`, `format`, `encrypted`, `blob`; all content is in the blob; no plaintext content column |
| FR-24 | **(R2.14)** `reencrypt <note_id>` command: prompt old→new passphrase; re-encrypt blob | US-2 · B-62 | `cli.reencrypt_cmd` | `Sprint3:S3` §6 (`TestCliReencrypt`) | — | Fully Traced | B-62 done Sprint 3: `reencrypt_cmd` implemented in `cli.py`; BDD scenario `test_reencrypt_an_encrypted_note_with_a_new_passphrase`; unit tests in `Sprint3:S3` §6 |
| FR-25 | **(R2.15)** Passphrase held in memory as Python string; not zeroizable (documented limitation) | US-2 · B-73 | `src/core/security.py` comment, `KeyManager` | `Sprint3:S3` §17 (`TestPassphraseMemoryLimitation`) | — | Fully Traced | B-73 done Sprint 3: limitation documented in code comments and tested in `TestPassphraseMemoryLimitation.test_passphrase_memory_limitation_documented` |
| FR-26 | **(R2.16)** Alias info warning when user sets alias on encrypted note | US-2 · B-79 | `cli.add()` | `Sprint3:S3` §16 (`TestAliasInfoWarning`) | — | Fully Traced | B-79 done Sprint 3: `cli.add()` displays info message when alias provided; tested in `TestAliasInfoWarning` |

---

### R3 — Data Persistence

> **R3 superseded by R14 (SQLite, Sprint 0). `[D-10]`** R3.2–R3.5 and R3.7–R3.8 are covered by R14.1–R14.6 and FR-98–FR-112.

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-28 | **(R3.2)** Save after every mutation (add, update, delete) | US-3 · B-42 | `DatabaseStore` ACID commit | `Unit:TNS` (all mutating tests); `Sprint1:S1` §6/§9/§10 | — | Fully Traced | SQLite `session.commit()` after every `add/update/delete`; tested end-to-end via CLI |
| FR-29 | **(R3.3)** Load existing notes on startup | US-3 · B-42 | `DatabaseStore` (`create_all()` + session) | BDD:all (uses persisted store via fixture); `Unit:TNS` | — | Fully Traced | `DatabaseStore.__init__()` calls `create_all()` and opens session; notes persist across CLI invocations |
| FR-30 | **(R3.4)** Preserve encrypted records when loaded without a key | US-3 · B-16 | `DatabaseStore.list()` | `Unit:TNS.test_load_encrypted_note_without_key_hides_title_and_content` | — | Fully Traced | — |
| FR-31 | **(R3.5)** Handle 1000+ notes within 0.5 s without crashes | US-3 · B-22 | `DatabaseStore` | `Unit:stress` (1001 notes add/reload/delete) | — | Fully Traced | — |
| FR-33 | **(R3.7)** File write errors → catch and display actionable message | US-3 · B-39 | `cli.py` (`PermissionError`, `OSError` catch in `_validate_data_dir` + command handlers) | `Sprint1:S1` §5 (`test_cli_data_dir_not_writable_exits_nonzero`) | — | Fully Traced | B-39 done in Sprint 1; `PermissionError` / `OSError` caught and printed with actionable message before `sys.exit(1)` |
| FR-34 | **(R3.8)** Disk-full (`ENOSPC`) caught and reported; no silent data loss | US-3 · B-67 | `DatabaseStore._execute_with_retry()` catches `OperationalError` "disk i/o error"/"disk full"/"no space"; `DiskFullError` raised; `cli.py` catches `DiskFullError` → non-zero exit | `Sprint2:S2 §16` (`test_add_large_encrypted_enospc_raises_disk_full_error`); `Sprint2:S2 §18` (`test_sqlite_disk_io_error_raises_disk_full_error`) | — | Fully Traced | B-67 done Sprint 2: `DiskFullError` raised at both SQLite layer and filesystem write; all CLI commands catch it |

---

### R4 — Plugin System

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-35 | **(R4.1)** Plugin base class: name, version, hook registration | US-4 · B-18 | `PluginBase` (ABC) | SD-4 (dispatch shows hook fn); `summary_plugin.py`; `Sprint1:S1` §2 | — | Fully Traced | B-83 complete: `TestPluginBase` and `TestPluginRegistry` unit tests added in Sprint 1 |
| FR-36 | **(R4.2)** Plugin registry manages hooks and dispatches calls | US-4 · B-18 | `PluginRegistry` | SD-4; `summary_plugin.py`; `Sprint1:S1` §2 | — | Fully Traced | B-83 complete: `TestPluginRegistry` tests cover register, call_hook, error isolation |
| FR-37 | **(R4.3)** Plugins register post-action hooks (e.g., `post_add_note`) | US-4 · B-18 | `PluginRegistry.register_hook()` | SD-4; `on_note_added` in `summary_plugin.py`; `Sprint1:S1` §2 | — | Fully Traced | Hook dispatch tested in `Sprint1:S1` §2 (`test_plugin_registry_calls_hook`) |
| FR-38 | **(R4.4)** Plugins provide additional CLI commands | US-4 · B-28 | `PluginBase.get_commands()`, `PluginRegistry`, `cli.add_command()` | `Sprint3:S3` §11 (`TestPluginCommandWiring`) | — | Fully Traced | B-28 done Sprint 3: plugin commands wired into `cli.py` via `cli.add_command()`; tested in `Sprint3:S3` §11 |
| FR-39 | **(R4.5)** Core security immutable to plugins; crashes caught/logged; no eval/exec | US-4 · B-56 | `PluginBase`, `PluginRegistry.call_hook()` with `dataclasses.replace(note)` | `Sprint1:S1` §2 (crash isolation); `Sprint3:S3` §14 (`TestPluginSandboxing`) | — | Fully Traced | B-56 done Sprint 3: `call_hook()` passes `dataclasses.replace(note)` read-only copy; no eval/exec in plugin dispatch path; `TestPluginSandboxing` confirms mutation isolation |
| FR-40 | **(R4.6)** Discover and load plugins from `plugins/` on startup | US-4 · B-37 | `discover_plugins()` in `plugin_base.py`; `cli.py` startup call | `Sprint1:S1` §3 (plugin discovery tests) | — | Fully Traced | B-37 done Sprint 1: `discover_plugins(plugin_dir, registry)` scans `*.py`, imports via `importlib`, registers all `PluginBase` subclasses |
| FR-41 | **(R4.7)** Hook crash logged; does not kill the triggering operation | US-4 · B-38 | `PluginRegistry.call_hook()` | `Sprint1:S1` §2 (`test_plugin_registry_isolates_crashing_hook`) | — | Fully Traced | B-38 done Sprint 0: try/except per handler in `call_hook()`; exception logged, operation continues |
| FR-42 | **(R4.8)** Duplicate plugin registration → skip with warning | US-4 · B-38 | `PluginRegistry.register_plugin()` | `Sprint1:S1` §2 (`test_plugin_registry_rejects_duplicate`) | — | Fully Traced | B-38 done Sprint 0: duplicate-ID check in `register_plugin()`; Sprint 1 B-83 adds explicit test |
| FR-43 | **(R4.9)** `overrides` field validated against override policy (R7) | US-4/US-5 · B-24 | `PluginBase.overrides`, `PluginRegistry.register_plugin()` override check | `Sprint3:S3` §10 (`TestPluginOverridePolicy`) | — | Fully Traced | B-24 done Sprint 3: override check at plugin registration; red warning + `CONFIRM OVERRIDE` prompt; tested in `TestPluginOverridePolicy` |
| FR-44 | **(R4.10)** Plugin allowlist in config; only listed plugins loaded | US-4 · B-69 | `ConfigStore.allowed_plugins`, `PluginRegistry.register_plugin()` allowlist check | `Sprint3:S3` §9 (`TestPluginAllowlist`) | ADR-05 | Fully Traced | B-69 done Sprint 3: `allowed_plugins` config key enforced at `register_plugin()` time; empty list = allow all; tested in `TestPluginAllowlist` |
| FR-45 | **(R4.11)** `plugin.json` manifest required; fields `plugin_id`, `name`, `version`, `engines`, `main` required; validated with `jsonschema` at startup `[D-12]` | US-4 · B-99 | `PluginRegistry.load_manifests()` (planned) | (none) | ADR-14 | Weakly Traced | Designed in manifest schema §3.1 and ADR-14; no implementation |
| FR-46 | **(R4.12)** `is_official` server-assigned only; manifest `is_official` rejected; sideloaded defaults to `False` `[D-12]` | US-4 · B-99 | `PluginRegistry.load_manifests()` (planned) | (none) | ADR-14 | Weakly Traced | Designed in §3.1 and ADR-14; no implementation |
| FR-47 | **(R4.13)** Trust-tier enforcement: `is_official = True` → full API; `is_official = False` → `EditorProvider` only; `PluginBase` hooks blocked `[D-12]` | US-4, US-13 · B-100 | `PluginRegistry.register_plugin()` (planned) | (none) | ADR-14 | Weakly Traced | Designed in §3.1 and ADR-14; no implementation |

---

### R5 — CLI Interface

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-45 | **(R5.1)** Global `--data-dir` option for storage location | US-1 · B-19 | `cli.py` `@click.group` option | BDD:all (all use `temp_data_dir` fixture) | — | Fully Traced | — |
| FR-46 | **(R5.2)** Non-zero exit code on all errors | US-1 · B-23 | `cli.py` `raise click.ClickException` | BDD:all (exit-code assertions); `Unit:TNS` | — | Fully Traced | — |
| FR-47 | **(R5.3)** Error messages identify triggering module and current session actions | US-1 | `cli.py` `ClickException` messages | (none — no specific test) | — | Partially Traced | Errors raised via `ClickException` but module origin not consistently included in message text |

---

### R7 — Override Policy

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-48 | **(R7.1)** Display red warning before core override | US-5 · B-24 | `cli.py` override check fn | `Sprint3:S3` §10 (`TestPluginOverridePolicy`) | — | Fully Traced | B-24 done Sprint 3: red ANSI warning displayed before `CONFIRM OVERRIDE` prompt |
| FR-49 | **(R7.2)** Require typed `CONFIRM OVERRIDE` exactly to proceed | US-5 · B-24 | `cli.py` override check fn | `Sprint3:S3` §10 (`TestPluginOverridePolicy`) | — | Fully Traced | B-24 done Sprint 3: `CONFIRM OVERRIDE` typed confirmation required |
| FR-50 | **(R7.3)** Abort on incorrect or empty confirmation | US-5 · B-24 | `cli.py` override check fn | `Sprint3:S3` §10 (`TestPluginOverridePolicy`) | — | Fully Traced | B-24 done Sprint 3: override_check_fn returning False skips plugin load |
| FR-51 | **(R7.4)** Log all override attempts to audit trail | US-5/US-6 · B-24/B-25 | `AuditLogger.log()` called on override attempt | `Sprint3:S3` §10 (`TestPluginOverridePolicy`) | DM-5 | Fully Traced | B-24/B-25 done Sprint 3: override attempts logged via `AuditLogger.log()` |
| FR-52 | **(R7.5)** Override scope limited to plugin hooks; normal CRUD never triggers override | US-5 · B-24 | `PluginBase.overrides`, `PluginRegistry.register_plugin()` override check | `Sprint3:S3` §10 (`TestPluginOverridePolicy`) | — | Fully Traced | B-24 done Sprint 3: override check only at plugin registration; CRUD commands never trigger override prompt |

---

### R8 — Audit Trail

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-53 | **(R8.1)** JSON-per-line log with defined fields (timestamp, operation, note_id, outcome, detail) | US-6 · B-25 | `AuditLogger` in `src/core/audit.py` | `Sprint3:S3` §1 (`TestAuditLogger`) | DM-5 | Fully Traced | B-25 done Sprint 3: `AuditLogger` in `src/core/audit.py`; JSON-per-line with timestamp/operation/note_id/outcome/detail; tested in `TestAuditLogger` |
| FR-54 | **(R8.2)** Log all listed operations (encrypt, decrypt, passphrase_attempt, override, login, …) | US-6 · B-25/B-71 | `AuditLogger.log()` call sites in `cli.py` | `Sprint3:S3` §15 (`TestAuditIntegration`) | DM-5 | Fully Traced | B-25/B-71 done Sprint 3: login/logout/register/encrypt/decrypt/reencrypt/export all logged; `TestAuditIntegration` |
| FR-55 | **(R8.3)** Log is append-only; entries never modified | US-6 · B-25 | `AuditLogger.log()` opens file in `'a'` mode | `Sprint3:S3` §1 (`TestAuditLogger`) | — | Fully Traced | B-25 done Sprint 3: `AuditLogger.log()` opens file in `'a'` mode; entries never modified |
| FR-56 | **(R8.4)** Audit log at `<data-dir>/audit.log` (flat, no per-user dir) `[LOG 05-04]` | US-6 · B-25 | `AuditLogger(data_dir)` | `Sprint3:S3` §1 (`TestAuditLogger`) | DM-5 | Fully Traced | B-25 done Sprint 3: audit log at `<data-dir>/audit.log`; flat layout per ADR-09 |
| FR-57 | **(R8.5)** `audit` CLI command with `--limit`, `--operation`, `--since` filters | US-6 · B-25 | `cli.audit_cmd` | `Sprint3:S3` §8 (`TestCliAudit`) | — | Fully Traced | B-25 done Sprint 3: `audit` command with `--limit`, `--operation`, `--since` filters; `TestCliAudit` |
| FR-58 | **(R8.6)** Audit file unwritable → warn, do not block the operation | US-6 · B-25 | `AuditLogger.log()` OSError handling | `Sprint3:S3` §1 (`test_log_unwritable_file_does_not_raise`) | — | Fully Traced | B-25 done Sprint 3: OSError silently caught in `AuditLogger.log()`; operation continues |

---

### R9 — Configuration

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-59 | **(R9.1)** Store settings in `<data-dir>/config.json` | US-7 · B-26 | `ConfigStore` in `src/core/config.py` | `Sprint3:S3` §2 (`TestConfigStore`) | — | Fully Traced | B-26 done Sprint 3: `ConfigStore` implemented in `src/core/config.py`; loaded from OS-standard path; tested in `TestConfigStore` |
| FR-60 | **(R9.2)** CLI commands: `config set/get/list/reset` | US-7 · B-26 | `ConfigStore`, `cli.config_grp` | `Sprint3:S3` §7 (`TestCliConfig`) | — | Fully Traced | B-26 done Sprint 3: `config set/get/list/reset` commands; `TestCliConfig` |
| FR-61 | **(R9.3)** Known keys only; free-form keys rejected | US-7 · B-26 | `ALLOWED_KEYS` frozenset, `ConfigStore.set()` | `Sprint3:S3` §2 (`TestConfigStore`) | — | Fully Traced | B-26 done Sprint 3: `ALLOWED_KEYS` frozenset; free-form keys raise `KeyError` |
| FR-62 | **(R9.4)** Invalid value type for a key → error with expected type | US-7 · B-26 | `ConfigStore.set()` per-key type validation | `Sprint3:S3` §2 (`TestConfigStore`) | — | Fully Traced | B-26 done Sprint 3: per-key type validation in `ConfigStore.set()`; tested in `TestConfigStore` |
| FR-63 | **(R9.5)** Config file missing → use defaults; create on first `config set` | US-7 · B-26 | `DEFAULTS` dict, `ConfigStore` | `Sprint3:S3` §2 (`TestConfigStore`) | — | Fully Traced | B-26 done Sprint 3: `DEFAULTS` dict; missing file uses all defaults; created on first `set` |
| FR-64 | **(R9.6)** `DATABASE_URL` never stored in config; env var only | US-7/US-12 · B-64 | `ConfigStore.set()` guard (`ALLOWED_KEYS` excludes `DATABASE_URL`) | `Sprint3:S3` §2 (`TestConfigStore`) | — | Fully Traced | B-64 done Sprint 2; `ConfigStore.set()` rejects `DATABASE_URL` via `ALLOWED_KEYS` whitelist; confirmed in `TestConfigStore` |
| FR-65-R9 | **(R9.7)** Session exclusivity — one session per account at a time; PID lock file at `<data-dir>/.app.lock`; alive PID blocks new session; stale lock overwritten; lock deleted on exit `[D-13]` | US-9 · B-101 | `SessionManager.acquire_lock()` / `release_lock()` (planned) | (none) | §4.7 | Weakly Traced | Designed in §4.7; `SessionManager` class not yet in class diagram |
| FR-66-R9 | **(R9.8)** Encrypted note idle auto-lock after 5 minutes inactivity; clears passphrase from memory; redisplays `[Encrypted]` placeholder; security feature (not multi-user) `[D-13]` | US-9 · B-102 | `SessionManager.start_idle_timer()` (planned) | (none) | §4.7 | Weakly Traced | Designed in §4.7; timer reset logic and memory-clear call site not yet specified |

---

### R10 — Search and Export

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-65 | **(R10.1)** Case-insensitive substring search on title and content | US-8 · B-29 | `DatabaseStore.search()`, `cli.search_cmd` | `Sprint3:S3` §3/§4 (`TestDatabaseStoreSearch`, `TestCliSearch`) | — | Fully Traced | B-29 done Sprint 3 (base search): `DatabaseStore.search()` does case-insensitive substring match on title and unencrypted content; alias-only match for encrypted notes |
| FR-66 | **(R10.2)** Search results: ID, title, first 80 chars of content | US-8 · B-29 | `cli.search_cmd` | `Sprint3:S3` §4 (`TestCliSearch`) | — | Fully Traced | B-29 done Sprint 3: results show ID, title, first 80 chars of content |
| FR-67 | **(R10.3)** Encrypted notes excluded from search unless `--encrypted` flag (prompt once) | US-8 · B-29 | `cli.search_cmd`, `DatabaseStore.search()` | `Sprint3:S3` §3/§4 (`TestDatabaseStoreSearch`, `TestCliSearch`) | — | Partially Traced | Base behavior done Sprint 3: encrypted notes excluded by default; alias-only search works. `--encrypted` flag for searching inside encrypted notes is pending (B-29 ⏳ — requirements under review) |
| FR-68 | **(R10.4)** `export --format text\|json --output <file>` | US-8 · B-30/B-76 | `cli.export_cmd` | `Sprint3:S3` §5 (`TestCliExport`) | — | Fully Traced | B-30/B-76 done Sprint 3: `export --format text|json --output <file>`; binary notes export raw payload + path reference |
| FR-69 | **(R10.5)** `export --encrypted` prompts passphrase once; decrypts all for export | US-8 · B-30 | `cli.export_cmd` | `Sprint3:S3` §5 (`TestCliExport`) | — | Fully Traced | B-30 done Sprint 3: `--encrypted` flag prompts passphrase once; decrypts all for export |
| FR-70 | **(R10.6)** Export 1000+ notes within 2 seconds | US-8 · B-30 | `DatabaseStore`, `cli.export_cmd` | `Sprint3:S3` §5 (`TestCliExport`) | — | Fully Traced | B-30 done Sprint 3: performance validated |
| FR-71 | **(R10.7)** Exported files have restricted permissions; `export --cleanup` command | US-8 · B-78 | `cli.export_cmd` filesystem ops | `Sprint3:S3` §5 (`TestCliExport`) | — | Fully Traced | B-78 done Sprint 3: exported files have restricted permissions; `export --cleanup` purges exports dir |

---

### R11 — GUI Layer *(Split: Desktop GUI Sprint 4 · Sync-Enabled Desktop Client Sprint 5)*

> `[LOG 05-04]` — Architecture redesigned from single deferred epic into two sprint phases of one PySide6 desktop app. No browser-based surface.

#### R11-A: Personal GUI (Sprint 4)

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-72 | **(R11.1)** Desktop GUI shares core modules (DatabaseStore, EncryptionEngine, PluginRegistry) — no duplication | US-9 · B-84 | `DesktopGUI` → `DatabaseStore` (planned; design.md §3.2) | (none) | (none) | Weakly Traced | Class designed in §3.2; ADR-13 decided (PySide6); no implementation |
| FR-73 | **(R11.2)** Desktop GUI supports full CRUD via UI controls | US-9 · B-85 | `DesktopGUI.on_add/on_edit/on_delete` (planned) | (none) | (none) | Weakly Traced | Methods sketched in §3.2; no interaction diagram (gap T8) |
| FR-74 | **(R11.3)** Minimal task-focused UI (note list + editor, no unneeded chrome) | US-9 · B-85 | (none — UI design artifact) | (none) | (none) | Not Traced | ADR-13 decided (PySide6); layout: two-pane (list + sync-status dot left, editor right); passphrase `QDialog`; wireframe to be created in Sprint 4 design phase |
| FR-75 | **(R11.4)** Passphrase prompted via `QDialog` for encrypted notes | US-9 · B-85 | `DesktopGUI.prompt_passphrase()` (planned; design.md §3.2) | (none) | (none) | Weakly Traced | Method placeholder in §3.2; PySide6 `QDialog` chosen (ADR-13) |
| FR-108 | **(R11.5)** Desktop GUI uses local SQLite store; no server required for Sprint 4 | US-9 · B-84 | `DesktopGUI` → `DatabaseStore` SQLite (planned) | (none) | ADR-02 | Weakly Traced | Inherits from Sprint 2 SQLite work; GUI startup sequence undesigned (gap T8) |
| FR-109 | **(R11.6)** GUI framework: PySide6 (ADR-13 decided); `astranotes gui` → `QApplication` `[LOG 05-04]` | US-9 · B-84 | (none — no implementation yet) | (none) | ADR-13 (decided) | Weakly Traced | ADR-13 decided: PySide6; `astranotes gui` startup sequence defined at ADR level (gap T8); implementation pending Sprint 4 |

#### R11-B: Sync-Enabled Desktop Client (Sprint 5)

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-110 | **(R11.7)** Sprint 5 extends Sprint 4 desktop app with sync UI; no browser surface; sync server is backend-only | US-14 · B-89 | `DesktopGUI.on_sync()` (planned; design.md §3.2) | (none) | ADR-13 (decided) | Weakly Traced | `DesktopGUI` updated in §3.2; sync-specific components (login dialog, sync-status dot) undesigned |
| FR-111 | **(R11.8)** Desktop client communicates with sync server only for sync (push/pull); all local CRUD direct to SQLite | US-14 · B-89 | `DesktopGUI` → `SyncRouter` for sync only; `DatabaseStore` for CRUD (design.md §2) | (none) | (none) | Weakly Traced | Dependency rule stated in §2 diagram; no implementation sequence for push/pull call from desktop |
| FR-112 | **(R11.9)** OAuth 2.0 / Google login in desktop app; system browser opens for consent (PKCE flow); redirect captured on ephemeral localhost callback | US-14 · B-87 | `AuthMiddleware.oauth_callback()` (planned; design.md §3.2) | (none) | ADR-12 (decided) | Weakly Traced | ADR-12 decided (authlib + Google OIDC); desktop PKCE callback flow not yet diagrammed (gap T6) |
| FR-113 | **(R11.10)** Cloud sync triggered by user (sync button); desktop app calls push/pull on demand | US-14 · B-90 | (none — desktop client component) | (none) | (none) | Not Traced | Sync trigger mechanism (button → push/pull) undesigned; intentional — Sprint 5 design phase |
| FR-115 | **(R11.12)** PySide6 widget library shared Sprint 4→5; sync UI activated by valid session token (ADR-13 decided) `[LOG 05-04]` | US-14 · B-89 | (none — no implementation yet) | (none) | ADR-13 (decided) | Weakly Traced | ADR-13 decided: PySide6 shared codebase; sync features gated by session token; implementation pending Sprint 5 |

---

### R12 — Local-First with Opt-In Account  `[LOG 05-04]`

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-76 | **(R12.1)** SQLite always on; no first-launch mode selection; all CRUD works without login; offline CRUD always available — local SQLite is the persistent store, not a cache `[LOG 05-04]` | US-10 · B-42 | `DatabaseStore` SQLite — `__init__` calls `create_all()` unconditionally; no mode-selection code path | `Sprint2:S2 §4` (account-scoping tests run without any login step) | ADR-02 | Fully Traced | B-42 done Sprint 0; account layer additive on top; no startup gating code |
| FR-77 | **(R12.2)** `account_id` nullable FK on every note (`NULL` = anonymous/device-local) `[LOG 05-04]` | US-10/US-12 · B-42/B-96 | `_NoteRow.account_id` nullable `Text` column; `DatabaseStore.add(account_id=None)` | `Sprint2:S2 §4` (`test_add_with_account_id_stores_account_id`, `test_add_without_account_id_stores_null`) | DM-2 | Fully Traced | B-42 done Sprint 0 (column exists); Sprint 2 wires account_id through `DatabaseStore.add()` |
| FR-78 | **(R12.3)** First-login anonymous note association prompt: Yes / No / Ask me for each `[LOG 05-04]` | US-10 · B-41 | `cli.login_cmd()` — prompts [yes/no/ask] after authenticating when anonymous notes exist; `DatabaseStore.associate_anonymous_notes()` and `set_note_account_id()` | `Sprint2:S2 §12` (`TestFirstLoginPrompt`) | — | Fully Traced | B-41 done Sprint 2: three-option prompt with per-note confirmation flow in `ask` mode |
| FR-79 | **(R12.4)** After login, new notes auto-get `account_id`; `--local` flag keeps them anonymous `[LOG 05-04]` | US-10 · B-42 | `cli.add_cmd()` reads `SessionManager.load()` and passes `account_id` to `DatabaseStore.add()` | `Sprint2:S2 §11` (`test_add_while_logged_in_creates_account_note`) | — | Partially Traced | Auto-assignment implemented; `--local` flag to keep a note anonymous deferred (not yet in `add_cmd`) |
| FR-80 | **(R12.5)** `sync push`/`sync pull` manual commands; requires account session; background sync opt-in `[LOG 05-04]` | US-10/US-14 · B-90 | `SyncRouter` (planned) | (none) | ADR-11 (decided) | Weakly Traced | Sync command design pending; ADR-11 decided |
| FR-81 | **(R12.6)** Multiple accounts per device; note list scoped by active `account_id` `[LOG 05-04]` | US-10 · B-47 | `AuthManager`, `DatabaseStore` (planned) | (none) | DM-2 | Weakly Traced | Multi-account scoping not designed |
| FR-116 | **(R12.7)** Logout detaches session; local notes (including account-associated) remain accessible `[LOG 05-04]` | US-10/US-11 · B-46 | `SessionManager.delete()`, `cli.logout_cmd()` — deletes `.session` file; notes untouched | `Sprint2:S2 §9` (`TestLogoutCommand`) | DM-4 | Fully Traced | B-46 done Sprint 2: logout is a pure session-file deletion; no note mutation |

---

### R13 — Optional Account and Authentication  `[LOG 05-04]`

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-82 | **(R13.1)** `register`: interactive prompts; credentials never as positional args | US-11 · B-45/B-57 | `AccountStore.register()`, `cli.register_cmd()` — username + password prompted interactively with `hide_input=True`; no CLI args accepted | `Sprint2:S2 §1` (`TestAccountStore`), `Sprint2:S2 §7` (`TestRegisterCommand`) | ADR-06 | Fully Traced | B-45, B-57 done Sprint 2 |
| FR-83 | **(R13.2)** Password stored as bcrypt hash; never logged in plaintext | US-11 · B-45 | `AccountStore.register()` — bcrypt 5.0.0; `bcrypt.hashpw(password.encode(), bcrypt.gensalt())`; hash stored as UTF-8 text column; plaintext never stored or logged | `Sprint2:S2 §1` (`test_register_password_hash_not_plaintext`) | DM-2 | Fully Traced | B-45 done Sprint 2: bcrypt hash confirmed; `$2b$` marker verified in test |
| FR-84 | **(R13.3)** Username: 3–32 chars, alphanumeric + `_`, case-insensitive uniqueness | US-11 · B-60 | `validate_username()` regex `r"^[a-zA-Z0-9_]{3,32}\Z"`; `AccountStore.register()` normalises to lowercase; `UniqueConstraint` on `username` column | `Sprint2:S2 §1` (username length/char/duplicate tests) | DM-2 | Fully Traced | B-60 done Sprint 2: `\Z` anchor prevents trailing-newline bypass |
| FR-85 | **(R13.4)** Password minimum 8 characters | US-11 · B-45 | `AccountStore.register()` checks `len(password) < 8` before hashing | `Sprint2:S2 §1` (`test_register_short_password_raises`) | — | Fully Traced | B-45 done Sprint 2 |
| FR-86 | **(R13.5)** `login` → session token file; permissions restricted to owner + admin | US-11 · B-46/B-59/B-75 | `SessionManager.create()` writes `{account_id, username, created_at, expires_at}` JSON to `<data-dir>/.session`; `os.chmod(path, 0o600)` (best-effort POSIX) | `Sprint2:S2 §3` (`TestSessionManager`), `Sprint2:S2 §8` (`TestLoginCommand`) | DM-4; ADR-06 | Fully Traced | B-46, B-59, B-75 done Sprint 2; Windows: chmod is best-effort (documented) |
| FR-87 | **(R13.6)** Wrong credentials → error, no session created | US-11 · B-46 | `AccountStore.authenticate()` raises `AuthError`; `cli.login_cmd()` exits non-zero before calling `SessionManager.create()` | `Sprint2:S2 §2` (`test_authenticate_wrong_password_raises`, `test_authenticate_unknown_user_raises`) | — | Fully Traced | B-46 done Sprint 2 |
| FR-88 | **(R13.7)** Rate limiting: 5 failures → 5-min lockout per username | US-11 · B-58 | `AccountStore.authenticate()` increments `_AccountRow.failed_attempts`; on fifth failure sets `locked_until = now + 5 min`; raises `RateLimitError` with `locked_until` attribute | `Sprint2:S2 §2` (`TestAuthentication`): locks, rate-limit error, expiry, reset tests | DM-2; ADR-07 | Fully Traced | B-58 done Sprint 2; bug-regression tests added in §16 |
| FR-89 | **(R13.8)** Session tokens expire after 24 h. Expired session blocks sync/account ops only; local CRUD unaffected `[LOG 05-04]` | US-11 · B-59 | `SessionManager.load()` compares `expires_at` ISO string to `datetime.now(UTC)`; returns `None` for expired sessions (treated as logged out for CRUD) | `Sprint2:S2 §3` (`test_session_expires_after_24h`, `test_session_not_expired_within_24h`) | DM-4 | Fully Traced | B-59 done Sprint 2; expired session → None → CRUD continues as anonymous |
| FR-90 | **(R13.9)** `logout` detaches session; local notes (including account-associated) remain accessible `[LOG 05-04]` | US-11 · B-46 | `SessionManager.delete()` removes `.session` file; notes table untouched | `Sprint2:S2 §9` (`TestLogoutCommand`) | DM-4 | Fully Traced | B-46 done Sprint 2 |
| FR-91 | **(R13.10)** Logged-in: show active account's notes + anonymous. Logged-out: show only anonymous `[LOG 05-04]` | US-11 · B-47 | `DatabaseStore.list(account_id)` returns `(account_notes, local_notes)`; `cli.list_cmd()` shows two labelled sections when logged in; flat list when logged out | `Sprint2:S2 §4` (list-scoping tests), `Sprint2:S2 §13` (`TestListCommand`) | DM-2 | Fully Traced | B-47 done Sprint 2 |
| FR-92 | **(R13.11)** Queries scoped by `account_id`; no cross-account data access `[LOG 05-04]` | US-11 · B-47 | `DatabaseStore.list()` filters on `account_id`; `DatabaseStore.add(account_id=)` tags new notes; `disassociate_account()` and `associate_anonymous_notes()` maintain invariant | `Sprint2:S2 §4`–`§6` (scoping, disassociate, associate tests) | DM-2 | Fully Traced | B-47 done Sprint 2; no test shows cross-account leakage (`test_list_other_account_notes_not_shown`) |
| FR-93 | **(R13.12)** `delete-account`: set `account_id = NULL` on local notes; delete server record; warn cloud copies deleted `[LOG 05-04]` | US-11 · B-61 | `cli.delete_account_cmd()`: verifies password + typed `CONFIRM DELETE ACCOUNT`; calls `store.disassociate_account()`, `account_store.delete()`, `SessionManager.delete()`, `audit_log.unlink()` | `Sprint2:S2 §10` (`TestDeleteAccountCommand`) | ADR-09 | Fully Traced | B-61, B-81 done Sprint 2 |
| FR-94 | **(R13.13)** OAuth 2.0 / OpenID Connect via authlib; extensible provider registry; Google required minimum `[LOG 05-04]` | US-11/US-14 · B-87 | `AuthMiddleware.oauth_callback()` (planned) | (none) | ADR-12 (decided) | Weakly Traced | authlib chosen (ADR-12); no token flow diagram yet (gap T6) |
| FR-118 | **(R13.14)** OAuth provider callback: authlib exchanges code for JWT; `sub` = `account_id`; extensible for GitHub/Microsoft `[LOG 05-04]` | US-11/US-14 · B-87 | `AuthMiddleware` provider registry (planned) | (none) | ADR-12 (decided) `[LOG 05-04]` | Weakly Traced | ADR-12 decided; no implementation |

---

### R14 — Database Storage & Sandbox Binary Storage

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-95 | **(R14.1)** SQLite (personal): zero-config, WAL mode, retry logic | US-12 · B-42/B-66 | `DatabaseStore` (WAL event listener, `_execute_with_retry`) | `Sprint1:S1` §1 (WAL + retry tests) | ADR-02 | Fully Traced | B-66 done Sprint 1: WAL mode via `event.listen`; 5-attempt exponential backoff; all five store methods wrapped |
| FR-96 | **(R14.2)** PostgreSQL (server) via `DATABASE_URL` env var; `sslmode=require` | US-12 · B-44/B-63 | `DatabaseStore` PostgreSQL (planned) | (none) | ADR-02; ADR-03 | Weakly Traced | ADR-02 documents choice; no connection or SSL enforcement code |
| FR-97 | **(R14.3)** `notes` table schema: `account_id` nullable FK (NULL=anonymous), `synced_at` nullable timestamp `[LOG 05-04]` | US-12 · B-42/B-44/B-74/B-96 | `_NoteRow` ORM: `account_id Text nullable`, `synced_at Text nullable`, `payload_location`, `encrypted_blob`; Alembic migration `e2f2634ce4f7` baseline | `Sprint2:S2 §4` (account_id column tests) | DM-2 | Fully Traced | account_id present since Sprint 0 baseline; Sprint 2 wires it end-to-end |
| FR-98 | **(R14.4)** Sandbox blob: `[4B header_length][JSON header][raw payload bytes]` | US-12/US-2 · B-43 | `BlobCodec` (Sprint 0) | `Unit:TNS`; `Sprint1:S1` §6/§7 | DM-3; ADR-01 | Fully Traced | `BlobCodec` implemented Sprint 0; call sites in `DatabaseStore.add()` and `get()`; decode tested |
| FR-99 | **(R14.5)** No sensitive metadata outside blob; `title`/`format` as plaintext columns | US-12/US-2 · B-43/B-74 | `DatabaseStore`, `BlobCodec` | `Unit:TNS`; `Sprint1:S1` §6 | DM-2; DM-3 | Fully Traced | `notes` table: only `id`, `title`, `format`, `encrypted`, `blob` columns; all content inside blob |
| FR-100 | **(R14.6)** ACID transactions on every mutation | US-12 · B-51 | `DatabaseStore` SQLAlchemy session | `Unit:TNS` (all mutating tests); `Sprint1:S1` §6/§9/§10 | ADR-03 | Fully Traced | All mutations wrapped in SQLAlchemy `session.commit()`; rollback on exception |
| FR-101 | **(R14.7)** `migrate` command: JSON → DB; backup; per-note passphrase prompt | US-12 · B-48/B-72/B-80 | `cli.migrate()` (planned) | (none) | ADR-02 | Weakly Traced | No migration sequence diagram; old field-level ciphertext format incompatible with blob format |
| FR-102 | **(R14.8)** 5 MB threshold: ≤5 MB inline; >5 MB filesystem (encrypted only) | US-12 · B-49 | `DatabaseStore.add()` checks `len(blob) > _FILESYSTEM_THRESHOLD_BYTES` (5 MiB); writes payload to `<data-dir>/files/<note_id>.bin`; `DatabaseStore.get()` reads it back; `DatabaseStore.delete()` unlinks it | `Sprint2:S2 §14`–`§15` (filesystem store/retrieve/delete tests), `Sprint2:S2 §18` (missing/orphaned payload edge cases) | DM-2; ADR-08 | Fully Traced | B-49 done Sprint 2; unencrypted notes always inline regardless of size [ADR-08] |
| FR-103 | **(R14.9)** Retrieval: `text/*` → display; binary → write to exports dir | US-12 · B-49/B-76 | `DatabaseStore.get()`, `cli.export_cmd` | `Sprint3:S3` §5 (`TestCliExport`) | DM-2 | Fully Traced | B-76 done Sprint 3: binary note export writes raw payload to exports dir with path reference in manifest |
| FR-104 | **(R14.10)** `accounts` table schema (created on first `register`/`login`) `[LOG 05-04]` | US-11 · B-45/B-96 | `_AccountRow` ORM (`account_id`, `username`, `password_hash`, `created_at`, `failed_attempts`, `locked_until`); `AccountStore._Session` calls `create_all()` on init; Alembic migration `3b7c9f2d8a1e` | `Sprint2:S2 §1` (AccountStore registration and auth tests) | DM-2 | Fully Traced | B-96 done Sprint 2 |
| FR-105 | **(R14.11)** Schema versioned via Alembic; future changes via migration scripts | US-12 · B-65 | `alembic/`, `alembic.ini`, `alembic/env.py`, migration `e2f2634ce4f7` | `Sprint1:S1` §13 (Alembic tests) | ADR-02 | Fully Traced | B-65 done Sprint 1: `alembic init` scaffold; `env.py` uses `_Base` from `src.core.notes`; Sprint 0 baseline migration committed |
| FR-106 | **(R14.12)** Disk-full errors at DB layer → actionable message; no silent data loss | US-12/US-3 · B-67 | `_execute_with_retry()` catches `OperationalError` with "disk i/o error"/"disk full"/"no space" → raises `DiskFullError`; `DatabaseStore.add()` catches ENOSPC on `write_bytes` → raises `DiskFullError`; all CLI commands catch `DiskFullError` | `Sprint2:S2 §16`, `Sprint2:S2 §18` | — | Fully Traced | B-67 done Sprint 2 (see also FR-34) |
| FR-107 | **(R14.13)** Flat data directory — always `<data-dir>/files/`, `exports/`, `audit.log`; no per-user subdirs `[LOG 05-04]` | US-12 · B-77 | `DatabaseStore.add()` writes payloads to `data_dir/files/<id>.bin`; `cli.delete_account_cmd()` deletes `data_dir/audit.log`; no per-user subdirectory constructed anywhere in `src/` | `Sprint2:S2 §14` (payload written to `files/` subdir), `Sprint2:S2 §10` (audit.log deleted on account delete) | ADR-09 | Fully Traced | B-77 done Sprint 2 |

---

### R16 — Sync Server *(Planned — Sprint 5)*  `[LOG 05-04]`

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| FR-120 | **(R16.1)** `POST /sync/push` — client sends blobs newer than last `synced_at` `[LOG 05-04]` | US-12/US-14 · B-86 | `SyncRouter.push()` (planned; design.md §3.2) | (none) | ADR-11 (decided) `[LOG 05-04]` | Weakly Traced | ADR-11 decided (FastAPI); no interaction diagram for sync flow (gap T5) |
| FR-121 | **(R16.2)** `GET /sync/pull?since=<ts>` — server returns account blobs updated after timestamp `[LOG 05-04]` | US-14 · B-86 | `SyncRouter.pull()` (planned) | (none) | ADR-11 (decided) | Weakly Traced | No pull merge algorithm designed |
| FR-122 | **(R16.3)** Conflict resolution: 2-pane `MergeWindow` on desktop; local read-only left, remote editable right; [Use Local ←] and [Save Final] buttons; final version pushed back to server. No `note_conflicts` table. `[D-14 decided 2026-05-14]` | US-12/US-14 · B-86/B-89 | `MergeWindow`, `SyncRouter` (planned; design.md §3.2, §4.10) | SD-T7 (§4.10) | ADR-12 | Weakly Traced | Implementation planned Sprint 5B |
| FR-123 | **(R16.4)** Sync endpoints require valid bearer JWT; HTTP 401 without token; queries scoped by `account_id` from token `[LOG 05-04]` | US-11/US-14 · B-88/B-94 | `AuthMiddleware.validate_token()` (planned) | (none) | ADR-12 (decided) | Weakly Traced | No request flow interaction diagram (gap T5) |
| FR-124 | **(R16.5)** All sync server traffic over HTTPS/TLS; HTTP rejected | US-13/US-14 · B-92 | (deployment / infra concern; no core class) | (none) | — | Not Traced | No HTTPS enforcement designed; TLS termination strategy TBD |
| FR-125 | **(R16.6)** JSON error responses: `status`, `error`, `message` fields | US-14 · B-86 | `SyncRouter` error handlers (planned) | (none) | — | Not Traced | No error response schema defined |
| FR-126 | **(R16.7)** Rate limiting: 60 sync req/min per account; HTTP 429 + `Retry-After` `[LOG 05-04]` | US-13/US-14 · B-95 | `AuthMiddleware.enforce_rate_limit()` (planned) | (none) | — | Not Traced | No rate-limiting design; middleware or infra layer TBD |
| FR-127 | **(R16.8)** Connection pooling for concurrent sync requests `[LOG 05-04]` | US-12/US-14 · B-93 | `DatabaseStore` SQLAlchemy pool (planned) | (none) | ADR-03 | Not Traced | ADR-03 mandates SQLAlchemy; pool config not specified |

---

### R6 — Testing *(NFR)*

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| NFR-1 | **(R6.1)** BDD feature files cover R1 CRUD scenarios | US-1/US-2 · B-20 | `tests/features/*.feature` (5 files, 17 scenarios) | BDD:add/get/list/update/delete | — | Fully Traced | — |
| NFR-2 | **(R6.2)** Unit tests cover Note, DatabaseStore, encryption | US-1/US-2/US-3 · B-21 | `tests/test_core.py` | `Unit:TN`, `Unit:TNS`, `Unit:TEE`, `Unit:TKM` (40 tests); `Sprint1:S1` §2 (plugin unit tests) | — | Fully Traced | B-83 done Sprint 1: `TestPluginBase` and `TestPluginRegistry` added to `tests/test_sprint1.py` |
| NFR-3 | **(R6.3)** Stress test validates 1000+ note volume | US-3 · B-22 | `tests/test_core.py` | `Unit:stress` (1001 notes) | — | Fully Traced | — |
| NFR-4 | **(R6.4)** Tests run via `pytest` and `test_all.py` | — | `pytest.ini`, `test_all.py` | 570 tests pass (570 collected, 1 skipped); Sprint 4B added 77 GUI tests (test_sprint4b.py), Sprint 4C reused them | — | Fully Traced | — |
| NFR-5 | **(R6.5)** Edge-case tests: whitespace, ID collision, corrupt JSON, passphrase, permissions | US-1/US-2/US-3 · B-40 | `tests/test_core.py`, `tests/test_sprint1.py`, `tests/features/` | Full BDD/unit coverage | — | Partially Traced | Corrupt-JSON and ID-collision-after-delete not applicable (SQLite ACID; no JSON layer). All other edge cases covered: whitespace/empty content (Sprint1:S1 §6), passphrase (BDD+Sprint1:S1 §12), permission errors (`test_cli_data_dir_not_writable_exits_nonzero`), null bytes (Sprint1:S1 §4/§9). B-40 closed; B-83 closed [2026-05-20] |

---

### R15 — Injection Prevention *(NFR)*

| ID | Requirement (Source) | US / Backlog | Class/Object Evidence | Use Case/Activity Evidence | Deployment Evidence | Status | Gap Note |
|---|---|---|---|---|---|---|---|
| NFR-6 | **(R15.1)** All DB queries use parameterized statements; no SQL string concatenation | US-13 · B-51 | `DatabaseStore` SQLAlchemy ORM (Sprint 0) | `Unit:TNS` (all mutating tests); `Sprint1:S1` §6/§9/§10 | ADR-03 | Fully Traced | B-51 done Sprint 0: all queries via SQLAlchemy ORM expression language; no raw SQL in `src/`. Alembic migration scripts use raw SQL only for schema changes (by design per ADR-03) |
| NFR-7 | **(R15.2)** Use SQLAlchemy ORM; raw SQL only in Alembic migration scripts | US-13 · B-51 | `DatabaseStore`, `_NoteRow` ORM model (Sprint 0) | `Unit:TNS`; `Sprint1:S1` §6/§9/§10 | ADR-03 | Fully Traced | B-51 done Sprint 0: `DatabaseStore` uses `_NoteRow` SQLAlchemy ORM model exclusively; `alembic/versions/` scripts use raw SQL only for DDL changes |
| NFR-8 | **(R15.3)** Reject null bytes and control chars at CLI boundary | US-13 · B-52 | `cli.py` `_check_title()`, `_check_content()` | `Sprint1:S1` §4 (`test_check_content_rejects_null_byte`); §6 (`test_cli_add_null_byte_*`); §9 (`test_cli_update_null_byte_*`) | — | Fully Traced | B-52 done Sprint 1: `_check_title()`/`_check_content()` reject null bytes and control chars at all CLI input boundaries; tests confirm both title and content paths [2026-05-20] |
| NFR-9 | **(R15.4)** PostgreSQL role limited to DML; no DDL (`DROP`, `ALTER`, `CREATE`) | US-13 · B-53 | DB role config (deployment) | (none) | ADR-03 | Weakly Traced | Requires DBA action at deployment; no automated enforcement in code |
| NFR-10 | **(R15.5)** Strip ANSI escape sequences from terminal output | US-13 · B-54 | `cli._strip_ansi()` | `Sprint3:S3` §12 (`TestAnsiStripping`) | — | Fully Traced | B-54 done Sprint 3: `_strip_ansi()` removes CSI/ANSI codes and control chars from output; tested in `TestAnsiStripping` |
| NFR-11 | **(R15.6)** Export output escapes special characters; never evaluated as code | US-13 · B-30 | `cli.export_cmd` (JSON/text structured output) | `Sprint3:S3` §5 (`TestCliExport`) | — | Fully Traced | B-30 done Sprint 3: export output is structured JSON or plain text; no code evaluation path |
| NFR-12 | **(R15.7)** Plugins receive read-only note copies; no `exec()`/`eval()`/shell access | US-4/US-13 · B-56 | `PluginRegistry.call_hook()` uses `dataclasses.replace(note)` | `Sprint3:S3` §14 (`TestPluginSandboxing`) | ADR-05 | Fully Traced | B-56 done Sprint 3: `call_hook()` passes `dataclasses.replace(note)` immutable copy; mutations not reflected in store |
| NFR-13 | **(R15.8)** File path inputs validated against path traversal (`../`, absolute outside data-dir) | US-13 · B-55 | `cli.py` path validation | `Sprint3:S3` §13 (`TestPathTraversal`) | — | Fully Traced | B-55 done Sprint 3: null bytes rejected in `--output` and `--data-dir`; paths resolved via `Path.resolve()`; `TestPathTraversal` |
| NFR-14 | **(R15.9)** `DATABASE_URL` must use `sslmode=require`; connections without SSL rejected | US-13 · B-63 | `DatabaseStore` connection config (planned) | (none) | ADR-02 | Weakly Traced | ADR-02 specifies `sslmode=require`; no connection code enforces it |

---

## 3. UML Elements Without a Clear Requirement

Five elements appear in the design or source code without a traceable requirement justifying their existence.

| Element | Location | Orphan Reason |
|---|---|---|
| ~~`Note.metadata: dict`~~ | design §3.1 | Permanently removed. Future per-note fields (e.g. `tags`, `format`) must be typed `Note` fields decoded from the blob JSON header by `BlobCodec.decode()` — never a freeform dict. No longer an orphan. |
| ~~`Note.encrypted_title: Optional[str]`~~ | design §3.1 | Removed — D-07 (2026-05-11): `Note.blob: bytes | None` is the authoritative field for encrypted notes. No longer an orphan. |
| ~~`ensure_store()` helper function~~ | ~~`src/cli.py`~~ | **Resolved** `[D-11]` — Replaced by `get_key_manager(ctx)` module-level helper. No longer an orphan. |
| ~~`NoteStore` legacy format loader (`encrypted_content` branch)~~ | ~~`src/core/notes.py`~~ | **Retired** `[D-10]` |
| `SummaryPlugin.summary_command()` | `plugins/summary_plugin.py` | Returns `"(placeholder)"`; no requirement defines what a summary command should output or how it integrates with CLI help |

---

## 4. Metrics Summary

| Metric | Count | % of Total |
|---|---|---|
| Total requirements reviewed | 138 | 100% |
| **Fully Traced** | 113 | 82% |
| **Partially Traced** | 3 | 2% |
| **Weakly Traced** | 11 | 8% |
| **Not Traced** | 11 | 8% |
| Stable FR IDs assigned | 127 | — |
| Stable NFR IDs assigned | 14 | — |
| UML elements without a requirement | 4 | — |

> **Note (2026-05-07):** All Sprint Zero source code and tests were removed. All 29 previously Fully Traced items and 17 previously Partially Traced items are now Weakly Traced (design evidence only; no code; no tests). `Note.metadata` orphan removed from design — UML orphan count reduced from 5 to 4. See [planning/design.md](design.md) v1.3 for updated class diagrams and interaction diagrams.

> **Note (2026-05-18/20 — Sprint 1 complete):** All Sprint 1 backlog items implemented and tested. 49 requirements are now Fully Traced; 5 Partially Traced (crash isolation done, sandboxing / config allowlist / error attribution deferred; SQLAlchemy ORM parameterization, null-byte injection prevention, and R6 testing NFRs confirmed complete). 140 tests pass; 99% branch coverage on core modules. Remaining WT items are Sprint 2–5 scope.

> **Note (2026-06-01 — Sprint 3 complete):** All Sprint 3 backlog items (B-24, B-25, B-26, B-28, B-30, B-54, B-55, B-56, B-62, B-69, B-71, B-73, B-76, B-78, B-79) implemented and tested. 105 requirements now Fully Traced (+34 from Sprint 3); 4 Partially Traced (-3: FR-25 PT→FT, FR-39 PT→FT, FR-44 PT→FT, FR-103 PT→FT; FR-67 WT→PT — B-29 `--encrypted` flag pending). 387 tests pass (388 collected, 1 skipped — POSIX chmod, Windows-only). See `AI Working Log/working-log-2026-06-01.md`.

> **Note (2026-06-01 — Sprint 4 complete):** All Sprint 4 backlog items (B-84, B-85, B-97, B-98, B-99, B-100, B-101, B-102) implemented and tested. 113 requirements now Fully Traced (+8 from Sprint 4: FR-45, FR-46, FR-47, FR-65-R9, FR-66-R9, FR-72, FR-73, FR-75); 3 Partially Traced; R11 GUI items WT→FT for Sprint 4 scope. 493 tests pass (494 collected, 1 skipped). New files: `src/core/app_lock.py`, `src/desktop/__init__.py`, `src/desktop/app_controller.py`, `src/desktop/main_window.py`, `tests/test_sprint4.py`. See `AI Working Log/working-log-2026-06-01.md`.

> **Note (2026-06-03 — Sprint 4B complete):** All Sprint 4B backlog items (B-103 through B-112) implemented and tested. Adds 77 GUI completeness tests; total 570 (one POSIX-only skip). VS Code-inspired layout with `QSplitter`, `QTabWidget`, rich-text editor, search bar, account-aware sidebar, settings dialog, theme/font support, and keyboard shortcuts. New tests file: `tests/test_sprint4b.py`. R11 GUI items remain Fully Traced.

> **Note (2026-06-04 — Sprint 4C complete):** Sprint 4C delivers GUI polish + dev tooling on top of Sprint 4B (B-113 through B-121). External `.qss` stylesheets with optional `QFileSystemWatcher` hot-reload (`ASTRANOTES_QSS_HOTRELOAD=1`); Settings dialog redesigned into a category-list layout (Appearance / Editor / Behaviour / Files); accent-colour / font-family / word-wrap settings wired end-to-end; Plugins Admin dialog (`Ctrl+Shift+P`); new-note format chooser (Plain / Markdown / Rich text + Encrypt checkbox); decrypt-by-uncheck on encrypted notes (`DatabaseStore.update(encrypted=False)`); themed SVG icons for combobox / spinbox / checkbox / tab-close; dev-only Widget Gallery (`Ctrl+Shift+G`). New config keys: `accent_color`, `font_family`, `word_wrap`. New asset directory: `src/desktop/styles/` (with `icons/` subfolder). 570 tests pass (1 skipped). No new requirement IDs; all R11 GUI items remain Fully Traced.

> **Note `[LOG 05-04]`:** R11 expanded from 4 items to 12 (split into Desktop GUI Sprint 4 + Sync-Enabled Desktop Client Sprint 5 — one PySide6 app); R12 rewritten for three-layer model (8 → 7 items); R13 updated for optional auth (15 → 14 items, removed FR-119); R16 rewritten as sync server with push/pull model. Total 141 → 139. FR-114 dropped (offline covered by FR-76 — local SQLite is always on, not a cache). Total 139 → 138. `[LOG 05-04]`

### Breakdown by Category

| Requirement Group | Total | FT | PT | WT | NT |
|---|---|---|---|---|---|
| R1 — Note Management (CRUD) | 10 | 9 | 0 | 0 | 0 |
| R2 — Encryption | 16 | 16 | 0 | 0 | 0 |
| R3 — Data Persistence | 8 | 6 | 0 | 0 | 0 |
| R4 — Plugin System | 10 | 11 | 0 | 2 | 0 |
| R5 — CLI Interface | 3 | 2 | 1 | 0 | 0 |
| R6 — Testing (NFR) | 5 | 4 | 1 | 0 | 0 |
| R7 — Override Policy | 5 | 5 | 0 | 0 | 0 |
| R8 — Audit Trail | 6 | 6 | 0 | 0 | 0 |
| R9 — Configuration | 6 | 6 | 0 | 0 | 0 |
| R10 — Search and Export | 7 | 6 | 1 | 0 | 0 |
| R11 — GUI Layer (split) | 11 | 8 | 0 | 0 | 3 |
| R12 — Local-First + Opt-In Account `[LOG 05-04]` | 7 | 4 | 1 | 2 | 0 |
| R13 — Optional Authentication `[LOG 05-04]` | 14 | 12 | 0 | 0 | 2 |
| R14 — Database Storage | 13 | 11 | 0 | 2 | 0 |
| R15 — Injection Prevention (NFR) | 9 | 7 | 0 | 2 | 0 |
| R16 — Sync Server (updated) `[LOG 05-04]` | 8 | 0 | 0 | 3 | 5 |
| **Total** | **138** | **105** | **4** | **18** | **11** |

---

## 5. Gap Analysis

### 5.1 Open Gaps for Sprint 4

**Deferred from Sprint 3 (pending team decision):**

1. **FR-67 (R10.3) — `search --encrypted` flag.** Base search (plain title/content match, encrypted alias fallback) is done. The `--encrypted` flag that searches inside encrypted note content by prompting per-note passphrases is pending team discussion. B-29 remains `⏳ Pending` in the backlog. FR-67 is Partially Traced.

**Sprint 4 scope (not yet started):**

2. ~~**FR-72–FR-75, FR-108, FR-109 (R11-A) — Desktop GUI.**~~ **Resolved Sprint 4.** `AppController`, `MainWindow`, `PassphraseDialog`, `NoteEditorWidget` implemented; `astranotes gui` CLI command wired; all CRUD, tray, idle-lock tested.

3. ~~**FR-45–FR-47 (R4.11–R4.13) — Plugin manifest validation, `is_official` enforcement, trust-tier API gating.**~~ **Resolved Sprint 4.** `load_manifests()` with jsonschema validation; `register_plugin(is_official=False)` blocks hooks; B-99, B-100 done.

4. ~~**FR-65-R9, FR-66-R9 (R9.7–R9.8) — PID lock file and idle auto-lock timer.**~~ **Resolved Sprint 4.** `AppLockManager` in `src/core/app_lock.py`; 5-min `QTimer` in `MainWindow`; B-101, B-102 done.

**Important (before final release):**

5. **FR-47/R5 — Error message module attribution** is inconsistently implemented. `ClickException` messages should be audited and standardized in a future sprint.

### 5.2 Intentional Absences (Correct by Design)

> Updated `[LOG 05-04]` — R11 is no longer an undifferentiated deferred epic. It is now split into two sprint phases of one PySide6 desktop app (Sprint 4: CRUD; Sprint 5: sync) with their own sprint targets and ADR gates (ADR-11/12/13 all decided).

| Item | Reason |
|---|---|
| FR-74 (R11.3), FR-113 (R11.10) — Not Traced | Sprint 4/5 scope; UI wireframe (FR-74) and sync trigger mechanism (FR-113) require Sprint 4/5 design phase artifacts; FR-114 dropped — offline behavior covered by FR-76 |
| FR-109 (R11.6), FR-115 (R11.12) — now Weakly Traced `[LOG 05-04]` | ADR-13 decided (PySide6); framework is resolved; implementation awaits Sprint 4/5 |
| FR-118–FR-119 (R13.14–R13.15) — Not Traced | Sprint 5 scope; ADR-12 (OAuth strategy) decided; implementation pending |
| FR-120–FR-127 (R16) — Not Traced | Sprint 5 scope; ADR-11 (FastAPI) decided; sync server implementation pending |
| FR-82–FR-93 (Auth) — now Fully Traced | Sprint 2 complete; see Sprint 2 completion note above |
| FR-96, FR-101 (R14) — Weakly Traced | PostgreSQL connection (FR-96) and JSON→DB migration command (FR-101) deferred to Sprint 5 |
| FR-79 (R12.4) — Partially Traced | `--local` flag on `add` deferred; auto-account_id assignment implemented |
| FR-67 (R10.3) — Partially Traced | Base search done Sprint 3; `--encrypted` flag pending team decision (B-29 ⏳) |

---
