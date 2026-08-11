# 요구사항–결정–검증 추적표

| 요구/위험 | 설계·코드 | ADR/문서 | 검증 |
| --- | --- | --- | --- |
| 양력·한국 음력·윤달 | `app/birth.py`, `app/saju.py` | research README, [PRD](product/PRD.md) | `tests/test_birth.py`, `tests/test_saju.py` |
| 출생 시각 미상 | `birth_time_known`, unknown 시주 UI | ARCHITECTURE, [PRD](product/PRD.md) | API·compatibility tests |
| 시간대/경도 경계 | `app/locations.py`, true solar | TRD, research README | `tests/test_locations.py`, `tests/test_saju.py` |
| 현재 이후 두 사람 시간 | `app/compatibility.py`, `app/events.py` | [PRD](product/PRD.md), doctoring | `tests/test_compatibility.py`, API tests |
| 최소정보 CalDAV | `app/caldav.py` | ARCHITECTURE, RFC refs | `tests/test_caldav.py`, smoke |
| 원격 포함 개인정보 삭제 | `delete_published_collection`, store query | ADR-0002, threat model | deletion API tests |
| 공급망·잠금 | pinned CI, `uv.lock`, `requirements.lock` | ADR-0001 | deployment/CI Checks |
| 시간별 루프 | scheduled sentinel/NIM proposal | ADR-0003, [OPERABILITY](operations/OPERABILITY.md), [loop](operations/HOURLY_PRODUCT_LOOP.md) | workflow contract + current-head Checks |
| 한국어·한자 보조 설명 | static labels and summaries | PRD, research | static API/UI assertions |
| 인증·운영 경계 | HTTP Basic, Radicale owner-only | SECURITY, [THREAT_MODEL](security/THREAT_MODEL.md) | API auth tests, container build |

제품 요구사항은 [PRD](product/PRD.md), 기술 계약은 [TRD](technical/TRD.md),
검증 정책은 [TEST_STRATEGY](testing/TEST_STRATEGY.md), 운영 계약은
[OPERABILITY](operations/OPERABILITY.md)에서 유지한다.

추적표에 없는 변경은 PR에서 새 요구·결정·검증 행을 추가해야 한다. 수동 운영
증적에는 현재 commit SHA와 실행 명령을 함께 기록하되 출생 원문은 기록하지 않는다.
