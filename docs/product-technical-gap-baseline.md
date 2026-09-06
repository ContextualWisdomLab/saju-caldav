# Product–Technical Gap Baseline

Status: Proposed until the owning pull request is merged and its exact head is
verified.

## Product and technical boundary

The [PRD](product/PRD.md) owns the buyer-facing Four Pillars and CalDAV workflow.
The [TRD](technical/TRD.md), [UML](architecture/UML.md), and
[ERD](architecture/ERD.md) describe its implementation and persistence
boundaries. `scripts/hourly_product_loop.py` is an operational quality
sentinel; it does not own calendrical domain truth or customer data.

## Context map

```text
User workflow -> saju-caldav API -> profile/calendar persistence -> CalDAV adapter
                                   |
                                   `-> quality sentinel (read-only verification)
```

## Current gap and action

Gap: Operational sentinel identifiers were generic inside the repository-owned
boundary.

Exact evidence: `scripts/hourly_product_loop.py` on protected `main` at
`fa72a2c8b988abeb7efacc886cbb3fd8849314af` used generic result, runner, and
field names.

Action: Adopt sentinel-specific internal names, preserve the CLI and JSON wire
contract, and enforce the boundary with an AST contract test.

Status: Proposed.

## Verification and follow-up

- The focused contract test must demonstrate RED before the source change and GREEN
  on the proposed head.
- Full lint and test suites must pass on the exact pull-request head before ordinary
  merge.
- After merge, update this row to `Landed` with the merge commit and release evidence.
