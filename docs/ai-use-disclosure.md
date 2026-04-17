# AstraNotes — AI-Use Disclosure

## Overview

AstraNotes uses AI assistance as part of its development workflow. This document describes the scope, boundaries, and governance of AI involvement in the project.

## AI Tool

- **Tool:** GitHub Copilot (Claude model)
- **Partner name:** Astra
- **Role:** AI engineering partner — proposes design options, drafts code/tests/docs, and assists with workflow

## Scope of AI Assistance

AI is used to assist with the following artifact types:

| Artifact Type | AI Role |
|---------------|---------|
| Source code | Draft implementations, suggest patterns, generate boilerplate |
| Tests | Draft BDD scenarios, unit tests, edge-case coverage |
| Documentation | Draft planning docs, requirements, user stories, process notes |
| Design | Propose architecture options, identify trade-offs, flag risks |
| Review | Identify inconsistencies, suggest improvements, cross-check docs |

## Human Oversight

All AI-generated output goes through human review before acceptance:

1. **Proposals, not decisions.** AI output is treated as a draft proposal. The human team member makes all final decisions on architecture, design, and correctness.
2. **Review and validation.** Every AI-generated artifact is reviewed against acceptance criteria, tested, and validated before being committed.
3. **Rejection criteria.** AI output is rejected if it contains wrong assumptions, code duplication, low quality, or deviates from requirements.
4. **Incremental changes.** AI contributions are accepted as small, reviewable increments — not large rewrites.

## What AI Does NOT Do

- AI does not make architectural decisions — it proposes options for human review.
- AI does not approve or merge code — human team member owns the final accept/reject.
- AI does not have access to production systems, user data, or deployment infrastructure.
- AI does not bypass safety checks, tests, or review processes.

## Governance

- The [Working Agreement](../Copilot/Working%20Agreement.md) defines the full collaboration rules.
- Working logs in `Copilot/` record AI-assisted sessions with rationale and decisions.
- The human team member owns all final decisions and is accountable for the project output.

## Course Context

This project is developed as part of CSEN 296-B at Santa Clara University. AI assistance is used as a documented development tool, not as a substitute for student understanding and decision-making.
