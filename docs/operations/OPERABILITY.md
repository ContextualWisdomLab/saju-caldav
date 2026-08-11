# 운영성과와 구매자 증적

## 상태 신호

- `GET /health`는 프로세스 상태를 `{"status":"ok"}`로 반환한다.
- SQLite integrity, Radicale collection 목록, 컨테이너 health를 배포 후 확인한다.
- 동기화 시각은 `last_synced_at`에 기록하지만, 삭제 때 이 표시에 의존하지 않고
  원격 DELETE를 항상 시도한다. 404는 이미 지워진 상태로 처리하고 연결·권한
  오류는 로컬 메타데이터를 남긴 채 중단한다.

## 배포 체크리스트

1. 합성 smoke 입력으로 profile → preview → sync → CalDAV GET을 확인한다.
2. 변경 전 SQLite/Radicale 백업을 별도 경로에 만들고 백업 크기·무결성을 기록한다.
3. `docker compose ps`, health, SQLite `PRAGMA integrity_check`를 확인한다.
4. 삭제 회귀는 합성 프로필로 원격 collection DELETE와 로컬 행 부재를 확인한다.
5. 실패하면 이전 이미지·백업으로 되돌리고, 실제 PII를 로그에 출력하지 않는다.

## 시간별 품질 루프

`.github/workflows/hourly-product-loop.yml`은 매시 17분에 실행한다. 열린 PR이
있으면 새 개발을 만들지 않고 기존 PR의 head·Checks·리뷰를 우선한다. sentinel은
모델 없이 품질을 확인하고, NIM 제안은 ADR-0003의 모든 게이트를 통과할 때만
bounded artifact/PR을 만든다. 자세한 단계와 중단 조건은
[HOURLY_PRODUCT_LOOP.md](HOURLY_PRODUCT_LOOP.md)에 있다.

## 사고 대응

CalDAV 잔존·자격 증명 노출·잘못된 음력 계산이 의심되면 동기화를 중단하고,
영향 범위와 마지막 정상 SHA를 고정하며, 민감 데이터가 없는 증적만 수집한다.
보정·삭제·재발행은 승인된 운영자만 수행한다. 인증(CSAP/SOC 2) 상태나 법적
준수는 사고 기록만으로 주장하지 않는다.
