# Saju CalDAV Service Design

## Product intent

Saju CalDAV turns a person's birth date and time into a Four Pillars chart,
then lets an operator build calendar rules from stem, branch, and Five Phase
fields. Each saved rule becomes an independently subscribable CalDAV calendar.

The first acceptance example is a woman born on 1990-06-15 at 08:30 local
time. With the default `Asia/Seoul` civil-time convention, the chart is
`庚午 / 壬午 / 辛亥 / 壬辰`; therefore the day branch is `亥` (Water) and the
hour stem is `壬` (Water).

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
- RFC 4791, “Calendaring Extensions to WebDAV (CalDAV),”
  <https://www.rfc-editor.org/rfc/rfc4791>.
- RFC 5545, “Internet Calendaring and Scheduling Core Object Specification,”
  <https://www.rfc-editor.org/rfc/rfc5545>.

Paper-supported calendrical descriptions and repository-specific engineering
choices must remain explicitly separated in documentation and code comments.

## Product scope

### Included

1. One password-protected operator can manage multiple birth profiles.
2. A profile accepts name, Gregorian birth date/time, gender, IANA timezone,
   and optional longitude-based true-solar-time correction.
3. The result shows year, month, day, and hour pillars plus stem/branch Five
   Phase labels.
4. An operator can create multiple calendars per profile.
5. A calendar rule supports `all` or `any` logic over equality predicates for
   day/hour stem, branch, and element fields.
6. A predicate value can be a literal (`壬`, `亥`, `水`) or a reference to the
   selected profile's natal chart (`natal.day.branch`).
7. The service previews matches for a requested date range.
8. The service materializes stable RFC 5545 VEVENT resources and publishes
   them to Radicale over CalDAV.
9. The web UI displays the CalDAV collection URL and connection instructions.
10. Docker Compose runs the web service and Radicale with persistent volumes.

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
  "birth_local": "1990-06-15T08:30:00",
  "gender": "female",
  "timezone": "Asia/Seoul",
  "time_mode": "civil",
  "longitude": null,
  "chart": {
    "year": {"stem": "庚", "branch": "午", "element": "金"},
    "month": {"stem": "壬", "branch": "午", "element": "水"},
    "day": {"stem": "辛", "branch": "亥", "element": "水"},
    "hour": {"stem": "壬", "branch": "辰", "element": "水"}
  }
}
```

Each pillar exposes both `stem_element` and `branch_element`; the abbreviated
`element` above refers to the branch element for day/hour matching displays.

### Calendar definition

```json
{
  "profile_id": "UUID",
  "name": "내 亥日의 壬時",
  "slug": "my-hai-ren-hours",
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

1. Add a person and immediately see the Four Pillars.
2. Create a named rule using human-readable field/value rows.
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
- Public CI uses synthetic data only.
- SQLite and Radicale data live in ignored persistent volumes.

## Verification

Completion requires all of the following current-state evidence:

1. Unit test proves `1990-06-15 08:30 Asia/Seoul female` yields `辛亥` day,
   `亥`/Water day branch, and `壬辰` hour with `壬`/Water stem.
2. Rule test proves natal day branch plus literal hour stem generates the
   expected matching windows and rejects unknown fields.
3. API integration test creates a profile, calendar, and preview.
4. CalDAV integration test creates a Radicale collection, uploads events,
   and reads them back with `PROPFIND`/`REPORT` or an independent client.
5. Browser smoke test completes the primary journey at desktop and mobile
   widths with no console errors.
6. Docker Compose starts from `.env.example`-shaped secrets and persists data.
7. CodeGraph indexes the final repository and can trace the profile request to
   chart calculation and calendar sync to CalDAV publishing.
8. GitHub Actions run unit/integration checks on the pushed repository.
9. If SSH connectivity is available, the same stack runs on
   `seongho@192.168.68.3` and a LAN CalDAV round trip succeeds.

