# ERD / 저장 구조

```mermaid
erDiagram
  profiles ||--o{ calendars : owns
  profiles ||--o{ calendars : "secondary_profile_id"
  profiles {
    text id PK
    text name
    text birth_calendar
    int birth_year
    int birth_month
    int birth_day
    text birth_time
    boolean birth_time_known
    boolean is_leap_month
    text birth_city
    text timezone
    text time_mode
    real longitude
    json chart_json
  }
  calendars {
    text id PK
    text profile_id FK
    text secondary_profile_id
    text name
    text slug UK
    text visibility
    text kind
    json rule_json
    text last_synced_at
  }
```

`secondary_profile_id`는 SQLite foreign key 없이 애플리케이션에서 검증하는
궁합 보조 참조다. 프로필 삭제 전에 양쪽 참조를 검색하고, 주 참조 삭제는
`ON DELETE CASCADE`로 로컬 캘린더를 정리한다. `chart_json`과 `rule_json`은
CalDAV 이벤트로 복사하지 않는 민감·내부 표현이다.
