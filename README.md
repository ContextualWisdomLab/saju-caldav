# 時曆 · Saju CalDAV

양력 출생 시각에서 사주 네 기둥을 계산하고, 간지 조건이 맞는 날짜와 시각을
개인 CalDAV 캘린더로 발행하는 단일 운영자용 서비스입니다.

> 문화·역법 참고 도구입니다. 운세의 과학적 타당성이나 미래 사건과의
> 인과관계를 주장하지 않습니다.

## 검증 기준

양력 `1990-06-15 08:30`, 여성, `Asia/Seoul`, 표준시 입력은 다음과 같이
고정 검증됩니다.

| 년주 | 월주 | 일주 | 시주 |
| --- | --- | --- | --- |
| 庚午 | 壬午 | 辛亥 | 壬辰 |

- 일지: `亥水`
- 시간: `壬水`
- 같은 사람의 일지와 같은 `亥`일이면서 시간이 `壬`인 조건의 해당일
  미리보기: `1990-06-15 07:00–09:00 KST`

이 기준은 `lunar-python`과 독립 구현 `sxtwl`로 교차 확인했고, 저장소의
회귀 테스트로 고정했습니다.

## 기능

- 출생 프로필별 년주·월주·일주·시주 계산
- 표준시 기본, 출생지 경도를 사용한 진태양시 보정 선택
- 일주·시주의 천간, 지지, 오행을 조합하는 허용 목록 기반 규칙
- 날짜 범위 미리보기와 결정적 RFC 5545 iCalendar 이벤트 생성
- Radicale을 통한 RFC 4791 CalDAV 캘린더 발행
- HTTP Basic으로 보호되는 한국어 운영자 웹 콘솔
- SQLite 메타데이터와 소유자 전용 CalDAV 저장소

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
- [배포와 CalDAV 연결](docs/DEPLOYMENT.md)
- [Figma 운영자 콘솔](https://www.figma.com/design/P4wdj2MnYwItYch3zdGIWt)
- [제품 설계](docs/superpowers/specs/2026-07-19-saju-caldav-design.md)
- [구현 계획](docs/superpowers/plans/2026-07-19-saju-caldav.md)

## 개인정보

출생 정보는 민감한 개인정보로 취급합니다. 실제 데이터베이스, `.env`, CalDAV
컬렉션, 운영 로그는 저장소나 공개 CI로 보내지 않습니다. 공개 테스트에는 오직
사용자가 명시한 회귀 검증용 합성 데이터만 포함합니다.
