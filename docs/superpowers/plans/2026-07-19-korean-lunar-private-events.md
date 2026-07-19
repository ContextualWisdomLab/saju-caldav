# Korean Lunar and Private Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing Saju CalDAV service with Korean lunar birth input, Korean-first explanations, private neutral CalDAV events, and current-day-forward matching without publishing the private regression fixture.

**Architecture:** Preserve the existing solar-term-aware `calculate_chart` and rule/event engine. Add one Korean lunar normalization boundary that stores both the original input and normalized Gregorian local timestamp, then keep every downstream calculation on that timestamp. Reuse the existing FastAPI, SQLite, vanilla web UI, Radicale publisher, and Figma visual system.

**Tech Stack:** Python 3.12, FastAPI 0.139.2, korean-lunar-calendar 0.4.0, lunar-python 1.4.8, icalendar 7.2.0, SQLite, vanilla HTML/CSS/JavaScript, pytest, Ruff, CodeGraph, Figma, Docker Compose.

## Global Constraints

- Solar and Korean lunar input are supported; lunar input distinguishes normal and leap months.
- Korean lunar conversion follows the KASI/KARI standard and is limited to the converter's documented range.
- Four Pillars year/month/day calculation still receives a normalized Gregorian local timestamp so solar-term boundaries remain in one code path.
- Civil time with an IANA timezone is the default. True-solar correction remains an opt-in advanced mode and latitude is never collected.
- Plain Korean is the primary UI language; Chinese characters appear only as optional expert notation.
- Calendar `SUMMARY` is the user-chosen neutral name. Birth data, chart values, rule values, categories, and `X-SAJU-*` properties are absent from VEVENT output.
- Preview and sync with no explicit range start on the profile timezone's current date.
- The requested regression fixture is read from local environment variables and is not committed to public docs, tests, Figma, or sample scripts.
- Every behavior change follows red-green-refactor and ends with fresh focused and full verification.

---

### Task 1: Korean lunar input normalization

**Files:**
- Create: `app/birth.py`
- Modify: `pyproject.toml`
- Modify: `requirements.lock`
- Test: `tests/test_birth.py`

**Interfaces:**
- Produces: immutable `BirthInput(calendar, year, month, day, at, is_leap_month)`.
- Produces: `normalize_birth(value: BirthInput) -> datetime` returning a naive Gregorian local wall time.
- Consumes: `KoreanLunarCalendar.setLunarDate(year, month, day, isIntercalation)`.

- [ ] **Step 1: Write the failing public tests with unrelated synthetic dates**

```python
from datetime import datetime, time

import pytest

from app.birth import BirthInput, normalize_birth


def test_korean_lunar_new_year_normalizes_to_gregorian_local_time():
    value = BirthInput("lunar", 2024, 1, 1, time(8, 30), False)
    assert normalize_birth(value) == datetime(2024, 2, 10, 8, 30)


def test_impossible_leap_month_is_rejected():
    value = BirthInput("lunar", 2024, 1, 1, time(8, 30), True)
    with pytest.raises(ValueError, match="윤달"):
        normalize_birth(value)


def test_solar_input_rejects_leap_month_flag():
    value = BirthInput("solar", 2024, 2, 10, time(8, 30), True)
    with pytest.raises(ValueError, match="양력"):
        normalize_birth(value)
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `uv run pytest tests/test_birth.py -q`

Expected: collection fails because `app.birth` does not exist.

- [ ] **Step 3: Add the pinned converter and implement the minimum boundary**

```python
from dataclasses import dataclass
from datetime import datetime, time

from korean_lunar_calendar import KoreanLunarCalendar


@dataclass(frozen=True, slots=True)
class BirthInput:
    calendar: str
    year: int
    month: int
    day: int
    at: time
    is_leap_month: bool = False


def normalize_birth(value: BirthInput) -> datetime:
    if value.calendar == "solar":
        if value.is_leap_month:
            raise ValueError("양력에는 윤달을 지정할 수 없습니다")
        return datetime.combine(
            datetime(value.year, value.month, value.day).date(), value.at
        )
    if value.calendar != "lunar":
        raise ValueError("달력 기준은 solar 또는 lunar여야 합니다")
    converter = KoreanLunarCalendar()
    if not converter.setLunarDate(
        value.year, value.month, value.day, value.is_leap_month
    ):
        raise ValueError("지원하지 않거나 존재하지 않는 한국 음력·윤달 날짜입니다")
    return datetime(
        converter.solarYear,
        converter.solarMonth,
        converter.solarDay,
        value.at.hour,
        value.at.minute,
        value.at.second,
    )
```

Add `korean-lunar-calendar==0.4.0` and regenerate the existing hash-locked runtime file with the repository's current `uv` workflow.

- [ ] **Step 4: Verify GREEN and dependency integrity**

Run: `uv run pytest tests/test_birth.py -q`

Expected: `3 passed`.

Run: `uv lock --check`

Expected: exit 0.

- [ ] **Step 5: Commit the normalization boundary**

```bash
git add app/birth.py tests/test_birth.py pyproject.toml uv.lock requirements.lock
git commit -m "feat: normalize Korean lunar birth dates"
```

### Task 2: Persist original birth input and expose it through the API

**Files:**
- Modify: `app/store.py`
- Modify: `app/main.py`
- Modify: `tests/test_store.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- `ProfileCreate` consumes `birth_calendar`, `birth_year`, `birth_month`, `birth_day`, `birth_time`, and `is_leap_month`.
- `Store.create_profile(...)` stores those original fields plus `birth_local`, the normalized local timestamp.
- `_profile_chart(profile)` continues consuming only normalized `birth_local`.

- [ ] **Step 1: Add failing API and store round-trip tests**

```python
payload = {
    "name": "음력 입력 예시",
    "birth_calendar": "lunar",
    "birth_year": 2024,
    "birth_month": 1,
    "birth_day": 1,
    "birth_time": "08:30:00",
    "is_leap_month": False,
    "gender": "unspecified",
    "timezone": "Asia/Seoul",
    "time_mode": "civil",
    "longitude": None,
}
response = client.post("/api/profiles", auth=AUTH, json=payload)
assert response.status_code == 201
body = response.json()
assert body["birth_calendar"] == "lunar"
assert body["birth_local"] == "2024-02-10T08:30:00"
```

Also create an existing-schema database in `tests/test_store.py`, call
`Store.initialize()`, and assert the new columns are added and old rows are
backfilled as solar input.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `uv run pytest tests/test_store.py tests/test_api.py -q`

Expected: request validation rejects the new fields and the store lacks the new columns.

- [ ] **Step 3: Implement idempotent SQLite migration and API normalization**

Add nullable columns for `birth_calendar`, `birth_year`, `birth_month`,
`birth_day`, `birth_time`, and `is_leap_month`, then backfill existing rows from
`birth_local` as solar. Keep `birth_local` as the canonical normalized value to
avoid changing `calculate_chart` callers.

Define the request model with bounded integers and `datetime.time`, construct a
`BirthInput`, call `normalize_birth`, and pass both original and normalized data
to `Store.create_profile`. Reject converter errors as HTTP 422 with Korean text.

```python
class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    birth_calendar: Literal["solar", "lunar"] = "solar"
    birth_year: int = Field(ge=1000, le=2050)
    birth_month: int = Field(ge=1, le=12)
    birth_day: int = Field(ge=1, le=31)
    birth_time: time
    is_leap_month: bool = False
    gender: Literal["female", "male", "unspecified"] = "unspecified"
    timezone: str = Field(default="Asia/Seoul", min_length=1, max_length=80)
    time_mode: Literal["civil", "true_solar"] = "civil"
    longitude: float | None = Field(default=None, ge=-180, le=180)


normalized = normalize_birth(
    BirthInput(
        requested.birth_calendar,
        requested.birth_year,
        requested.birth_month,
        requested.birth_day,
        requested.birth_time,
        requested.is_leap_month,
    )
)
```

```python
columns = {row[1] for row in connection.execute("PRAGMA table_info(profiles)")}
for name, sql_type in {
    "birth_calendar": "TEXT NOT NULL DEFAULT 'solar'",
    "birth_year": "INTEGER",
    "birth_month": "INTEGER",
    "birth_day": "INTEGER",
    "birth_time": "TEXT",
    "is_leap_month": "INTEGER NOT NULL DEFAULT 0",
}.items():
    if name not in columns:
        connection.execute(f"ALTER TABLE profiles ADD COLUMN {name} {sql_type}")
connection.execute(
    """
    UPDATE profiles
    SET birth_year = COALESCE(birth_year, CAST(substr(birth_local, 1, 4) AS INTEGER)),
        birth_month = COALESCE(birth_month, CAST(substr(birth_local, 6, 2) AS INTEGER)),
        birth_day = COALESCE(birth_day, CAST(substr(birth_local, 9, 2) AS INTEGER)),
        birth_time = COALESCE(birth_time, substr(birth_local, 12))
    """
)
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `uv run pytest tests/test_store.py tests/test_api.py -q`

Expected: all focused tests pass.

- [ ] **Step 5: Commit profile persistence and API changes**

```bash
git add app/main.py app/store.py tests/test_api.py tests/test_store.py
git commit -m "feat: accept solar and Korean lunar profiles"
```

### Task 3: Make Korean explanations primary in the authenticated product

**Files:**
- Modify: `app/saju.py`
- Modify: `app/main.py`
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`
- Modify: `tests/test_saju.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- `Pillar` produces `stem_korean`, `branch_korean`, `stem_description`, and `branch_description`.
- `_pillar_json` returns those fields alongside raw machine values.
- The UI renders Korean labels first and places `ganzhi` inside a collapsed `details` expert section.

- [ ] **Step 1: Add failing label and response tests**

```python
def test_pillar_explains_symbols_in_korean():
    pillar = Pillar("壬", "亥")
    assert pillar.stem_korean == "임수"
    assert pillar.stem_description == "양의 성질을 가진 큰물"
    assert pillar.branch_korean == "해수"
    assert pillar.branch_description == "십이지의 돼지, 오행으로는 물"
```

Assert authenticated API chart objects include the four Korean fields without
changing the existing raw keys used by the rule engine.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `uv run pytest tests/test_saju.py tests/test_api.py -q`

Expected: `Pillar` lacks the Korean properties.

- [ ] **Step 3: Add constant mappings and update the existing single-page flow**

Use fixed mappings for all 10 stems and 12 branches in `app/saju.py`. In the
form, add native controls for solar/lunar, numeric year/month/day, time, and a
leap-month checkbox shown only for lunar input. Keep timezone and true-solar
settings under an advanced disclosure; do not add latitude. Replace raw-only
select labels with forms such as `임수 — 양의 큰물 (壬)` and
`해수 — 돼지·물 (亥)`.

```python
STEM_KOREAN = {
    "甲": ("갑목", "양의 성질을 가진 큰나무"),
    "乙": ("을목", "음의 성질을 가진 풀과 덩굴"),
    "丙": ("병화", "양의 성질을 가진 큰불"),
    "丁": ("정화", "음의 성질을 가진 작은불"),
    "戊": ("무토", "양의 성질을 가진 큰땅"),
    "己": ("기토", "음의 성질을 가진 부드러운 땅"),
    "庚": ("경금", "양의 성질을 가진 단단한 쇠"),
    "辛": ("신금", "음의 성질을 가진 세밀한 쇠"),
    "壬": ("임수", "양의 성질을 가진 큰물"),
    "癸": ("계수", "음의 성질을 가진 작은물"),
}
BRANCH_KOREAN = {
    "子": ("자수", "십이지의 쥐, 오행으로는 물"),
    "丑": ("축토", "십이지의 소, 오행으로는 흙"),
    "寅": ("인목", "십이지의 호랑이, 오행으로는 나무"),
    "卯": ("묘목", "십이지의 토끼, 오행으로는 나무"),
    "辰": ("진토", "십이지의 용, 오행으로는 흙"),
    "巳": ("사화", "십이지의 뱀, 오행으로는 불"),
    "午": ("오화", "십이지의 말, 오행으로는 불"),
    "未": ("미토", "십이지의 양, 오행으로는 흙"),
    "申": ("신금", "십이지의 원숭이, 오행으로는 쇠"),
    "酉": ("유금", "십이지의 닭, 오행으로는 쇠"),
    "戌": ("술토", "십이지의 개, 오행으로는 흙"),
    "亥": ("해수", "십이지의 돼지, 오행으로는 물"),
}
```

```html
<label>달력 기준
  <select name="birth_calendar" id="birth-calendar">
    <option value="solar">양력</option>
    <option value="lunar">음력</option>
  </select>
</label>
<label id="leap-month-field" hidden>
  <input type="checkbox" name="is_leap_month"> 윤달입니다
</label>
<details>
  <summary>고급 시간 설정</summary>
  <!-- existing timezone, time_mode, and optional longitude controls -->
</details>
```

- [ ] **Step 4: Verify HTML/JavaScript behavior with focused API tests and syntax checks**

Run: `uv run pytest tests/test_saju.py tests/test_api.py -q`

Expected: all focused tests pass.

Run: `node --check app/static/app.js`

Expected: exit 0 with no output.

- [ ] **Step 5: Commit the Korean-first interface**

```bash
git add app/saju.py app/main.py app/static tests/test_saju.py tests/test_api.py
git commit -m "feat: explain calendar rules in Korean"
```

### Task 4: Start default searches on the profile's current local date

**Files:**
- Modify: `app/main.py`
- Modify: `app/static/app.js`
- Modify: `tests/test_api.py`

**Interfaces:**
- `DateRange` accepts optional `start_date` and `end_date`.
- `_resolve_date_range(requested, timezone, now=None) -> tuple[date, date]` uses `ZoneInfo(timezone)` and defaults to today through today plus 365 days.
- Explicit ranges preserve the existing maximum 730-day validation.

- [ ] **Step 1: Write a failing timezone-aware default-range API test**

Patch `_now` to an instant whose date differs between UTC and `Asia/Seoul`, post
an empty JSON object to `/preview`, and assert every returned event starts on or
after the Seoul local date. Add the same assertion to `/sync` using the fake
publisher.

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `uv run pytest tests/test_api.py -q`

Expected: HTTP 422 because both dates are currently required.

- [ ] **Step 3: Resolve omitted ranges on the server and simplify the client**

Use `datetime.now(ZoneInfo(timezone)).date()` for the default start and
`start + timedelta(days=365)` for the default end. Change the browser to send
`{}` for normal preview and sync so browser timezone and UTC string conversion
cannot shift the date.

```python
class DateRange(BaseModel):
    start_date: date | None = None
    end_date: date | None = None


def _resolve_date_range(requested: DateRange, timezone: str) -> tuple[date, date]:
    start = requested.start_date or datetime.now(ZoneInfo(timezone)).date()
    end = requested.end_date or start + timedelta(days=365)
    return start, end
```

```javascript
const range = {};
const preview = await api(`/api/calendars/${calendar.id}/preview`, {
  method: "POST",
  body: JSON.stringify(range),
});
```

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_api.py tests/test_events.py -q`

Expected: all focused tests pass.

- [ ] **Step 5: Commit current-day search behavior**

```bash
git add app/main.py app/static/app.js tests/test_api.py
git commit -m "feat: search matching windows from today"
```

### Task 5: Remove chart details from CalDAV resources

**Files:**
- Modify: `app/caldav.py`
- Modify: `tests/test_caldav.py`

**Interfaces:**
- `build_icalendar(calendar_id, calendar_name, window) -> bytes` keeps UID,
  timestamps, `TRANSP:TRANSPARENT`, and `CLASS:PRIVATE`.
- VEVENT summary becomes exactly `calendar_name` and description becomes a
  generic Korean sentence.

- [ ] **Step 1: Replace the existing expectations with a failing privacy test**

```python
event = Calendar.from_ical(build_icalendar("calendar", "나의 시간", window)).walk("VEVENT")[0]
assert str(event["SUMMARY"]) == "나의 시간"
assert str(event["DESCRIPTION"]) == "사용자 지정 조건과 맞는 시간입니다."
assert str(event["CLASS"]) == "PRIVATE"
serialized = event.to_ical()
for sensitive in (b"X-SAJU", b"CATEGORIES", b"DAY-PILLAR", b"HOUR-PILLAR"):
    assert sensitive not in serialized.upper()
```

- [ ] **Step 2: Run the test and confirm RED**

Run: `uv run pytest tests/test_caldav.py -q`

Expected: the current summary and custom properties expose chart details.

- [ ] **Step 3: Make the minimum serializer change**

Keep standard date, UID, transparency, and privacy properties. Remove chart
values, categories, and all `X-SAJU-*` fields. Do not add a configurable detail
mode until a user asks for it.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_caldav.py -q`

Expected: all focused tests pass.

- [ ] **Step 5: Commit private event serialization**

```bash
git add app/caldav.py tests/test_caldav.py
git commit -m "fix: keep CalDAV event details private"
```

### Task 6: Move the private regression fixture out of public artifacts

**Files:**
- Create: `scripts/private_regression.py`
- Modify: `scripts/acceptance_smoke.py`
- Modify: `README.md`
- Modify: `docs/research/README.md`
- Modify: `tests/test_saju.py`
- Modify: `tests/test_events.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_caldav.py`

**Interfaces:**
- `scripts/private_regression.py` consumes `PRIVATE_BIRTH_LOCAL`,
  `PRIVATE_TIMEZONE`, `PRIVATE_EXPECT_DAY_BRANCH`, and
  `PRIVATE_EXPECT_HOUR_STEM` from the process environment.
- Public tests and smoke scripts use unrelated synthetic values.

- [ ] **Step 1: Add the opt-in private regression command**

```python
birth_local = datetime.fromisoformat(os.environ["PRIVATE_BIRTH_LOCAL"])
chart = calculate_chart(
    birth_local,
    os.environ.get("PRIVATE_TIMEZONE", "Asia/Seoul"),
    "civil",
    None,
)
assert chart.day.branch == os.environ["PRIVATE_EXPECT_DAY_BRANCH"]
assert chart.hour.stem == os.environ["PRIVATE_EXPECT_HOUR_STEM"]
print("PRIVATE_REGRESSION_OK")
```

- [ ] **Step 2: Remove the private values from tracked public files**

Replace public samples with unrelated synthetic dates and Korean-neutral names.
Remove the README verification table, exact research example, assert-named Figma
references, and exact values from the acceptance smoke script.

- [ ] **Step 3: Prove no tracked text file contains the fixture**

Run the private values through `git grep` one at a time.

Expected: no matches in tracked files.

- [ ] **Step 4: Run public and local-private verification**

Run: `uv run pytest -q`

Expected: all public tests pass.

Run the private regression with values supplied only in the process environment.

Expected: `PRIVATE_REGRESSION_OK`.

- [ ] **Step 5: Commit public-artifact cleanup**

```bash
git add README.md docs/research/README.md scripts tests
git commit -m "privacy: keep acceptance fixture out of public artifacts"
```

### Task 7: Align Figma and visually verify the live web app

**Files:**
- Modify: existing Figma file `P4wdj2MnYwItYch3zdGIWt`
- Modify: `README.md` only if the final Figma URL changes

**Interfaces:**
- Figma remains the visual source for the existing paper/ink/vermilion design.
- The main frame shows solar/lunar, leap-month, Korean-first rule language, and
  advanced timezone/solar-time controls.
- The public acceptance frame is removed.

- [ ] **Step 1: Inspect the existing Figma page, components, fonts, and variables**

Use `get_metadata`, `get_design_context`, and a screenshot before writes. Reuse
the existing foundations and do not invent new color or type tokens.

- [ ] **Step 2: Update Figma incrementally**

Delete the public acceptance frame. Update the main form copy and controls in
small `use_figma` calls with loaded fonts, auto-layout, returned node IDs, and no
more than ten logical operations per call.

```javascript
const page = await figma.getNodeByIdAsync("0:1");
await figma.setCurrentPageAsync(page);
const acceptance = await figma.getNodeByIdAsync("6:2");
if (acceptance) acceptance.remove();
return { mutatedNodeIds: ["6:2"] };
```

- [ ] **Step 3: Start the local app and complete both core journeys**

Use synthetic solar and lunar profiles, create a neutrally named calendar,
preview from today, and inspect the generated event. Verify desktop and mobile
layouts, focus visibility, labels, conditional leap-month control, and the
advanced disclosure.

- [ ] **Step 4: Compare Figma and rendered screenshots**

Use the same viewport for both, inspect the combined comparison, fix visible
spacing, clipping, typography, border, and responsive mismatches, then capture
again.

- [ ] **Step 5: Commit any final UI fidelity fixes**

```bash
git add app/static README.md
git commit -m "style: align lunar calendar flow with Figma"
```

### Task 8: Full validation, CodeGraph, publication, and server proof

**Files:**
- Modify: `docs/research/README.md`
- Modify: `docs/DEPLOYMENT.md`
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:**
- Documents cite the Korean lunisolar paper, KASI notice, RFC 5545, and the
  exact converter version/range.
- CodeGraph traces profile normalization to chart calculation and calendar sync
  to neutral CalDAV serialization.

- [ ] **Step 1: Update durable research and operations documentation**

Document observed evidence separately from engineering choices: Korean lunar
dates depend on new-moon/solar-term rules and can differ by national standard;
the implementation uses korean-lunar-calendar 0.4.0 for input conversion and
retains lunar-python for the chart calculation path.

- [ ] **Step 2: Run the full local verification gate**

Run: `uv run pytest -q`

Expected: zero failures.

Run: `uv run ruff check .`

Expected: `All checks passed!`.

Run: `node --check app/static/app.js`

Expected: exit 0.

Run: `docker compose config -q`

Expected: exit 0 with required test environment supplied.

Run: `git diff --check`

Expected: exit 0.

- [ ] **Step 3: Synchronize and query CodeGraph**

Run: `codegraph sync`

Run: `codegraph explore "Trace lunar profile input through normalization and chart calculation, then trace current-day matching through private CalDAV event serialization"`

Expected: both call paths are present on the current working tree.

- [ ] **Step 4: Run a local Docker/Radicale round trip**

Start the stack with local-only random credentials, create synthetic profiles,
sync a calendar, read it back with CalDAV, parse VEVENT, and assert its date is
current/future while its text contains no chart details.

- [ ] **Step 5: Run the private acceptance only through environment values**

Execute `scripts/private_regression.py` and the live API/CalDAV path without
printing the sensitive input or expected values. Record only pass/fail and event
count.

- [ ] **Step 6: Push the existing PR branch and verify current-head checks**

Push `agent/fix-ci-bootstrap`, then inspect PR #6 `headRefOid`, all checks, review
threads, rulesets, and merge state. Bind every conclusion to the pushed head.

- [ ] **Step 7: Deploy to the LAN server when SSH is available**

Resolve the `passepartout` SSH route without logging secrets. Deploy under one
explicit application directory on `seongho@192.168.68.3`, start the Compose
stack, run web health and authenticated CalDAV readback, and leave credentials
only in the server-side ignored environment file.

- [ ] **Step 8: Finish the branch only after fresh evidence**

Report exact local test counts, current-head GitHub check state, Figma URL,
server URLs reachable on the LAN, and any honest limitations such as the Korean
lunar conversion range. Do not mark the Goal complete while a required check,
deployment, or private regression remains unverified.
