# ADR-0006: RFC 5545 VEVENT 최소정보 방출

## 상태

Accepted — 2026-08-25

## 문맥

애플리케이션은 계산 결과를 Radicale CalDAV 컬렉션에 iCalendar로 보낸다.
[ARCHITECTURE.md](../ARCHITECTURE.md)는 이미 RFC 5545 `VEVENT`에 사용자가
선택한 `CLASS`, `TRANSP:TRANSPARENT`, 사용자가 붙인 중립적 캘린더 이름과
일반 문장 설명만 포함하고, 명식·규칙·천간·지지·오행·`X-SAJU-*`는 보내지
않는다고 적는다. 이 방출 계약은 아키텍처 문서에만 있고 결정 기록과 RFC
위치 표시가 없었다.

## 결정

1. CalDAV로 보내는 일정은 RFC 5545 `VEVENT`다.
2. 각 이벤트는 사용자가 선택한 `CLASS:PRIVATE`, `CLASS:CONFIDENTIAL`,
   `CLASS:PUBLIC` 중 하나와 `TRANSP:TRANSPARENT`를 가진다.
3. 제목은 사용자가 붙인 중립적 캘린더 이름이다. 설명은 일반 문장만 포함한다.
4. 명식, 규칙, 천간·지지, 오행 또는 `X-SAJU-*` 속성은 CalDAV로 보내지 않는다.

## 근거와 결과

`CLASS`는 캘린더 클라이언트 표시용이며 Radicale의 인증·`owner_only` 접근
제어를 바꾸지 않는다. 이 기록은 [ARCHITECTURE.md](../ARCHITECTURE.md)가
이미 서술한 방출 계약을 결정 기록으로 고정한 것이며, 새 제품 동작을
추가하지 않는다.

## 검증

- `tests/test_caldav.py`의 `CLASS`·`TRANSP:TRANSPARENT`·`X-SAJU-*` 부재 확인
- [ARCHITECTURE.md](../ARCHITECTURE.md) iCalendar 방출 문단

## 참고문헌

Desruisseaux, B. (Ed.). (2009). *Internet calendaring and scheduling core
object specification (iCalendar)* (RFC 5545). RFC Editor.
https://doi.org/10.17487/RFC5545
https://www.rfc-editor.org/rfc/rfc5545
