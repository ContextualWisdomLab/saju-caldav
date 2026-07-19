# 배포와 CalDAV 연결

## 요구 사항

- Docker Compose 또는 Podman Compose
- 웹용 포트 기본 `8000`, CalDAV용 포트 기본 `5232`
- 외부 접근 시 TLS 역방향 프록시 또는 VPN

## 시작

```bash
cp .env.example .env
chmod 600 .env
```

`.env`에서 웹과 CalDAV 암호를 서로 다른 24자 이상의 임의 값으로 바꿉니다.

```bash
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8000/health
```

## 종단간 검증

다음 스모크 테스트는 합성 출생 프로필과 중립적인 이름의 캘린더를 생성하고,
서버가 계산한 오늘부터의 미리보기와 동기화를 수행한 뒤 CalDAV `PROPFIND`와
`GET`으로 `.ics` 리소스를 다시 읽습니다. 기본 이벤트가 `PRIVATE`이고 명식 전용
속성이 없는지도 확인합니다. 테스트 프로필과 CalDAV 컬렉션은 종료 시 삭제합니다.

```bash
set -a
. ./.env
set +a
uv run python scripts/acceptance_smoke.py
```

성공 표식은 다음과 같습니다.

```text
SAJU_CALDAV_SMOKE_OK event_count=<현재 이후에 찾은 개수>
```

실제 사용자의 회귀값은 저장소나 명령행 인자에 적지 않고 서버 쪽 환경 변수로만
주입합니다. `PRIVATE_BIRTH_LOCAL`, `PRIVATE_TIMEZONE`,
`PRIVATE_EXPECT_DAY_BRANCH`, `PRIVATE_EXPECT_HOUR_STEM`이 설정되어 있으면 같은
스모크 테스트가 비공개 기대값까지 확인하되 출력에는 값이나 생년월일을 남기지
않습니다. 계산기만 빠르게 확인할 때는 다음 명령을 사용합니다.

```bash
uv run python scripts/private_regression.py
```

## 캘린더 앱 연결

- 서버 주소: `https://<host>/` 또는 VPN 안의 `http://<host>:5232/`
- 사용자 이름: `CALDAV_USERNAME`
- 암호: `CALDAV_PASSWORD`
- 직접 컬렉션 URL: `.../<CALDAV_USERNAME>/<calendar-slug>/`

Apple Calendar 등 자동 검색이 실패하면 운영자 콘솔에서 동기화 결과로 표시되는
컬렉션 URL을 직접 사용합니다.

캘린더의 공개 수준은 iCalendar `CLASS` 표시입니다. `PUBLIC`을 선택해도 Radicale
컬렉션 자체가 익명 공개되지는 않으며 위 사용자 이름과 암호가 계속 필요합니다.

## 운영

- 백업: `app-data`와 `radicale-data` 이름 볼륨을 같은 시점에 백업합니다.
- 복구: 서비스를 내린 뒤 두 볼륨을 복원하고 다시 시작합니다.
- 암호 변경: `.env` 수정 후 `docker compose up -d --force-recreate`를 실행합니다.
  Radicale의 bcrypt 파일은 시작할 때 새 암호로 재생성됩니다.
- 로그에는 출생 데이터나 암호를 출력하지 않습니다.
- 데이터베이스와 CalDAV 볼륨은 서버에만 두고 공개 CI로 복사하지 않습니다.
- 인터넷에 포트를 직접 노출하지 마십시오. Basic 인증은 TLS 없이는 자격 증명을
  보호하지 못합니다.

## 원격 호스트 예시

```bash
git clone https://github.com/ContextualWisdomLab/saju-caldav.git
cd saju-caldav
cp .env.example .env
# 암호 설정 후
docker compose up -d --build
```
