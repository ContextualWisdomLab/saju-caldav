# Saju CalDAV Service Design

## Product intent

Saju CalDAV turns a person's solar or Korean lunar birth date and local time
into a Four Pillars chart, then lets an operator build calendar rules from
stem, branch, and Five Phase fields. Each saved rule becomes an independently
subscribable CalDAV calendar whose events are real Gregorian date-time windows
from the current day onward.

Personally identifying acceptance values stay in a local or secret-backed
regression fixture. Public documentation, demo data, Figma, logs, and calendar
events do not repeat the fixture's birth timestamp, gender, or exact chart.

This is a calendrical and cultural-reference product. It does not claim that
fortune-telling predictions are scientifically validated and it must not be
used as the sole basis for medical, legal, financial, employment, or other
high-impact decisions.

## Evidence basis

- Stéphanie Homola, “Chinese Eight Signs Prediction: Ontology, Knowledge,
  and Computation,” *Social Analysis* 65(2), 2021,
  <https://doi.org/10.3167/sa.2021.650204>. The paper describes the four
  year/month/day/hour stem-branch pairs and modulo-60 classification.
- Helmer Aslaksen, “The Mathematics of the Chinese Calendar,” 2010,
  <https://gwern.net/doc/science/2010-aslaksen.pdf>. It documents the
  sexagenary cycle, ten Heavenly Stems, twelve Earthly Branches, and double
  hours.
- 이청하·신순옥, “역법에서의 시진(時辰) 설정에 대한 타당성 논의,”
  *산업진흥연구* 8(2), 2023,
  <https://doi.org/10.21186/IPR.2023.8.2.119>. It records the Korean debate
  around civil time, longitude-based solar time, and the Zi-hour boundary.
- 박한얼·민병희·안영숙, “한국 음력의 운용과 계산법 연구,”
  *천문학논총* 32(3), 2017, pp. 407–420,
  <https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002294846>.
  It documents Korean lunisolar operation, solar-term and new-moon boundaries,
  leap-month exceptions, and uncertainty near midnight.
- RFC 4791, “Calendaring Extensions to WebDAV (CalDAV),”
  <https://www.rfc-editor.org/rfc/rfc4791>.
- RFC 5545, “Internet Calendaring and Scheduling Core Object Specification,”
  <https://www.rfc-editor.org/rfc/rfc5545>.

Paper-supported calendrical descriptions and repository-specific engineering
choices must remain explicitly separated in documentation and code comments.

## Product scope

### Included

1. One password-protected operator can manage multiple birth profiles.
2. A profile accepts name, solar or Korean lunar date, birth time, leap-month
   status when applicable, and an IANA timezone. A city can supply the timezone;
   latitude is never requested.
3. Longitude-based true-solar-time correction is an advanced opt-in. The normal
   form does not request coordinates, and a selected city can supply longitude.
4. The result leads with plain Korean labels and explanations. Chinese
   characters are secondary expert notation.
5. An operator can create multiple calendars per profile.
6. A calendar rule supports `all` or `any` logic over equality predicates for
   day/hour stem, branch, and element fields.
7. A predicate value can be a literal or a reference to the selected profile's
   natal chart. The UI describes both choices in Korean rather than exposing
   raw symbols as the primary vocabulary.
8. Preview and sync default to the profile timezone's current local date and a
   bounded future horizon; explicit date ranges remain available.
9. The service materializes stable RFC 5545 VEVENT resources and publishes
   them to Radicale over CalDAV.
10. The event title is the operator's neutral calendar name. Exact birth data,
    chart symbols, rule values, and custom `X-SAJU-*` properties are omitted
    from calendar resources by default.
11. The web UI displays the CalDAV collection URL and connection instructions.
12. Docker Compose runs the web service and Radicale with persistent volumes.

### Deliberately excluded

- Fortune interpretation, compatibility scoring, auspicious/inauspicious
  claims, Daewoon calculations, billing, teams, public profile sharing, and
  mobile-native apps.
- A custom WebDAV/CalDAV protocol implementation. Radicale owns protocol
  compatibility.
- Uploading real birth records to public CI, Figma, or external analytics.

## Time convention

The default mode is `civil`: use the supplied IANA timezone and clock time.
The optional `true_solar` mode applies longitude correction plus the equation
of time before assigning the day and double-hour. The UI must always show the
active convention and corrected time.

The MVP changes the sexagenary day at local midnight. Zi hour is represented
as two contiguous one-hour calendar segments (`00:00–01:00` and
`23:00–24:00`) because the civil date changes inside the traditional
`23:00–01:00` interval. This prevents a single VEVENT from silently spanning
two different day pillars. The convention is documented, deterministic, and
testable.

## Calendar input normalization

Three approaches were considered:

1. Treat a lunar-looking date as if it were Gregorian. This is rejected because
   invalid Gregorian-shaped dates and leap months cannot be represented safely.
2. Let the Four Pillars dependency interpret a Chinese lunar date directly.
   This is rejected because Korean and Chinese lunar dates can differ near
   astronomical and timezone boundaries.
3. Preserve the entered calendar system and components, convert Korean lunar
   input to a Gregorian local date with a KASI-standard converter, then reuse
   the existing solar-term-aware chart calculation. This is the selected path.

The profile stores the original calendar system, year, month, day, time, and
leap-month flag together with the normalized Gregorian local timestamp. A
round-trip display can therefore explain what the user entered without
reconstructing it from the normalized value. Invalid or impossible leap-month
dates are rejected before chart calculation.

## Architecture

The system has two runtime services:

1. `web`: FastAPI serves a same-origin HTML/CSS/JavaScript interface and JSON
   API. It performs chart calculation, validates rules, stores profiles and
   calendar definitions in SQLite, previews events, and publishes resources.
2. `radicale`: the established Radicale server owns CalDAV discovery,
   collections, ETags, and calendar-object storage.

Both services use HTTP Basic credentials from environment variables. Radicale
is reachable on the LAN for native clients. Internet exposure requires a TLS
reverse proxy; the repository does not pretend that plain LAN HTTP is safe on
the public internet.

## Modules

- `app/saju.py`: immutable stem/branch data, chart calculation, time
  correction, and double-hour calculation.
- `app/rules.py`: allow-listed rule validation and matching. No executable
  expressions or user-supplied code.
- `app/events.py`: deterministic match-window generation and RFC 5545 event
  construction.
- `app/store.py`: parameterized SQLite persistence for profiles and calendars.
- `app/caldav.py`: small HTTP CalDAV publisher for collection creation and
  idempotent VEVENT `PUT` requests.
- `app/main.py`: FastAPI routes, HTTP Basic boundary, and static UI hosting.
- `app/static/`: dependency-free accessible web interface.

## Data contracts

### Profile

```json
{
  "id": "UUID",
  "name": "샘플",
  "birth_calendar": "lunar",
  "birth_year": 2000,
  "birth_month": 1,
  "birth_day": 1,
  "birth_time": "08:30:00",
  "is_leap_month": false,
  "birth_local": "2000-02-05T08:30:00",
  "gender": "unspecified",
  "timezone": "Asia/Seoul",
  "time_mode": "civil",
  "longitude": null
}
```

The authenticated response also includes the calculated chart. Each pillar
exposes machine values plus `korean_label`, `korean_description`, and optional
expert notation; public examples do not reproduce the private regression chart.

### Calendar definition

```json
{
  "profile_id": "UUID",
  "name": "나의 물결 시간",
  "slug": "my-water-hours",
  "logic": "all",
  "predicates": [
    {"field": "day.branch", "source": "natal", "value": "day.branch"},
    {"field": "hour.stem", "source": "literal", "value": "壬"}
  ]
}
```

Allowed fields are `day.stem`, `day.branch`, `day.stem_element`,
`day.branch_element`, `hour.stem`, `hour.branch`, `hour.stem_element`, and
`hour.branch_element`. The only MVP operator is equality; this keeps the rule
builder understandable and the matcher safe.

## API

- `GET /api/health` — unauthenticated process and database liveness.
- `GET /api/profiles` — list profiles and calculated charts.
- `POST /api/profiles` — validate and create a profile.
- `DELETE /api/profiles/{id}` — delete a profile and its definitions.
- `GET /api/calendars` — list calendar definitions.
- `POST /api/calendars` — validate and create a definition.
- `DELETE /api/calendars/{id}` — delete a definition.
- `POST /api/calendars/{id}/preview` — generate a bounded preview.
- `POST /api/calendars/{id}/sync` — publish a bounded horizon to Radicale.

Preview and sync ranges are limited to 730 days. Stable event UIDs are hashes
of calendar ID, start time, end time, and rule version so repeated syncs update
rather than duplicate resources.

## User experience

The single-page operator console uses an editorial almanac aesthetic: warm
paper, ink-black type, vermilion accents, generous whitespace, and a subtle
calendar grid. It avoids mystical stock imagery and generic dashboard chrome.

The primary journey is visible without route changes:

1. Add a person with solar/lunar and normal/leap-month controls, then see a
   plain-Korean chart explanation with optional expert notation.
2. Create a neutrally named rule using human-readable field/value rows such as
   “태어난 날의 띠와 같은 날” and “임수 시간”.
3. Preview the next matches as dated time cards.
4. Sync and copy the CalDAV connection details.

Native form controls, visible labels, keyboard focus, reduced-motion support,
WCAG AA contrast, and responsive behavior are required.

## Security and privacy

- No default production passwords; Compose fails when required secrets are
  absent.
- Password comparisons use constant-time checks.
- Radicale htpasswd uses bcrypt.
- SQL uses parameters and JSON rule fields are allow-listed.
- CORS is not enabled; state-changing endpoints accept JSON only.
- Logs exclude birth timestamps, chart bodies, passwords, and authorization
  headers.
- Public docs, Figma, sample scripts, and normal CI exclude the private
  acceptance fixture. An opt-in private regression command reads its input and
  expected values from environment variables.
- `SUMMARY` contains only the user-chosen neutral calendar name;
  `DESCRIPTION` contains a generic Korean notice; `CLASS:PRIVATE` remains set.
- Public CI uses synthetic data only.
- SQLite and Radicale data live in ignored persistent volumes.

## Verification

Completion requires all of the following current-state evidence:

1. A local or secret-backed regression verifies the requested private birth
   fixture without committing its values. Public unit tests use unrelated
   synthetic solar, lunar, leap-month, solar-term, and midnight cases.
2. Rule tests prove natal day branch plus literal hour stem generates the
   expected matching windows and rejects unknown fields.
3. API integration test creates a profile, calendar, and preview.
4. CalDAV integration test creates a Radicale collection, uploads events,
   and reads them back with `PROPFIND`/`REPORT` or an independent client.
5. Browser smoke test completes the solar and lunar journeys at desktop and
   mobile widths, verifies Korean-first labels, and finds no console errors.
6. Docker Compose starts from `.env.example`-shaped secrets and persists data.
7. CodeGraph indexes the final repository and can trace the profile request to
   chart calculation and calendar sync to CalDAV publishing.
8. GitHub Actions run unit/integration checks on the pushed repository.
9. If SSH connectivity is available, the same stack runs on
   `seongho@192.168.68.3` and a LAN CalDAV round trip succeeds.
