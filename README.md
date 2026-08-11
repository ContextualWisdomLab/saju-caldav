# 사주 캘린더 · CalDAV

양력 또는 한국 음력 출생 시각에서 사주 네 기둥을 계산하고, 두 사람에게
고르게 맞는 현재 이후의 실제 날짜·시각이나 사용자가 만든 조건의 일치 시간을
개인 CalDAV 캘린더로 발행하는 단일 운영자용 서비스입니다.

> 문화·역법 참고 도구입니다. 운세의 과학적 타당성이나 미래 사건과의
> 인과관계를 주장하지 않습니다.

## 기능

- 양력·한국 음력·윤달 출생 입력과 계산용 양력 시각의 분리 보존
- 태어난 시각 미상 입력: 일주 기반 추천은 제공하고 알 수 없는 시주는 비워 둠
- 출생 프로필별 년주·월주·일주·시주 계산과 한글 뜻 우선 설명
- 두 사람의 출생 정보를 한 화면에 입력해 가까운 날짜별 추천 시간 확인
- 기본 생활 시간(09:00–23:00) 추천과 새벽을 포함하는 24시간 검색 선택
- 한 사람에게만 유리한 후보를 줄이고, 두 사람의 일지와 날짜·시간 지지 관계를
  함께 보여 주는 설명 가능한 문화적 점수
- 추천 결과를 별도 CalDAV 캘린더로 저장하고 반복 동기화
- 출생 도시에서 IANA 시간대를 자동 선택하고 좌표 입력 없이 표준시 계산
- 선택한 도시의 서버 내부 경도를 사용하는 진태양시 보정 선택
- 일주·시주의 천간, 지지, 오행을 조합하는 허용 목록 기반 규칙
- 프로필 시간대의 오늘부터 1년간 조건 일치 시각 미리보기
- 비공개·제한 공개·공개 표시를 고르는 RFC 5545 iCalendar 이벤트
- Radicale을 통한 RFC 4791 CalDAV 캘린더 발행
- HTTP Basic으로 보호되는 한국어 운영자 웹 콘솔
- SQLite 메타데이터와 소유자 전용 CalDAV 저장소

첫 화면의 `두 사람의 좋은 시간 찾기`에서 저장된 프로필을 선택하거나 두 사람의
생년월일과 탄생 시를 바로 입력하면 됩니다. 기본 검색은 프로필 시간대의 지금
이후부터 1년 안에서 날짜마다 가장 균형이 높은 시간 하나를 골라 가까운 순으로
보여 줍니다. 기본값은 첫 번째 사람이 선택한 민간시 또는 진태양시 기준
09:00–23:00이며, 필요하면 `24시간 전체`로 새벽 후보까지 볼 수 있습니다. 더
세밀한 천간·지지 조건은 아래의 `고급: 직접 조건 만들기`에서 계속 사용할 수
있습니다.

태어난 시각을 모르면 `태어난 시각을 모릅니다`를 선택할 수 있습니다. 서비스는
양력 또는 한국 음력 생일로 일주를 계산해 두 사람 추천을 계속 제공하지만, 시주를
임의로 추정하지 않습니다. 이 프로필은 출생 시주를 참조하는 고급 조건만 사용할
수 없으며, 현재 시간의 천간·지지를 직접 고르는 조건은 그대로 사용할 수 있습니다.

## 빠른 시작

Python 3.12 이상과 [uv](https://docs.astral.sh/uv/)를 사용합니다.

```bash
uv sync --dev
APP_USERNAME=operator APP_PASSWORD='긴-임의-암호' \
  uv run uvicorn app.main:app --reload
```

CalDAV까지 포함한 배포는 다음과 같습니다.

```bash
cp .env.example .env
# .env의 APP_PASSWORD와 CALDAV_PASSWORD를 서로 다른 긴 임의 값으로 변경
docker compose up -d --build
```

- 운영자 콘솔: `http://localhost:8000/`
- CalDAV 기본 URL: `http://localhost:5232/`
- 사용자 캘린더 URL: `http://localhost:5232/<CALDAV_USERNAME>/<slug>/`

신뢰할 수 없는 네트워크에 노출할 때에는 Basic 인증을 평문 HTTP로 쓰지 말고,
TLS 역방향 프록시 또는 VPN 안에서만 접근해야 합니다. 상세 절차는
[배포 가이드](docs/DEPLOYMENT.md)에 있습니다.

## 개발 검증

```bash
uv run pytest -q
uv run ruff check .
```

공개 저장소에 둘 수 없는 실제 회귀값은 환경 변수로만 주입해 로컬에서
검증합니다. 이 명령은 입력값을 출력하지 않습니다.

```bash
uv run python scripts/private_regression.py
```

실행 중인 전체 스택은 실제 프로필 생성부터 CalDAV 읽기까지 검증할 수 있습니다.

```bash
set -a
. ./.env
set +a
uv run python scripts/acceptance_smoke.py
```

## 문서

- [역법 조사와 구현 규칙](docs/research/README.md)
- [아키텍처와 위협 경계](docs/ARCHITECTURE.md)
- [ADR-0001: 런타임 잠금과 CI 출처](docs/adr/0001-runtime-lock-and-ci-provenance.md)
- [배포와 CalDAV 연결](docs/DEPLOYMENT.md)
- [Figma 운영자 콘솔](https://www.figma.com/design/P4wdj2MnYwItYch3zdGIWt)
- [제품 설계](docs/superpowers/specs/2026-07-19-saju-caldav-design.md)
- [구현 계획](docs/superpowers/plans/2026-07-19-saju-caldav.md)
- [제3자 소프트웨어 고지](THIRD_PARTY_NOTICES.md)

## 개인정보

출생 정보는 민감한 개인정보로 취급합니다. 실제 데이터베이스, `.env`, CalDAV
컬렉션, 운영 로그는 저장소나 공개 CI로 보내지 않습니다. 공개 테스트에는 오직
서비스와 무관한 합성 데이터만 포함합니다. 실제 회귀 입력과 기대값은 환경
변수로만 전달하며, CalDAV 이벤트에도 사주 원문이나 규칙 값을 기록하지 않습니다.
`PUBLIC`을 선택해도 출생 정보와 규칙은 이벤트에 들어가지 않으며, Radicale의
계정 인증과 소유자 전용 접근 제어는 그대로 유지됩니다.
