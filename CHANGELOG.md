# 변경 이력

이 파일은 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 구조를 따르며,
버전은 [Semantic Versioning](https://semver.org/spec/v2.0.0.html)을 따른다.

## [Unreleased]

다음 변경은 아직 릴리스되지 않았다.

### Changed

- 두 사람 시간 검색을 `관계 작용`과 `공통 조건` 모드로 분리하고, 개인 점수와
  관계 작용 점수를 함께 표시
- 후보 카드에 일지·일간·지지·오행 흐름 설명과 긍정 연결·충·생극 흐름 지표를 추가
- 기존 `balanced_branch_harmony` 캘린더는 공통 조건 모드로 보존

### Added

- `AUTH_MODE=basic|hybrid|oidc`와 Keyverse Bearer 검증, `sub`·조직·workspace
  기준의 프로필·캘린더 테넌트 격리
- 기존 SQLite 프로필에 소유 subject·조직·workspace를 안전하게 보강하는 스키마
  마이그레이션과 OIDC 운영 전환 문서
- CalDAV·iCalendar RFC를 ADR-0002 참고문헌과 ADR-0006·0007 결정 기록으로 인용

## [0.2.0] - 2026-08-11

### Added

- 저장된 출생 프로필을 한글 요약과 함께 확인하고 삭제하는 운영자 콘솔 흐름
- 동기화된 CalDAV 컬렉션을 먼저 삭제하는 프로필·캘린더 개인정보 삭제 경계
- 삭제 실패 시 로컬 메타데이터를 보존하는 fail-closed API와 회귀 테스트
- 제품·기술·보안·운영·검증 추적 문서와 시간별 품질 루프 설계

### Changed

- 프로필 삭제가 궁합 캘린더의 보조 프로필 연결까지 정리하도록 변경

## [0.1.0] - 2026-08-11

### Added

- 양력·한국 음력·윤달 출생 입력과 출생 시각 미상 보존
- 년주·월주·일주·시주 계산, 한글 설명, 두 사람 시간 추천
- 허용 목록 기반 조건 캘린더 미리보기와 RFC 5545/RFC 4791 CalDAV 발행
- 시간대·선택적 진태양시, Radicale 저장소, HTTP Basic 운영자 콘솔

[Unreleased]: https://github.com/ContextualWisdomLab/saju-caldav/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/ContextualWisdomLab/saju-caldav/releases/tag/v0.2.0
[0.1.0]: https://github.com/ContextualWisdomLab/saju-caldav/releases/tag/v0.1.0
