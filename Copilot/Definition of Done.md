# Copilot Definition of Done

A feature or fix is done when it meets these criteria and is ready to merge.

## Quality and Verification
- Code builds and passes all tests.
- New or modified behavior has automated test coverage.
- Existing tests still pass.
- Key use cases and edge cases validated.
- No unresolved warnings or regressions.

## Documentation
- Working log entry in `AI Working Log/`.
- Relevant docs in `docs/` updated.
- Corresponding docs updated after any code or config change.
- Planning docs (`planning/`) updated after feature completion or modification.
- CLI and user-facing changes described.
- Setup and usage notes documented.

## Review and Readiness
- Reviewed for correctness, readability, maintainability.
- Matches acceptance criteria and scope.
- Maps to a real requirement or user need.
- Logic and design explainable.
- Incremental and reviewable.
- Known limitations documented.
- Safe to merge.

## Requirements and Validation
- Traceable from requirement to implementation to test.
- Acceptance checks defined and executed.
- Reviewed for feasibility and practical use.
- Security and privacy considered where relevant.
- Delivers clear value.

## Engineering Standards
- No dead code, debug artifacts, or experimental leftovers.
- Follows project naming, formatting, and structure conventions.
- Security and performance considered for relevant changes.
- Backlog updated with status and follow-ups.

## Working Log Requirements
Add a dated file to `AI Working Log/` (e.g., `working-log-YYYY-MM-DD.md`). For every completed item, record:
- What changed.
- Why.
- Key decisions.
- Tests performed.
- Follow-up actions.

## Discussion List
- At the end of every session, review `Copilot/discussion-list.md` and add any new unresolved questions or deferred decisions as D-xx items.
- A session is not fully "done" if there are open questions that will block the next sprint and have not been added to the discussion list.

## MVP and Incremental Delivery
- Ship the smallest useful version first.
- Validate MVP with tests and feedback.
- Expand only after core behavior is stable.
- Done = reliable, documented, review-ready.
