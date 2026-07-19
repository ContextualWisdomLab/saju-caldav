from datetime import datetime
from pathlib import Path

from app.store import Store


def test_profile_and_calendar_round_trip_and_cascade(tmp_path: Path) -> None:
    store = Store(tmp_path / "saju.db")
    store.initialize()
    profile = store.create_profile(
        name="샘플'); DROP TABLE profiles; --",
        birth_local=datetime(1990, 6, 15, 8, 30),
        gender="female",
        timezone="Asia/Seoul",
        time_mode="civil",
        longitude=None,
        chart={"day": {"stem": "辛", "branch": "亥"}},
    )
    calendar = store.create_calendar(
        profile_id=profile["id"],
        name="내 亥日의 壬時",
        slug="my-hai-ren-hours",
        rule={
            "logic": "all",
            "predicates": [
                {"field": "day.branch", "source": "natal", "value": "day.branch"},
                {"field": "hour.stem", "source": "literal", "value": "壬"},
            ],
        },
    )

    assert store.get_profile(profile["id"])["chart"]["day"]["branch"] == "亥"
    assert store.get_calendar(calendar["id"])["rule"]["predicates"][1]["value"] == "壬"
    assert len(store.list_profiles()) == 1
    assert len(store.list_calendars(profile["id"])) == 1

    assert store.delete_profile(profile["id"])
    assert store.get_calendar(calendar["id"]) is None

