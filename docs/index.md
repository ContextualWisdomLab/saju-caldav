# 사주 캘린더 · CalDAV

사주 캘린더 · CalDAV는 양력 또는 한국 음력 출생 시각에서 사주 네 기둥을 계산하고, 설명 가능한 시간 조건을 개인 CalDAV 캘린더로 발행하는 단일 운영자용 서비스입니다. 문화·역법 참고 도구이며 운세의 과학적 타당성이나 미래 사건과의 인과관계를 주장하지 않습니다.

[Ask DeepWiki](https://deepwiki.com/ContextualWisdomLab/saju-caldav)

## 시작하기

- [저장소 README](https://github.com/ContextualWisdomLab/saju-caldav#readme) — 기능, 빠른 시작, 로컬 및 Docker 실행 방법.
- [배포 가이드](DEPLOYMENT.md) — 운영 배포와 CalDAV 연결 절차.
- [제품 요구사항](product/PRD.md) — 사용자 가치, 범위, 제품 수용 기준.
- [기술 요구사항](technical/TRD.md) — 런타임, 데이터, 연동 및 품질 계약.
- [아키텍처와 위협 경계](ARCHITECTURE.md) — 서비스 경계와 주요 기술 결정.
- [ADR 색인](adr/README.md) — 수용된 아키텍처 결정과 근거.
- [위협 모델](security/THREAT_MODEL.md) — 인증, 데이터, 네트워크 보안 경계.
- [Keyverse OIDC 연동](security/KEYVERSE.md) — OIDC issuer, audience, JWKS 및 이행 경계.
- [역법 조사와 구현 규칙](research/README.md) — RFC와 역법 근거, 구현 규칙.
- [운영성과](operations/OPERABILITY.md) — 운영 및 복구 계약.
- [요구사항 추적](TRACEABILITY.md) — 제품·기술 요구사항과 검증 증거 연결.

## 제품과 아키텍처

서비스는 출생 프로필, 관계 작용 또는 공통 조건 탐색, RFC 5545 iCalendar 이벤트 생성, RFC 4791 CalDAV 발행을 하나의 운영 경계 안에서 제공합니다. 운영자 웹 콘솔은 HTTP Basic 또는 검증된 Keyverse OIDC bearer를 사용할 수 있으며, OIDC 모드에서는 검증 실패를 Basic으로 우회하지 않습니다. 프로필과 캘린더 상태는 검증된 사용자·조직·workspace 경계를 따라 격리됩니다.

출생 정보는 민감한 개인정보로 취급합니다. 실제 데이터베이스, 비밀 환경 변수, CalDAV 컬렉션, 운영 로그와 실제 회귀 입력은 공개 저장소나 공개 CI에 포함하지 않습니다. 공개 테스트는 서비스와 무관한 합성 데이터만 사용합니다.

## 온보딩과 검증

Python 3.12 이상과 `uv`를 사용합니다. 기본 개발 검증은 `uv run pytest -q`와 `uv run ruff check .`이며, 전체 스택은 저장소의 acceptance smoke 절차로 프로필 생성부터 CalDAV 읽기까지 확인할 수 있습니다. 운영 배포 전에는 TLS 또는 신뢰된 네트워크 경계, 서로 다른 강한 인증 비밀, OIDC 설정과 CalDAV 접근 제어를 배포 가이드에 따라 확인하십시오.

## 릴리스와 더 보기

- [GitHub Releases](https://github.com/ContextualWisdomLab/saju-caldav/releases)
- [변경 이력](https://github.com/ContextualWisdomLab/saju-caldav/blob/main/CHANGELOG.md)
- [ContextualWisdomLab](https://github.com/ContextualWisdomLab)

이 사이트는 저장소의 공개 문서 진입점입니다. 실제 GitHub Pages 게시 상태는 저장소 설정과 배포가 완료되고 공개 URL에서 확인된 경우에만 게시된 것으로 간주합니다.
