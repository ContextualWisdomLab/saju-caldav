"""Authentication mode selection for local Basic and Keyverse OIDC callers."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi.security import HTTPBasicCredentials

from app.identity import AuthIdentity, TenantScope
from app.oidc import OidcSettings, OidcVerificationError, OidcVerifier


class AuthenticationError(ValueError):
    """Raised when no configured authentication mechanism proves identity."""


@dataclass(frozen=True, slots=True)
class AuthConfig:
    """Select a fail-closed authentication mode for one process."""

    mode: str
    username: str
    password: str


class Authenticator:
    """Authenticate Basic migration callers or verified Keyverse bearer tokens."""

    def __init__(
        self,
        config: AuthConfig,
        *,
        oidc_verifier: OidcVerifier | None = None,
    ) -> None:
        """Validate mode and retain only the configured auth adapters."""

        if config.mode not in {"basic", "hybrid", "oidc"}:
            raise ValueError("AUTH_MODE must be basic, hybrid, or oidc")
        if config.mode in {"hybrid", "oidc"} and oidc_verifier is None:
            raise ValueError(
                "OIDC configuration is required when AUTH_MODE is hybrid or oidc"
            )
        self.config = config
        self.oidc_verifier = oidc_verifier

    def authenticate(
        self,
        authorization: str | None,
        credentials: HTTPBasicCredentials | None,
    ) -> AuthIdentity:
        """Return a verified identity without falling back across OIDC failures."""

        if authorization and authorization.lower().startswith("bearer "):
            if self.config.mode == "basic" or self.oidc_verifier is None:
                raise AuthenticationError("bearer authentication is disabled")
            token = authorization[7:].strip()
            try:
                return self.oidc_verifier.verify(token)
            except OidcVerificationError as error:
                raise AuthenticationError("invalid bearer token") from error
        if self.config.mode == "oidc":
            raise AuthenticationError("OIDC bearer authentication required")
        if credentials is None or not self.config.password:
            raise AuthenticationError("operator authentication required")
        username_valid = secrets.compare_digest(
            credentials.username.encode("utf-8"),
            self.config.username.encode("utf-8"),
        )
        password_valid = secrets.compare_digest(
            credentials.password.encode("utf-8"),
            self.config.password.encode("utf-8"),
        )
        valid = username_valid and password_valid
        if not valid:
            raise AuthenticationError("operator authentication required")
        return AuthIdentity(
            scope=TenantScope("legacy:operator", "legacy", "legacy"),
            role="operator",
            method="basic",
        )


def oidc_verifier_from_environment(environ: dict[str, str]) -> OidcVerifier | None:
    """Build the Keyverse verifier only when OIDC settings are present."""

    if not environ.get("OIDC_ISSUER", "").strip():
        return None
    return OidcVerifier(OidcSettings.from_environment(environ))
