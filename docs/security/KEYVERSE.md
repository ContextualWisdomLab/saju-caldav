# Keyverse OIDC 연동

이 서비스는 ContextualWisdomLab/keyverse를 중앙 IdP로 사용할 수 있는 OIDC
resource server 경계를 제공합니다. Keyverse client 등록만으로 인증이 완료된
것으로 간주하지 않으며, 서비스가 서명·issuer·audience·시간·조직·workspace·role을
검증한 뒤에만 프로필과 캘린더를 조회합니다.

## 현재 상태

`AUTH_MODE=basic`이 기본값이고, 기존 개발·운영자 설치의 동작을 보존합니다.
`AUTH_MODE=oidc`는 아래 계약이 모두 배포된 경우에만 켜십시오. `hybrid`는
마이그레이션 기간에만 사용하며 Basic 인증과 검증된 Bearer 인증을 모두 허용합니다.
Keyverse client reconciliation, 브라우저 authorization-code/PKCE 로그인, 실제
issuer의 토큰 수용·거부 증거가 없는 상태에서 이 앱을
`authorization-ready`로 표시하지 않습니다.

## 검증 계약

| 설정 | 의미 |
| --- | --- |
| `OIDC_ISSUER` | 정확히 일치하는 HTTPS Keyverse issuer |
| `OIDC_AUDIENCE` | 이 서비스에 발급된 정확한 audience (`saju-caldav-web`) |
| `OIDC_JWKS_URL` | HTTPS JWKS endpoint. 비우면 issuer의 Keycloak cert 경로 |
| `OIDC_REQUIRED_ORG` | 토큰 `org`와 정확히 일치해야 하는 조직 |
| `OIDC_REQUIRED_WORKSPACE` | 토큰 `workspace`와 정확히 일치해야 하는 workspace |
| `OIDC_ALLOWED_ROLES` | 허용된 role 목록. 기본값은 `member` |
| `OIDC_CLOCK_SKEW_SECONDS` | `exp`/`iat` 허용 시계 오차(0–300초) |
| `OIDC_JWKS_CACHE_SECONDS` | 서명 키 캐시(30–3600초) |

Bearer 토큰은 RS256과 `kid`가 있는 JWT여야 합니다. `iss`, 비어 있지 않은 불투명
`sub`, 정확한 `aud`, NumericDate `exp`·`iat`, 비어 있지 않은 `org`·`workspace`,
허용된 `role`을 모두 확인합니다. 검증된 `sub`·조직·workspace가 SQLite 프로필의
소유 범위가 되며, 다른 범위의 ID는 존재 여부를 드러내지 않고 404로 처리합니다.
토큰, Authorization 헤더, JWKS 응답은 로그에 기록하지 않습니다.

## Keyverse RP 등록

`deploy/templates/oidc-rp-saju-caldav.json`은 secret-free desired-state
템플릿입니다. Keyverse의 `docs/rp-onboarding.md` 절차대로 배포 컨트롤러에서
placeholder를 해석한 mode-0600 파일을 만들고 다음 순서를 지킵니다.

1. exact HTTPS redirect/origin/logout URI, PKCE `S256`, code flow만 렌더링합니다.
2. `/clients/relying-parties:validate`의 `ready_to_apply=true`를 확인합니다.
3. 같은 원본 payload를 `/clients/relying-parties/{client_id}`에 PUT합니다.
4. `convergence_state=in_sync`와 receipt 일치를 확인합니다.
5. 별도의 승인된 secret-management 경계에서만 필요한 confidential credential을
   저장합니다. 이 앱의 public client 템플릿에는 client secret이 없습니다.

이 저장소에는 Keyverse admin token, client secret, 개인 redirect URI를 넣지
않습니다. 현재 서버에 issuer가 등록되어 있지 않으면 운영 서버의 `AUTH_MODE`를
변경하지 말고 Basic을 유지하십시오.

## 수동 검증 예시

```bash
AUTH_MODE=oidc \
OIDC_ISSUER=https://keyverse.example/realms/cwl \
OIDC_AUDIENCE=saju-caldav-web \
OIDC_REQUIRED_ORG=org-cwl \
OIDC_REQUIRED_WORKSPACE=workspace-org-cwl \
OIDC_ALLOWED_ROLES=member \
docker compose up -d --build
```

운영 전에는 실제 Keyverse가 서명한 합성 계정 토큰으로 정상 요청을 확인하고,
issuer·signature·algorithm·expiry·audience·sub·org·workspace·role을 각각 바꾼
토큰이 거부되는지, 다른 subject가 기존 프로필에 접근하지 못하는지 기록하십시오.
이 문서와 테스트는 그 downstream 경계를 증명하지만 Keyverse 서버에 client를
자동 등록하거나 실제 사용자 로그인을 대신하지 않습니다.

관련 중앙 결정은 [Keyverse ADR-0008](https://github.com/ContextualWisdomLab/keyverse/blob/main/docs/adr/0008-keyverse-rp-authorization-boundary.md),
이 저장소의 결정은 [ADR-0004](../adr/0004-keyverse-oidc-rp-boundary.md)에 있습니다.
