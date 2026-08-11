# ADR-0003: 시간별 품질 감시와 NVIDIA NIM 제안 루프

## 상태

Proposed — 2026-08-11

## 문맥

열린 PR이 오래 남거나 현재 head의 테스트·보안·문서 상태가 낡으면 구매자에게
보이는 품질이 빠르게 떨어진다. 동시에 사주 계산 핵심은 결정적이고 개인정보를
다루므로 모델이 자격 증명·운영 DB·CalDAV에 접근해 자동 병합하는 구조는 허용할
수 없다.

## 결정

`.github/workflows/hourly-product-loop.yml`은 매시 17분과 수동 실행을 사용한다.
결정적 품질 sentinel은 모델 없이 잠금·테스트·ruff·coverage·문서 계약을 점검한다.
열린 PR이 있으면 gate는 후보의 현재 `headRefOid`, Checks, 리뷰 결정과 개수,
unresolved review thread, applicable rulesets를 다시 조회하고 요약만 남긴다.
현재 저장소의 NIM 단계는 구성 여부를 확인하는 안전한 gate일 뿐이며, 모델 실행·
bounded patch·verifier·PR publisher를 포함하지 않는다.

향후 NIM 제안을 활성화할 때 필요한 조건은 다음과 같다.

- 열린 PR이 0개이고 기본 브랜치 SHA를 고정할 것
- `NVIDIA_NIM_API_KEY`가 있고 `COPILOT_GITHUB_TOKEN`을 사용하지 않을 것
- OpenCode 바이너리와 외부 Action은 검증된 SHA로 고정할 것
- 모델 프로세스에서 GitHub/OIDC/Action runtime 토큰, `git push`, `gh`, 외부
  네트워크를 제거할 것
- 변경 파일·diff 크기·심볼릭 링크·임의 DB/CalDAV 접근을 제한할 것
- 모델 결과를 uncredentialed verifier가 테스트·coverage·diff 정책으로 검증한
  뒤, maintainer 앱 토큰을 늦게 주입하는 publisher가 한 개의 PR만 발행할 것

자동화는 merge, release, production deploy를 수행하지 않는다. 기존 중앙
reviewer-agent 키와 라우팅을 대체하지 않는다. Fugu, Conductor, TRINITY는
오케스트레이션 설계의 연구 입력이지만, 결정적 역법 결과를 모델 출력으로
대체하지 않는다.

## 현재 상태 전이

`gate → sentinel → safe summary → human review/merge`

게이트 실패, NIM 키 부재, 열린 PR, 검증 실패는 조용한 성공이 아니라 run summary와
운영 알림에 원인을 남긴다. 자세한 운영 규칙은
[시간별 루프](../operations/HOURLY_PRODUCT_LOOP.md)에 둔다.

NIM 실행을 도입하는 경우에만 다음의 별도 상태 전이를 설계·검증한다.

`NIM gate → base SHA 고정 → uncredentialed verify → bounded PR → current-head
checks/review → human merge`

## 보류 조건

NIM secret, maintainer 앱 자격 증명, 중앙 workflow 재사용 계약과 위협 경계가 이
저장소에 명시적으로 제공될 때까지 이 ADR은 Proposed로 남긴다. 그 전에는 현재의
sentinel과 안전한 gate만 활성화하며, NIM 모델이 실행되거나 PR이 발행된다고
간주하지 않는다.
