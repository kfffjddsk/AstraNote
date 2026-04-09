# Copilot Definition of Done

A feature, fix, or improvement is considered complete when it satisfies the following criteria and is ready for merge, release, or the next iteration.

## Quality and Verification
- Code builds, runs, and passes all validation steps.
- Relevant unit and integration tests are added or updated.
- Existing tests continue to pass after the change.
- Automated tests cover the new or modified behavior.
- Key use cases and edge cases are validated.
- No unresolved warnings, lint issues, or obvious regressions remain.

## Documentation
- A working log entry is created in the `Copilot` folder.
- Relevant documentation is updated in `docs/` or project docs.
- Corresponding docs are updated after any code, test, or configuration change.
- User-facing behavior and CLI changes are clearly described.
- Any setup, configuration, or usage notes are documented.

## Review and Readiness
- Code has been reviewed for correctness, readability, and maintainability.
- Implementation matches acceptance criteria and agreed scope.
- The change maps to a real objective, requirement, or user need.
- The logic and design can be clearly explained.
- The change is incremental and small enough for reliable review.
- Any known limitations or deferred improvements are documented.
- The change is safe to merge and does not leave the project in a broken state.

## Requirements and Validation
- The work is traceable from requirement to design, implementation, and tests.
- Testing, validation, and acceptance checks are defined and executed.
- The solution is reviewed for realism, feasibility, and practical use.
- Security, privacy, and governance concerns are explicitly considered where relevant.
- The work contributes clear value and is worth moving forward.

## Engineering Standards
- Implementation is clean with no dead code, debug artifacts, or experimental leftovers.
- Naming, formatting, and structure follow project conventions.
- Security, privacy, and performance implications are considered for relevant changes.
- Backlog or issue tracking is updated with status, dependencies, and follow-up tasks.

## Working Log Requirements
For every completed item, record:
- A short summary of what changed.
- Why the change was made.
- Key decisions and design notes.
- Tests and validation steps performed.
- Any follow-up actions or next sprint items.

## MVP and Incremental Delivery
- Deliver the smallest useful version of a feature first.
- Validate the MVP with tests and feedback.
- Expand to a complete feature only after the core behavior is stable.
- Mark the item done only when the delivered work is reliable, documented, and review-ready.
