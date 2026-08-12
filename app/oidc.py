"""Fail-closed Keyverse OIDC JWT verification for the Saju API."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt

from app.identity import AuthIdentity, TenantScope

MIN_FORCED_JWKS_REFRESH_SECONDS = 30.0


class OidcVerificationError(ValueError):
    """Raised when a bearer token cannot prove the configured identity."""


@dataclass(frozen=True, slots=True)
class OidcSettings:
    """Bounded Keyverse issuer and authorization policy configuration."""

    issuer: str
    audience: str
    jwks_url: str
    required_organization: str
    required_workspace: str
    allowed_roles: frozenset[str]
    clock_skew_seconds: int = 60
    jwks_cache_seconds: int = 300

    @classmethod
    def from_environment(cls, environ: dict[str, str]) -> OidcSettings:
        """Build settings from deployment values without accepting unsafe URLs."""

        issuer = environ.get("OIDC_ISSUER", "").strip().rstrip("/")
        audience = environ.get("OIDC_AUDIENCE", "").strip()
        required_organization = environ.get("OIDC_REQUIRED_ORG", "").strip()
        required_workspace = environ.get("OIDC_REQUIRED_WORKSPACE", "").strip()
        if not issuer or not audience or not required_organization or not required_workspace:
            raise ValueError(
                "OIDC_ISSUER, OIDC_AUDIENCE, OIDC_REQUIRED_ORG, and "
                "OIDC_REQUIRED_WORKSPACE are required"
            )
        parsed = urlsplit(issuer)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OIDC_ISSUER must be an HTTPS URL without credentials")
        jwks_url = environ.get("OIDC_JWKS_URL", "").strip()
        if not jwks_url:
            jwks_url = f"{issuer}/protocol/openid-connect/certs"
        parsed_jwks = urlsplit(jwks_url)
        if (
            parsed_jwks.scheme != "https"
            or not parsed_jwks.hostname
            or parsed_jwks.username is not None
            or parsed_jwks.password is not None
            or parsed_jwks.query
            or parsed_jwks.fragment
        ):
            raise ValueError("OIDC_JWKS_URL must be an HTTPS URL without credentials")
        raw_roles = environ.get("OIDC_ALLOWED_ROLES", "member").split(",")
        allowed_roles = frozenset(role.strip() for role in raw_roles if role.strip())
        if not allowed_roles or any(len(role) > 64 for role in allowed_roles):
            raise ValueError("OIDC_ALLOWED_ROLES must contain one role")
        try:
            clock_skew_seconds = int(environ.get("OIDC_CLOCK_SKEW_SECONDS", "60"))
        except ValueError as error:
            raise ValueError("OIDC_CLOCK_SKEW_SECONDS must be an integer") from error
        if not 0 <= clock_skew_seconds <= 300:
            raise ValueError("OIDC_CLOCK_SKEW_SECONDS must be between 0 and 300")
        try:
            jwks_cache_seconds = int(environ.get("OIDC_JWKS_CACHE_SECONDS", "300"))
        except ValueError as error:
            raise ValueError("OIDC_JWKS_CACHE_SECONDS must be an integer") from error
        if not 30 <= jwks_cache_seconds <= 3600:
            raise ValueError("OIDC_JWKS_CACHE_SECONDS must be between 30 and 3600")
        return cls(
            issuer=issuer,
            audience=audience,
            jwks_url=jwks_url,
            required_organization=required_organization,
            required_workspace=required_workspace,
            allowed_roles=allowed_roles,
            clock_skew_seconds=clock_skew_seconds,
            jwks_cache_seconds=jwks_cache_seconds,
        )


class OidcVerifier:
    """Validate Keyverse-signed JWTs and return a tenant-bound identity."""

    def __init__(
        self,
        settings: OidcSettings,
        *,
        jwks_loader: Callable[[str], dict[str, Any]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Create a verifier with injectable network and clock seams for tests."""

        self.settings = settings
        self._jwks_loader = jwks_loader or self._load_jwks
        self._clock = clock or time.time
        self._jwks: dict[str, dict[str, Any]] = {}
        self._jwks_loaded_at = 0.0
        self._jwks_forced_at = 0.0
        self._jwks_lock = Lock()

    @staticmethod
    def _load_jwks(url: str) -> dict[str, Any]:
        """Fetch one bounded JWKS document without sending bearer material."""

        try:
            response = httpx.get(
                url,
                headers={"Accept": "application/json"},
                timeout=5.0,
                follow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, OSError, ValueError, TypeError) as error:
            raise OidcVerificationError("unable to load JWKS") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
            raise OidcVerificationError("invalid JWKS document")
        return payload

    def _refresh_jwks(self, *, force: bool = False) -> dict[str, dict[str, Any]]:
        """Load and index a bounded JWKS set, refreshing once on key rotation."""

        now = self._clock()
        with self._jwks_lock:
            if (
                not force
                and self._jwks
                and now - self._jwks_loaded_at < self.settings.jwks_cache_seconds
            ):
                return self._jwks
            if force:
                if self._jwks and (
                    now - self._jwks_forced_at < MIN_FORCED_JWKS_REFRESH_SECONDS
                ):
                    return self._jwks
                self._jwks_forced_at = now

        # Keep the network call outside the lock. A slow or unavailable issuer
        # must not block unrelated requests that can use the cached key set.
        document = self._jwks_loader(self.settings.jwks_url)
        if not isinstance(document, dict):
            raise OidcVerificationError("invalid JWKS document")
        raw_keys = document.get("keys")
        if not isinstance(raw_keys, list) or len(raw_keys) > 64:
            raise OidcVerificationError("invalid JWKS document")
        keys: dict[str, dict[str, Any]] = {}
        for raw_key in raw_keys:
            if not isinstance(raw_key, dict):
                continue
            kid = raw_key.get("kid")
            if (
                isinstance(kid, str)
                and 1 <= len(kid) <= 256
                and raw_key.get("kty") == "RSA"
                and raw_key.get("alg", "RS256") == "RS256"
                and raw_key.get("use", "sig") == "sig"
            ):
                keys[kid] = raw_key
        if not keys:
            raise OidcVerificationError("JWKS contains no usable signing keys")
        with self._jwks_lock:
            if now >= self._jwks_loaded_at:
                self._jwks = keys
                self._jwks_loaded_at = now
            return self._jwks

    def verify(self, token: str) -> AuthIdentity:
        """Validate signature, issuer, audience, time, and Keyverse claims."""

        if not token or len(token) > 16_384:
            raise OidcVerificationError("invalid bearer token")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise OidcVerificationError("unsupported token algorithm")
            kid = header["kid"]
            if not kid:
                raise OidcVerificationError("invalid signing key identifier")
            keys = self._refresh_jwks()
            raw_key = keys.get(kid)
            if raw_key is None:
                raw_key = self._refresh_jwks(force=True).get(kid)
            if raw_key is None:
                raise OidcVerificationError("unknown signing key")
            signing_key = jwt.PyJWK.from_dict(raw_key).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.settings.audience,
                issuer=self.settings.issuer,
                leeway=self.settings.clock_skew_seconds,
                options={
                    "require": ["iss", "sub", "aud", "exp", "iat"],
                    "verify_signature": True,
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except OidcVerificationError:
            raise
        except (
            httpx.HTTPError,
            jwt.InvalidTokenError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            raise OidcVerificationError("invalid bearer token") from error
        if not isinstance(claims, dict):
            raise OidcVerificationError("invalid token claims")
        subject = claims.get("sub")
        organization = claims.get("org")
        workspace = claims.get("workspace")
        role = claims.get("role")

        def claim_string(value: object, label: str) -> str:
            """Return one bounded non-empty string claim or reject it."""

            if (
                not isinstance(value, str)
                or not 1 <= len(value) <= 256
                or value != value.strip()
            ):
                raise OidcVerificationError(f"{label} claim is invalid")
            return value

        subject = claim_string(subject, "subject")
        organization = claim_string(organization, "organization")
        workspace = claim_string(workspace, "workspace")
        if not isinstance(role, str) or not 1 <= len(role) <= 64:
            raise OidcVerificationError("required tenant claims are missing")
        if organization != self.settings.required_organization:
            raise OidcVerificationError("token organization is not allowed")
        if workspace != self.settings.required_workspace:
            raise OidcVerificationError("token workspace is not allowed")
        if role not in self.settings.allowed_roles:
            raise OidcVerificationError("token role is not allowed")
        now = self._clock()
        expires_at = claims.get("exp")
        issued_at = claims.get("iat")
        if (
            isinstance(expires_at, bool)
            or not isinstance(expires_at, (int, float))
            or not math.isfinite(float(expires_at))
            or expires_at <= now - self.settings.clock_skew_seconds
        ):
            raise OidcVerificationError("token expiration time is invalid")
        if (
            isinstance(issued_at, bool)
            or not isinstance(issued_at, (int, float))
            or not math.isfinite(float(issued_at))
            or issued_at > now + self.settings.clock_skew_seconds
        ):
            raise OidcVerificationError("token issued-at time is invalid")
        return AuthIdentity(
            scope=TenantScope(subject, organization, workspace),
            role=role,
            method="oidc",
        )
