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

