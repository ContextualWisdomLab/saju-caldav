from pathlib import Path

from fastapi.testclient import TestClient

from app.caldav import SyncResult
from app.main import create_app
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
    app = create_app(
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
            "name": "1990년 샘플",
            "birth_local": "1990-06-15T08:30:00",
            "gender": "female",
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
            "name": "내 亥日의 壬時",
            "slug": "my-hai-ren-hours",
            "rule": {
                "logic": "all",
                "predicates": [
                    {"field": "day.branch", "source": "natal", "value": "day.branch"},
                    {"field": "hour.stem", "source": "literal", "value": "壬"},
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
    assert profile["chart"]["day"] == {
        "stem": "辛",
        "branch": "亥",
        "ganzhi": "辛亥",
        "stem_element": "金",
        "branch_element": "水",
    }
    assert profile["chart"]["hour"]["stem"] == "壬"
    assert profile["gender"] == "female"

    calendar = _create_calendar(client, str(profile["id"]))
    preview = client.post(
        f"/api/calendars/{calendar['id']}/preview",
        auth=_auth(),
        json={"start_date": "1990-06-15", "end_date": "1990-06-15"},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["count"] == 1
    assert preview.json()["events"][0]["start"] == "1990-06-15T07:00:00+09:00"
    assert preview.json()["events"][0]["hour_pillar"] == "壬辰"

    synced = client.post(
        f"/api/calendars/{calendar['id']}/sync",
        auth=_auth(),
        json={"start_date": "1990-06-15", "end_date": "1990-06-15"},
    )
    assert synced.status_code == 200, synced.text
    assert synced.json() == {
        "collection_url": "https://cal.example/operator/my-hai-ren-hours/",
        "event_count": 1,
    }
    assert publisher.calls[0]["slug"] == "my-hai-ren-hours"


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
