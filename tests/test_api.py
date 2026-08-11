import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.caldav import SyncResult
from app.store import Store


class RecordingPublisher:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, str]] = []

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

    def delete(self, calendar_id, slug):
        self.delete_calls.append({"calendar_id": calendar_id, "slug": slug})


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


def _create_unknown_time_profile(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/profiles",
        auth=_auth(),
        json={
            "name": "태어난 시각 미상 예시",
            "birth_calendar": "lunar",
            "birth_year": 2000,
            "birth_month": 1,
            "birth_day": 2,
            "birth_time": None,
            "birth_time_known": False,
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


def _calendar_payload(profile_id: str) -> dict[str, object]:
    return {
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
    }


def _create_calendar(client: TestClient, profile_id: str) -> dict[str, object]:
    response = client.post(
        "/api/calendars", auth=_auth(), json=_calendar_payload(profile_id)
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
    assert "태어난 시각을 모릅니다" in page.text
    assert "생활 시간" in page.text
    assert 'id="compatibility-result"' in page.text
    assert "출생 도시" in page.text
    assert 'id="profile-list"' in page.text
    assert "연결된 CalDAV 캘린더도 함께 삭제" in page.text
    assert 'name="longitude"' not in page.text
    assert 'name="visibility"' in page.text
    assert client.get("/static/styles.css").status_code == 200
    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "출생 정보 삭제" in script.text
    assert "연결된 캘린더" in script.text


def test_acceptance_profile_calendar_preview_and_sync(tmp_path: Path) -> None:
    client, publisher = _client(tmp_path)

    profile = _create_profile(client)
    assert profile["chart"]["day"]["branch"] == "午"
    assert profile["chart"]["hour"]["stem"] == "戊"
    assert profile["chart"]["day"]["branch_korean"] == "오화"
    assert profile["chart"]["hour"]["stem_description"] == "양의 성질을 가진 큰땅"
    assert profile["birth_calendar"] == "solar"
    assert profile["birth_time_known"] is True
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


def test_unknown_birth_time_keeps_day_pillar_without_inventing_hour_pillar(
    tmp_path: Path,
) -> None:
    client, _ = _client(tmp_path)

    profile = _create_unknown_time_profile(client)

    assert profile["birth_calendar"] == "lunar"
    assert profile["birth_time"] is None
    assert profile["birth_time_known"] is False
    assert profile["birth_local"].endswith("T12:00:00")
    assert profile["chart"]["day"]["ganzhi"]
    assert profile["chart"]["hour"] is None
    assert profile["chart"]["calculation_local"].endswith("T12:00:00")


def test_unknown_birth_time_still_supports_two_person_recommendations(
    tmp_path: Path,
) -> None:
    client, _ = _client(tmp_path)
    primary = _create_profile(client)
    secondary = _create_unknown_time_profile(client)

    response = client.post(
        "/api/compatibility/preview",
        auth=_auth(),
        json={
            "primary_profile_id": primary["id"],
            "secondary_profile_id": secondary["id"],
            "start_date": "2000-02-06",
            "end_date": "2000-03-06",
            "limit": 8,
        },
    )

    assert response.status_code == 200, response.text
    assert 1 <= response.json()["count"] <= 8


def test_unknown_birth_time_rejects_true_solar_mode(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    response = client.post(
        "/api/profiles",
        auth=_auth(),
        json={
            "name": "시각 미상 진태양시 예시",
            "birth_calendar": "solar",
            "birth_year": 2000,
            "birth_month": 1,
            "birth_day": 2,
            "birth_time": None,
            "birth_time_known": False,
            "is_leap_month": False,
            "gender": "unspecified",
            "birth_city": "seoul",
            "timezone": "Asia/Seoul",
            "time_mode": "true_solar",
            "longitude": None,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "태어난 시각을 모르면 진태양시를 적용할 수 없습니다. 공식 표준시를 선택하세요"
    }


def test_known_birth_time_is_required_by_default(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    response = client.post(
        "/api/profiles",
        auth=_auth(),
        json={
            "name": "빠진 시각 예시",
            "birth_calendar": "solar",
            "birth_year": 2000,
            "birth_month": 1,
            "birth_day": 2,
            "gender": "unspecified",
            "birth_city": "seoul",
            "timezone": "Asia/Seoul",
            "time_mode": "civil",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "태어난 시각을 입력하거나 ‘태어난 시각을 모릅니다’를 선택하세요"
    }


def test_unknown_birth_time_allows_day_rule_but_rejects_natal_hour_rule(
    tmp_path: Path,
) -> None:
    client, _ = _client(tmp_path)
    profile = _create_unknown_time_profile(client)

    allowed = client.post(
        "/api/calendars",
        auth=_auth(),
        json={
            "profile_id": profile["id"],
            "name": "일지와 현재 시간 기준",
            "slug": "unknown-time-day-rule",
            "visibility": "private",
            "rule": {
                "logic": "all",
                "predicates": [
                    {"field": "day.branch", "source": "natal", "value": "day.branch"},
                    {"field": "hour.stem", "source": "literal", "value": "壬"},
                ],
            },
        },
    )
    assert allowed.status_code == 201, allowed.text

    rejected = client.post(
        "/api/calendars",
        auth=_auth(),
        json={
            "profile_id": profile["id"],
            "name": "알 수 없는 시주 기준",
            "slug": "unknown-time-hour-rule",
            "visibility": "private",
            "rule": {
                "logic": "all",
                "predicates": [
                    {"field": "hour.stem", "source": "natal", "value": "hour.stem"}
                ],
            },
        },
    )
    assert rejected.status_code == 422
    assert rejected.json() == {
        "detail": "태어난 시각을 모르는 프로필은 출생 시주 조건을 사용할 수 없습니다"
    }


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
    assert payload["include_overnight"] is False
    assert payload["primary_name"] == "공개 테스트 예시"
    assert payload["secondary_name"] == "두 번째 공개 예시"
    assert 1 <= payload["count"] <= 8
    assert all(event["score"] >= 60 for event in payload["events"])
    assert all(event["label"].endswith("시간") for event in payload["events"])
    assert all(event["reasons"] for event in payload["events"])
    for event in payload["events"]:
        start = datetime.fromisoformat(event["start"])
        end = datetime.fromisoformat(event["end"])
        assert start.date() == end.date()
        assert start.time() >= time(9)
        assert end.time() <= time(23)

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
            "include_overnight": True,
        },
    )
    assert created.status_code == 201, created.text
    calendar = created.json()
    assert calendar["kind"] == "compatibility"
    assert calendar["secondary_profile_id"] == secondary["id"]
    assert calendar["rule"]["include_overnight"] is True

    calendar_preview = client.post(
        f"/api/calendars/{calendar['id']}/preview",
        auth=_auth(),
        json={"start_date": "2000-01-01", "end_date": "2000-01-31"},
    )
    assert calendar_preview.status_code == 200, calendar_preview.text
    assert calendar_preview.json()["include_overnight"] is True
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


def test_api_not_found_duplicate_and_unavailable_publisher_paths(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    calendars = client.get("/api/calendars", auth=_auth())
    missing_profile = client.delete("/api/profiles/missing", auth=_auth())
    missing_calendar = client.delete("/api/calendars/missing", auth=_auth())
    missing_preview = client.post(
        "/api/calendars/missing/preview", auth=_auth(), json={}
    )
    missing_sync = client.post("/api/calendars/missing/sync", auth=_auth(), json={})
    assert calendars.json() == []
    assert missing_profile.status_code == 404
    assert missing_calendar.status_code == 404
    assert missing_preview.status_code == 404
    assert missing_sync.status_code == 404

    profile = _create_profile(client)
    calendar = _create_calendar(client, str(profile["id"]))
    duplicate = client.post(
        "/api/calendars",
        auth=_auth(),
        json=_calendar_payload(str(profile["id"])),
    )
    assert duplicate.status_code == 409
    secondary = _create_secondary_profile(client)
    compatibility_duplicate = client.post(
        "/api/compatibility/calendars",
        auth=_auth(),
        json={
            "primary_profile_id": profile["id"],
            "secondary_profile_id": secondary["id"],
            "name": "중복 달력",
            "slug": "my-custom-hours",
        },
    )
    assert compatibility_duplicate.status_code == 409

    unavailable_app = main_module.create_app(
        store=Store(tmp_path / "unavailable.db"),
        username="operator",
        password="correct-horse-battery-staple",
        publisher=main_module.UnavailablePublisher(),
    )
    unavailable = TestClient(unavailable_app)
    unavailable_profile = _create_profile(unavailable)
    unavailable_calendar = _create_calendar(unavailable, str(unavailable_profile["id"]))
    failed_sync = unavailable.post(
        f"/api/calendars/{unavailable_calendar['id']}/sync",
        auth=_auth(),
        json={"start_date": "2000-01-01", "end_date": "2000-01-01"},
    )
    assert failed_sync.status_code == 502

    first_delete = client.delete(f"/api/calendars/{calendar['id']}", auth=_auth())
    second_delete = client.delete(f"/api/calendars/{calendar['id']}", auth=_auth())
    profile_delete = client.delete(f"/api/profiles/{profile['id']}", auth=_auth())
    assert first_delete.status_code == 204
    assert second_delete.status_code == 404
    assert profile_delete.status_code == 204


def test_delete_synced_calendar_removes_remote_collection_before_metadata(
    tmp_path: Path,
) -> None:
    client, publisher = _client(tmp_path)
    profile = _create_profile(client)
    calendar = _create_calendar(client, str(profile["id"]))

    synced = client.post(
        f"/api/calendars/{calendar['id']}/sync",
        auth=_auth(),
        json={"start_date": "2000-01-01", "end_date": "2000-01-01"},
    )
    assert synced.status_code == 200, synced.text

    deleted = client.delete(f"/api/calendars/{calendar['id']}", auth=_auth())

    assert deleted.status_code == 204
    assert publisher.delete_calls == [
        {"calendar_id": calendar["id"], "slug": calendar["slug"]}
    ]
    assert client.get("/api/calendars", auth=_auth()).json() == []


def test_delete_synced_profile_removes_primary_and_secondary_remote_collections(
    tmp_path: Path,
) -> None:
    client, publisher = _client(tmp_path)
    primary = _create_profile(client)
    secondary = _create_secondary_profile(client)
    primary_calendar = _create_calendar(client, str(primary["id"]))
    compatibility = client.post(
        "/api/compatibility/calendars",
        auth=_auth(),
        json={
            "primary_profile_id": primary["id"],
            "secondary_profile_id": secondary["id"],
            "name": "둘이 좋은 시간",
            "slug": "pair-delete-check",
        },
    )
    assert compatibility.status_code == 201, compatibility.text

    for calendar in (primary_calendar, compatibility.json()):
        response = client.post(
            f"/api/calendars/{calendar['id']}/sync",
            auth=_auth(),
            json={"start_date": "2000-01-01", "end_date": "2000-01-01"},
        )
        assert response.status_code == 200, response.text

    deleted = client.delete(f"/api/profiles/{primary['id']}", auth=_auth())

    assert deleted.status_code == 204
    assert {call["slug"] for call in publisher.delete_calls} == {
        primary_calendar["slug"],
        "pair-delete-check",
    }
    assert client.get("/api/profiles", auth=_auth()).json() == [secondary]
    assert client.get("/api/calendars", auth=_auth()).json() == []


def test_synced_delete_fails_closed_when_remote_publisher_is_unavailable(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "unavailable-delete.db")
    app = main_module.create_app(
        store=store,
        username="operator",
        password="correct-horse-battery-staple",
        publisher=main_module.UnavailablePublisher(),
    )
    client = TestClient(app)
    profile = _create_profile(client)
    calendar = _create_calendar(client, str(profile["id"]))

    with sqlite3.connect(tmp_path / "unavailable-delete.db") as connection:
        connection.execute(
            "UPDATE calendars SET last_synced_at = ? WHERE id = ?",
            ("2026-08-11T00:00:00+00:00", calendar["id"]),
        )

    deleted = client.delete(f"/api/calendars/{calendar['id']}", auth=_auth())

    assert deleted.status_code == 502
    remaining = client.get("/api/calendars", auth=_auth()).json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == calendar["id"]
    assert remaining[0]["last_synced_at"] == "2026-08-11T00:00:00+00:00"


def test_delete_operations_report_race_after_metadata_disappears(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _ = _client(tmp_path)
    profile = _create_profile(client)
    calendar = _create_calendar(client, str(profile["id"]))
    store = Store(tmp_path / "saju.db")

    monkeypatch.setattr(store, "get_profile", lambda profile_id: profile)
    monkeypatch.setattr(store, "list_calendars_for_profile", lambda profile_id: [])
    monkeypatch.setattr(store, "delete_profile", lambda profile_id: False)
    profile_app = main_module.create_app(
        store=store,
        username="operator",
        password="correct-horse-battery-staple",
        publisher=RecordingPublisher(),
    )
    profile_response = TestClient(profile_app).delete(
        f"/api/profiles/{profile['id']}", auth=_auth()
    )
    assert profile_response.status_code == 404

    monkeypatch.setattr(store, "get_calendar", lambda calendar_id: calendar)
    monkeypatch.setattr(store, "delete_calendar", lambda calendar_id: False)
    calendar_app = main_module.create_app(
        store=store,
        username="operator",
        password="correct-horse-battery-staple",
        publisher=RecordingPublisher(),
    )
    calendar_response = TestClient(calendar_app).delete(
        f"/api/calendars/{calendar['id']}", auth=_auth()
    )
    assert calendar_response.status_code == 404


def test_invalid_birth_date_and_missing_static_index_are_reported(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    invalid = client.post(
        "/api/profiles",
        auth=_auth(),
        json={
            "name": "잘못된 날짜",
            "birth_year": 2000,
            "birth_month": 2,
            "birth_day": 31,
            "birth_time": "12:00:00",
        },
    )
    assert invalid.status_code == 422

    fallback = TestClient(
        main_module.create_app(
            store=Store(tmp_path / "fallback.db"),
            username="operator",
            password="correct-horse-battery-staple",
            publisher=RecordingPublisher(),
            static_dir=tmp_path / "missing-assets",
        )
    )
    response = fallback.get("/", auth=_auth())
    assert response.status_code == 200
    assert response.text == "Saju CalDAV operator console"


def test_publisher_is_built_from_complete_environment(monkeypatch) -> None:
    expected = object()
    monkeypatch.setenv("CALDAV_BASE_URL", "https://example.com/caldav")
    monkeypatch.setenv("CALDAV_USERNAME", "operator")
    monkeypatch.setenv("CALDAV_PASSWORD", "secret")
    monkeypatch.setattr(main_module, "CalDavPublisher", lambda *args: expected)

    assert main_module._publisher_from_environment() is expected


def test_internal_context_errors_are_mapped_to_http_statuses(tmp_path: Path, monkeypatch) -> None:
    client, _ = _client(tmp_path)
    primary_response = _create_profile(client)
    secondary_response = _create_secondary_profile(client)
    calendar_response = _create_calendar(client, str(primary_response["id"]))
    store = Store(tmp_path / "saju.db")
    primary = store.get_profile(str(primary_response["id"]))
    secondary = store.get_profile(str(secondary_response["id"]))
    calendar = store.get_calendar(str(calendar_response["id"]))
    assert primary and secondary and calendar
    chart = main_module._profile_chart(primary)
    rule = main_module.validate_rule(dict(calendar["rule"]))

    def assert_status(status_code: int, function) -> None:
        with pytest.raises(main_module.HTTPException) as captured:
            function()
        assert captured.value.status_code == status_code

    assert_status(
        404,
        lambda: main_module._calendar_context(
            SimpleNamespace(get_calendar=lambda calendar_id: None), "missing"
        ),
    )
    assert_status(
        404,
        lambda: main_module._calendar_context(
            SimpleNamespace(
                get_calendar=lambda calendar_id: calendar,
                get_profile=lambda profile_id: None,
            ),
            "missing-profile",
        ),
    )
    invalid_rule_calendar = {**calendar, "rule": {"logic": "bad"}}
    assert_status(
        422,
        lambda: main_module._calendar_context(
            SimpleNamespace(
                get_calendar=lambda calendar_id: invalid_rule_calendar,
                get_profile=lambda profile_id: primary,
            ),
            str(calendar["id"]),
        ),
    )
    assert_status(
        404,
        lambda: main_module._compatibility_context(store, "missing", "also-missing"),
    )

    bad_zone = {**primary, "timezone": "Mars/Olympus"}
    assert_status(
        422,
        lambda: main_module._compatibility_context(
            SimpleNamespace(
                get_profile=lambda profile_id: bad_zone if profile_id == "primary" else secondary
            ),
            "primary",
            "secondary",
        ),
    )
    bad_birth = {**primary, "birth_local": "not-a-date"}
    assert_status(
        422,
        lambda: main_module._compatibility_context(
            SimpleNamespace(
                get_profile=lambda profile_id: bad_birth if profile_id == "primary" else secondary
            ),
            "primary",
            "secondary",
        ),
    )

    compatibility_request = main_module.CompatibilityRequest(
        primary_profile_id=str(primary["id"]),
        secondary_profile_id=str(secondary["id"]),
        start_date=date(2000, 1, 1),
        end_date=date(2000, 1, 1),
    )
    with monkeypatch.context() as scoped:
        scoped.setattr(
            main_module,
            "_compatibility_context",
            lambda *args: (bad_zone, secondary, chart, chart),
        )
        assert_status(
            422,
            lambda: main_module._compatibility_candidates(store, compatibility_request),
        )
    reversed_compatibility = compatibility_request.model_copy(
        update={"start_date": date(2000, 1, 2), "end_date": date(2000, 1, 1)}
    )
    assert_status(
        422,
        lambda: main_module._compatibility_candidates(store, reversed_compatibility),
    )

    date_range = main_module.DateRange(start_date=date(2000, 1, 1), end_date=date(2000, 1, 1))
    with monkeypatch.context() as scoped:
        scoped.setattr(
            main_module,
            "_calendar_context",
            lambda *args: (calendar, bad_zone, rule, chart),
        )
        assert_status(
            422,
            lambda: main_module._windows(store, str(calendar["id"]), date_range),
        )
    reversed_range = date_range.model_copy(
        update={"start_date": date(2000, 1, 2), "end_date": date(2000, 1, 1)}
    )
    assert_status(
        422,
        lambda: main_module._windows(store, str(calendar["id"]), reversed_range),
    )


def test_database_lock_is_retryable_but_other_operational_errors_propagate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = Store(tmp_path / "locked.db")
    app = main_module.create_app(
        store=store,
        username="operator",
        password="correct-horse-battery-staple",
        publisher=RecordingPublisher(),
    )
    busy_error = sqlite3.OperationalError("database is locked")
    busy_error.sqlite_errorcode = sqlite3.SQLITE_BUSY | (2 << 8)
    monkeypatch.setattr(store, "list_profiles", lambda: (_ for _ in ()).throw(busy_error))
    retrying_client = TestClient(app, raise_server_exceptions=False)

    busy_response = retrying_client.get("/api/profiles", auth=_auth())

    assert busy_response.status_code == 503
    assert busy_response.headers["retry-after"] == "1"
    assert busy_response.json() == {"detail": "database is busy; retry shortly"}

    io_error = sqlite3.OperationalError("disk I/O error")
    io_error.sqlite_errorcode = sqlite3.SQLITE_IOERR
    monkeypatch.setattr(store, "list_profiles", lambda: (_ for _ in ()).throw(io_error))
    propagating_client = TestClient(app)

    with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
        propagating_client.get("/api/profiles", auth=_auth())


def test_calendar_delete_waits_for_in_flight_sync(tmp_path: Path, monkeypatch) -> None:
    class BlockingPublisher(RecordingPublisher):
        def __init__(self) -> None:
            super().__init__()
            self.started = Event()
            self.release = Event()

        def sync(self, *args):
            self.started.set()
            if not self.release.wait(5):
                raise TimeoutError("test did not release CalDAV sync")
            return super().sync(*args)

    store = Store(tmp_path / "serialized.db")
    publisher = BlockingPublisher()
    app = main_module.create_app(
        store=store,
        username="operator",
        password="correct-horse-battery-staple",
        publisher=publisher,
    )
    client = TestClient(app)
    profile = _create_profile(client)
    calendar = _create_calendar(client, str(profile["id"]))
    delete_requested = Event()
    delete_entered = Event()
    original_delete = store.delete_calendar

    def observed_delete(calendar_id: str) -> bool:
        delete_entered.set()
        return original_delete(calendar_id)

    monkeypatch.setattr(store, "delete_calendar", observed_delete)

    def sync():
        return client.post(
            f"/api/calendars/{calendar['id']}/sync",
            auth=_auth(),
            json={"start_date": "2000-01-01", "end_date": "2000-01-01"},
        )

    def delete():
        delete_requested.set()
        return client.delete(f"/api/calendars/{calendar['id']}", auth=_auth())

    with ThreadPoolExecutor(max_workers=2) as executor:
        sync_future = executor.submit(sync)
        sync_started = publisher.started.wait(5)
        delete_future = executor.submit(delete)
        delete_started = delete_requested.wait(5)
        delete_reached_store_during_sync = delete_entered.wait(0.2)
        publisher.release.set()
        sync_response = sync_future.result(timeout=10)
        delete_response = delete_future.result(timeout=10)

    assert sync_started
    assert delete_started
    assert not delete_reached_store_during_sync
    assert sync_response.status_code == 200
    assert delete_response.status_code == 204

def test_profile_erasure_review_contracts_are_enforced(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    script = client.get("/static/app.js").text
    styles = client.get("/static/styles.css").text

    assert "profile.birth_calendar === \"lunar\" && profile.is_leap_month" in script
    assert "aria-label=\"\${escapeHtml(profile.name)} 출생 정보 삭제\"" in script
    assert "function refreshPairProfileChoices()" in script
    refresh_call = script.index("refreshPairProfileChoices();")
    empty_profiles = script.index("if (!state.profiles.length)", refresh_call)
    assert refresh_call < empty_profiles
    assert '\$("#chart-profile-name").textContent = "";' in script
    assert '\$("#pillars").textContent = "";' in script
    assert "출생 정보 삭제 완료, 목록 갱신 실패:" in script
    strong_rule = styles.split(".profile-copy strong {", 1)[1].split("}", 1)[0]
    assert "overflow-wrap: anywhere;" in strong_rule


def test_delete_attempts_remote_cleanup_when_sync_marking_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = Store(tmp_path / "mark-failure.db")
    publisher = RecordingPublisher()
    app = main_module.create_app(
        store=store,
        username="operator",
        password="correct-horse-battery-staple",
        publisher=publisher,
    )
    client = TestClient(app)
    profile = _create_profile(client)
    calendar = _create_calendar(client, str(profile["id"]))

    def fail_mark_synced(calendar_id: str) -> None:
        del calendar_id
        raise RuntimeError("synthetic sync marker failure")

    monkeypatch.setattr(store, "mark_synced", fail_mark_synced)

    with pytest.raises(RuntimeError, match="synthetic sync marker failure"):
        client.post(
            f"/api/calendars/{calendar['id']}/sync",
            auth=_auth(),
            json={"start_date": "2000-01-01", "end_date": "2000-01-01"},
        )

    deleted = client.delete(f"/api/calendars/{calendar['id']}", auth=_auth())

    assert deleted.status_code == 204
    assert publisher.calls
    assert publisher.delete_calls == [
        {"calendar_id": calendar["id"], "slug": calendar["slug"]}
    ]

