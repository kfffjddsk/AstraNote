# AstraNotes — Product Backlog

Items ordered by priority. Status reflects current state.

## Done

| ID | Item | User Story | Status |
|----|------|------------|--------|
| B-01 | Add unencrypted note via CLI | US-1 | Done |
| B-02 | Add encrypted note with passphrase prompt | US-2 | Done |
| B-03 | Reject empty title/content on add | US-1 | Done |
| B-04 | Get unencrypted note by ID | US-1 | Done |
| B-05 | Get encrypted note with correct passphrase | US-2 | Done |
| B-06 | Reject wrong passphrase on get | US-2 | Done |
| B-07 | List notes with encrypted content hidden | US-1, US-2 | Done |
| B-08 | Update unencrypted note | US-1 | Done |
| B-09 | Update encrypted note with passphrase | US-2 | Done |
| B-10 | Reject wrong passphrase on update | US-2 | Done |
| B-11 | Delete unencrypted note | US-1 | Done |
| B-12 | Delete encrypted note with passphrase | US-2 | Done |
| B-13 | Reject wrong passphrase on delete | US-2 | Done |
| B-14 | Error handling for missing note IDs | US-1 | Done |
| B-15 | JSON persistence with save-on-mutate | US-3 | Done |
| B-16 | Preserve encrypted records on no-key load | US-3 | Done |
| B-17 | AES-256-GCM encryption with PBKDF2 | US-2 | Done |
| B-18 | Plugin base class and registry | US-4 | Done |
| B-19 | `--data-dir` global option | US-1 | Done |
| B-20 | BDD test coverage (17 scenarios) | US-1–US-4 | Done |
| B-21 | Unit tests for core modules (16 tests) | US-1–US-3 | Done |
| B-22 | Stress test for 1001 notes | US-3 | Done |
| B-23 | Non-zero exit codes on CLI errors | US-1 | Done |

## Backlog (Not Started)

| ID | Item | User Story | Priority |
|----|------|------------|----------|
| B-24 | Override policy: red-alert + typed confirmation | US-5 | Medium |
| B-25 | Append-only audit trail for security operations | US-6 | Medium |
| B-26 | Configuration module for settings storage | US-7 | Medium |
| B-27 | GUI layer sharing core logic | US-9 | Low |
| B-28 | Plugin CLI commands wired into main CLI | US-4 | Medium |
| B-29 | Note search/filter by title or content | US-8 | Low |
| B-30 | Export notes to file (text/JSON) | US-8 | Low |
