# ADR-0004: Keyverse OIDC와 프로필 소유 범위 경계

## 상태

Accepted (2026-08-11)

## 문맥

Saju CalDAV는 기존 단일 운영자 Basic 인증으로 모든 프로필과 캘린더를 읽었다.
ContextualWisdomLab/keyverse는 생태계 중앙 IdP이지만, 같은 조직의 저장소라는
사실이나 client 등록 결과만으로 애플리케이션 권한이 생기지는 않는다. Keyverse
ADR-0008은 각 RP가 issuer, audience, JWKS 신뢰, claim 매핑, tenant 경계와
ABAC/RBAC를 직접 검증하도록 요구한다.

출생 정보는 민감한 개인정보이므로 다른 Keyverse subject가 UUID를 알아도 프로필,
규칙, CalDAV 컬렉션을 볼 수 없어야 한다. 동시에 실제 Keyverse issuer와 RP client가
아직 배포되지 않은 현재 개발 서버를 갑자기 잠그면 안 된다.

## 결정

1. API에 RS256 OIDC bearer 검증기를 둔다. 정확한 HTTPS `iss`, `aud`, `kid`와
   JWKS 서명, `sub`, `exp`, `iat`, `org`, `workspace`, 허용 `role`을 모두 확인하고
   실패하면 거부한다. Bearer 검증 실패 시 Basic으로 되돌아가지 않는다.
2. 검증된 `(sub, org, workspace)`를 SQLite `profiles`의 소유 범위로 저장한다.
   프로필과 그 프로필이 참여한 compatibility calendar의 모든 조회·변경·동기화는
   같은 범위로 제한한다. 다른 범위는 정보 노출을 줄이기 위해 404를 반환한다.
3. `AUTH_MODE=basic`을 하위 호환 기본값으로 유지하고, `hybrid`는 명시적으로
   구성된 OIDC 검증기와 Basic을 함께 쓰는 이행 모드로만 둔다. `oidc`와 `hybrid`는
   issuer/audience/org/workspace/JWKS 설정이 없으면 프로세스를 시작하지 않는다.
4. Keyverse RP 등록은 secret-free desired-state 템플릿과 Keyverse의
   validate→PUT→convergence 절차로 분리한다. admin token, client secret, 실제
   출생 데이터는 이 저장소에 넣지 않는다.

## 고려한 선택지

### 기존 Basic만 유지

구현은 단순하지만 중앙 IdP와 subject별 격리를 제공하지 못한다. 배포 이후의
다중 사용자 확장에도 안전한 기반이 아니므로 선택하지 않았다.

### Keyverse 토큰을 프록시 헤더로 신뢰

헤더 위조와 프록시 설정 실수에 취약하고, Keyverse ADR-0008의 서명·issuer·audience
검증 의무를 충족하지 못한다. 선택하지 않았다.

### 애플리케이션에서 OIDC 서명과 소유 범위를 직접 검증

JWKS 캐시와 키 회전을 포함한 좁은 resource-server 경계를 만들 수 있고, 기존
FastAPI API를 유지하면서 단계적으로 Basic에서 전환할 수 있다. 이 결정을 택했다.

## 결과

좋은 점:

- Keyverse 신뢰 경계와 애플리케이션 authorization 경계를 분리해 검증한다.
- subject·조직·workspace별 프로필 및 캘린더 격리가 SQLite 쿼리에서 강제된다.
- 기존 서버는 설정을 바꾸지 않는 한 계속 Basic으로 동작한다.
- 테스트가 정상 토큰, 변조된 claim, 키 회전, 네트워크 실패, cross-scope 접근을
  함께 검증한다.

주의할 점:

- 실제 Keyverse client reconciliation과 브라우저 authorization-code/PKCE 로그인은
  별도 배포 경계이며 이 PR만으로 완료되지 않는다.
- `AUTH_MODE=oidc`를 켜려면 운영자가 정확한 issuer와 tenant 값을 secret-free
  설정으로 공급해야 한다.
- 기존 legacy 프로필은 Basic 범위(`legacy:operator`)로 남는다. OIDC 사용자에게
  자동으로 이전하지 않으며, 이전은 별도의 승인된 데이터 작업이다.

## 검증 증거

- `tests/test_oidc.py`: 토큰 검증, JWKS 실패·회전, API subject 격리와 store 범위
  격리.
- `app/oidc.py`: 토큰 또는 credential을 로그에 남기지 않는 고정된 HTTPS JWKS 로더.
- `docs/security/KEYVERSE.md`: 배포 설정과 Keyverse desired-state 절차.

중앙 계약의 기준은 Keyverse ADR-0008이며, 이 앱은 실제 Keyverse 로그인·client
convergence 증거가 확보되기 전까지 `deployment-restricted` 상태다.
