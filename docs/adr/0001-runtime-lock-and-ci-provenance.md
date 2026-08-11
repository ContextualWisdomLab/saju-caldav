# ADR-0001: 런타임 잠금 파일과 CI 공급망 출처를 하나의 검증 경계로 관리

## 상태

Accepted — 2026-08-11

## 문맥

이 서비스의 Docker 이미지는 `pyproject.toml`을 설치하지 않고 해시가 고정된
`requirements.lock`을 `--require-hashes`로 설치한다. 따라서 `pyproject.toml`과
`uv.lock`만 갱신하면 개발 환경은 새 버전을 사용해도 운영 이미지는 이전 버전을
계속 사용할 수 있다. 실제 열린 PR #10, #21에서 이 불일치가 발견됐고, PR #19의
회귀 테스트가 같은 문제를 재현했다.

CI는 저장소 내용을 checkout하고 외부 액션을 실행하므로, 이동하는 태그만 쓰면
실행되는 코드의 출처가 커밋마다 달라질 수 있다. 자격 증명이 필요한 단계가 없는
CI에서 checkout 자격 증명을 유지할 이유도 없다.

## 결정

1. 런타임 의존성은 `pyproject.toml`에 정확한 버전(`==`)으로 선언한다.
2. `uv.lock`은 프로젝트 해석 결과의 기준으로 유지한다.
3. Docker가 설치하는 `requirements.lock`은 다음 명령으로만 재생성한다.

   ```text
   uv export --frozen --no-dev --no-emit-project --format requirements.txt \\
     --output-file requirements.lock
   ```

4. `tests/test_deployment.py`가 모든 런타임 의존성의 이름·버전을
   `requirements.lock`과 비교해 잠금 파일 누락을 배포 전에 실패시킨다.
5. 저장소 CI의 외부 액션은 전체 커밋 SHA로 고정하고, checkout 단계는
   `persist-credentials: false`를 사용한다. 캐시 정책을 바꿀 때에는 해당 액션의
   호환 가능한 입력을 명시하고 보안 검사를 통과해야 한다.
6. 의존성·CI 변경은 하나의 현재-head PR에서 테스트, 보안 검사, 문서 변경을
   함께 검토한다. 통과하지 않은 자동 리뷰나 오래된 head의 승인을 병합 근거로
   사용하지 않는다.

## 결과

좋은 점:

- 개발 환경과 실제 이미지의 런타임 버전이 같아진다.
- 해시 잠금과 CI 커밋 출처가 코드 리뷰에서 확인 가능하다.
- 새 의존성 PR이 `requirements.lock`을 빠뜨리면 테스트가 즉시 알려 준다.

비용과 완화:

- 런타임 의존성을 올릴 때 `uv.lock`과 `requirements.lock`을 함께 갱신해야
  한다. 이를 자동 검증 테스트와 PR 체크리스트로 강제한다.
- SHA 고정은 태그보다 업데이트가 번거롭다. Dependabot PR을 사용하고, 새
  커밋의 전체 테스트·보안 검사를 다시 실행한다.

## 검증

- `uv lock --check`
- `uv run pytest -q`
- `uv run ruff check .`
- `git diff --check`
- 현재 PR head의 CI, dependency review, SAST, CodeQL, Strix, Noema, OpenCode
  결과를 모두 재조회
