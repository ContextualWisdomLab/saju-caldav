"""FastAPI operator console and JSON API."""

from __future__ import annotations

import os
import secrets
import sqlite3
from datetime import date, datetime, time
from pathlib import Path
from typing import Literal, Protocol

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.birth import BirthInput, normalize_birth
from app.caldav import CalDavPublisher, SyncResult
from app.events import MatchingWindow, generate_windows
from app.rules import Rule, validate_rule
from app.saju import Chart, Pillar, calculate_chart
from app.store import Store


class Publisher(Protocol):
    def sync(
        self,
        calendar_id: str,
        slug: str,
        calendar_name: str,
        windows: list[MatchingWindow],
    ) -> SyncResult: ...


class UnavailablePublisher:
    def sync(
        self,
        calendar_id: str,
        slug: str,
        calendar_name: str,
        windows: list[MatchingWindow],
    ) -> SyncResult:
        del calendar_id, slug, calendar_name, windows
        raise RuntimeError("CalDAV publisher credentials are not configured")


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    birth_calendar: Literal["solar", "lunar"] = "solar"
    birth_year: int = Field(ge=1000, le=2050)
    birth_month: int = Field(ge=1, le=12)
    birth_day: int = Field(ge=1, le=31)
    birth_time: time
    is_leap_month: bool = False
    gender: Literal["female", "male", "unspecified"] = "unspecified"
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
    rule: dict[str, object]


class DateRange(BaseModel):
    start_date: date
    end_date: date


def _pillar_json(pillar: Pillar) -> dict[str, str]:
    return {
        "stem": pillar.stem,
        "branch": pillar.branch,
        "ganzhi": pillar.ganzhi,
        "stem_element": pillar.stem_element,
        "branch_element": pillar.branch_element,
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
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return calendar, profile, rule, natal


def _windows(
    store: Store,
    calendar_id: str,
    requested: DateRange,
) -> tuple[dict[str, object], list[MatchingWindow]]:
    calendar, profile, rule, natal = _calendar_context(store, calendar_id)
    try:
        windows = generate_windows(
            rule,
            natal,
            requested.start_date,
            requested.end_date,
            str(profile["timezone"]),
            str(profile["time_mode"]),
            float(profile["longitude"]) if profile["longitude"] is not None else None,
        )
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

    application = FastAPI(
        title="Saju CalDAV",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    security = HTTPBasic(auto_error=False)

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

    @api.post("/profiles", status_code=status.HTTP_201_CREATED)
    def create_profile(requested: ProfileCreate) -> dict[str, object]:
        try:
            birth_local = normalize_birth(
                BirthInput(
                    calendar=requested.birth_calendar,
                    year=requested.birth_year,
                    month=requested.birth_month,
                    day=requested.birth_day,
                    at=requested.birth_time,
                    is_leap_month=requested.is_leap_month,
                )
            )
            chart = calculate_chart(
                birth_local,
                requested.timezone,
                requested.time_mode,
                requested.longitude,
            )
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return metadata_store.create_profile(
            name=requested.name,
            birth_calendar=requested.birth_calendar,
            birth_year=requested.birth_year,
            birth_month=requested.birth_month,
            birth_day=requested.birth_day,
            birth_time=requested.birth_time.isoformat(),
            is_leap_month=requested.is_leap_month,
            birth_local=birth_local,
            gender=requested.gender,
            timezone=requested.timezone,
            time_mode=requested.time_mode,
            longitude=requested.longitude,
            chart=_chart_json(chart),
        )

    @api.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_profile(profile_id: str) -> None:
        if not metadata_store.delete_profile(profile_id):
            raise HTTPException(status_code=404, detail="profile not found")

    @api.get("/calendars")
    def list_calendars(profile_id: str | None = None) -> list[dict[str, object]]:
        return metadata_store.list_calendars(profile_id)

    @api.post("/calendars", status_code=status.HTTP_201_CREATED)
    def create_calendar(requested: CalendarCreate) -> dict[str, object]:
        if metadata_store.get_profile(requested.profile_id) is None:
            raise HTTPException(status_code=404, detail="profile not found")
        try:
            validate_rule(requested.rule)
            return metadata_store.create_calendar(
                profile_id=requested.profile_id,
                name=requested.name,
                slug=requested.slug,
                rule=requested.rule,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="calendar slug already exists") from error

    @api.delete("/calendars/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_calendar(calendar_id: str) -> None:
        if not metadata_store.delete_calendar(calendar_id):
            raise HTTPException(status_code=404, detail="calendar not found")

    @api.post("/calendars/{calendar_id}/preview")
    def preview_calendar(calendar_id: str, requested: DateRange) -> dict[str, object]:
        _, windows = _windows(metadata_store, calendar_id, requested)
        return {
            "count": len(windows),
            "events": [
                {
                    "start": window.start.isoformat(),
                    "end": window.end.isoformat(),
                    "day_pillar": window.chart.day.ganzhi,
                    "hour_pillar": window.chart.hour.ganzhi,
                }
                for window in windows
            ],
        }

    @api.post("/calendars/{calendar_id}/sync")
    def sync_calendar(calendar_id: str, requested: DateRange) -> dict[str, object]:
        calendar, windows = _windows(metadata_store, calendar_id, requested)
        try:
            result = caldav_publisher.sync(
                calendar_id,
                str(calendar["slug"]),
                str(calendar["name"]),
                windows,
            )
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
