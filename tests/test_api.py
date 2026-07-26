import sqlite3
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

    def sync(self, calendar_id, slug, calendar_name, visibility, windows):
        if visibility not in {"private", "confidential", "public"}:
            raise ValueError(
                f"지원하지 않는 공개 수준: {visibility!r}; "
                "사용할 수 있는 값: private, confidential, public"
            )
        self.calls.append(
            {
                "calendar_id": calendar_id,
                "slug": slug,
                "calendar_name": calendar_name,
                "visibility": visibility,
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
            "birth_city": "seoul",
            "time_mode": "civil",
            "longitude": None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_secondary_profile(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/profiles",
        auth=_auth(),
        json={
            "name": "두 번째 공개 예시",
            "birth_calendar": "solar",
            "birth_year": 2000,
            "birth_month": 1,
            "birth_day": 2,
            "birth_time": "12:15:00",
            "is_leap_month": False,
            "gender": "unspecified",
            "timezone": "Asia/Seoul",
            "birth_city": "seoul",
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
            "visibility": "confidential",
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
    locations = client.get("/api/locations", auth=_auth())
    assert locations.status_code == 200
    assert locations.json()[0]["label"] == "대한민국 · 서울"
    assert "longitude" not in locations.json()[0]


def test_operator_console_and_static_assets_are_served(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    assert client.get("/").status_code == 401
    page = client.get("/", auth=_auth())
    assert page.status_code == 200
    assert "두 사람의 좋은 시간 찾기" in page.text
    assert "둘이 좋은 날과 시간 찾기" in page.text
    assert "사주를 잘 몰라도 됩니다" in page.text
    assert 'id="compatibility-result"' in page.text
    assert "출생 도시" in page.text
    assert 'name="longitude"' not in page.text
    assert 'name="visibility"' in page.text
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
    assert profile["birth_city"] == "seoul"
    assert profile["birth_city_name"] == "대한민국 · 서울"

    calendar = _create_calendar(client, str(profile["id"]))
    assert calendar["visibility"] == "confidential"
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
    assert publisher.calls[0]["visibility"] == "confidential"


def test_two_person_preview_calendar_and_sync_are_plain_korean(
    tmp_path: Path,
) -> None:
    client, publisher = _client(tmp_path)
    primary = _create_profile(client)
    secondary = _create_secondary_profile(client)

    preview = client.post(
        "/api/compatibility/preview",
        auth=_auth(),
        json={
            "primary_profile_id": primary["id"],
            "secondary_profile_id": secondary["id"],
            "start_date": "2000-01-01",
            "end_date": "2000-01-31",
            "limit": 8,
        },
    )
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["method"] == "balanced_branch_harmony"
    assert payload["primary_name"] == "공개 테스트 예시"
    assert payload["secondary_name"] == "두 번째 공개 예시"
    assert 1 <= payload["count"] <= 8
    assert all(event["score"] >= 60 for event in payload["events"])
    assert all(event["label"].endswith("시간") for event in payload["events"])
    assert all(event["reasons"] for event in payload["events"])

    created = client.post(
        "/api/compatibility/calendars",
        auth=_auth(),
        json={
            "primary_profile_id": primary["id"],
            "secondary_profile_id": secondary["id"],
            "name": "둘이 좋은 시간",
            "slug": "good-time-together",
            "visibility": "private",
            "limit": 8,
        },
    )
    assert created.status_code == 201, created.text
    calendar = created.json()
    assert calendar["kind"] == "compatibility"
    assert calendar["secondary_profile_id"] == secondary["id"]

    calendar_preview = client.post(
        f"/api/calendars/{calendar['id']}/preview",
        auth=_auth(),
        json={"start_date": "2000-01-01", "end_date": "2000-01-31"},
    )
    assert calendar_preview.status_code == 200, calendar_preview.text
    assert calendar_preview.json()["events"][0]["reasons"]

    synced = client.post(
        f"/api/calendars/{calendar['id']}/sync",
        auth=_auth(),
        json={"start_date": "2000-01-01", "end_date": "2000-01-31"},
    )
    assert synced.status_code == 200, synced.text
    assert publisher.calls[-1]["calendar_name"] == "둘이 좋은 시간"
    assert publisher.calls[-1]["visibility"] == "private"
    assert synced.json()["event_count"] == len(publisher.calls[-1]["windows"])


def test_two_person_flow_requires_distinct_profiles(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    profile = _create_profile(client)

    response = client.post(
        "/api/compatibility/preview",
        auth=_auth(),
        json={
            "primary_profile_id": profile["id"],
            "secondary_profile_id": profile["id"],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "서로 다른 두 사람의 프로필을 선택하세요"


def test_city_automatically_supplies_timezone_and_true_solar_longitude(
    tmp_path: Path,
) -> None:
    client, _ = _client(tmp_path)

    response = client.post(
        "/api/profiles",
        auth=_auth(),
        json={
            "name": "도시 자동 설정 예시",
            "birth_calendar": "solar",
            "birth_year": 2000,
            "birth_month": 1,
            "birth_day": 1,
            "birth_time": "12:15:00",
            "is_leap_month": False,
            "gender": "unspecified",
            "birth_city": "seoul",
            "timezone": "Etc/UTC",
            "time_mode": "true_solar",
            "longitude": None,
        },
    )

    assert response.status_code == 201, response.text
    profile = response.json()
    assert profile["timezone"] == "Asia/Seoul"
    assert profile["longitude"] == 126.978
    assert profile["birth_city_name"] == "대한민국 · 서울"


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


def test_invalid_profile_timezone_is_reported_as_input_error(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    response = client.post(
        "/api/profiles",
        auth=_auth(),
        json={
            "name": "잘못된 시간대 예시",
            "birth_calendar": "solar",
            "birth_year": 2000,
            "birth_month": 1,
            "birth_day": 1,
            "birth_time": "12:15:00",
            "is_leap_month": False,
            "gender": "unspecified",
            "timezone": "Mars/Olympus",
            "time_mode": "civil",
            "longitude": None,
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "입력한 시간대 정보를 사용할 수 없습니다"}


def test_omitted_range_keeps_only_ongoing_and_future_windows(
    tmp_path: Path, monkeypatch
) -> None:
    client, publisher = _client(tmp_path)
    seoul_now = datetime(2026, 7, 19, 12, 30, tzinfo=ZoneInfo("Asia/Seoul"))
    monkeypatch.setattr(main_module, "_now", lambda zone: seoul_now.astimezone(zone))
    profile_response = client.post(
        "/api/profiles",
        auth=_auth(),
        json={
            "name": "현재 구간 테스트",
            "birth_calendar": "solar",
            "birth_year": 2026,
            "birth_month": 7,
            "birth_day": 19,
            "birth_time": "00:30:00",
            "is_leap_month": False,
            "gender": "unspecified",
            "birth_city": "seoul",
            "timezone": "Asia/Seoul",
            "time_mode": "civil",
            "longitude": None,
        },
    )
    assert profile_response.status_code == 201, profile_response.text
    profile = profile_response.json()
    calendar_response = client.post(
        "/api/calendars",
        auth=_auth(),
        json={
            "profile_id": profile["id"],
            "name": "현재와 미래 시간",
            "slug": "current-and-future",
            "visibility": "private",
            "rule": {
                "logic": "all",
                "predicates": [
                    {
                        "field": "day.branch",
                        "source": "natal",
                        "value": "day.branch",
                    }
                ],
            },
        },
    )
    assert calendar_response.status_code == 201, calendar_response.text
    calendar = calendar_response.json()

    preview = client.post(
        f"/api/calendars/{calendar['id']}/preview", auth=_auth(), json={}
    )
    assert preview.status_code == 200, preview.text
    preview_windows = preview.json()["events"]
    assert preview_windows[0]["start"] == "2026-07-19T11:00:00+09:00"
    assert preview_windows[0]["end"] == "2026-07-19T13:00:00+09:00"
    assert all(datetime.fromisoformat(event["end"]) > seoul_now for event in preview_windows)

    synced = client.post(
        f"/api/calendars/{calendar['id']}/sync", auth=_auth(), json={}
    )
    assert synced.status_code == 200, synced.text
    assert publisher.calls
    published_windows = publisher.calls[0]["windows"]
    assert published_windows[0].start.isoformat() == "2026-07-19T11:00:00+09:00"
    assert all(window.end > seoul_now for window in published_windows)


def test_invalid_stored_timezone_is_reported_as_input_error(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    profile = _create_profile(client)
    calendar = _create_calendar(client, str(profile["id"]))
    with sqlite3.connect(tmp_path / "saju.db") as connection:
        connection.execute(
            "UPDATE profiles SET timezone = ? WHERE id = ?",
            ("Mars/Olympus", profile["id"]),
        )

    response = client.post(
        f"/api/calendars/{calendar['id']}/preview",
        auth=_auth(),
        json={"start_date": "2026-07-19", "end_date": "2026-07-19"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "저장된 시간대 정보를 사용할 수 없습니다"}


def test_invalid_stored_visibility_is_reported_as_input_error(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    profile = _create_profile(client)
    calendar = _create_calendar(client, str(profile["id"]))
    with sqlite3.connect(tmp_path / "saju.db") as connection:
        connection.execute(
            "UPDATE calendars SET visibility = ? WHERE id = ?",
            ("secret", calendar["id"]),
        )

    response = client.post(
        f"/api/calendars/{calendar['id']}/sync",
        auth=_auth(),
        json={"start_date": "2000-01-01", "end_date": "2000-01-01"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "secret" in detail
    assert "private, confidential, public" in detail


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
