from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

import app.main as main_module
from app.caldav import SyncResult
from app.store import Store


class RecordingPublisher:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def sync(self, calendar_id, slug, calendar_name, windows):
        self.calls.append(
            {
                "calendar_id": calendar_id,
                "slug": slug,
                "calendar_name": calendar_name,
                "windows": windows,
            }
        )
        return SyncResult(
            collection_url=f"https://cal.example/operator/{slug}/",
            event_count=len(windows),
        )


def _client(tmp_path: Path) -> tuple[TestClient, RecordingPublisher]:
    store = Store(tmp_path / "saju.db")
    publisher = RecordingPublisher()
    app = main_module.create_app(
        store=store,
        username="operator",
        password="correct-horse-battery-staple",
        publisher=publisher,
    )
    return TestClient(app), publisher


def _auth() -> tuple[str, str]:
    return ("operator", "correct-horse-battery-staple")


def _create_profile(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/profiles",
        auth=_auth(),
        json={
            "name": "공개 테스트 예시",
            "birth_calendar": "solar",
            "birth_year": 2000,
            "birth_month": 1,
            "birth_day": 1,
            "birth_time": "12:15:00",
            "is_leap_month": False,
            "gender": "unspecified",
            "timezone": "Asia/Seoul",
            "time_mode": "civil",
            "longitude": None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_calendar(client: TestClient, profile_id: str) -> dict[str, object]:
    response = client.post(
        "/api/calendars",
        auth=_auth(),
        json={
            "profile_id": profile_id,
            "name": "나의 맞춤 시간",
            "slug": "my-custom-hours",
            "rule": {
                "logic": "all",
                "predicates": [
                    {"field": "day.branch", "source": "natal", "value": "day.branch"},
                    {"field": "hour.stem", "source": "literal", "value": "戊"},
                ],
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_operator_authentication(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    assert client.get("/health").json() == {"status": "ok"}
    unauthorized = client.get("/api/profiles")
    assert unauthorized.status_code == 401
    assert unauthorized.headers["www-authenticate"] == "Basic"
    assert client.get("/api/profiles", auth=_auth()).json() == []


def test_operator_console_and_static_assets_are_served(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    assert client.get("/").status_code == 401
    page = client.get("/", auth=_auth())
    assert page.status_code == 200
    assert "사주 명식을" in page.text
    assert "시간 캘린더로" in page.text
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_acceptance_profile_calendar_preview_and_sync(tmp_path: Path) -> None:
    client, publisher = _client(tmp_path)

    profile = _create_profile(client)
    assert profile["chart"]["day"]["branch"] == "午"
    assert profile["chart"]["hour"]["stem"] == "戊"
    assert profile["chart"]["day"]["branch_korean"] == "오화"
    assert profile["chart"]["hour"]["stem_description"] == "양의 성질을 가진 큰땅"
    assert profile["birth_calendar"] == "solar"
    assert profile["birth_local"] == "2000-01-01T12:15:00"
    assert profile["gender"] == "unspecified"

    calendar = _create_calendar(client, str(profile["id"]))
    preview = client.post(
        f"/api/calendars/{calendar['id']}/preview",
        auth=_auth(),
        json={"start_date": "2000-01-01", "end_date": "2000-01-01"},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["count"] == 1
    assert preview.json()["events"][0]["start"] == "2000-01-01T11:00:00+09:00"
    assert preview.json()["events"][0]["hour_pillar"] == "戊午"
    assert preview.json()["events"][0]["day_branch_korean"] == "오화"
    assert preview.json()["events"][0]["hour_stem_korean"] == "무토"

    synced = client.post(
        f"/api/calendars/{calendar['id']}/sync",
        auth=_auth(),
        json={"start_date": "2000-01-01", "end_date": "2000-01-01"},
    )
    assert synced.status_code == 200, synced.text
    assert synced.json() == {
        "collection_url": "https://cal.example/operator/my-custom-hours/",
        "event_count": 1,
    }
    assert publisher.calls[0]["slug"] == "my-custom-hours"


def test_lunar_profile_keeps_original_input_and_normalizes_birth_time(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    response = client.post(
        "/api/profiles",
        auth=_auth(),
        json={
            "name": "음력 입력 예시",
            "birth_calendar": "lunar",
            "birth_year": 2024,
            "birth_month": 1,
            "birth_day": 1,
            "birth_time": "08:30:00",
            "is_leap_month": False,
            "gender": "unspecified",
            "timezone": "Asia/Seoul",
            "time_mode": "civil",
            "longitude": None,
        },
    )

    assert response.status_code == 201, response.text
    profile = response.json()
    assert profile["birth_calendar"] == "lunar"
    assert profile["birth_year"] == 2024
    assert profile["birth_month"] == 1
    assert profile["birth_day"] == 1
    assert profile["birth_time"] == "08:30:00"
    assert profile["is_leap_month"] == 0
    assert profile["birth_local"] == "2024-02-10T08:30:00"


def test_omitted_range_starts_on_current_profile_date(
    tmp_path: Path, monkeypatch
) -> None:
    client, publisher = _client(tmp_path)
    profile = _create_profile(client)
    calendar = _create_calendar(client, str(profile["id"]))
    seoul_now = datetime(2026, 7, 19, 0, 30, tzinfo=ZoneInfo("Asia/Seoul"))
    monkeypatch.setattr(main_module, "_now", lambda zone: seoul_now.astimezone(zone))

    preview = client.post(
        f"/api/calendars/{calendar['id']}/preview", auth=_auth(), json={}
    )
    assert preview.status_code == 200, preview.text
    assert all(
        datetime.fromisoformat(event["start"]).date() >= seoul_now.date()
        for event in preview.json()["events"]
    )

    synced = client.post(
        f"/api/calendars/{calendar['id']}/sync", auth=_auth(), json={}
    )
    assert synced.status_code == 200, synced.text
    assert publisher.calls
    assert all(window.start.date() >= seoul_now.date() for window in publisher.calls[0]["windows"])


def test_invalid_rule_and_missing_profile_are_rejected(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    profile = _create_profile(client)

    invalid = client.post(
        "/api/calendars",
        auth=_auth(),
        json={
            "profile_id": profile["id"],
            "name": "위험한 규칙",
            "slug": "unsafe-rule",
            "rule": {
                "logic": "all",
                "predicates": [
                    {"field": "__class__", "source": "literal", "value": "anything"}
                ],
            },
        },
    )
    assert invalid.status_code == 422

    missing = client.post(
        "/api/calendars",
        auth=_auth(),
        json={
            "profile_id": "missing",
            "name": "없는 프로필",
            "slug": "missing-profile",
            "rule": {
                "logic": "all",
                "predicates": [
                    {"field": "hour.stem", "source": "literal", "value": "壬"}
                ],
            },
        },
    )
    assert missing.status_code == 404
