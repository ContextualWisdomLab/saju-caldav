"""Verified identity and tenant scope values used by the API boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantScope:
    """Identify the only tenant partition a request may read or mutate."""

    subject: str
    organization: str
    workspace: str


@dataclass(frozen=True, slots=True)
class AuthIdentity:
    """Represent an authenticated caller after the authentication boundary."""

    scope: TenantScope
    role: str
    method: str
