# Discussion List

**Purpose:** Open questions and unresolved items that need a decision before the affected sprint begins.  
At the start of each session, Astra reads this file and raises any items that are blocking upcoming work.  
Add an item here whenever the team decides to defer a decision, or by saying "add that to the discussion list."  
When an item is resolved, mark it **Resolved** with a brief note and the date — do not delete it.

---

## Open Items

### D-01 — OAuth PKCE Desktop Redirect Mechanism
**Added:** 2026-05-05  
**Blocking:** Sprint 5B (desktop OAuth login)  
**Context:** Sprint 5 adds Google OAuth login to the desktop app. Because the consent page lives on Google's servers, the user's system browser must open briefly so Google can show the consent screen. After the user approves, Google redirects back to the app — but how? Two options:  
  - Option A: Desktop app spins up an ephemeral `localhost:<port>/callback` HTTP listener, captures the code, then shuts it down.  
  - Option B: Register a custom URI scheme (e.g., `astranotes://callback`) so the OS routes the redirect directly to the app without any HTTP listener.  

**Why it matters:** Affects ADR-12 implementation, security review (localhost listener is standard PKCE; custom scheme requires OS registration), and the OAuth callback sequence diagram (gap T6).  
**Question for team:** Which option? Or is Google OAuth login out of scope and only local username/password is needed for Sprint 5?

---

### D-02 — System Tray Icon
**Added:** 2026-05-05  
**Blocking:** Sprint 4 scope definition  
**Context:** A system tray icon (minimize to tray, show/hide window, quit) was mentioned as a possible Sprint 4 stretch goal but has no backlog item (no B-xx) and no requirement.  
**Question for team:** Keep as stretch goal and add B-97? Or drop entirely?

---

### D-03 — Settings Dialog: Advanced / Future Fields
**Added:** 2026-05-05  
**Blocking:** Sprint 4 + Sprint 5 implementation  
**Context:** The Settings QDialog now has a defined set of fields (see `docs/design.md` §3.2 `show_settings()`). Fields to decide before implementation:  
  - Should "theme" (light/dark) be applied immediately on selection, or only on OK/Apply?  
  - Should "font size" apply to the editor only, or also the note list?  
  - Auto-sync interval: is 5 min the minimum, or should the user be able to enter a custom value?  
  - Account tab: should login/logout be inside Settings, or is a dedicated menu action sufficient?  
**Question for team:** Decide UX behaviour for each field before Sprint 4/5 GUI implementation begins.

---

## Resolved Items

*(None yet — resolved items will be recorded here with decision and date.)*
