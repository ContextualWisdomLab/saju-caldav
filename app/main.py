"""FastAPI operator console and JSON API."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from pathlib import Path
from threading import Lock
from typing import Literal, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.auth import (
    AuthConfig,
    AuthenticationError,
    Authenticator,
    oidc_verifier_from_environment,
)
from app.birth import BirthInput, normalize_birth
from app.caldav import CalDavPublisher, SyncResult
from app.compatibility import (
    PAIR_RELATION_MODE,
    SHARED_RELATIONS_MODE,
    CompatibilityCandidate,
    generate_compatibility_candidates,
    normalize_compatibility_mode,
)
from app.events import MatchingWindow, generate_windows
from app.identity import AuthIdentity
from app.locations import list_birth_cities, resolve_birth_place
from app.rules import Rule, validate_rule
from app.saju import Chart, Pillar, calculate_chart
from app.store import Store


class Publisher(Protocol):
    """Define the narrow sync/delete contract used by the API orchestration."""

    def sync(
        self,
        calendar_id: str,
        slug: str,
        calendar_name: str,
        visibility: str,
        windows: list[MatchingWindow],
    ) -> SyncResult:  # pragma: no cover - protocol declaration
        """Publish matching windows to a remote calendar collection."""

        pass

    def delete(
        self, calendar_id: str, slug: str
    ) -> None:  # pragma: no cover - protocol declaration
        """Delete a remote calendar collection idempotently."""

        pass


class UnavailablePublisher:
    """Fail closed when CalDAV credentials are not configured."""

    def sync(
        self,
        calendar_id: str,
        slug: str,
        calendar_name: str,
        visibility: str,
        windows: list[MatchingWindow],
    ) -> SyncResult:
        """Reject publishing rather than silently claiming a remote sync."""

        del calendar_id, slug, calendar_name, visibility, windows
        raise RuntimeError("CalDAV publisher credentials are not configured")

    def delete(self, calendar_id: str, slug: str) -> None:
        """Reject remote deletion when the publisher is unavailable."""

        del calendar_id, slug
        raise RuntimeError("CalDAV publisher credentials are not configured")


class ProfileCreate(BaseModel):
    """Validate a user-supplied birth profile before chart calculation."""

    name: str = Field(min_length=1, max_length=80)
    birth_calendar: Literal["solar", "lunar"] = "solar"
    birth_year: int = Field(ge=1000, le=2050)
    birth_month: int = Field(ge=1, le=12)
    birth_day: int = Field(ge=1, le=31)
    birth_time: time | None = None
    birth_time_known: bool = True
    is_leap_month: bool = False
    gender: Literal["female", "male", "unspecified"] = "unspecified"
    birth_city: str | None = Field(default=None, max_length=80)
    timezone: str = Field(default="Asia/Seoul", min_length=1, max_length=80)
    time_mode: Literal["civil", "true_solar"] = "civil"
    longitude: float | None = Field(default=None, ge=-180, le=180)


class CalendarCreate(BaseModel):
    """Validate a single-profile matching calendar request."""

    profile_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    visibility: Literal["private", "confidential", "public"] = "private"
    rule: dict[str, object]


class DateRange(BaseModel):
    """Represent an optional inclusive local-date search range."""

    start_date: date | None = None
    end_date: date | None = None


class CompatibilityRequest(DateRange):
    """Request ranked matching windows for two stored profiles."""

    primary_profile_id: str = Field(min_length=1, max_length=80)
    secondary_profile_id: str = Field(min_length=1, max_length=80)
    mode: Literal["pair_relation_activation", "shared_branch_relations"] = (
        PAIR_RELATION_MODE
    )
    limit: int = Field(default=12, ge=1, le=96)
    include_overnight: bool = False


class CompatibilityCalendarCreate(BaseModel):
    """Validate creation settings for a two-person compatibility calendar."""

    primary_profile_id: str = Field(min_length=1, max_length=80)
    secondary_profile_id: str = Field(min_length=1, max_length=80)
    mode: Literal["pair_relation_activation", "shared_branch_relations"] = (
        PAIR_RELATION_MODE
    )
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    visibility: Literal["private", "confidential", "public"] = "private"
    limit: int = Field(default=36, ge=1, le=96)
    include_overnight: bool = False


def _now(zone: ZoneInfo) -> datetime:
    return datetime.now(zone)


def _compatibility_metadata(mode: str) -> tuple[str, str]:
    normalized = normalize_compatibility_mode(mode)
    if normalized == PAIR_RELATION_MODE:
        return "pair_relation_activation", normalized
    return "balanced_branch_harmony", SHARED_RELATIONS_MODE


def _stored_compatibility_mode(settings: dict[str, object]) -> str:
    # Calendars created before the direct pair mode keep their shared semantics.
    value = settings.get("mode", settings.get("method", SHARED_RELATIONS_MODE))
    try:
        return normalize_compatibility_mode(str(value))
    except ValueError:
        return SHARED_RELATIONS_MODE


def _stored_compatibility_request(
    calendar: dict[str, object],
    requested: DateRange,
) -> CompatibilityRequest:
    """Rebuild a stored compatibility rule for preview or synchronization."""

    settings = dict(calendar["rule"])
    return CompatibilityRequest(
        primary_profile_id=str(calendar["profile_id"]),
        secondary_profile_id=str(calendar["secondary_profile_id"]),
        mode=_stored_compatibility_mode(settings),
        start_date=requested.start_date,
        end_date=requested.end_date,
        limit=int(settings.get("limit", 36)),
        include_overnight=bool(settings.get("include_overnight", False)),
    )


def _resolve_date_range(
    requested: DateRange,
    zone: ZoneInfo,
    now: datetime | None = None,
) -> tuple[date, date]:
    current = now or _now(zone)
    start = requested.start_date or current.astimezone(zone).date()
    end = requested.end_date or start + timedelta(days=365)
    return start, end


def _pillar_json(pillar: Pillar) -> dict[str, str]:
    return {
        "stem": pillar.stem,
        "branch": pillar.branch,
        "ganzhi": pillar.ganzhi,
        "stem_element": pillar.stem_element,
        "branch_element": pillar.branch_element,
        "stem_korean": pillar.stem_korean,
        "stem_description": pillar.stem_description,
        "branch_korean": pillar.branch_korean,
        "branch_description": pillar.branch_description,
    }


def _chart_json(chart: Chart) -> dict[str, object]:
    return {
        "year": _pillar_json(chart.year),
        "month": _pillar_json(chart.month),
        "day": _pillar_json(chart.day),
        "hour": _pillar_json(chart.hour),
        "calculation_local": chart.calculation_local.isoformat(),
    }


def _profile_chart(profile: dict[str, object]) -> Chart:
    return calculate_chart(
        datetime.fromisoformat(str(profile["birth_local"])),
        str(profile["timezone"]),
        str(profile["time_mode"]),
        float(profile["longitude"]) if profile["longitude"] is not None else None,
    )


def _calendar_context(
    store: Store,
    calendar_id: str,
    identity: AuthIdentity | None = None,
) -> tuple[dict[str, object], dict[str, object], Rule, Chart]:
    scope = identity.scope if identity is not None else None
    calendar = (
        store.get_calendar(calendar_id)
        if identity is None
        else store.get_calendar(calendar_id, scope)
    )
    if calendar is None:
        raise HTTPException(status_code=404, detail="calendar not found")
    profile = (
        store.get_profile(str(calendar["profile_id"]))
        if identity is None
        else store.get_profile(str(calendar["profile_id"]), scope)
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    try:
        rule = validate_rule(dict(calendar["rule"]))
        natal = _profile_chart(profile)
    except ZoneInfoNotFoundError as error:
        raise HTTPException(
            status_code=422, detail="저장된 시간대 정보를 사용할 수 없습니다"
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return calendar, profile, rule, natal


def _compatibility_context(
    store: Store,
    primary_profile_id: str,
    secondary_profile_id: str,
    identity: AuthIdentity | None = None,
) -> tuple[dict[str, object], dict[str, object], Chart, Chart]:
    if primary_profile_id == secondary_profile_id:
        raise HTTPException(
            status_code=422,
            detail="서로 다른 두 사람의 프로필을 선택하세요",
        )
    scope = identity.scope if identity is not None else None
    if identity is None:
        primary = store.get_profile(primary_profile_id)
        secondary = store.get_profile(secondary_profile_id)
    else:
        primary = store.get_profile(primary_profile_id, scope)
        secondary = store.get_profile(secondary_profile_id, scope)
    if primary is None or secondary is None:
        raise HTTPException(status_code=404, detail="profile not found")
    try:
        return primary, secondary, _profile_chart(primary), _profile_chart(secondary)
    except ZoneInfoNotFoundError as error:
        raise HTTPException(
            status_code=422,
            detail="저장된 시간대 정보를 사용할 수 없습니다",
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _compatibility_candidates(
    store: Store,
    requested: CompatibilityRequest,
    identity: AuthIdentity | None = None,
) -> tuple[dict[str, object], dict[str, object], list[CompatibilityCandidate]]:
    primary, secondary, primary_chart, secondary_chart = _compatibility_context(
        store,
        requested.primary_profile_id,
        requested.secondary_profile_id,
        identity,
    )
    try:
        timezone = str(primary["timezone"])
        zone = ZoneInfo(timezone)
        current = _now(zone)
        start_date, end_date = _resolve_date_range(requested, zone, current)
        candidates = generate_compatibility_candidates(
            primary_chart,
            secondary_chart,
            str(primary["name"]),
            str(secondary["name"]),
            start_date,
            end_date,
            timezone,
            str(primary["time_mode"]),
            float(primary["longitude"]) if primary["longitude"] is not None else None,
            requested.limit,
            current if requested.start_date is None else None,
            requested.include_overnight,
            requested.mode,
        )
    except ZoneInfoNotFoundError as error:
        raise HTTPException(
            status_code=422,
            detail="저장된 시간대 정보를 사용할 수 없습니다",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return primary, secondary, candidates


def _candidate_json(candidate: CompatibilityCandidate) -> dict[str, object]:
    window = candidate.window
    return {
        "start": window.start.isoformat(),
        "end": window.end.isoformat(),
        "score": candidate.score,
        "primary_score": candidate.primary_score,
        "secondary_score": candidate.secondary_score,
        "personal_score": candidate.personal_score,
        "relationship_score": candidate.relationship_score,
        "label": candidate.label,
        "reasons": list(candidate.reasons),
        "day_pillar": window.chart.day.ganzhi,
        "hour_pillar": window.chart.hour.ganzhi,
        "day_branch_korean": window.chart.day.branch_korean,
        "hour_branch_korean": window.chart.hour.branch_korean,
    }


def _windows(
    store: Store,
    calendar_id: str,
    requested: DateRange,
    identity: AuthIdentity | None = None,
) -> tuple[dict[str, object], list[MatchingWindow]]:
    scope = identity.scope if identity is not None else None
    stored_calendar = (
        store.get_calendar(calendar_id)
        if identity is None
        else store.get_calendar(calendar_id, scope)
    )
    if stored_calendar is None:
        raise HTTPException(status_code=404, detail="calendar not found")
    if stored_calendar.get("kind") == "compatibility":
        requested_pair = _stored_compatibility_request(stored_calendar, requested)
        _, _, candidates = _compatibility_candidates(store, requested_pair, identity)
        return stored_calendar, [candidate.window for candidate in candidates]

    calendar, profile, rule, natal = _calendar_context(store, calendar_id, identity)
    try:
        timezone = str(profile["timezone"])
        zone = ZoneInfo(timezone)
        current = _now(zone)
        start_date, end_date = _resolve_date_range(requested, zone, current)
        windows = generate_windows(
            rule,
            natal,
            start_date,
            end_date,
            timezone,
            str(profile["time_mode"]),
            float(profile["longitude"]) if profile["longitude"] is not None else None,
        )
        if requested.start_date is None:
            windows = [window for window in windows if window.end > current]
    except ZoneInfoNotFoundError as error:
        raise HTTPException(
            status_code=422, detail="저장된 시간대 정보를 사용할 수 없습니다"
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return calendar, windows


def _publisher_from_environment() -> Publisher:
    base_url = os.environ.get("CALDAV_BASE_URL", "")
    username = os.environ.get("CALDAV_USERNAME", "")
    password = os.environ.get("CALDAV_PASSWORD", "")
    if not all((base_url, username, password)):
        return UnavailablePublisher()
    return CalDavPublisher(base_url, username, password)


def create_app(
    *,
    store: Store | None = None,
    username: str | None = None,
    password: str | None = None,
    publisher: Publisher | None = None,
    static_dir: Path | None = None,
    auth_mode: str | None = None,
    oidc_verifier=None,
) -> FastAPI:
    """Build the authenticated FastAPI application and its persistence adapters."""

    metadata_store = store or Store(os.environ.get("SAJU_DB_PATH", "data/saju.db"))
    metadata_store.initialize()
    operator_username = (
        username if username is not None else os.environ.get("APP_USERNAME", "operator")
    )
    operator_password = password if password is not None else os.environ.get("APP_PASSWORD", "")
    selected_auth_mode = (auth_mode or os.environ.get("AUTH_MODE", "basic")).strip().lower()
    configured_oidc_verifier = oidc_verifier
    if configured_oidc_verifier is None and selected_auth_mode in {"hybrid", "oidc"}:
        configured_oidc_verifier = oidc_verifier_from_environment(dict(os.environ))
    authenticator = Authenticator(
        AuthConfig(selected_auth_mode, operator_username, operator_password),
        oidc_verifier=configured_oidc_verifier,
    )
    caldav_publisher = publisher or _publisher_from_environment()
    assets = static_dir or Path(__file__).with_name("static")
    # ponytail: process-local serialization fits the single-worker deployment;
    # use a distributed lock before adding Uvicorn workers.
    calendar_operation_lock = Lock()

    application = FastAPI(
        title="Saju CalDAV",
        version="0.2.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    security = HTTPBasic(auto_error=False)

    @application.exception_handler(sqlite3.OperationalError)
    def handle_database_operational_error(
        _request: Request,
        error: sqlite3.OperationalError,
    ) -> JSONResponse:
        """Turn transient SQLite lock contention into a retryable 503 response."""

        if (getattr(error, "sqlite_errorcode", 0) & 0xFF) not in {
            sqlite3.SQLITE_BUSY,
            sqlite3.SQLITE_LOCKED,
        }:
            raise error
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "database is busy; retry shortly"},
            headers={"Retry-After": "1"},
        )

    def serialize_calendar_operation() -> Iterator[None]:
        """Serialize mutating calendar operations for the single-worker service."""

        with calendar_operation_lock:
            yield

    serialized_calendar_operation = Depends(serialize_calendar_operation)

    def delete_published_collection(calendar: dict[str, object]) -> None:
        """Erase a remote CalDAV collection before deleting local metadata."""

        try:
            caldav_publisher.delete(str(calendar["id"]), str(calendar["slug"]))
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    def require_identity(
        request: Request,
        credentials: HTTPBasicCredentials | None = Depends(security),  # noqa: B008
    ) -> AuthIdentity:
        """Authenticate Basic migration callers or a verified Keyverse bearer."""

        try:
            return authenticator.authenticate(request.headers.get("authorization"), credentials)
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
                headers={
                    "WWW-Authenticate": (
                        "Bearer" if selected_auth_mode == "oidc" else "Basic"
                    )
                },
            ) from error

    def store_scope_args(identity: AuthIdentity) -> tuple[object, ...]:
        """Keep the legacy Basic mode call shape while scoping Keyverse requests."""

        if selected_auth_mode == "basic":
            return ()
        return (identity.scope,)

    def store_scope_kwargs(identity: AuthIdentity) -> dict[str, object]:
        """Return a scope keyword only for tenant-aware authentication modes."""

        if selected_auth_mode == "basic":
            return {}
        return {"scope": identity.scope}

    def scoped_identity(identity: AuthIdentity) -> AuthIdentity | None:
        """Return the tenant identity only when Keyverse authorization is active."""

        return None if selected_auth_mode == "basic" else identity

    api = APIRouter(prefix="/api")

    @application.get("/health")
    def health() -> dict[str, str]:
        """Return the liveness response without exposing application metadata."""

        return {"status": "ok"}

    @api.get("/profiles")
    def list_profiles(
        identity: AuthIdentity = Depends(require_identity),  # noqa: B008
    ) -> list[dict[str, object]]:
        """List stored birth profiles for the authenticated operator."""

        return metadata_store.list_profiles(*store_scope_args(identity))

    @api.get("/locations")
    def list_locations(
        identity: AuthIdentity = Depends(require_identity),  # noqa: B008
    ) -> list[dict[str, str]]:
        """List client-safe birth-city presets without exposing coordinates."""

        del identity
        return list_birth_cities()

    @api.post("/profiles", status_code=status.HTTP_201_CREATED)
    def create_profile(
        requested: ProfileCreate,
        identity: AuthIdentity = Depends(require_identity),  # noqa: B008
    ) -> dict[str, object]:
        """Normalize birth input, calculate a chart, and persist the profile."""

        if requested.birth_time_known and requested.birth_time is None:
            raise HTTPException(
                status_code=422,
                detail="태어난 시각을 입력하거나 ‘태어난 시각을 모릅니다’를 선택하세요",
            )
        if not requested.birth_time_known and requested.time_mode == "true_solar":
            raise HTTPException(
                status_code=422,
                detail=(
                    "태어난 시각을 모르면 진태양시를 적용할 수 없습니다. "
                    "공식 표준시를 선택하세요"
                ),
            )
        calculation_time = (
            requested.birth_time if requested.birth_time_known else time(12, 0)
        )
        try:
            birth_local = normalize_birth(
                BirthInput(
                    calendar=requested.birth_calendar,
                    year=requested.birth_year,
                    month=requested.birth_month,
                    day=requested.birth_day,
                    at=calculation_time,
                    is_leap_month=requested.is_leap_month,
                )
            )
            place = resolve_birth_place(
                requested.birth_city,
                requested.timezone,
                requested.time_mode,
                requested.longitude,
            )
            chart = calculate_chart(
                birth_local,
                place.timezone,
                requested.time_mode,
                place.longitude,
            )
        except ZoneInfoNotFoundError as error:
            raise HTTPException(
                status_code=422, detail="입력한 시간대 정보를 사용할 수 없습니다"
            ) from error
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        chart_json = _chart_json(chart)
        if not requested.birth_time_known:
            chart_json["hour"] = None
        return metadata_store.create_profile(
            name=requested.name,
            birth_calendar=requested.birth_calendar,
            birth_year=requested.birth_year,
            birth_month=requested.birth_month,
            birth_day=requested.birth_day,
            birth_time=(
                requested.birth_time.isoformat()
                if requested.birth_time_known and requested.birth_time is not None
                else None
            ),
            birth_time_known=requested.birth_time_known,
            is_leap_month=requested.is_leap_month,
            birth_local=birth_local,
            birth_city=place.city_id,
            birth_city_name=place.city_name,
            gender=requested.gender,
            timezone=place.timezone,
            time_mode=requested.time_mode,
            longitude=place.longitude,
            chart=chart_json,
            owner_subject=identity.scope.subject,
            tenant_organization=identity.scope.organization,
            tenant_workspace=identity.scope.workspace,
        )

    @api.delete(
        "/profiles/{profile_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[serialized_calendar_operation],
    )
    def delete_profile(
        profile_id: str,
        identity: AuthIdentity = Depends(require_identity),  # noqa: B008
    ) -> None:
        """Erase linked remote collections before deleting a birth profile locally."""

        scope_args = store_scope_args(identity)
        if metadata_store.get_profile(profile_id, *scope_args) is None:
            raise HTTPException(status_code=404, detail="profile not found")
        for calendar in metadata_store.list_calendars_for_profile(profile_id, *scope_args):
            delete_published_collection(calendar)
        if not metadata_store.delete_profile(profile_id, *scope_args):
            raise HTTPException(status_code=404, detail="profile not found")

    @api.get("/calendars")
    def list_calendars(
        profile_id: str | None = None,
        identity: AuthIdentity = Depends(require_identity),  # noqa: B008
    ) -> list[dict[str, object]]:
        """List calendars, optionally restricted to their primary profile."""

        return metadata_store.list_calendars(profile_id, *store_scope_args(identity))

    @api.post(
        "/calendars",
        status_code=status.HTTP_201_CREATED,
        dependencies=[serialized_calendar_operation],
    )
    def create_calendar(
        requested: CalendarCreate,
        identity: AuthIdentity = Depends(require_identity),  # noqa: B008
    ) -> dict[str, object]:
        """Validate and persist a rule-based calendar definition."""

        scope_args = store_scope_args(identity)
        profile = metadata_store.get_profile(requested.profile_id, *scope_args)
        if profile is None:
            raise HTTPException(status_code=404, detail="profile not found")
        try:
            rule = validate_rule(requested.rule)
            if not bool(profile["birth_time_known"]) and any(
                predicate.source == "natal" and predicate.value.startswith("hour.")
                for predicate in rule.predicates
            ):
                raise ValueError(
                    "태어난 시각을 모르는 프로필은 출생 시주 조건을 사용할 수 없습니다"
                )
            return metadata_store.create_calendar(
                profile_id=requested.profile_id,
                name=requested.name,
                slug=requested.slug,
                visibility=requested.visibility,
                rule=requested.rule,
                kind="rule",
                **store_scope_kwargs(identity),
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except PermissionError as error:
            raise HTTPException(status_code=404, detail="profile not found") from error
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="calendar slug already exists") from error

    @api.delete(
        "/calendars/{calendar_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[serialized_calendar_operation],
    )
    def delete_calendar(
        calendar_id: str,
        identity: AuthIdentity = Depends(require_identity),  # noqa: B008
    ) -> None:
        """Delete the remote collection first, then remove local calendar metadata."""

        scope_args = store_scope_args(identity)
        calendar = metadata_store.get_calendar(calendar_id, *scope_args)
        if calendar is None:
            raise HTTPException(status_code=404, detail="calendar not found")
        delete_published_collection(calendar)
        if not metadata_store.delete_calendar(calendar_id, *scope_args):
            raise HTTPException(status_code=404, detail="calendar not found")

    @api.post("/calendars/{calendar_id}/preview")
    def preview_calendar(
        calendar_id: str,
        requested: DateRange,
        identity: AuthIdentity = Depends(require_identity),  # noqa: B008
    ) -> dict[str, object]:
        """Preview current rule or compatibility matches without publishing them."""

        route_identity = scoped_identity(identity)
        calendar = metadata_store.get_calendar(calendar_id, *store_scope_args(identity))
        if calendar is None:
            raise HTTPException(status_code=404, detail="calendar not found")
        if calendar.get("kind") == "compatibility":
            compatibility_request = _stored_compatibility_request(calendar, requested)
            primary, secondary, candidates = _compatibility_candidates(
                metadata_store,
                compatibility_request,
                route_identity,
            )
            method, interpretation = _compatibility_metadata(compatibility_request.mode)
            return {
                "count": len(candidates),
                "primary_name": primary["name"],
                "secondary_name": secondary["name"],
                "method": method,
                "interpretation": interpretation,
                "gender_policy": "record_only",
                "mode": interpretation,
                "include_overnight": compatibility_request.include_overnight,
                "events": [_candidate_json(candidate) for candidate in candidates],
            }
        _, windows = _windows(metadata_store, calendar_id, requested, route_identity)
        return {
            "count": len(windows),
            "events": [
                {
                    "start": window.start.isoformat(),
                    "end": window.end.isoformat(),
                    "day_pillar": window.chart.day.ganzhi,
                    "hour_pillar": window.chart.hour.ganzhi,
                    "day_branch_korean": window.chart.day.branch_korean,
                    "hour_stem_korean": window.chart.hour.stem_korean,
                }
                for window in windows
            ],
        }

    @api.post("/compatibility/preview")
    def preview_compatibility(
        requested: CompatibilityRequest,
        identity: AuthIdentity = Depends(require_identity),  # noqa: B008
    ) -> dict[str, object]:
        """Return ranked, explainable compatibility candidates for two profiles."""

        primary, secondary, candidates = _compatibility_candidates(
            metadata_store,
            requested,
            scoped_identity(identity),
        )
        method, interpretation = _compatibility_metadata(requested.mode)
        return {
            "count": len(candidates),
            "primary_name": primary["name"],
            "secondary_name": secondary["name"],
            "method": method,
            "interpretation": interpretation,
            "gender_policy": "record_only",
            "mode": interpretation,
            "include_overnight": requested.include_overnight,
            "events": [_candidate_json(candidate) for candidate in candidates],
        }

    @api.post(
        "/compatibility/calendars",
        status_code=status.HTTP_201_CREATED,
        dependencies=[serialized_calendar_operation],
    )
    def create_compatibility_calendar(
        requested: CompatibilityCalendarCreate,
        identity: AuthIdentity = Depends(require_identity),  # noqa: B008
    ) -> dict[str, object]:
        """Persist a two-profile compatibility calendar definition."""

        route_identity = scoped_identity(identity)
        _compatibility_context(
            metadata_store,
            requested.primary_profile_id,
            requested.secondary_profile_id,
            route_identity,
        )
        try:
            return metadata_store.create_calendar(
                profile_id=requested.primary_profile_id,
                secondary_profile_id=requested.secondary_profile_id,
                name=requested.name,
                slug=requested.slug,
                visibility=requested.visibility,
                kind="compatibility",
                rule={
                    "mode": requested.mode,
                    "method": _compatibility_metadata(requested.mode)[0],
                    "limit": requested.limit,
                    "include_overnight": requested.include_overnight,
                },
                **store_scope_kwargs(identity),
            )
        except PermissionError as error:
            raise HTTPException(status_code=404, detail="profile not found") from error
        except sqlite3.IntegrityError as error:
            raise HTTPException(
                status_code=409,
                detail="calendar slug already exists",
            ) from error

    @api.post(
        "/calendars/{calendar_id}/sync",
        dependencies=[serialized_calendar_operation],
    )
    def sync_calendar(
        calendar_id: str,
        requested: DateRange,
        identity: AuthIdentity = Depends(require_identity),  # noqa: B008
    ) -> dict[str, object]:
        """Generate current matches, publish them, and record the sync marker."""

        route_identity = scoped_identity(identity)
        calendar, windows = _windows(metadata_store, calendar_id, requested, route_identity)
        try:
            result = caldav_publisher.sync(
                calendar_id,
                str(calendar["slug"]),
                str(calendar["name"]),
                str(calendar["visibility"]),
                windows,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        metadata_store.mark_synced(calendar_id, *store_scope_args(identity))
        return {
            "collection_url": result.collection_url,
            "event_count": result.event_count,
        }

    application.include_router(api)

    if assets.exists():
        application.mount("/static", StaticFiles(directory=assets), name="static")

    @application.get("/")
    def index(identity: AuthIdentity = Depends(require_identity)):  # noqa: B008
        """Serve the Korean operator console when static assets are available."""

        del identity
        index_file = assets / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return PlainTextResponse("Saju CalDAV operator console")

    return application


app = create_app()
