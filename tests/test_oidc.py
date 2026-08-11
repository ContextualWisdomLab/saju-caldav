from __future__ import annotations

import base64
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.security import HTTPBasicCredentials
from fastapi.testclient import TestClient

import app.main as main_module
from app.auth import AuthConfig, AuthenticationError, Authenticator
from app.identity import AuthIdentity, TenantScope
from app.oidc import OidcSettings, OidcVerificationError, OidcVerifier
from app.store import Store

ISSUER = "https://keyverse.example/realms/cwl"
AUDIENCE = "saju-caldav-web"
ORGANIZATION = "org-cwl"
WORKSPACE = "workspace-org-cwl"


def _settings() -> OidcSettings:
    return OidcSettings(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=f"{ISSUER}/protocol/openid-connect/certs",
        required_organization=ORGANIZATION,
        required_workspace=WORKSPACE,
        allowed_roles=frozenset({"member"}),
        clock_skew_seconds=5,
        jwks_cache_seconds=300,
    )


@pytest.fixture(scope="module")
def signing_material() -> tuple[rsa.RSAPrivateKey, dict[str, str]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()

    def encoded(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    jwk = {
        "kty": "RSA",
        "kid": "key-1",
        "use": "sig",
        "alg": "RS256",
        "n": encoded(public_numbers.n),
        "e": encoded(public_numbers.e),
    }
    return private_key, jwk


def _token(
    private_key: rsa.RSAPrivateKey,
    *,
    now: float | None = None,
    kid: str = "key-1",
    **changes: object,
) -> str:
    current = int(now if now is not None else time.time())
    claims: dict[str, object] = {
        "iss": ISSUER,
        "sub": "user-1",
        "aud": AUDIENCE,
        "exp": current + 300,
        "iat": current - 1,
        "org": ORGANIZATION,
        "workspace": WORKSPACE,
        "role": "member",
    }
    claims.update(changes)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def _verifier(
    jwk: dict[str, str],
    *,
    now: float | None = None,
    loader=None,
) -> OidcVerifier:
    clock = (lambda: now) if now is not None else time.time
    return OidcVerifier(
        _settings(),
        jwks_loader=loader or (lambda _url: {"keys": [jwk]}),
        clock=clock,
    )


def test_oidc_settings_require_exact_https_contract() -> None:
    settings = OidcSettings.from_environment(
        {
            "OIDC_ISSUER": ISSUER,
            "OIDC_AUDIENCE": AUDIENCE,
            "OIDC_REQUIRED_ORG": ORGANIZATION,
            "OIDC_REQUIRED_WORKSPACE": WORKSPACE,
        }
    )
    assert settings.jwks_url.endswith("/protocol/openid-connect/certs")
    assert settings.allowed_roles == frozenset({"member"})
    assert settings.jwks_cache_seconds == 300

    invalid_environments = (
        {},
        {"OIDC_ISSUER": "http://keyverse.example", "OIDC_AUDIENCE": AUDIENCE,
         "OIDC_REQUIRED_ORG": ORGANIZATION, "OIDC_REQUIRED_WORKSPACE": WORKSPACE},
        {"OIDC_ISSUER": ISSUER, "OIDC_AUDIENCE": AUDIENCE,
         "OIDC_REQUIRED_ORG": ORGANIZATION, "OIDC_REQUIRED_WORKSPACE": WORKSPACE,
         "OIDC_JWKS_URL": "https://keyverse.example/certs?tenant=cwl"},
        {"OIDC_ISSUER": ISSUER, "OIDC_AUDIENCE": AUDIENCE,
         "OIDC_REQUIRED_ORG": ORGANIZATION, "OIDC_REQUIRED_WORKSPACE": WORKSPACE,
         "OIDC_CLOCK_SKEW_SECONDS": "301"},
        {"OIDC_ISSUER": ISSUER, "OIDC_AUDIENCE": AUDIENCE,
         "OIDC_REQUIRED_ORG": ORGANIZATION, "OIDC_REQUIRED_WORKSPACE": WORKSPACE,
         "OIDC_JWKS_CACHE_SECONDS": "29"},
        {"OIDC_ISSUER": ISSUER, "OIDC_AUDIENCE": AUDIENCE,
         "OIDC_REQUIRED_ORG": ORGANIZATION, "OIDC_REQUIRED_WORKSPACE": WORKSPACE,
         "OIDC_ALLOWED_ROLES": ""},
        {"OIDC_ISSUER": ISSUER, "OIDC_AUDIENCE": AUDIENCE,
         "OIDC_REQUIRED_ORG": ORGANIZATION, "OIDC_REQUIRED_WORKSPACE": WORKSPACE,
         "OIDC_CLOCK_SKEW_SECONDS": "not-an-integer"},
        {"OIDC_ISSUER": ISSUER, "OIDC_AUDIENCE": AUDIENCE,
         "OIDC_REQUIRED_ORG": ORGANIZATION, "OIDC_REQUIRED_WORKSPACE": WORKSPACE,
         "OIDC_JWKS_CACHE_SECONDS": "not-an-integer"},
        {"OIDC_ISSUER": ISSUER, "OIDC_AUDIENCE": AUDIENCE,
         "OIDC_REQUIRED_ORG": ORGANIZATION, "OIDC_REQUIRED_WORKSPACE": WORKSPACE,
         "OIDC_ALLOWED_ROLES": "member," + "x" * 65},
    )
    for environ in invalid_environments:
        with pytest.raises(ValueError):
            OidcSettings.from_environment(environ)

    for value in (
        "https://user:password@keyverse.example/realms/cwl",
        "https://user@keyverse.example/realms/cwl",
        "https://keyverse.example/realms/cwl#fragment",
    ):
        invalid = {
            "OIDC_ISSUER": value,
            "OIDC_AUDIENCE": AUDIENCE,
            "OIDC_REQUIRED_ORG": ORGANIZATION,
            "OIDC_REQUIRED_WORKSPACE": WORKSPACE,
        }
        with pytest.raises(ValueError):
            OidcSettings.from_environment(invalid)

    for value in (
        "http://keyverse.example/certs",
        "https://user:password@keyverse.example/certs",
        "https://user@keyverse.example/certs",
        "https://keyverse.example/certs#fragment",
    ):
        invalid = {
            "OIDC_ISSUER": ISSUER,
            "OIDC_AUDIENCE": AUDIENCE,
            "OIDC_REQUIRED_ORG": ORGANIZATION,
            "OIDC_REQUIRED_WORKSPACE": WORKSPACE,
            "OIDC_JWKS_URL": value,
        }
        with pytest.raises(ValueError):
            OidcSettings.from_environment(invalid)


def test_oidc_loader_validates_http_responses(monkeypatch) -> None:
    valid_response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"keys": []},
    )
    monkeypatch.setattr("app.oidc.httpx.get", lambda *_args, **_kwargs: valid_response)
    assert OidcVerifier._load_jwks("https://keyverse.example/certs") == {"keys": []}

    invalid_response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: ["not-an-object"],
    )
    monkeypatch.setattr("app.oidc.httpx.get", lambda *_args, **_kwargs: invalid_response)
    with pytest.raises(OidcVerificationError, match="invalid JWKS"):
        OidcVerifier._load_jwks("https://keyverse.example/certs")


def test_oidc_verifier_accepts_verified_claims_and_reuses_jwks(
    signing_material: tuple[rsa.RSAPrivateKey, dict[str, str]],
) -> None:
    private_key, jwk = signing_material
    now = 1_800_000_000.0
    calls: list[str] = []

    def loader(url: str) -> dict[str, object]:
        calls.append(url)
        return {"keys": [jwk]}

    verifier = _verifier(jwk, now=now, loader=loader)
    token = _token(private_key, now=now)
    identity = verifier.verify(token)
    assert identity == AuthIdentity(
        scope=TenantScope("user-1", ORGANIZATION, WORKSPACE),
        role="member",
        method="oidc",
    )
    assert verifier.verify(token) == identity
    assert calls == [_settings().jwks_url]


@pytest.mark.parametrize(
    ("claim", "value"),
    (
        ("iss", "https://other.example/realms/cwl"),
        ("aud", "other-client"),
        ("sub", ""),
        ("org", "other-org"),
        ("workspace", "other-workspace"),
        ("role", ""),
        ("role", "admin"),
        ("exp", True),
        ("iat", True),
    ),
)
def test_oidc_verifier_rejects_claim_tampering(
    signing_material: tuple[rsa.RSAPrivateKey, dict[str, str]],
    claim: str,
    value: object,
) -> None:
    private_key, jwk = signing_material
    now = 1_800_000_000.0
    verifier = _verifier(jwk, now=now)
    token = _token(private_key, now=now, **{claim: value})
    with pytest.raises(OidcVerificationError):
        verifier.verify(token)


def test_oidc_verifier_rejects_time_window_and_token_shape(
    signing_material: tuple[rsa.RSAPrivateKey, dict[str, str]],
) -> None:
    private_key, jwk = signing_material
    now = 1_800_000_000.0
    verifier = _verifier(jwk, now=now)
    for token in (
        _token(private_key, now=now, exp=now - 10),
        _token(private_key, now=now, iat=now + 10),
        "not-a-jwt",
        "",
        "x" * 16_385,
    ):
        with pytest.raises(OidcVerificationError):
            verifier.verify(token)

    hmac_token = jwt.encode(
        {"iss": ISSUER, "sub": "user-1"}, "not-a-signing-key", algorithm="HS256"
    )
    with pytest.raises(OidcVerificationError):
        verifier.verify(hmac_token)


def test_oidc_verifier_rejects_rotated_or_malformed_jwks(
    signing_material: tuple[rsa.RSAPrivateKey, dict[str, str]],
) -> None:
    private_key, jwk = signing_material
    token = _token(private_key, now=1_800_000_000.0)
    for document in ({}, {"keys": []}, {"keys": ["not-a-key"]}, {"keys": [{}]}, []):
        verifier = _verifier(jwk, now=1_800_000_000.0, loader=lambda _url, d=document: d)
        with pytest.raises(OidcVerificationError):
            verifier.verify(token)

    unknown_kid = jwt.encode(
        {
            "iss": ISSUER,
            "sub": "user-1",
            "aud": AUDIENCE,
            "exp": 1_800_000_300,
            "iat": 1_799_999_999,
            "org": ORGANIZATION,
            "workspace": WORKSPACE,
            "role": "member",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "unknown"},
    )
    with pytest.raises(OidcVerificationError):
        _verifier(jwk, now=1_800_000_000.0).verify(unknown_kid)

    empty_kid = jwt.encode(
        {
            "iss": ISSUER,
            "sub": "user-1",
            "aud": AUDIENCE,
            "exp": 1_800_000_300,
            "iat": 1_799_999_999,
            "org": ORGANIZATION,
            "workspace": WORKSPACE,
            "role": "member",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": ""},
    )
    with pytest.raises(OidcVerificationError):
        _verifier(jwk, now=1_800_000_000.0).verify(empty_kid)


def test_oidc_verifier_accepts_key_after_forced_jwks_refresh(
    signing_material: tuple[rsa.RSAPrivateKey, dict[str, str]],
) -> None:
    private_key, jwk = signing_material
    rotated_jwk = {**jwk, "kid": "key-2"}
    documents = iter(({"keys": [jwk]}, {"keys": [rotated_jwk]}))
    calls: list[str] = []

    def loader(url: str) -> dict[str, object]:
        calls.append(url)
        return next(documents)

    verifier = _verifier(jwk, now=1_800_000_000.0, loader=loader)
    token = _token(private_key, now=1_800_000_000.0, kid="key-2")

    assert verifier.verify(token).scope.subject == "user-1"
    assert calls == [_settings().jwks_url, _settings().jwks_url]


def test_oidc_verifier_throttles_repeated_unknown_key_refreshes(
    signing_material: tuple[rsa.RSAPrivateKey, dict[str, str]],
) -> None:
    private_key, jwk = signing_material
    calls: list[str] = []

    def loader(url: str) -> dict[str, object]:
        calls.append(url)
        return {"keys": [jwk]}

    verifier = _verifier(jwk, now=1_800_000_000.0, loader=loader)
    token = _token(private_key, now=1_800_000_000.0, kid="unknown")
    for _ in range(2):
        with pytest.raises(OidcVerificationError, match="unknown signing key"):
            verifier.verify(token)

    assert calls == [_settings().jwks_url, _settings().jwks_url]


def test_oidc_loader_turns_network_failure_into_safe_error(monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        raise OSError("network secret should not escape")

    monkeypatch.setattr("app.oidc.httpx.get", fail)
    with pytest.raises(OidcVerificationError, match="unable to load JWKS"):
        OidcVerifier._load_jwks("https://keyverse.example/certs")


class _TokenVerifier:
    def __init__(self, identities: dict[str, AuthIdentity]) -> None:
        self.identities = identities

    def verify(self, token: str) -> AuthIdentity:
        if token not in self.identities:
            raise OidcVerificationError("unknown synthetic token")
        return self.identities[token]


def _profile_payload(name: str) -> dict[str, object]:
    return {
        "name": name,
        "birth_calendar": "solar",
        "birth_year": 1990,
        "birth_month": 6,
        "birth_day": 15,
        "birth_time": "08:30:00",
        "birth_time_known": True,
        "gender": "female",
        "birth_city": "seoul",
        "timezone": "Asia/Seoul",
        "time_mode": "civil",
    }


def test_oidc_api_scopes_profiles_and_calendars_to_verified_subject(tmp_path: Path) -> None:
    user_a = AuthIdentity(TenantScope("user-a", ORGANIZATION, WORKSPACE), "member", "oidc")
    user_b = AuthIdentity(TenantScope("user-b", ORGANIZATION, WORKSPACE), "member", "oidc")
    app = main_module.create_app(
        store=Store(tmp_path / "oidc.db"),
        auth_mode="oidc",
        oidc_verifier=_TokenVerifier({"token-a": user_a, "token-b": user_b}),
    )
    client = TestClient(app)

    created = client.post(
        "/api/profiles", headers={"Authorization": "Bearer token-a"}, json=_profile_payload("A")
    )
    assert created.status_code == 201, created.text
    profile = created.json()
    assert "owner_subject" not in profile
    assert client.get("/api/profiles", headers={"Authorization": "Bearer token-b"}).json() == []
    assert client.get(
        "/api/profiles", headers={"Authorization": "Bearer token-a"}
    ).json()[0]["id"] == profile["id"]
    assert client.get("/api/profiles", auth=("operator", "password")).status_code == 401
    assert client.get(
        "/api/profiles", headers={"Authorization": "Bearer invalid"}
    ).status_code == 401

    calendar = client.post(
        "/api/calendars",
        headers={"Authorization": "Bearer token-a"},
        json={
            "profile_id": profile["id"],
            "name": "A calendar",
            "slug": "a-calendar",
            "rule": {
                "logic": "all",
                "predicates": [
                    {"field": "day.branch", "source": "literal", "value": "亥"}
                ],
            },
        },
    )
    assert calendar.status_code == 201, calendar.text
    calendar_id = calendar.json()["id"]
    assert client.get(
        "/api/calendars", headers={"Authorization": "Bearer token-b"}
    ).json() == []
    assert client.post(
        f"/api/calendars/{calendar_id}/preview",
        headers={"Authorization": "Bearer token-b"},
        json={"start_date": "2026-01-01", "end_date": "2026-01-01"},
    ).status_code == 404
    delete_response = client.delete(
        f"/api/calendars/{calendar_id}", headers={"Authorization": "Bearer token-b"}
    )
    assert delete_response.status_code == 404


def test_oidc_api_compatibility_and_permission_races_are_scoped(
    tmp_path: Path,
    monkeypatch,
) -> None:
    identity = AuthIdentity(TenantScope("user-a", ORGANIZATION, WORKSPACE), "member", "oidc")
    verifier = _TokenVerifier({"token-a": identity})
    store = Store(tmp_path / "oidc-compatibility.db")
    app = main_module.create_app(store=store, auth_mode="oidc", oidc_verifier=verifier)
    client = TestClient(app)
    headers = {"Authorization": "Bearer token-a"}
    first = client.post("/api/profiles", headers=headers, json=_profile_payload("one"))
    second = client.post("/api/profiles", headers=headers, json=_profile_payload("two"))
    assert first.status_code == second.status_code == 201
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    preview = client.post(
        "/api/compatibility/preview",
        headers=headers,
        json={
            "primary_profile_id": first_id,
            "secondary_profile_id": second_id,
            "start_date": "1990-06-15",
            "end_date": "1990-06-15",
        },
    )
    assert preview.status_code == 200, preview.text
    created = client.post(
        "/api/compatibility/calendars",
        headers=headers,
        json={
            "primary_profile_id": first_id,
            "secondary_profile_id": second_id,
            "name": "pair",
            "slug": "oidc-pair",
        },
    )
    assert created.status_code == 201, created.text

    monkeypatch.setattr(
        store,
        "create_calendar",
        lambda **_kwargs: (_ for _ in ()).throw(PermissionError("race")),
    )
    denied_single = client.post(
        "/api/calendars",
        headers=headers,
        json={
            "profile_id": first_id,
            "name": "race",
            "slug": "oidc-race",
            "rule": {
                "logic": "all",
                "predicates": [
                    {"field": "day.branch", "source": "literal", "value": "亥"}
                ],
            },
        },
    )
    assert denied_single.status_code == 404
    denied_pair = client.post(
        "/api/compatibility/calendars",
        headers=headers,
        json={
            "primary_profile_id": first_id,
            "secondary_profile_id": second_id,
            "name": "race pair",
            "slug": "oidc-race-pair",
        },
    )
    assert denied_pair.status_code == 404


def test_create_app_builds_keyverse_verifier_from_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("OIDC_REQUIRED_ORG", ORGANIZATION)
    monkeypatch.setenv("OIDC_REQUIRED_WORKSPACE", WORKSPACE)
    app = main_module.create_app(
        store=Store(tmp_path / "env-oidc.db"),
        auth_mode="oidc",
    )
    assert app.title == "Saju CalDAV"


def test_authenticator_rejects_missing_hybrid_oidc_and_keeps_bearer_fail_closed() -> None:
    with pytest.raises(ValueError, match="AUTH_MODE"):
        Authenticator(AuthConfig("invalid", "operator", "password"))
    with pytest.raises(ValueError, match="OIDC configuration"):
        Authenticator(AuthConfig("hybrid", "operator", "password"))

    identity = AuthIdentity(TenantScope("user", ORGANIZATION, WORKSPACE), "member", "oidc")
    verifier = _TokenVerifier({"valid": identity})
    authenticator = Authenticator(
        AuthConfig("hybrid", "operator", "password"), oidc_verifier=verifier
    )
    assert authenticator.authenticate("Bearer valid", None) == identity
    with pytest.raises(AuthenticationError, match="invalid bearer"):
        authenticator.authenticate("Bearer invalid", None)
    credentials = HTTPBasicCredentials(username="operator", password="password")
    assert authenticator.authenticate(None, credentials).method == "basic"
    with pytest.raises(AuthenticationError, match="operator authentication"):
        authenticator.authenticate(None, None)
    with pytest.raises(AuthenticationError, match="operator authentication"):
        authenticator.authenticate(
            None,
            HTTPBasicCredentials(username="operator", password="wrong"),
        )
    with pytest.raises(AuthenticationError, match="OIDC bearer"):
        Authenticator(
            AuthConfig("oidc", "operator", "password"), oidc_verifier=verifier
        ).authenticate(None, None)
    with pytest.raises(AuthenticationError, match="bearer authentication"):
        Authenticator(AuthConfig("basic", "operator", "password")).authenticate(
            "Bearer valid", None
        )


def test_oidc_verifier_can_be_built_from_environment_and_claims_are_bounded(
    signing_material: tuple[rsa.RSAPrivateKey, dict[str, str]],
) -> None:
    environ = {
        "OIDC_ISSUER": ISSUER,
        "OIDC_AUDIENCE": AUDIENCE,
        "OIDC_REQUIRED_ORG": ORGANIZATION,
        "OIDC_REQUIRED_WORKSPACE": WORKSPACE,
    }
    assert main_module.oidc_verifier_from_environment({}) is None
    verifier = main_module.oidc_verifier_from_environment(environ)
    assert verifier is not None
    assert verifier.settings.issuer == ISSUER

    private_key, jwk = signing_material
    token = _token(private_key, now=1_800_000_000, sub="x" * 257)
    with pytest.raises(OidcVerificationError, match="subject"):
        _verifier(jwk, now=1_800_000_000).verify(token)


def test_oidc_verifier_rejects_non_mapping_decoded_claims(
    signing_material: tuple[rsa.RSAPrivateKey, dict[str, str]],
    monkeypatch,
) -> None:
    private_key, jwk = signing_material
    monkeypatch.setattr("app.oidc.jwt.decode", lambda *_args, **_kwargs: [])
    with pytest.raises(OidcVerificationError, match="token claims"):
        _verifier(jwk, now=1_800_000_000).verify(
            _token(private_key, now=1_800_000_000)
        )


def test_scoped_store_blocks_cross_tenant_calendar_access(tmp_path: Path) -> None:
    store = Store(tmp_path / "scoped.db")
    store.initialize()
    scope_a = TenantScope("user-a", ORGANIZATION, WORKSPACE)
    scope_b = TenantScope("user-b", ORGANIZATION, WORKSPACE)

    def create_profile(name: str, scope: TenantScope) -> dict[str, object]:
        return store.create_profile(
            name=name,
            birth_calendar="solar",
            birth_year=1990,
            birth_month=6,
            birth_day=15,
            birth_time="08:30:00",
            birth_time_known=True,
            is_leap_month=False,
            birth_local=datetime(1990, 6, 15, 8, 30),
            birth_city="seoul",
            birth_city_name="대한민국 · 서울",
            gender="female",
            timezone="Asia/Seoul",
            time_mode="civil",
            longitude=None,
            chart={},
            owner_subject=scope.subject,
            tenant_organization=scope.organization,
            tenant_workspace=scope.workspace,
        )

    primary = create_profile("primary", scope_a)
    secondary = create_profile("secondary", scope_a)
    foreign = create_profile("foreign", scope_b)
    assert store.list_profiles(scope_a) == [primary, secondary]
    assert store.get_profile(str(foreign["id"]), scope_a) is None

    calendar = store.create_calendar(
        profile_id=str(primary["id"]),
        name="single",
        slug="single-calendar",
        visibility="private",
        rule={},
        scope=scope_a,
    )
    compatibility = store.create_calendar(
        profile_id=str(primary["id"]),
        secondary_profile_id=str(secondary["id"]),
        name="pair",
        slug="pair-calendar",
        visibility="private",
        kind="compatibility",
        rule={"limit": 1},
        scope=scope_a,
    )
    with pytest.raises(ValueError, match="must differ"):
        store.create_calendar(
            profile_id=str(primary["id"]),
            secondary_profile_id=str(primary["id"]),
            name="same-person",
            slug="same-person-calendar",
            visibility="private",
            kind="compatibility",
            rule={},
            scope=scope_a,
        )
    with pytest.raises(PermissionError):
        store.create_calendar(
            profile_id=str(primary["id"]),
            secondary_profile_id=str(foreign["id"]),
            name="cross",
            slug="cross-calendar",
            visibility="private",
            rule={},
            scope=scope_a,
        )
    assert store.list_calendars(scope=scope_a)
    assert store.list_calendars(str(primary["id"]), scope_a)
    assert store.list_calendars_for_profile(str(secondary["id"]), scope_a) == [compatibility]
    assert store.get_calendar(str(calendar["id"]), scope_b) is None
    store.mark_synced(str(calendar["id"]), scope_a)
    assert store.get_calendar(str(calendar["id"]), scope_a)["last_synced_at"]
    assert store.delete_calendar(str(calendar["id"]), scope_b) is False
    assert store.delete_calendar(str(calendar["id"]), scope_a) is True
    assert store.delete_profile(str(secondary["id"]), scope_b) is False
    assert store.delete_profile(str(secondary["id"]), scope_a) is True
