# AstraNotes — Product Backlog

Items ordered by priority. Status reflects current state.

## Sprint Zero — Done ✅

| ID | Item | User Story | Priority | Status |
|----|------|------------|----------|--------|
| B-01 | Add unencrypted note via CLI | US-1 | High | ✅ Done |
| B-02 | Add encrypted note with passphrase prompt | US-2 | High | ✅ Done |
| B-03 | Reject empty title/content on add | US-1 | High | ✅ Done |
| B-04 | Get unencrypted note by ID | US-1 | High | ✅ Done |
| B-05 | Get encrypted note with correct passphrase | US-2 | High | ✅ Done |
| B-06 | Reject wrong passphrase on get | US-2 | High | ✅ Done |
| B-07 | List notes with encrypted content hidden | US-1, US-2 | High | ✅ Done |
| B-08 | Update unencrypted note | US-1 | High | ✅ Done |
| B-09 | Update encrypted note with passphrase | US-2 | High | ✅ Done |
| B-10 | Reject wrong passphrase on update | US-2 | High | ✅ Done |
| B-11 | Delete unencrypted note | US-1 | High | ✅ Done |
| B-12 | Delete encrypted note with passphrase | US-2 | High | ✅ Done |
| B-13 | Reject wrong passphrase on delete | US-2 | High | ✅ Done |
| B-14 | Error handling for missing note IDs | US-1 | High | ✅ Done |
| B-16 | Preserve encrypted records on no-key load | US-3 | High | ✅ Done |
| B-17 | AES-256-GCM encryption with PBKDF2 | US-2 | High | ✅ Done |
| B-18 | Plugin base class and registry | US-4 | High | ✅ Done |
| B-20 | BDD test coverage (17 scenarios) | US-1–US-4 | High | ✅ Done |
| B-21 | Unit tests for core modules (23 tests) | US-1–US-3 | High | ✅ Done |
| B-22 | Stress test for 1001 notes | US-3 | High | ✅ Done |
| B-42 | SQLite local store — `DatabaseStore` with `notes.db`, nullable `account_id` | US-12 | High | ✅ Done |
| B-43 | `BlobCodec` encode/encrypt pipeline; `DatabaseStore` add/get/update/delete/list | US-12, US-2 | High | ✅ Done |
| B-51 | Parameterized queries via SQLAlchemy ORM — no raw SQL | US-12, US-13 | High | ✅ Done |
| B-74 | Plaintext `title` column for fast listing (no blob parsing on list) | US-1, US-12 | High | ✅ Done |
| B-31 | UUID-based note IDs — `uuid4()` in `Note.create()` (no ID collision) | US-1 | High | ✅ Done (Sprint 0) |
| B-33 | Co-existence invariant: unencrypted ops do not corrupt encrypted notes | US-2 | High | ✅ Done (Sprint 0) |
| B-34 | Passphrase min-length enforcement (8 chars) in `KeyManager` | US-2 | High | ✅ Done (Sprint 0) |
| B-38 | Plugin error isolation — try/except per handler in `PluginRegistry.call_hook()` | US-4 | Medium | ✅ Done (Sprint 0) |

---

## Sprint 1 — Done ✅

> **Goal:** Wire Click CLI, fix remaining edge cases, and harden plugin integration. Items B-19 and B-23 were Sprint 0 scope, deferred because CLI was not implemented in Sprint 0. Completed May 2026 — 140 tests, 99% branch coverage on core modules.

| ID | Item | User Story | Priority | Status |
|----|------|------------|----------|--------|
| B-19 | `--data-dir` global option *(deferred from Sprint 0)* | US-1 | High | ✅ Done |
| B-23 | Non-zero exit codes on CLI errors *(deferred from Sprint 0)* | US-1 | High | ✅ Done |
| B-32 | Passphrase confirmation prompt on encrypt | US-2 | High | ✅ Done |
| B-36 | `--data-dir` validation (must be directory, writable) | US-1 | Medium | ✅ Done |
| B-37 | Plugin discovery and loading from `plugins/` | US-4 | Medium | ✅ Done |
| B-39 | File permission error handling with friendly messages | US-3 | Medium | ✅ Done |
| B-40 | BDD + unit tests for new edge cases (B-32, B-36, B-37, B-39, B-52 scenarios) | US-1–US-4 | Medium | ✅ Done |
| B-52 | Input validation: reject null bytes and control characters at CLI boundary | US-1, US-11, US-13 | High | ✅ Done |
| B-65 | Alembic schema versioning for database migrations `[D-10]` | US-12 | Medium | ✅ Done |
| B-66 | SQLite WAL mode + retry logic for concurrent access `[D-10]` | US-12 | Medium | ✅ Done |
| B-83 | Unit tests for PluginBase and PluginRegistry (closes test debt from B-18) | US-4 | High | ✅ Done |

---

## Sprint 2 — Done ✅

> **Goal:** Opt-in account layer, session management, and auth hardening. Completed May 2026 — 246 tests total (106 new Sprint 2 tests + 3 bug-regression tests + 8 branch-coverage tests), 1 skipped (POSIX permission test, Windows-only skip). 100% branch coverage on all core modules.

| ID | Item | User Story | Priority | Status |
|----|------|------------|----------|--------|
| B-41 | First-login anonymous note association prompt `[LOG 05-04]` | US-10 | High | ✅ Done |
| B-45 | User registration and bcrypt password hashing | US-11 | Medium | ✅ Done |
| B-46 | Login/logout session management | US-11 | Medium | ✅ Done |
| B-47 | User isolation — scope queries by `account_id` `[LOG 05-04]` | US-11 | Medium | ✅ Done |
| B-49 | Hybrid storage: 5 MB threshold, encrypted-only filesystem payloads | US-12 | High | ✅ Done |
| B-57 | Interactive auth prompts (hide_input=True) — never accept password as CLI arg | US-11 | High | ✅ Done |
| B-58 | Auth rate limiting — 5 failures → 5-min lockout per username | US-11 | High | ✅ Done |
| B-59 | Session token file with 24h expiry at `<data-dir>/.session` | US-11 | High | ✅ Done |
| B-60 | Username validation — 3–32 chars, alphanumeric + underscore, case-insensitive | US-11 | Medium | ✅ Done |
| B-61 | Account deletion: set `account_id = NULL` on local notes; delete server record; warn user `[LOG 05-04]` | US-11 | Medium | ✅ Done |
| B-64 | `DATABASE_URL` env-var only — never stored in config.json | US-12, US-13 | High | ✅ Done |
| B-67 | Disk-full (`ENOSPC`) error handling at DB and filesystem layers | US-3, US-12 | Medium | ✅ Done |
| B-68 | Filesystem payload orphan cleanup on note delete | US-12 | Medium | ✅ Done |
| B-75 | Session token file permissions — restrict to creator + administrator only | US-11 | High | ✅ Done |
| B-77 | Flat data directory — always `<data-dir>/` layout `[LOG 05-04]` | US-12 | Medium | ✅ Done |
| B-81 | Per-user audit log deletion on `delete-account` | US-6, US-11 | High | ✅ Done |
| B-96 | `accounts` table (local SQLite): `account_id` UUID PK, `username`, `password_hash`, `failed_attempts`, `locked_until` `[LOG 05-04]` | US-11, US-12 | High | ✅ Done |

---

## Sprint 3 — ✅ Done

> **Goal:** Plugin hardening, audit trail, config module, search, and export. Completed May 2026 — 387 tests passing (388 collected, 1 skipped). BDD: 30 scenarios across 8 feature files. **Note:** B-29 (`--encrypted` search) is pending — requirements under review.

| ID | Item | User Story | Priority | Status |
|----|------|------------|----------|--------|
| B-24 | Override policy: red warning + `CONFIRM OVERRIDE` for plugin overrides | US-5 | Medium | ✅ Done |
| B-25 | Audit trail: JSON-per-line log with structured fields and filters | US-6 | Medium | ✅ Done |
| B-26 | Config module: known-key whitelist with `set`/`get`/`list`/`reset` | US-7 | Medium | ✅ Done |
| B-28 | Plugin CLI commands wired into main CLI | US-4 | Medium | ✅ Done |
| B-29 | Substring search with `--encrypted` flag | US-8 | Low | ⏳ Pending |
| B-30 | Export to text/JSON with `--output` and `--encrypted` | US-8 | Low | ✅ Done |
| B-54 | Strip ANSI/control codes from terminal output | US-1, US-13 | Medium | ✅ Done |
| B-55 | Path traversal prevention for `--data-dir`, `--output`, filesystem payloads | US-1, US-12, US-13 | Medium | ✅ Done |
| B-56 | Plugin sandboxing — read-only note copies, no exec/eval, no raw DB access | US-4, US-13 | Medium | ✅ Done |
| B-62 | Passphrase rotation via `reencrypt <note_id>` | US-2 | Medium | ✅ Done |
| B-69 | Plugin allowlist in config — reject unlisted plugins | US-4 | Medium | ✅ Done |
| B-71 | Expand audit trail scope — login/logout/register/delete-account/export | US-6 | Medium | ✅ Done |
| B-73 | Document passphrase memory-residency limitation | US-2 | Low | ✅ Done |
| B-76 | Export binary notes: write raw payload file + path reference in manifest | US-8 | Medium | ✅ Done |
| B-78 | Export file permissions + `export --cleanup` command | US-8 | High | ✅ Done |
| B-79 | Alias info warning for encrypted notes | US-2 | Medium | ✅ Done |

---

## Sprint 4 — Personal GUI *(Planned)*

> **Goal:** PySide6 desktop GUI for personal use (ADR-13). See [Sprint 4 Plan](sprint-zero-plan.md).

| ID | Description | US | Priority |
|----|-------------|----|----------|
| B-27 | GUI layer — umbrella epic (B-84/B-85 Sprint 4 CRUD; B-89/B-90 Sprint 5 sync) | US-9, US-14 | Low |
| B-84 | PySide6 desktop GUI skeleton — `astranotes gui` → `AppController` → `QApplication`; two-pane layout; passphrase `QDialog` `[ADR-13]` `[D-13]` | US-9 | High | ✅ Done |
| B-85 | Desktop GUI: full CRUD screens with passphrase dialog for encrypted notes | US-9 | High | ✅ Done |
| B-97 | System tray icon — minimize to tray; `QSystemTrayIcon` + `QMenu` (Show/Hide, Quit) | US-9 | Medium | ✅ Done |
| B-98 | GUI passphrase security level — `security_level` config key; `high` (default) / `session` modes | US-9 | Medium | ✅ Done |
| B-99 | Plugin manifest validation — `load_manifests()`; validates required fields; rejects `is_official` in manifest `[REQ R4.11, R4.12]` `[D-12]` | US-4 | High | ✅ Done |
| B-100 | Trust-tier enforcement in `PluginRegistry.register_plugin()` — `is_official` server-injected only `[REQ R4.13]` `[D-12]` | US-4, US-13 | High | ✅ Done |
| B-101 | `AppController` + `SessionManager` PID lock file — session exclusivity; stale lock overwritten `[REQ R9.7]` `[D-13]` | US-9 | High | ✅ Done |
| B-102 | Encrypted note idle auto-lock — 5-min `QTimer`; clears passphrase on timeout `[REQ R9.8]` `[D-13]` | US-9 | Medium | ✅ Done |

---

## Sprint 4B — GUI Completeness ✅ Done

> **Goal:** Elevate the Sprint 4 personal GUI from a functional skeleton to a polished, VS Code-inspired desktop app. Redesigned two-pane layout with a tab bar for open notes, rich-text editor, search, account-aware note list, settings dialog, theme/font support, keyboard shortcuts, and proper encrypted-note UX (alias input + explicit unlock button). Completed June 2026 — 570 tests total (77 new Sprint 4B tests), 0 failures.

| ID | Description | US | Priority | Status |
|----|-------------|----|----------|--------|
| B-103 | VS Code-inspired layout redesign — resizable `QSplitter` for sidebar; collapsible note-list pane; dark/light palette applied on startup | US-9 | High | ✅ Done |
| B-104 | Tab bar for open notes — `QTabWidget` above editor; tabs closeable/movable; active tab synced with note list selection | US-9 | High | ✅ Done |
| B-105 | Rich text editor — `QTextEdit` (HTML); formatting toolbar (Bold, Italic, Underline, font-size selector); `get_html_content()` for HTML; `get_content()` still returns plain text (backward compat) | US-9 | High | ✅ Done |
| B-106 | Encrypted note alias input + explicit unlock button — `QLineEdit` alias row when encrypted; `🔓 Unlock` button shown instead of auto-prompting on selection | US-9 | High | ✅ Done |
| B-107 | Search bar in GUI — `QLineEdit` above note list; filters note list in real-time via `DatabaseStore.search()`; Ctrl+F focuses it | US-9 | Medium | ✅ Done |
| B-108 | Account-aware note list — two labelled sections ("Your Notes" / "Local Notes") when a session token is active; flat list when logged out | US-9 | Medium | ✅ Done |
| B-109 | Settings dialog — `SettingsDialog(QDialog)` exposing `theme`, `font_size`, `default_encrypt`, `passphrase_min_length`; saved via `ConfigStore.set()` | US-9 | Medium | ✅ Done |
| B-110 | Theme support — `DARK_STYLESHEET` / `LIGHT_STYLESHEET` constants; `apply_theme()` helper; applied on startup and live on settings change | US-9 | Medium | ✅ Done |
| B-111 | Font size support — `apply_font_size()` on `NoteEditorWidget`; `AppController` reads `font_size` config and calls `apply_theme()` on startup | US-9 | Low | ✅ Done |
| B-112 | Keyboard shortcuts — Ctrl+N (new note), Ctrl+S (save), Del (delete), Ctrl+F (focus search), Ctrl+W (close tab), Ctrl+, (settings), Ctrl+Q (quit) in menu bar | US-9 | Low | ✅ Done |

---

## Sprint 4C — GUI Polish & UX Refinement ✅ Done

> **Goal:** Polish the Sprint 4B GUI based on visual / functional review. Extract stylesheets to external `.qss` files (with hot-reload for dev), redesign the Settings dialog into a category-list layout, add a Plugins Admin dialog, expose accent-colour / font-family / word-wrap settings end-to-end, allow encrypted notes to be decrypted from the editor, add a format chooser for new notes, and add real SVG icons for combobox / spinbox / checkbox / tab-close indicators. Completed June 2026 — 570 tests collected (569 pass, 1 POSIX-only skip).

| ID | Description | US | Priority | Status |
|----|-------------|----|----------|--------|
| B-113 | External QSS stylesheets — `src/desktop/styles/{dark,light}.qss` loaded via `load_stylesheet()`; designers can iterate without touching Python. Adds optional `QFileSystemWatcher` hot-reload gated by `ASTRANOTES_QSS_HOTRELOAD=1` env var. | US-9 | Medium | ✅ Done |
| B-114 | Settings dialog redesign — category list (`QListWidget` + `QStackedWidget`) with **Appearance / Editor / Behaviour / Files** pages; passphrase-length spinbox removed (backend default 8 chars remains); supported-formats info panel; right-aligned labels with consistent field column width. | US-9 | Medium | ✅ Done |
| B-115 | Accent / font-family / word-wrap settings end-to-end — new `ConfigStore` keys `accent_color` (purple/pink/cyan/green/orange), `font_family`, `word_wrap` (yes/no) with `_VALUE_CONSTRAINTS`; `apply_theme()` now substitutes the accent colour into the QSS and pushes the font into existing widgets via `app.allWidgets()`. | US-9 | Medium | ✅ Done |
| B-116 | Plugins Admin dialog — `PluginsDialog(QDialog)` with **Installed** + **Supported formats** tabs (`QTreeWidget`); checkable rows write the `allowed_plugins` config key; per-plugin description pane; filter box. Shortcut `Ctrl+Shift+P`. | US-4, US-9 | Medium | ✅ Done |
| B-117 | New-note format chooser — `_NewNoteTypeDialog` lists built-in formats (Plain text / Markdown / Rich text) and any plugin-provided formats; separate "Encrypt this note" checkbox. `NoteEditorWidget.apply_format()` toggles `setAcceptRichText` and shows/hides B/I/U buttons. Tab label reflects the chosen format. | US-9 | Medium | ✅ Done |
| B-118 | Decrypt-by-uncheck — `DatabaseStore.update()` gains `encrypted: Optional[bool]` kwarg. Setting `encrypted=False` clears the blob, removes the on-disk payload file if any, and writes plaintext content. `MainWindow._on_save` requires the user to unlock first before allowing decryption. | US-2, US-9 | High | ✅ Done |
| B-119 | Themed SVG icons — `src/desktop/styles/icons/{chevron-down,chevron-up,check,close-dark,close-light,close-hover}.svg`; QSS uses `{ICONS}` token that the loader substitutes with the absolute icon path. Replaces invisible / mojibake combobox arrows, spinbox arrows, checkbox tick, and tab close `×`. | US-9 | Medium | ✅ Done |
| B-120 | Dev-only Widget Gallery — `_WidgetGallery(QDialog)` with three tabs (Inputs / Lists & Trees / Misc) covering every styled widget for QSS iteration. Hidden `QAction`, shortcut `Ctrl+Shift+G`. No menu entry. | US-9 | Low | ✅ Done |
| B-121 | UX micro-fixes — sidebar selection clears on **New Note** so the new tab isn't visually associated with the previous note; editor font-size combo widened (52 → 72 px) so the value isn't covered by the chevron; list `:hover:!selected` to prevent highlight overlap between adjacent rows. | US-9 | Low | ✅ Done |

---

## Sprint 5A — Sync Server ✅ Done

> **Goal:** FastAPI push/pull sync server with PostgreSQL backend (ADR-11). See [Sprint 5 Plan](sprint-zero-plan.md).
>
> **Sprint 5A.1 (MVP) ✅ Done — June 2026:** FastAPI app factory, JWT bearer auth via `authlib.jose`, `POST /sync/push` + `GET /sync/pull?since=` with last-write-wins on `modified_at`, per-account isolation, error envelope, `SyncClient` httpx wrapper, `astranotes sync login/logout/push/pull` CLI, 40 new tests (609 / 1 skipped total).
>
> **Sprint 5A.2 (Hardening) ✅ Done — June 2026:** Postgres backend (B-44), least-privilege role docs (B-53), `sslmode=require` enforcement (B-63), HTTPS middleware (B-92), connection pool tuning + concurrent load test (B-93), in-process per-account rate limiter (B-95). 22 new tests (631 / 1 skipped total).

| ID | Description | US | Priority | Status |
|----|-------------|----|----------|--------|
| B-44 | PostgreSQL backend for sync server (`DATABASE_URL` env var) `[LOG 05-04]` | US-12 | Medium | ✅ Done (5A.2) |
| B-53 | Least-privilege PostgreSQL role (no DDL) | US-12, US-13 | Medium | ✅ Done (5A.2) |
| B-63 | PostgreSQL `sslmode=require` enforcement | US-12, US-13 | High | ✅ Done (5A.2) |
| B-86 | Sync server skeleton (FastAPI) — `POST /sync/push` and `GET /sync/pull?since=<ts>`; conflict detection on client `[LOG 05-04]` `[D-14]` | US-12, US-14 | High | ✅ Done (5A.1) |
| B-88 | JWT / bearer token validation middleware — HTTP 401 without valid token `[LOG 05-04]` | US-11, US-14 | High | ✅ Done (5A.1) |
| B-92 | HTTPS/TLS enforcement — reject plain HTTP connections | US-13, US-14 | High | ✅ Done (5A.2) |
| B-93 | Concurrent request handling — SQLAlchemy connection pool; load test ≥ 10 users | US-12, US-14 | High | ✅ Done (5A.2) |
| B-94 | Per-account data isolation at sync layer — queries scoped by `account_id` from JWT `[LOG 05-04]` | US-11, US-14 | High | ✅ Done (5A.1) |
| B-95 | Sync rate limiting — 60 req/min per account; HTTP 429 with `Retry-After` `[LOG 05-04]` | US-13, US-14 | Medium | ✅ Done (5A.2) |

---

## Sprint 5B — Desktop Sync UI + OAuth ✅ Done

> **Goal:** Sync-enabled PySide6 client with Google OAuth login (ADR-12). Completed 2026-06-05 — 669 tests passing.

| ID | Description | US | Priority | Status |
|----|-------------|----|----------|--------|
| B-87 | OAuth 2.0 / Google OIDC integration — `POST /auth/callback` PKCE endpoint, `get_or_create_oauth_account`, `callback_exchange()` in SyncClient `[LOG 05-04]` | US-11, US-14 | High | ✅ Done |
| B-89 | PySide6 sync-enabled desktop client — `SyncLoginDialog` (Google PKCE + local login tabs), sync toolbar button, Sync menu, `_status_sync_label` `[LOG 05-04]` | US-14 | High | ✅ Done |
| B-90 | GUI sync button wired to `SyncWorker` + `MergeWindow`; `_on_sync`, `_on_conflict_detected`, `_on_merge_accepted` in `MainWindow`; `Note.synced_at` field added `[LOG 05-04]` *(CLI half ✅ done in 5A.1)* | US-14 | Medium | ✅ Done |
| ~~B-91~~ | ~~Offline resilience — write queue + local web server~~ — **DROPPED** (superseded by Layer 1 SQLite always-on) `[LOG 05-04]` | — | — | Dropped |

---

## Sprint 5C — Installed-App Packaging ✅ Done (2026-06-06)

> **Goal:** Make AstraNotes behave correctly as a properly installed application — consistent OS-standard data paths, session persistence, package entry points, and build-time credential support.

| ID | Description | US | Priority | Status |
|----|-------------|----|----------|--------|
| B-96 | Unified platform data directory (`src/core/paths.py`) — Windows `%APPDATA%\AstraNotes`, macOS `~/Library/Application Support/AstraNotes`, Linux `$XDG_DATA_HOME/AstraNotes`; used by CLI and GUI so both use the same `notes.db` | US-1, US-12 | High | ✅ Done |
| B-97 | Session expiry increased from 24 h → 30 days in `SessionManager._SESSION_EXPIRY_HOURS` | US-11 | Medium | ✅ Done |
| B-98 | `pyproject.toml` with entry points: `astranotes` (CLI), `astranotes-gui` (desktop), `astranotes-server` (sync server) | — | Medium | ✅ Done |
| B-99 | `requirements.txt` cleaned: removed `authlib`, added `joserfc` + `redis` | — | Low | ✅ Done |
| B-100 | `src/desktop/bundled_defaults.py` — build-time patchable Google OAuth credentials with env-var + config fallback chain | US-11 | Medium | ✅ Done |

---

## Tech Debt — Done ✅ (2026-06-05)

| ID | Item | Resolved in | Notes |
|----|------|-------------|-------|
| TD-01 | `authlib.jose` → `joserfc` migration in `src/server/security.py` | 2026-06-05 | `DeprecationWarning` on every import eliminated; `OctKey` + `joserfc.jwt` API; no behaviour change; all existing tests pass. |
| TD-02 | `sync_auto_interval` config key was read from disk but never wired to a `QTimer` | 2026-06-05 | Added `sync_auto_interval` param to `MainWindow.__init__`; `start_auto_sync_timer()` method creates a `QTimer` firing `_on_sync()` every N minutes; `AppController` reads `sync_auto_interval` from config and calls `start_auto_sync_timer()` on startup; timer is stopped on sign-out. |
| TD-03 | In-process rate limiter resets on restart; broken in multi-worker deployments | 2026-06-05 | Added `RedisRateLimiter` (Redis sorted-set sliding window) and `make_rate_limiter()` factory to `src/server/rate_limit.py`. When `ASTRANOTES_REDIS_URL` is set and `redis` package is installed, Redis backend is used; otherwise falls back gracefully to in-process. `settings.redis_url` field added. |
| TD-04 | Server-side `server_notes` table had no Alembic migrations (used `create_all()` only) | 2026-06-05 | Created `alembic_server/` with `env.py` (targets `src.server.models.Base`), `script.py.mako`, and initial migration `0001_server_notes_initial`. Run with `alembic -c alembic_server.ini upgrade head`. Controlled by `ASTRANOTES_SERVER_DB_URL` env var. |
| TD-05 | No desktop path for account registration (must use CLI) | 2026-06-05 | Design document created at `Copilot/Plans/gui-account-registration.md`. Implementation deferred — see document for proposed "Register" tab in `SyncLoginDialog` and Settings → Sync panel. |
