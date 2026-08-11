# 테스트 전략

## 계층

1. **결정적 단위** — 역법 변환, 자시 경계, 음력 윤달, 시간대·진태양시, 관계표,
   UID와 iCalendar 직렬화를 순수 입력으로 검증한다.
2. **저장소 단위** — SQLite foreign key, secondary profile 연결, 동기화 시각,
   마이그레이션과 삭제 순서를 검증한다.
3. **API 계약** — 인증, 한국어 오류, 미상 시각, 두 사람 추천, preview/sync,
   원격 삭제 fail-closed를 합성 TestClient로 검증한다.
4. **경계 통합** — 로컬 HTTP recorder로 MKCALENDAR/PUT/DELETE와 Radicale
   acceptance smoke를 검증한다.
5. **정적·공급망** — ruff, `node --check`, lock 검사, diff check, CodeQL/SAST/
   dependency/Trivy/Strix 및 container build를 현재 head에서 재실행한다.

## 품질 문턱

```bash
uv run coverage run -m pytest -q
uv run coverage report  # fail_under = 100
uv run ruff check .
uv run python scripts/private_regression.py  # 비공개 환경 변수만
```

지원 런타임은 Python 3.12 이상이며 CI와 릴리스 후보에서 Python 3.14도 실행한다.
브라우저 자동화는 실제 출생값 없이 정적 자산·접근성·삭제 확인 흐름을 검증한다.
coverage 예외는 Protocol 선언 같은 실행 불가능한 인터페이스에만 `pragma: no cover`
를 사용하고 이유를 코드에 남긴다.

## 실패 처리

실패한 테스트·스캐너·리뷰를 통과로 재분류하지 않는다. flaky 여부, 소스 결함,
provider/credential 지연, stale head를 구분하고, 수정 후 전체 문턱을 다시 실행한다.
