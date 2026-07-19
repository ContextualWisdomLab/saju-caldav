# Saju CalDAV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish a password-protected web service that calculates Four Pillars, creates custom stem/branch matching calendars, and serves them through Radicale CalDAV.

**Architecture:** A FastAPI process owns chart calculation, safe rule matching, SQLite metadata, the operator UI, and a narrow CalDAV publisher. A separate Radicale process owns protocol-compatible calendar collections and resources. Docker Compose runs both from one pinned Python image.

**Tech Stack:** Python 3.12, FastAPI 0.139.2, lunar-python 1.4.8, icalendar 7.2.0, Radicale 3.7.6, SQLite, dependency-free HTML/CSS/JavaScript, pytest, Podman/Docker Compose.

## Global Constraints

- Default time mode is civil time in an IANA timezone; true-solar correction is opt-in and requires longitude.
- Sexagenary day changes at local midnight; Zi hour is split at midnight.
- Literal and natal-reference equality predicates are the only rule operations.
- Preview and sync ranges are limited to 730 days.
- No real birth data or credentials in the repository, CI, Figma, or logs.
- Radicale owns CalDAV protocol behavior; do not implement a replacement server.
- The exact acceptance chart is supplied only through private environment variables.

---

### Task 1: Calendrical core

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/saju.py`
- Test: `tests/test_saju.py`

**Interfaces:**
- Produces: `calculate_chart(birth_local: datetime, timezone: str, time_mode: str, longitude: float | None) -> Chart`
- Produces: `chart_for_local(local_dt: datetime, timezone: str, time_mode: str, longitude: float | None) -> Chart`
- Produces: immutable `Pillar` and `Chart` dataclasses with stem/branch element fields.

- [ ] **Step 1: Create project metadata and write the failing acceptance test**

```python
def test_acceptance_birth_chart_is_xinhai_and_renchen():
    chart = calculate_chart(datetime(1990, 6, 15, 8, 30), "Asia/Seoul", "civil", None)
    assert chart.day.ganzhi == expected_private_day
    assert chart.day.branch == "亥"
    assert chart.day.branch_element == "水"
    assert chart.hour.ganzhi == expected_private_hour
    assert chart.hour.stem == "壬"
    assert chart.hour.stem_element == "水"
```

- [ ] **Step 2: Run `uv run pytest tests/test_saju.py -q` and verify import failure**
- [ ] **Step 3: Implement the minimum immutable chart model, lunar-python bridge, hour-stem formula, and optional solar correction**
- [ ] **Step 4: Add boundary tests for invalid timezone, missing longitude, and Zi-hour midnight split; observe each failure before implementation**
- [ ] **Step 5: Run `uv run pytest tests/test_saju.py -q` and commit `feat: add calendrical core`**

### Task 2: Safe custom rules and event generation

**Files:**
- Create: `app/rules.py`
- Create: `app/events.py`
- Test: `tests/test_rules.py`
- Test: `tests/test_events.py`

**Interfaces:**
- Consumes: `Chart` and `chart_for_local` from Task 1.
- Produces: `Predicate`, `Rule`, `validate_rule(data: dict) -> Rule`, and `matches(rule: Rule, natal: Chart, current: Chart) -> bool`.
- Produces: `MatchingWindow` and `generate_windows(rule, natal, start_date, end_date, timezone, time_mode, longitude)`.

- [ ] **Step 1: Write a failing rule test using `day.branch = natal.day.branch` and `hour.stem = literal 壬`**
- [ ] **Step 2: Run `uv run pytest tests/test_rules.py -q` and verify the missing module failure**
- [ ] **Step 3: Implement allow-listed equality predicates and reject unknown fields, sources, and empty predicate sets**
- [ ] **Step 4: Write failing event tests for private matched windows, stable ordering, 730-day bounds, and split Zi segments**
- [ ] **Step 5: Implement solar-time segment enumeration and deterministic matching windows**
- [ ] **Step 6: Run both test files and commit `feat: generate custom matching windows`**

### Task 3: SQLite metadata store

**Files:**
- Create: `app/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: validated profile fields and rule JSON.
- Produces: `Store.initialize()`, profile CRUD, calendar CRUD, and cascade deletion using parameterized SQL.

- [ ] **Step 1: Write failing round-trip tests against a temporary SQLite file**
- [ ] **Step 2: Verify failure with `uv run pytest tests/test_store.py -q`**
- [ ] **Step 3: Implement schema initialization, JSON serialization, parameterized CRUD, foreign keys, and cascade delete**
- [ ] **Step 4: Run the store tests and commit `feat: persist profiles and calendars`**

### Task 4: RFC 5545 output and CalDAV publisher

**Files:**
- Create: `app/caldav.py`
- Test: `tests/test_caldav.py`

**Interfaces:**
- Consumes: `MatchingWindow`, calendar ID/slug/name, and CalDAV base credentials.
- Produces: `build_icalendar(...) -> bytes` and `CalDavPublisher.sync(...) -> SyncResult`.

- [ ] **Step 1: Write a failing test that parses generated bytes with icalendar and asserts UID, DTSTART, DTEND, SUMMARY, TRANSP, and Korean description**
- [ ] **Step 2: Verify the missing implementation failure**
- [ ] **Step 3: Implement deterministic UID generation and RFC 5545 serialization with `TRANSP:TRANSPARENT`**
- [ ] **Step 4: Write a failing publisher test against an in-process HTTP recorder for `MKCALENDAR` and idempotent `PUT` paths**
- [ ] **Step 5: Implement Basic-auth HTTP requests with bounded timeouts and explicit error messages**
- [ ] **Step 6: Run `uv run pytest tests/test_caldav.py -q` and commit `feat: publish CalDAV resources`**

### Task 5: API and operator interface

**Files:**
- Create: `app/main.py`
- Create: `app/static/index.html`
- Create: `app/static/styles.css`
- Create: `app/static/app.js`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: documented JSON routes from the design and a same-origin responsive UI.

- [ ] **Step 1: Write failing API tests for health, Basic auth, profile creation, calendar creation, preview, deletion, and validation failures**
- [ ] **Step 2: Verify failure with `uv run pytest tests/test_api.py -q`**
- [ ] **Step 3: Implement FastAPI lifespan initialization, constant-time Basic auth, Pydantic request validation, and JSON routes**
- [ ] **Step 4: Add the semantic HTML workflow with native inputs and Korean copy; add editorial-almanac CSS and reduced-motion/focus/mobile states**
- [ ] **Step 5: Add dependency-free JavaScript for profile, rule, preview, sync, copy, error, and loading states**
- [ ] **Step 6: Run API tests and a static syntax check, then commit `feat: add operator web app`**

### Task 6: Reproducible deployment and protocol integration

**Files:**
- Create: `Dockerfile`
- Create: `compose.yaml`
- Create: `radicale/config`
- Create: `scripts/run_radicale.py`
- Create: `scripts/caldav_smoke.py`
- Create: `.env.example`
- Create: `.dockerignore`
- Create: `.gitignore`
- Create: `tests/test_compose_integration.py`

**Interfaces:**
- Produces: one image with `web` and `radicale` commands; persistent `/data/app` and `/data/radicale` volumes; independent CalDAV smoke check.

- [ ] **Step 1: Write the integration test to start Compose, create and sync the acceptance calendar through the API, query Radicale, and parse the returned event**
- [ ] **Step 2: Verify the test fails because deployment files are absent**
- [ ] **Step 3: Implement the pinned image, bcrypt htpasswd bootstrap, Radicale owner-only config, required environment variables, health checks, and persistent volumes**
- [ ] **Step 4: Implement `scripts/caldav_smoke.py` using only the standard library plus icalendar**
- [ ] **Step 5: Run the Compose integration test and commit `ops: add reproducible CalDAV stack`**

### Task 7: Research, user documentation, CodeGraph, Figma, CI, and publication

**Files:**
- Create: `README.md`
- Create: `docs/research/README.md`
- Create: `docs/operations.md`
- Create: `.github/workflows/ci.yml`
- Create: `docs/design/figma.md`

**Interfaces:**
- Consumes: the completed app and deployment stack.
- Produces: durable research citations, setup/runbook, editable Figma artifact link, indexed code graph, and GitHub checks.

- [ ] **Step 1: Document claims, conventions, limitations, API examples, Apple/Thunderbird/DAVx5 connection steps, backups, and credential rotation**
- [ ] **Step 2: Run `codegraph init`, then `codegraph explore` for profile-to-chart and sync-to-CalDAV paths and record the evidence**
- [ ] **Step 3: Run the app locally, verify the primary journey in a browser at desktop and mobile widths, and capture it into a new Figma design file**
- [ ] **Step 4: Create GitHub Actions for Python tests and Compose configuration validation**
- [ ] **Step 5: Run the full verification suite, inspect `git diff --check` and `git status`, and commit `docs: finish Saju CalDAV delivery`**
- [ ] **Step 6: Create `ContextualWisdomLab/saju-caldav`, push `main`, and verify current-head GitHub Actions**
- [ ] **Step 7: Test batch SSH connectivity to `seongho@192.168.68.3`; when available, deploy under an explicit application directory and run the CalDAV smoke check**
