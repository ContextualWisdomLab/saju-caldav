"""FastAPI operator console and JSON API."""

from __future__ import annotations

import os
import secrets
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

from app.birth import BirthInput, normalize_birth
from app.caldav import CalDavPublisher, SyncResult
from app.compatibility import (
    CompatibilityCandidate,
    generate_compatibility_candidates,
)
from app.events import MatchingWindow, generate_windows
from app.locations import list_birth_cities, resolve_birth_place
from app.rules import Rule, validate_rule
from app.saju import Chart, Pillar, calculate_chart
from app.store import Store


class Publisher(Protocol):
    def sync(
        self,
        calendar_id: str,
        slug: str,
        calendar_name: str,
        visibility: str,
        windows: list[MatchingWindow],
    ) -> SyncResult:  # pragma: no cover - protocol declaration
        pass

    def delete(
        self, calendar_id: str, slug: str
    ) -> None:  # pragma: no cover - protocol declaration
        pass


class UnavailablePublisher:
    def sync(
        self,
        calendar_id: str,
        slug: str,
        calendar_name: str,
        visibility: str,
        windows: list[MatchingWindow],
    ) -> SyncResult:
        del calendar_id, slug, calendar_name, visibility, windows
        raise RuntimeError("CalDAV publisher credentials are not configured")

    def delete(self, calendar_id: str, slug: str) -> None:
        del calendar_id, slug
        raise RuntimeError("CalDAV publisher credentials are not configured")


class ProfileCreate(BaseModel):
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
    start_date: date | None = None
    end_date: date | None = None


class CompatibilityRequest(DateRange):
    primary_profile_id: str = Field(min_length=1, max_length=80)
    secondary_profile_id: str = Field(min_length=1, max_length=80)
    limit: int = Field(default=12, ge=1, le=96)
    include_overnight: bool = False


class CompatibilityCalendarCreate(BaseModel):
    primary_profile_id: str = Field(min_length=1, max_length=80)
    secondary_profile_id: str = Field(min_length=1, max_length=80)
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
) -> tuple[dict[str, object], dict[str, object], Rule, Chart]:
    calendar = store.get_calendar(calendar_id)
    if calendar is None:
        raise HTTPException(status_code=404, detail="calendar not found")
    profile = store.get_profile(str(calendar["profile_id"]))
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
) -> tuple[dict[str, object], dict[str, object], Chart, Chart]:
    if primary_profile_id == secondary_profile_id:
        raise HTTPException(
            status_code=422,
            detail="서로 다른 두 사람의 프로필을 선택하세요",
        )
    primary = store.get_profile(primary_profile_id)
    secondary = store.get_profile(secondary_profile_id)
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
) -> tuple[dict[str, object], dict[str, object], list[CompatibilityCandidate]]:
    primary, secondary, primary_chart, secondary_chart = _compatibility_context(
        store,
        requested.primary_profile_id,
        requested.secondary_profile_id,
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
) -> tuple[dict[str, object], list[MatchingWindow]]:
    stored_calendar = store.get_calendar(calendar_id)
    if stored_calendar is None:
        raise HTTPException(status_code=404, detail="calendar not found")
    if stored_calendar.get("kind") == "compatibility":
        settings = dict(stored_calendar["rule"])
        requested_pair = CompatibilityRequest(
            primary_profile_id=str(stored_calendar["profile_id"]),
            secondary_profile_id=str(stored_calendar["secondary_profile_id"]),
            start_date=requested.start_date,
            end_date=requested.end_date,
            limit=int(settings.get("limit", 36)),
            include_overnight=bool(settings.get("include_overnight", False)),
        )
        _, _, candidates = _compatibility_candidates(store, requested_pair)
        return stored_calendar, [candidate.window for candidate in candidates]

    calendar, profile, rule, natal = _calendar_context(store, calendar_id)
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
) -> FastAPI:
    metadata_store = store or Store(os.environ.get("SAJU_DB_PATH", "data/saju.db"))
    metadata_store.initialize()
    operator_username = (
        username if username is not None else os.environ.get("APP_USERNAME", "operator")
    )
    operator_password = password if password is not None else os.environ.get("APP_PASSWORD", "")
    caldav_publisher = publisher or _publisher_from_environment()
    assets = static_dir or Path(__file__).with_name("static")
    # ponytail: process-local serialization fits the single-worker deployment;
    # use a distributed lock before adding Uvicorn workers.
    calendar_operation_lock = Lock()

    application = FastAPI(
        title="Saju CalDAV",
        version="0.1.0",
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
        with calendar_operation_lock:
            yield

    serialized_calendar_operation = Depends(serialize_calendar_operation)

    def delete_published_collection(calendar: dict[str, object]) -> None:
        """Erase a remote CalDAV collection before deleting local metadata."""

        if not calendar.get("last_synced_at"):
            return
        try:
            caldav_publisher.delete(str(calendar["id"]), str(calendar["slug"]))
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    def require_operator(
        credentials: HTTPBasicCredentials | None = Depends(security),  # noqa: B008
    ) -> None:
        valid = bool(operator_password and credentials)
        if credentials is not None:
            valid = valid and secrets.compare_digest(
                credentials.username.encode(), operator_username.encode()
            )
            valid = valid and secrets.compare_digest(
                credentials.password.encode(), operator_password.encode()
            )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="operator authentication required",
                headers={"WWW-Authenticate": "Basic"},
            )

    api = APIRouter(prefix="/api", dependencies=[Depends(require_operator)])

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/profiles")
    def list_profiles() -> list[dict[str, object]]:
        return metadata_store.list_profiles()

    @api.get("/locations")
    def list_locations() -> list[dict[str, str]]:
        return list_birth_cities()

    @api.post("/profiles", status_code=status.HTTP_201_CREATED)
    def create_profile(requested: ProfileCreate) -> dict[str, object]:
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
        )

    @api.delete(
        "/profiles/{profile_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[serialized_calendar_operation],
    )
    def delete_profile(profile_id: str) -> None:
        if metadata_store.get_profile(profile_id) is None:
            raise HTTPException(status_code=404, detail="profile not found")
        for calendar in metadata_store.list_calendars_for_profile(profile_id):
            delete_published_collection(calendar)
        if not metadata_store.delete_profile(profile_id):
            raise HTTPException(status_code=404, detail="profile not found")

    @api.get("/calendars")
    def list_calendars(profile_id: str | None = None) -> list[dict[str, object]]:
        return metadata_store.list_calendars(profile_id)

    @api.post(
        "/calendars",
        status_code=status.HTTP_201_CREATED,
        dependencies=[serialized_calendar_operation],
    )
    def create_calendar(requested: CalendarCreate) -> dict[str, object]:
        profile = metadata_store.get_profile(requested.profile_id)
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
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="calendar slug already exists") from error

    @api.delete(
        "/calendars/{calendar_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[serialized_calendar_operation],
    )
    def delete_calendar(calendar_id: str) -> None:
        calendar = metadata_store.get_calendar(calendar_id)
        if calendar is None:
            raise HTTPException(status_code=404, detail="calendar not found")
        delete_published_collection(calendar)
        if not metadata_store.delete_calendar(calendar_id):
            raise HTTPException(status_code=404, detail="calendar not found")

    @api.post("/calendars/{calendar_id}/preview")
    def preview_calendar(calendar_id: str, requested: DateRange) -> dict[str, object]:
        calendar = metadata_store.get_calendar(calendar_id)
        if calendar is None:
            raise HTTPException(status_code=404, detail="calendar not found")
        if calendar.get("kind") == "compatibility":
            settings = dict(calendar["rule"])
            compatibility_request = CompatibilityRequest(
                primary_profile_id=str(calendar["profile_id"]),
                secondary_profile_id=str(calendar["secondary_profile_id"]),
                start_date=requested.start_date,
                end_date=requested.end_date,
                limit=int(settings.get("limit", 36)),
                include_overnight=bool(settings.get("include_overnight", False)),
            )
            primary, secondary, candidates = _compatibility_candidates(
                metadata_store,
                compatibility_request,
            )
            return {
                "count": len(candidates),
                "primary_name": primary["name"],
                "secondary_name": secondary["name"],
                "method": "balanced_branch_harmony",
                "include_overnight": compatibility_request.include_overnight,
                "events": [_candidate_json(candidate) for candidate in candidates],
            }
        _, windows = _windows(metadata_store, calendar_id, requested)
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
    def preview_compatibility(requested: CompatibilityRequest) -> dict[str, object]:
        primary, secondary, candidates = _compatibility_candidates(
            metadata_store,
            requested,
        )
        return {
            "count": len(candidates),
            "primary_name": primary["name"],
            "secondary_name": secondary["name"],
            "method": "balanced_branch_harmony",
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
    ) -> dict[str, object]:
        _compatibility_context(
            metadata_store,
            requested.primary_profile_id,
            requested.secondary_profile_id,
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
                    "mode": "balanced_branch_harmony",
                    "limit": requested.limit,
                    "include_overnight": requested.include_overnight,
                },
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(
                status_code=409,
                detail="calendar slug already exists",
            ) from error

    @api.post(
        "/calendars/{calendar_id}/sync",
        dependencies=[serialized_calendar_operation],
    )
    def sync_calendar(calendar_id: str, requested: DateRange) -> dict[str, object]:
        calendar, windows = _windows(metadata_store, calendar_id, requested)
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
        metadata_store.mark_synced(calendar_id)
        return {
            "collection_url": result.collection_url,
            "event_count": result.event_count,
        }

    application.include_router(api)

    if assets.exists():
        application.mount("/static", StaticFiles(directory=assets), name="static")

    @application.get("/", dependencies=[Depends(require_operator)])
    def index():
        index_file = assets / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return PlainTextResponse("Saju CalDAV operator console")

    return application


app = create_app()
