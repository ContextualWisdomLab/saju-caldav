# 위협 모델과 통제

## 보호 자산

출생 날짜·시각·달력 종류·도시·명식, 캘린더 규칙, CalDAV 자격 증명, 동기화된
일정, SQLite/ Radicale 백업이 보호 자산이다. 공개 이벤트는 중립 제목과 일반
설명만 담고 명식·규칙·천간·지지·오행을 담지 않는다.

## 주요 위협

| 위협 | 경로 | 통제 | 증거 |
| --- | --- | --- | --- |
| 무단 프로필 조회 | API/Basic | HTTP Basic, TLS/VPN 배치, 단일 operator 범위 | `tests/test_api.py` |
| 원격 데이터 잔존 | 삭제 후 Radicale | 원격 DELETE 선행, 404 멱등, 오류 502 | 삭제 회귀 테스트 |
| 규칙 주입 | JSON 규칙 | 허용 필드·리터럴만 검증, 임의 식 금지 | `tests/test_rules.py` |
| 공급망 변조 | CI Action/lock | SHA pin, uv/requirements lock, dependency/SAST | ADR-0001, Checks |
| LLM 자격 증명 노출 | 시간별 작업 | NIM 전용, 토큰 제거, bounded artifact, no auto-merge | ADR-0003 |
| 로그/이벤트 PII 유출 | 오류·iCalendar | 민감값 redaction, 최소정보 VEVENT, 합성 CI 데이터 | `docs/ARCHITECTURE.md` |
| 백업 유출 | SQLite/Radicale 볼륨 | 운영자 백업·접근권한·보존정책, 저장소 외부 | `docs/DEPLOYMENT.md` |

## 잔여 위험

HTTP Basic은 TLS 없이 안전하지 않으며, 대표 경도 기반 진태양시 보정은 정밀
천문 관측이 아니다. 서비스는 CSAP·SOC 2 인증을 주장하지 않는다. 인증을 목표로
할 때는 자산 범위, 증적, 공급자·처리자 계약, 접근 검토, 사고 대응을 별도
감사 범위로 확정해야 한다.

## 삭제 감사

현재는 삭제 요청의 시각과 결과를 PII 없이 운영 로그/백업 정책으로 확인한다.
향후 감사 이벤트를 추가할 때에는 profile ID를 원문 이름·생년월일 대신 불가역
식별자로 남기고, 감사 이벤트 자체의 보존·삭제 주기를 ADR로 결정한다.
