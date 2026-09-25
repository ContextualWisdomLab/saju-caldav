# ADR 색인

| 문서 | 상태 | 결정 |
| --- | --- | --- |
| [0001](0001-runtime-lock-and-ci-provenance.md) | Accepted | 런타임 잠금과 CI 출처를 하나의 검증 경계로 관리 |
| [0002](0002-profile-and-calendar-erasure.md) | Accepted | 원격 CalDAV를 먼저 지우는 개인정보 삭제 순서 |
| [0003](0003-hourly-quality-and-nim-proposal-loop.md) | Proposed | 시간별 품질 감시와 NIM 기반 bounded 제안 루프 |
| [0004](0004-keyverse-oidc-rp-boundary.md) | Accepted | Keyverse OIDC 검증과 subject·조직·workspace 소유 범위 |
| [0005](0005-shared-relationship-candidate-boundary.md) | Accepted | 개인 공통 조건과 두 사람 관계 작용 모드의 분리, 성별 해석 비적용 |
| [0006](0006-icalendar-vevent-emission.md) | Accepted | RFC 5545 VEVENT에 CLASS·TRANSPARENT만 보내고 명식은 보내지 않음 |
| [0007](0007-caldav-write-surface.md) | Accepted | CalDAV 쓰기는 MKCALENDAR와 결정적 PUT만 사용 |

새로운 저장소·런타임·보안·개인정보 결정은 구현 PR과 같은 PR에서 ADR을 추가하거나
갱신한다. ADR의 상태가 Proposed이면 자동화가 병합 근거로 사용하지 않는다.
