# 사주 캘린더 · CalDAV

사주 캘린더 · CalDAV는 양력 또는 한국 음력 출생 시각을 이해 가능한 한국어로 계산하고, 두 사람이 함께 확인할 미래의 시간 조건을 찾아 캘린더 흐름으로 이어 주는 운영자 도구입니다. 문화·역법 참고 도구이며 운세의 과학적 타당성, 미래 사건의 인과관계, 전통적인 궁합·길일의 정확성을 주장하지 않습니다.

[Ask DeepWiki](https://deepwiki.com/ContextualWisdomLab/saju-caldav)

## 시작하기

- [저장소 README](https://github.com/ContextualWisdomLab/saju-caldav#readme) — 제품 가치, 빠른 시작, 사용 흐름, 보안·라이선스 경계.
- [제품 요구사항](product/PRD.html) — 사용자 가치, 범위, 제품 수용 기준.
- [기술 요구사항](technical/TRD.html) — 런타임, 데이터, 연동 및 품질 계약.
- [아키텍처와 위협 경계](ARCHITECTURE.html) — 서비스 경계와 주요 기술 결정.
- [배포 가이드](DEPLOYMENT.html) — 현재 구현의 배포·CalDAV 연결 절차와 운영 조건.
- [ADR 색인](adr/README.html) — 수용된 아키텍처 결정과 근거.
- [위협 모델](security/THREAT_MODEL.html) — 인증, 데이터, 네트워크 보안 경계.
- [Keyverse OIDC 연동](security/KEYVERSE.html) — OIDC issuer, audience, JWKS 및 이행 경계.
- [역법 조사와 구현 규칙](research/README.html) — RFC와 역법 근거, 구현 규칙.
- [운영성과](operations/OPERABILITY.html) — 운영 및 복구 계약.
- [요구사항 추적](TRACEABILITY.html) — 제품·기술 요구사항과 검증 증거 연결.

## 제품과 아키텍처

서비스는 출생 프로필, 관계 작용 또는 공통 조건 탐색, RFC 5545 iCalendar 이벤트 생성과 RFC 4791 CalDAV 발행을 분리된 책임으로 다룹니다. 운영자 웹 콘솔은 HTTP Basic 또는 검증된 Keyverse OIDC bearer를 사용할 수 있으며, OIDC 검증 실패를 Basic 성공으로 바꾸지 않습니다. 사용자·조직·workspace 격리는 웹/API 계층과 SQLite 메타데이터에 적용됩니다.

출생 정보는 민감한 개인정보로 취급합니다. 실제 데이터베이스, 비밀 환경 변수, CalDAV 컬렉션, 운영 로그와 실제 회귀 입력은 공개 저장소나 공개 CI에 포함하지 않습니다. 공개 테스트는 서비스와 무관한 합성 데이터만 사용합니다.

## 상용 배포와 라이선스 상태

ContextualWisdomLab의 이 저장소 원본 소스는 Apache License 2.0으로 제공됩니다. 저장소에 포함된 `lunar-python 1.4.8`과 `korean-lunar-calendar 0.4.0`은 보존된 MIT 라이선스·해시 근거를 따릅니다.

현재 구현의 CalDAV full-stack 경계는 GPLv3 Radicale 3.7.7을 직접 사용하므로 ContextualWisdomLab의 상용 반입 정책에는 맞지 않습니다. [Issue #45](https://github.com/ContextualWisdomLab/saju-caldav/issues/45)가 상업적으로 허용되는 CalDAV 경계로의 제거·대체를 추적합니다. 이 문제가 닫히기 전에는 현재 Radicale 기반 배포를 조직의 상용 배포 기준을 충족한 경로로 설명하지 않습니다.

- [Apache-2.0 프로젝트 라이선스](https://github.com/ContextualWisdomLab/saju-caldav/blob/main/LICENSE)
- [제3자 소프트웨어 고지](https://github.com/ContextualWisdomLab/saju-caldav/blob/main/THIRD_PARTY_NOTICES.md)

## 온보딩과 검증

Python 3.12 이상과 `uv`를 사용합니다. 기본 개발 검증은 `uv run pytest -q`와 `uv run ruff check .`입니다. 기존 acceptance smoke는 현재 구현의 프로필 생성 → CalDAV 읽기 계약을 검증하지만, 그것이 Radicale의 상용 반입 정책 예외를 의미하지는 않습니다. 대체 CalDAV 경계는 같은 고객 기능과 격리·삭제·복구·실제 프로토콜 수용 기준을 보존해야 합니다.

## 릴리스와 더 보기

- [GitHub Releases](https://github.com/ContextualWisdomLab/saju-caldav/releases)
- [변경 이력](https://github.com/ContextualWisdomLab/saju-caldav/blob/main/CHANGELOG.md)
- [ContextualWisdomLab](https://github.com/ContextualWisdomLab)

이 사이트는 저장소의 공개 문서 진입점입니다. 실제 GitHub Pages 게시 상태는 저장소 설정과 배포가 완료되고 공개 URL에서 확인된 경우에만 게시된 것으로 간주합니다.
