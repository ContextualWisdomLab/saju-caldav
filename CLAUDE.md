# Saju CalDAV 개발 계약

## 제품 경계

이 저장소는 양력·한국 음력 출생 정보를 사주 네 기둥으로 계산하고, 사용자가
정한 문화적 비교 규칙을 현재 이후의 실제 날짜·시간과 대조해 CalDAV로 발행하는
단일 운영자 서비스다. 결과는 역법·문화 참고용이며 예측, 진단, 재정·법률 조언이
아니다.

## 변경 원칙

- `AGENTS.md`, 해당 ADR, `docs/TRACEABILITY.md`를 먼저 읽고 작업한다.
- 코드 탐색은 `.codegraph`가 있으면 `codegraph explore`를 먼저 사용하고, 변경 후
  `codegraph sync`로 인덱스를 갱신한다.
- 계산 규칙을 바꿀 때는 `docs/research/README.md`와 `docs/doctoring/README.md`에
  1차 자료 또는 동료심사 연구, APA 7 인용, 불확실성 경계를 함께 기록한다.
- 새 동작은 RED 테스트를 먼저 추가하고 GREEN으로 만든다. 공개 `app` 코드의
  statement·branch coverage와 문서화된 공개 함수의 docstring을 100%로 유지한다.
- 출생 정보는 합성 데이터만 테스트·로그에 사용한다. 비공개 회귀 입력은 환경
  변수로만 주입하며 실제 운영 DB·CalDAV·자격 증명을 저장소에 복사하지 않는다.
- 삭제는 로컬 메타데이터를 지우기 전에 동기화된 원격 CalDAV 컬렉션을 지운다.
  원격 권한·연결이 확인되지 않으면 fail-closed 한다.
- 규칙은 허용 목록으로만 역직렬화한다. 임의 코드·식·SQL을 실행하지 않는다.
- 외부 GitHub Action은 전체 커밋 SHA로 고정하고 checkout 자격 증명을 보존하지
  않는다. `NVIDIA_NIM_API_KEY` 외의 모델 키나 `COPILOT_GITHUB_TOKEN`을 새 LLM
  경로에 사용하지 않는다. 기존 reviewer-agent 자격 증명과 라우팅은 변경하지
  않는다.
- 자동화는 PR·release·배포를 스스로 병합하지 않는다. 현재 head의 모든 Checks,
  리뷰, unresolved thread, ruleset을 다시 확인한 뒤 사람이 승인할 수 있는
  단일 bounded PR만 남긴다.

## 필수 검증

```bash
uv lock --check
uv run coverage run -m pytest -q
uv run coverage report
uv run ruff check .
git diff --check
codegraph sync
```

컨테이너나 원격 서버를 확인할 때에는 합성 데이터와 별도 백업을 사용하고,
실제 데이터 삭제·마이그레이션·배포는 명시된 운영 절차와 승인 경계 안에서만
수행한다.
