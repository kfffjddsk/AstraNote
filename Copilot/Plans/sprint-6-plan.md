# Sprint 6 Implementation Plan — Plugin Editor Integration & Container Format Adoption

## Context

Sprint 5D (architecture refactoring) is fully done — 669 tests pass. The sprint extracted `notes.py` into `note.py`, `store.py`, `container.py`, and `editor_protocol.py`; relocated plugins under `src/plugins/`; added `PluginContext` and `PluginSecurity`; decomposed `MainWindow` into purpose-built desktop modules; consolidated sync into `src/desktop/sync/`; and added the `gpu_acceleration` config key. No new user-facing features were added.

Sprint 6 delivers the first user-visible payoff from that refactoring: bundled plugins wired as real `EditorProtocol` providers, the ASTR container format integrated end-to-end, `gpu_acceleration` exposed in Settings, and desktop account registration (TD-05).

Target: ≥ 700 tests.

---

## Files to Modify / Create

| File | Change |
|------|--------|
| `src/core/container.py` | Already exists — used by `DatabaseStore` in this sprint |
| `src/core/store.py` | Wire `Container` codec into `add()`, `get()`, `update()`; add Alembic migration |
| `src/core/editor_protocol.py` | Already exists — implemented by plugins in this sprint |
| `src/plugins/tiptap_plugin/tiptap_plugin.py` | Implement `EditorProtocol.create_editor()` returning `QWebEngineView` |
| `src/plugins/voice_plugin/voice_plugin.py` | Implement `EditorProtocol.create_editor()` returning record/play `QWidget` |
| `src/plugins/video_plugin/video_plugin.py` | Implement `EditorProtocol.create_editor()` returning `QVideoWidget` player |
| `src/desktop/settings_dialog.py` | Add gpu_acceleration yes/no combo to Appearance tab; restart toast |
| `src/desktop/sync/account_dialog.py` | Add Register tab to `SyncLoginDialog`; `POST /auth/register` call |
| `src/server/routers/auth.py` | Add `POST /auth/register` endpoint |
| `alembic/versions/<new>.py` | Container format migration for existing notes |
| `tests/test_sprint6.py` | New — all Sprint 6 tests (B-131 through B-138) |

---

## Step 1 — B-131: ASTR Container Format End-to-End

Wire `DatabaseStore` (`src/core/store.py`) to use the `Container` codec on every write and read.

### `store.py` changes
- In `add()`: after `BlobCodec.encode()`, wrap the framed blob with `Container.encode(header, payload)` before encrypting or storing.
- In `get()`: after retrieving the raw blob, call `Container.decode(data)` to strip the ASTR envelope before passing to `BlobCodec.decrypt()` / `BlobCodec.decode()`.
- In `update()`: same encode/decode symmetry as `add()` / `get()`.

### Migration
- New Alembic migration under `alembic/versions/` — add a `container_version` nullable integer column to the `notes` table (default `NULL` for legacy rows, `1` for new rows).
- On `get()`, if `container_version IS NULL`, read the raw blob without stripping the ASTR envelope (backward compat); set `container_version = 1` on next write.

---

## Step 2 — B-132: Tiptap Plugin as EditorProtocol

File: `src/plugins/tiptap_plugin/tiptap_plugin.py`

Implement `EditorProtocol`:
- `create_editor(note: Note, parent: QWidget) -> QWebEngineView`
  - Load the Vite/Tiptap bundle from `src/plugins/tiptap_plugin/dist/index.html` via `QWebEngineView.setUrl(QUrl.fromLocalFile(...))`.
  - Expose a `QWebChannel` bridge: `getContent()` JS call returns current HTML as a string; `setContent(html)` loads saved content on open.
- `get_content(editor_widget) -> bytes`: call `runJavaScript("getContent()")` synchronously; encode result as UTF-8.
- `supported_mime_types`: `["text/html"]`

Guard: if `QWebEngineView` is unavailable (import error), `create_editor()` raises `NotImplementedError` with a friendly message.

---

## Step 3 — B-133: Voice Plugin as EditorProtocol

File: `src/plugins/voice_plugin/voice_plugin.py`

Implement `EditorProtocol`:
- `create_editor(note: Note, parent: QWidget) -> QWidget`
  - Returns a `QWidget` with Record / Stop / Play buttons using `QAudioInput` / `QMediaPlayer`.
  - WAV payload stored inline if ≤ 5 MB; filesystem path written to blob header if > 5 MB (existing threshold logic in `store.py`).
- `get_content(editor_widget) -> bytes`: return raw WAV bytes from the widget's internal buffer.
- `supported_mime_types`: `["audio/wav"]`

---

## Step 4 — B-134: Video Plugin as EditorProtocol

File: `src/plugins/video_plugin/video_plugin.py`

Implement `EditorProtocol`:
- `create_editor(note: Note, parent: QWidget) -> QVideoWidget`
  - Returns a `QVideoWidget` with Open / Play / Pause controls using `QMediaPlayer`.
  - MP4 payload: inline if ≤ 5 MB; filesystem path in blob header if > 5 MB.
- `get_content(editor_widget) -> bytes`: return the buffered MP4 bytes (or a path reference dict encoded as JSON if filesystem).
- `supported_mime_types`: `["video/mp4"]`

---

## Step 5 — B-135: gpu_acceleration in Settings Dialog

File: `src/desktop/settings_dialog.py`

In the **Appearance** tab:
- Add a `QLabel` "GPU acceleration" and a `QComboBox` with items `["yes", "no"]`.
- On save: `config.set("gpu_acceleration", combo.currentText())`.
- After save, show a non-blocking `QMessageBox.information(...)` toast: "Restart AstraNotes for the GPU acceleration change to take effect."
- On open, read `config.get("gpu_acceleration")` to pre-select the current value.

---

## Step 6 — B-136: Desktop Account Registration

File: `src/desktop/sync/account_dialog.py`

Add a **Register** tab to `SyncLoginDialog` (resolves TD-05):

**Register tab fields:**
- Username `QLineEdit`
- Password `QLineEdit` (echo mode: Password)
- Confirm Password `QLineEdit` (echo mode: Password)
- "Create Account" `QPushButton`

**On submit:**
1. Validate passwords match; show inline error if not.
2. `POST /auth/register` with `{"username": ..., "password": ...}`.
3. On 201: auto-login (`SyncClient.login(username, password)`) → save token → close dialog.
4. On 409 (username taken): show inline "Username already taken" error.
5. On other error: show generic error dialog.

File: `src/server/routers/auth.py`

Add `POST /auth/register`:
- Accept `RegisterRequest` (`username: str`, `password: str`).
- Call `store.register(username, password)` (existing `AccountStore.register()`).
- On success: return 201 `{"account_id": ..., "username": ...}`.
- On `UsernameExistsError`: return 409 with R16.8 error envelope.
- Validation: username 3–32 chars alphanumeric + `_`; password ≥ 8 chars (server-side enforcement only).

---

## Step 7 — B-137: Tests for Sprint 5D New Modules

File: `tests/test_sprint6.py`

| Class | Count | Focus |
|-------|-------|-------|
| `TestContainer` | 6 | encode/decode round-trip, magic bytes, version field, truncated data raises, wrong magic raises, empty payload |
| `TestPluginContext` | 5 | get_note returns copy, get_config returns value, direct store access blocked, direct config write blocked, None note_id returns None |
| `TestPluginSecurity` | 5 | clean plugin passes, os import flagged, subprocess import flagged, socket import flagged, nested import flagged |
| `TestPluginLoader` | 4 | loads allowed plugin, skips disallowed, consent required for new version, consent recorded in config |
| `TestPluginConsentDialog` | 4 | renders plugin name/version, accept records consent, reject skips plugin, existing consent skips dialog |
| `TestContainerStoreIntegration` | 6 | add/get round-trip with Container, legacy row without container_version readable, update re-encodes, encrypted note encode/decode, filesystem payload path preserved, Alembic migration column present |

Target: ≥ 30 new tests.

---

## Step 8 — B-138: search --encrypted Flag

File: `src/cli.py`

Enable the `--encrypted` flag on `search_cmd` (B-29 now active):
- When `--encrypted` is passed, for each encrypted note: prompt passphrase once per note, decrypt blob, include in results if query matches content.
- Mismatched passphrase for a note: print warning, skip that note, continue.
- Update `FR-67` in traceability from Partially Traced → Fully Traced after test coverage added.

Add tests in `tests/test_sprint6.py`:
- `TestSearchEncryptedFlag`: 4 tests (match found, no match, wrong passphrase skipped, unencrypted notes still included).

---

## Verification

```
pytest tests/test_sprint6.py -v          # new tests
pytest --tb=short -q                     # full suite (target ≥ 700)
```

Backlog items to mark Done after this sprint: B-131 through B-138.
Tech debt TD-05 resolved by B-136.
