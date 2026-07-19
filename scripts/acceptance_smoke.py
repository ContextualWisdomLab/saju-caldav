"""Exercise the live API, matching engine, CalDAV publish, and readback path."""

from __future__ import annotations

import base64
import json
import os
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


def request(
    method: str,
    url: str,
    username: str,
    password: str,
    body: bytes | None = None,
    content_type: str = "application/json",
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    requested = Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": content_type,
            **(headers or {}),
        },
    )
    try:
        with urlopen(requested, timeout=20) as response:  # noqa: S310
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


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


def main() -> None:
    app_base = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8000")
    app_user = os.environ["APP_USERNAME"]
    app_password = os.environ["APP_PASSWORD"]
    caldav_base = os.environ.get("CALDAV_PUBLIC_URL", "http://127.0.0.1:5232")
    caldav_user = os.environ["CALDAV_USERNAME"]
    caldav_password = os.environ["CALDAV_PASSWORD"]
    suffix = f"{int(time.time())}-{os.getpid()}"
    profile_id = ""
    collection_url = f"{caldav_base.rstrip('/')}/{quote(caldav_user, safe='')}/smoke-{suffix}/"

    try:
        status, profile = api_json(
            "POST",
            app_base,
            "/api/profiles",
            app_user,
            app_password,
            {
                "name": f"acceptance-smoke-{suffix}",
                "birth_local": "1990-06-15T08:30:00",
                "gender": "female",
                "timezone": "Asia/Seoul",
                "time_mode": "civil",
                "longitude": None,
            },
        )
        assert status == 201 and isinstance(profile, dict), (status, profile)
        profile_id = str(profile["id"])
        chart = profile["chart"]
        assert isinstance(chart, dict)
        assert chart["day"]["branch"] == "亥"
        assert chart["hour"]["stem"] == "壬"

        status, calendar = api_json(
            "POST",
            app_base,
            "/api/calendars",
            app_user,
            app_password,
            {
                "profile_id": profile_id,
                "name": "acceptance 亥日 壬時",
                "slug": f"smoke-{suffix}",
                "rule": {
                    "logic": "all",
                    "predicates": [
                        {
                            "field": "day.branch",
                            "source": "natal",
                            "value": "day.branch",
                        },
                        {"field": "hour.stem", "source": "literal", "value": "壬"},
                    ],
                },
            },
        )
        assert status == 201 and isinstance(calendar, dict), (status, calendar)
        calendar_id = str(calendar["id"])
        range_payload = {"start_date": "1990-06-15", "end_date": "1990-06-15"}

        status, preview = api_json(
            "POST",
            app_base,
            f"/api/calendars/{calendar_id}/preview",
            app_user,
            app_password,
            range_payload,
        )
        assert status == 200 and isinstance(preview, dict), (status, preview)
        assert preview["count"] == 1
        assert preview["events"][0]["start"] == "1990-06-15T07:00:00+09:00"

        status, synced = api_json(
            "POST",
            app_base,
            f"/api/calendars/{calendar_id}/sync",
            app_user,
            app_password,
            range_payload,
        )
        assert status == 200 and isinstance(synced, dict), (status, synced)
        assert synced["event_count"] == 1

        status, listing = request(
            "PROPFIND",
            collection_url,
            caldav_user,
            caldav_password,
            (
                b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:">'
                b"<d:prop><d:getetag/></d:prop></d:propfind>"
            ),
            "application/xml",
            {"Depth": "1"},
        )
        assert status == 207 and b".ics" in listing, (status, listing[:500])
        print("SAJU_CALDAV_ACCEPTANCE_OK event_count=1 day_branch=亥 hour_stem=壬")
    finally:
        if collection_url:
            request("DELETE", collection_url, caldav_user, caldav_password)
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
