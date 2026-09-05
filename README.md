# 사주 캘린더 · CalDAV

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ContextualWisdomLab/saju-caldav)

**두 사람의 역법 입력을 이해 가능한 한국어로 계산하고, 함께 확인할 미래의 시간 조건을 찾아 개인 캘린더 흐름으로 이어 주는 운영자 도구입니다.**

양력 또는 한국 음력 출생 시각을 입력하면 사주 네 기둥을 계산하고, 두 사람 사이의 관계 작용 또는 각자에게 무난한 공통 조건을 구분해 설명합니다. 결과를 단순 점수로 끝내지 않고 어떤 날짜·시간 조건이 선택되었는지 보여 주며, RFC 5545 이벤트와 RFC 4791 CalDAV 발행 경계까지 연결합니다.

> 이 제품은 문화·역법 참고 도구입니다. 운세의 과학적 타당성, 미래 사건의 인과관계, 전통적인 궁합·길일의 정확성을 주장하지 않습니다.

## 무엇을 해결하나요?

| 작업 | 제품이 하는 일 |
| --- | --- |
| 출생 정보를 정확하게 입력 | 양력·한국 음력·윤달·출생 도시/시간대를 구분하고, 태어난 시각을 모르면 시주를 임의로 만들지 않습니다. |
| 두 사람이 함께 볼 시간을 찾기 | `관계 작용 시간`과 `공통 조건 시간`을 별도 모드로 계산하고 개인 점수와 관계 근거를 분리해 보여 줍니다. |
| 결과를 실제 일정으로 관리 | 허용 목록 기반 조건을 미리 본 뒤 iCalendar 이벤트로 만들고 CalDAV 컬렉션에 동기화·삭제할 수 있도록 설계되어 있습니다. |
| 민감한 출생 정보를 통제 | 프로필·메타데이터·캘린더 범위를 분리하고, 공개 테스트에는 서비스와 무관한 합성 데이터만 사용합니다. |

## 빠른 시작

Python 3.12 이상과 [uv](https://docs.astral.sh/uv/)가 필요합니다. 정확한 검증 범위는 현재 저장소 CI와 릴리스 증거를 기준으로 판단합니다.

```bash
uv sync --dev
APP_USERNAME=operator APP_PASSWORD='긴-임의-암호' \
  uv run uvicorn app.main:app --reload
```

이 경로는 웹 콘솔과 계산 API를 로컬에서 확인하는 가장 짧은 시작점입니다. 신뢰할 수 없는 네트워크에서 Basic 인증을 평문 HTTP로 노출하지 말고 TLS 역방향 프록시 또는 VPN 안에서 사용해야 합니다.

### 현재 CalDAV 배포 상태

저장소의 기존 full-stack 배포는 Radicale을 CalDAV 서버로 사용합니다. 그러나 현재 고정된 `radicale==3.7.7`은 GPLv3 프로젝트이므로 ContextualWisdomLab의 상용 반입 라이선스 정책에 맞지 않습니다. 이 저장소의 원본 소스 라이선스와는 별개의 **배포 의존성 결함**이며, [Issue #45](https://github.com/ContextualWisdomLab/saju-caldav/issues/45)에서 상업적으로 허용되는 CalDAV 경계로 교체하는 작업을 추적합니다.

따라서 Issue #45가 닫히기 전에는 기존 Radicale 기반 Docker Compose 경로를 ContextualWisdomLab의 상용 배포 기준을 충족한 경로로 간주하지 않습니다. 현재 구현·운영 계약을 조사해야 할 때에는 [배포 가이드](docs/DEPLOYMENT.md)와 [아키텍처](docs/ARCHITECTURE.md)를 함께 확인하세요.

## 사용 흐름

1. 저장된 프로필을 고르거나 생년월일, 달력 종류, 출생 도시와 태어난 시각을 입력합니다.
2. 태어난 시각을 모르면 `태어난 시각을 모릅니다`를 선택합니다. 일주는 계산하지만 알 수 없는 시주는 비워 둡니다.
3. `관계 작용 시간` 또는 `각자에게 무난한 공통 시간`을 선택합니다. 두 모드는 서로 다른 질문에 답하며 점수와 근거도 분리합니다.
4. 후보를 검토하고 필요한 조건만 캘린더 발행 경계로 보냅니다. 삭제할 때에는 로컬 프로필과 원격 컬렉션의 범위를 각각 확인합니다.

기본 검색 시간은 첫 번째 사람의 선택된 시간 기준 09:00–23:00이며 `24시간 전체`를 선택하면 새벽까지 포함할 수 있습니다. 기본 미리보기는 프로필 시간대의 오늘부터 `오늘 + 365일`까지 양끝을 포함하며, `start_date`와 `end_date`를 직접 주는 검색은 양끝 포함 최대 730개 날짜를 허용합니다.

## 계산과 설명의 경계

- 양력·한국 음력·윤달 입력을 계산용 양력 시각과 분리해 보존합니다.
- 출생 시각 미상은 명시적인 결측으로 유지하며 추정 시주를 만들지 않습니다.
- 관계 작용 모드는 두 사람의 일지 관계와 후보 날짜·시간 지지가 양쪽을 함께 잇는지를 계산합니다.
- 공통 조건 모드는 각 사람과 후보 지지를 따로 비교해 두 사람 모두에게 해당하는 조건을 찾습니다.
- 성별은 기록용으로만 보존하며 성별 기반 배우자성·대운 해석을 기본 후보에 섞지 않습니다.
- 고급 조건은 천간·지지·오행의 허용 목록을 사용하며 사용자 입력이 임의 실행 규칙이 되지 않도록 제한합니다.

## 인증과 통합

기본 운영자 인증은 HTTP Basic입니다. Keyverse를 연결할 때에는 [OIDC 연동 경계](docs/security/KEYVERSE.md)의 exact issuer, audience, JWKS 설정을 먼저 구성합니다.

`AUTH_MODE=hybrid`는 검증된 Bearer와 기존 Basic을 함께 허용하는 이행 모드입니다. Bearer 검증이 실패했다고 해서 Basic으로 우회하지 않습니다. client convergence와 토큰 수용·거부 증거를 확보한 뒤 `AUTH_MODE=oidc`로 전환하는 것이 현재 계약입니다.

CalDAV 발행은 제품의 별도 outbound 경계입니다. 애플리케이션 계산·프로필 상태와 CalDAV 자격 증명·컬렉션 권한을 같은 권한으로 취급하지 않습니다.

## 개인정보와 저장 경계

출생 날짜·시각·도시와 계산 결과는 민감한 개인정보로 취급합니다. 실제 데이터베이스, `.env`, CalDAV 컬렉션, 운영 로그를 저장소나 공개 CI에 넣지 않습니다. 공개 테스트에는 서비스와 무관한 합성 데이터만 포함합니다.

CalDAV 이벤트에도 사주 원문이나 규칙 값을 넣지 않습니다. iCalendar `PUBLIC`은 이벤트 표시 수준일 뿐 저장소 접근 권한을 익명 공개로 바꾸는 의미가 아닙니다. 프로필·메타데이터·원격 캘린더 삭제는 각각의 실제 저장 경계를 확인해야 합니다.

## 개발 검증

```bash
uv run pytest -q
uv run ruff check .
```

공개 저장소에 둘 수 없는 실제 회귀값은 환경 변수로만 주입합니다. 다음 명령은 입력값을 출력하지 않습니다.

```bash
uv run python scripts/private_regression.py
```

상용 라이선스 정책에 맞는 CalDAV 대체 경계가 마련된 뒤 full-stack acceptance 계약은 기존 실제 프로필 생성 → CalDAV 읽기 흐름과 동등하거나 더 강한 증거를 유지해야 합니다. 현재 acceptance 스크립트는 구현 현황을 검증하는 근거이며 Radicale 라이선스 정책 예외를 의미하지 않습니다.

## 문서

- [공개 문서 홈](docs/index.md)
- [제품 요구사항](docs/product/PRD.md) · [기술 요구사항](docs/technical/TRD.md)
- [아키텍처와 위협 경계](docs/ARCHITECTURE.md) · [UML](docs/architecture/UML.md)
- [ADR 색인](docs/adr/README.md) · [역법 조사와 구현 규칙](docs/research/README.md)
- [위협 모델](docs/security/THREAT_MODEL.md) · [Keyverse OIDC 연동](docs/security/KEYVERSE.md)
- [테스트 전략](docs/testing/TEST_STRATEGY.md) · [운영성](docs/operations/OPERABILITY.md)
- [요구사항 추적](docs/TRACEABILITY.md) · [근거·APA 7 기록](docs/doctoring/README.md)
- [배포와 CalDAV 연결](docs/DEPLOYMENT.md)
- [Figma 운영자 콘솔](https://www.figma.com/design/P4wdj2MnYwItYch3zdGIWt)
- [제품 설계](docs/superpowers/specs/2026-07-19-saju-caldav-design.md) · [구현 계획](docs/superpowers/plans/2026-07-19-saju-caldav.md)
- [제3자 소프트웨어 고지](THIRD_PARTY_NOTICES.md)

## 라이선스

ContextualWisdomLab이 이 저장소에서 제공하는 원본 소스는 [Apache License 2.0](LICENSE)으로 제공됩니다.

제3자 소프트웨어의 권리는 각각의 원 라이선스에 따릅니다. 저장소에 포함된 `lunar-python 1.4.8`과 고정 런타임 의존성 `korean-lunar-calendar 0.4.0`의 MIT 근거, 원본/배포물 해시와 라이선스 전문 위치는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 기록되어 있습니다. 현재 GPLv3 Radicale 배포 의존성은 이 Apache-2.0 부여 범위에 포함되지 않으며 상용 반입 정책 결함으로 [Issue #45](https://github.com/ContextualWisdomLab/saju-caldav/issues/45)에서 제거·대체를 추적합니다.
