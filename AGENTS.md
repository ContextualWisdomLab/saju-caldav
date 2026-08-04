# Repository Guidance

## Paper-first calendrical work

Before changing Four Pillars formulas, time boundaries, or solar-time
correction, read `docs/research/README.md` and distinguish cited calendrical
claims from repository-specific conventions. Add or update a regression test
for every changed convention.

## CodeGraph

This repository is indexed by CodeGraph. Use `codegraph explore` before text
search when locating code paths or understanding dependencies, then run
`codegraph sync` after material changes.

## Privacy

Use synthetic birth data in tests and public CI. Never commit real profile
databases, `.env` files, passwords, CalDAV collections, or production logs.


## Code-owner review gates — disabled (on hold)

As of 2026-08-04, code-owner review requirements (`require_code_owner_reviews` in branch
protection, `require_code_owner_review` in rulesets) are disabled across the ContextualWisdomLab
org: there is a single maintainer (solo developer), so a code-owner approval gate can never be
satisfied. This is ON HOLD until the org has multiple maintainers — do NOT re-enable these
settings or add CODEOWNERS-based merge gates before then.
