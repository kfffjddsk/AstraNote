# GUI Design: Account Registration & Auth Flows

**Status:** Design proposal — pending review and implementation  
**Author:** AI Partner (Claude, claude-sonnet-4-6)  
**Date:** 2026-06-05  
**Related backlog items:** B-87, B-89, B-90

---

## 1. Current State

The desktop app currently handles sync authentication through `SyncLoginDialog` — a two-tab `QDialog` launched on-demand (either from the toolbar "Sync Now" button or the `Sync → Sign In...` menu item).

### Existing tabs

| Tab | What it does |
|-----|-------------|
| Local account | `POST /auth/login` with username + password |
| Sign in with Google | PKCE flow — opens system browser, polls callback server |

### What's missing

- **New account registration** — there is no path for a user to create a local account from the desktop. They must use the CLI (`astranotes account create`) or a future web UI.
- **Account recovery / password reset** — no self-service path at all.
- **Persistent sign-in state** — the app shows "⬤ Synced / Not synced" in the status bar but no username or avatar.

---

## 2. Proposed UI Changes

### 2.1 SyncLoginDialog — Add "Register" tab

Add a third tab to the existing `SyncLoginDialog`:

```
┌──────────────────────────────────────────────────┐
│  AstraNotes — Sign in to sync                    │
├──────────────────────────────────────────────────┤
│  [ Local account ] [ Google ] [ Create account ] │
│                                                  │
│  Username:   [________________________]          │
│  Password:   [________________________]          │
│  Confirm:    [________________________]          │
│                                                  │
│  Password rules shown inline (min 8 chars)       │
│                                                  │
│  [ Create account ]      [ Cancel ]              │
└──────────────────────────────────────────────────┘
```

**Backend call:** `POST /auth/register` (already implemented in `src/server/routers/auth.py`)  
**On success:** auto-login (call `POST /auth/login` with same credentials), save token, close dialog.  
**On failure:** show inline error label (username taken, weak password, server unreachable).

---

### 2.2 Sync status label — show username

Replace the plain "⬤ Synced" label with a richer chip:

```
Before:  ⬤ Synced
After:   ⬤ michael_s  ▾   (click → dropdown: Sync Now / Sign Out)
```

When signed out:
```
         ⬤ Not synced   [Sign in]
```

The `[Sign in]` button is a `QPushButton` with `flat=True` styled as a hyperlink.

---

### 2.3 Settings panel — Sync section

Add a dedicated **Sync** page to the existing `SettingsDialog` (alongside Appearance, Editor, Behaviour, Files):

```
┌─────────────────────────────────────────────────┐
│  Sync server URL:   [http://localhost:8000_____] │
│                                                  │
│  Auto-sync interval:  [  0  ] minutes            │
│  (0 = disabled)                                  │
│                                                  │
│  ── Account ────────────────────────────────── │
│  Signed in as: michael_s                        │
│  [ Sign out ]                                   │
│  (or) [ Sign in / Register ]                    │
└─────────────────────────────────────────────────┘
```

Currently `sync_server_url` and `sync_auto_interval` can only be edited by hand in `config.json`. Surfacing them here removes a usability gap.

---

## 3. Proposed Dialog Flow

```
User clicks "Sync Now" or "Sync → Sign In..."
        │
        ▼
Token cached?
  ├─ Yes → proceed to sync
  └─ No  → SyncLoginDialog
               │
               ├─ Tab 1 (Local): enter creds → POST /auth/login
               │                               ├─ 200 OK → save token → close
               │                               └─ 4xx    → show error label
               │
               ├─ Tab 2 (Google): PKCE → browser → callback → POST /auth/callback
               │                                               ├─ 200 OK → save token → close
               │                                               └─ error  → show error label
               │
               └─ Tab 3 (Register): fill form → POST /auth/register
                                                 ├─ 201 OK → auto-login → save token → close
                                                 └─ 4xx   → show error label
```

---

## 4. Implementation Notes

### Register tab
- Reuse `PassphraseDialog`-style confirm field.
- Client-side: validate min 8 chars before sending (avoids one round-trip).
- `SyncClient` already has `register(username, password)` — or we need to add it (check `src/core/sync_client.py`).

### Username chip in status bar
- Store `username` from `load_cached_token()` return dict (currently `account_id` and `access_token` are saved — add `username` too).
- `QToolButton` with `setMenu()` gives a clickable button with a dropdown, fitting the toolbar aesthetic.

### Settings → Sync page
- Hook `_build_page_sync()` into `SettingsDialog._build_*` pattern (see `src/desktop/main_window.py` around line 543).
- Changing `sync_server_url` or `sync_auto_interval` writes to `ConfigStore`; a restart (or `MainWindow.start_auto_sync_timer()` re-call) picks it up.

---

## 5. Open Questions for Review

1. Should the Register tab live in `SyncLoginDialog` (same dialog, three tabs) or as a separate `RegisterDialog` launched from a link?  Three tabs keeps the surface small. A separate dialog feels less crowded for a multi-field form.

2. For the username chip in the status bar: dropdown vs. right-click context menu? Dropdown is more discoverable; context menu is more consistent with existing tray behaviour.

3. Password reset: out of scope for the desktop (server would need an email-sending path). Should the dialog link to a "Forgot password? Use the web portal" note?

4. Should `sync_auto_interval` changes take effect immediately (restart the timer in-place) or only after a restart? Immediate is friendlier but adds complexity.
