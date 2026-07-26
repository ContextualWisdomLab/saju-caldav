"""Exercise the live API, matching engine, CalDAV publish, and readback path."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from urllib.parse import quote, urljoin
from xml.etree import ElementTree

import httpx

HTTP_TIMEOUT_SECONDS = float(os.environ.get("SMOKE_HTTP_TIMEOUT_SECONDS", "120"))


def request(
    method: str,
    url: str,
    username: str,
    password: str,
    body: bytes | None = None,
    content_type: str = "application/json",
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    response = httpx.request(
        method,
        url,
        content=body,
        headers={
            "Content-Type": content_type,
            **(headers or {}),
        },
        auth=(username, password),
        timeout=HTTP_TIMEOUT_SECONDS,
        follow_redirects=False,
    )
    return response.status_code, response.content


def api_json(
    method: str,
    base_url: str,
    path: str,
    username: str,
    password: str,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object] | list[object] | None]:
    body = json.dumps(payload).encode() if payload is not None else None
    status, raw = request(method, f"{base_url.rstrip('/')}{path}", username, password, body)
    return status, json.loads(raw) if raw else None


def assert_caldav_collection(
    caldav_base: str,
    collection_url: str,
    username: str,
    password: str,
    expected_class: bytes,
) -> None:
    status, listing = request(
        "PROPFIND",
        collection_url,
        username,
        password,
        (
            b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:">'
            b"<d:prop><d:getetag/></d:prop></d:propfind>"
        ),
        "application/xml",
        {"Depth": "1"},
    )
    assert status == 207 and b".ics" in listing, (status, listing[:500])
    root = ElementTree.fromstring(listing)
    href = next(
        element.text
        for element in root.iter()
        if element.tag.endswith("href")
        and element.text
        and element.text.endswith(".ics")
    )
    status, event = request(
        "GET",
        urljoin(caldav_base.rstrip("/") + "/", href.lstrip("/")),
        username,
        password,
    )
    assert status == 200, (status, event[:500])
    assert b"CLASS:" + expected_class in event
    assert b"X-SAJU" not in event


def main() -> None:
    app_base = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8000")
    app_user = os.environ["APP_USERNAME"]
    app_password = os.environ["APP_PASSWORD"]
    caldav_base = os.environ.get("CALDAV_PUBLIC_URL", "http://127.0.0.1:5232")
    caldav_user = os.environ["CALDAV_USERNAME"]
    caldav_password = os.environ["CALDAV_PASSWORD"]
    visibility = os.environ.get("SMOKE_VISIBILITY", "private")
    visibility_classes = {
        "private": b"PRIVATE",
        "confidential": b"CONFIDENTIAL",
        "public": b"PUBLIC",
    }
    if visibility not in visibility_classes:
        raise ValueError("SMOKE_VISIBILITY must be private, confidential, or public")
    suffix = f"{int(time.time())}-{os.getpid()}"
    profile_id = ""
    secondary_profile_id = ""
    collection_url = f"{caldav_base.rstrip('/')}/{quote(caldav_user, safe='')}/smoke-{suffix}/"
    pair_collection_url = (
        f"{caldav_base.rstrip('/')}/{quote(caldav_user, safe='')}/pair-smoke-{suffix}/"
    )
    private_birth = os.environ.get("PRIVATE_BIRTH_LOCAL")
    birth_local = (
        datetime.fromisoformat(private_birth)
        if private_birth
        else datetime(2000, 1, 1, 12, 15)
    )
    if birth_local.tzinfo is not None:
        raise ValueError("birth input must be a local wall time without an offset")

    try:
        status, profile = api_json(
            "POST",
            app_base,
            "/api/profiles",
            app_user,
            app_password,
            {
                "name": f"smoke-{suffix}",
                "birth_calendar": "solar",
                "birth_year": birth_local.year,
                "birth_month": birth_local.month,
                "birth_day": birth_local.day,
                "birth_time": birth_local.time().isoformat(),
                "is_leap_month": False,
                "gender": "unspecified",
                "birth_city": "seoul",
                "timezone": os.environ.get("PRIVATE_TIMEZONE", "Asia/Seoul"),
                "time_mode": "civil",
                "longitude": None,
            },
        )
        assert status == 201 and isinstance(profile, dict), (status, profile)
        profile_id = str(profile["id"])
        chart = profile["chart"]
        assert isinstance(chart, dict)
        day = chart["day"]
        hour = chart["hour"]
        assert isinstance(day, dict) and isinstance(hour, dict)
        expected_day_branch = os.environ.get("PRIVATE_EXPECT_DAY_BRANCH")
        expected_hour_stem = os.environ.get("PRIVATE_EXPECT_HOUR_STEM")
        if expected_day_branch:
            assert day["branch"] == expected_day_branch
        if expected_hour_stem:
            assert hour["stem"] == expected_hour_stem
        hour_stem = str(expected_hour_stem or hour["stem"])

        status, calendar = api_json(
            "POST",
            app_base,
            "/api/calendars",
            app_user,
            app_password,
            {
                "profile_id": profile_id,
                "name": "맞춤 시간",
                "slug": f"smoke-{suffix}",
                "visibility": visibility,
                "rule": {
                    "logic": "all",
                    "predicates": [
                        {
                            "field": "day.branch",
                            "source": "natal",
                            "value": "day.branch",
                        },
                        {
                            "field": "hour.stem",
                            "source": "literal",
                            "value": hour_stem,
                        },
                    ],
                },
            },
        )
        assert status == 201 and isinstance(calendar, dict), (status, calendar)
        assert calendar["visibility"] == visibility
        calendar_id = str(calendar["id"])
        range_payload: dict[str, object] = {}

        status, preview = api_json(
            "POST",
            app_base,
            f"/api/calendars/{calendar_id}/preview",
            app_user,
            app_password,
            range_payload,
        )
        assert status == 200 and isinstance(preview, dict), (status, preview)
        assert int(preview["count"]) > 0

        status, synced = api_json(
            "POST",
            app_base,
            f"/api/calendars/{calendar_id}/sync",
            app_user,
            app_password,
            range_payload,
        )
        assert status == 200 and isinstance(synced, dict), (status, synced)
        assert synced["event_count"] == preview["count"]

        assert_caldav_collection(
            caldav_base,
            collection_url,
            caldav_user,
            caldav_password,
            visibility_classes[visibility],
        )

        status, secondary_profile = api_json(
            "POST",
            app_base,
            "/api/profiles",
            app_user,
            app_password,
            {
                "name": f"pair-smoke-{suffix}",
                "birth_calendar": "lunar",
                "birth_year": 2000,
                "birth_month": 1,
                "birth_day": 2,
                "birth_time": "08:30:00",
                "is_leap_month": False,
                "gender": "unspecified",
                "birth_city": "seoul",
                "timezone": "Asia/Seoul",
                "time_mode": "civil",
                "longitude": None,
            },
        )
        assert status == 201 and isinstance(secondary_profile, dict), (
            status,
            secondary_profile,
        )
        secondary_profile_id = str(secondary_profile["id"])

        status, pair_preview = api_json(
            "POST",
            app_base,
            "/api/compatibility/preview",
            app_user,
            app_password,
            {
                "primary_profile_id": profile_id,
                "secondary_profile_id": secondary_profile_id,
                "limit": 12,
            },
        )
        assert status == 200 and isinstance(pair_preview, dict), (status, pair_preview)
        assert int(pair_preview["count"]) > 0

        status, pair_calendar = api_json(
            "POST",
            app_base,
            "/api/compatibility/calendars",
            app_user,
            app_password,
            {
                "primary_profile_id": profile_id,
                "secondary_profile_id": secondary_profile_id,
                "name": "둘이 좋은 시간",
                "slug": f"pair-smoke-{suffix}",
                "visibility": visibility,
                "limit": 12,
            },
        )
        assert status == 201 and isinstance(pair_calendar, dict), (
            status,
            pair_calendar,
        )
        status, pair_synced = api_json(
            "POST",
            app_base,
            f"/api/calendars/{pair_calendar['id']}/sync",
            app_user,
            app_password,
            {},
        )
        assert status == 200 and isinstance(pair_synced, dict), (
            status,
            pair_synced,
        )
        assert pair_synced["event_count"] == pair_preview["count"]
        assert_caldav_collection(
            caldav_base,
            pair_collection_url,
            caldav_user,
            caldav_password,
            visibility_classes[visibility],
        )
        print(
            "SAJU_CALDAV_SMOKE_OK "
            f"rule_event_count={preview['count']} "
            f"pair_event_count={pair_preview['count']}"
        )
    finally:
        if collection_url:
            request("DELETE", collection_url, caldav_user, caldav_password)
        if pair_collection_url:
            request("DELETE", pair_collection_url, caldav_user, caldav_password)
        if secondary_profile_id:
            api_json(
                "DELETE",
                app_base,
                f"/api/profiles/{secondary_profile_id}",
                app_user,
                app_password,
            )
        if profile_id:
            api_json(
                "DELETE",
                app_base,
                f"/api/profiles/{profile_id}",
                app_user,
                app_password,
            )


if __name__ == "__main__":
    main()
