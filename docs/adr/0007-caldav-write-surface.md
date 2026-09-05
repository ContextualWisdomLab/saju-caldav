# ADR-0007: CalDAV 쓰기 표면은 MKCALENDAR와 결정적 PUT

## 상태

Accepted — 2026-08-25

## 문맥

애플리케이션은 내부망 CalDAV(Radicale)에 컬렉션과 이벤트를 기록한다.
[ARCHITECTURE.md](../ARCHITECTURE.md)는 애플리케이션이 CalDAV 서버에
`MKCALENDAR`와 결정적 `PUT`만 수행한다고 적는다. 이 제한은 아키텍처
문서에만 있고 RFC 4791을 인용한 결정 기록이 없었다.

## 결정

1. 애플리케이션이 CalDAV 서버에 수행하는 쓰기는 `MKCALENDAR`와 결정적
   `PUT`뿐이다.
2. 이벤트 UID는 캘린더 ID, 시작·종료 시각, 포맷 버전의 SHA-256에서 만들며,
   같은 범위를 다시 동기화하면 같은 리소스 경로를 `PUT`으로 덮어쓴다.

## 근거와 결과

좋은 점은 컬렉션 생성과 이벤트 기록이 RFC 4791의 캘린더 컬렉션·리소스
쓰기로 설명되고, 같은 범위의 재동기화가 중복 이벤트를 만들지 않는다는
점이다. 현재 버전은 범위에서 더 이상 일치하지 않는 과거 리소스를 자동
삭제하지 않으므로, 규칙을 바꿀 때는 새 slug를 쓰거나 기존 CalDAV 컬렉션을
삭제한다. 컬렉션 삭제의 원격 우선 순서는
[ADR-0002](0002-profile-and-calendar-erasure.md)다.

이 기록은 `MKCALENDAR`와 결정적 `PUT`만 수용한다. subject별 CalDAV
계정·ACL 매핑은 [ARCHITECTURE.md](../ARCHITECTURE.md)가 별도 설계와 교차
범위 테스트 뒤로 남겨 두었으므로 이 ADR의 수용 범위가 아니다.

## 검증

- `tests/test_caldav.py`의 `MKCALENDAR` 다음 `PUT` 순서 확인
- [ARCHITECTURE.md](../ARCHITECTURE.md) CalDAV 쓰기와 결정적 동기화 문단

## 참고문헌

Daboo, C., Desruisseaux, B., & Dusseault, L. (2007). *Calendaring extensions to
WebDAV (CalDAV)* (RFC 4791). RFC Editor. https://doi.org/10.17487/RFC4791
https://www.rfc-editor.org/rfc/rfc4791
