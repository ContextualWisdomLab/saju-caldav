import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.store import Store


def test_profile_and_calendar_round_trip_and_cascade(tmp_path: Path) -> None:
    store = Store(tmp_path / "saju.db")
    store.initialize()
    profile = store.create_profile(
        name="샘플'); DROP TABLE profiles; --",
        birth_calendar="solar",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_time="12:15:00",
        is_leap_month=False,
        birth_local=datetime(2000, 1, 1, 12, 15),
        gender="unspecified",
        timezone="Asia/Seoul",
        time_mode="civil",
        longitude=None,
        chart={"day": {"stem": "戊", "branch": "午"}},
    )
    calendar = store.create_calendar(
        profile_id=profile["id"],
        name="나의 맞춤 시간",
        slug="my-custom-hours",
        rule={
            "logic": "all",
            "predicates": [
                {"field": "day.branch", "source": "natal", "value": "day.branch"},
                {"field": "hour.stem", "source": "literal", "value": "戊"},
            ],
        },
    )

    assert store.get_profile(profile["id"])["chart"]["day"]["branch"] == "午"
    assert store.get_profile(profile["id"])["birth_calendar"] == "solar"
    assert store.get_calendar(calendar["id"])["rule"]["predicates"][1]["value"] == "戊"
    assert len(store.list_profiles()) == 1
    assert len(store.list_calendars(profile["id"])) == 1

    assert store.delete_profile(profile["id"])
    assert store.get_calendar(calendar["id"]) is None


def test_initialize_migrates_and_backfills_legacy_profiles(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                birth_local TEXT NOT NULL,
                gender TEXT NOT NULL,
                timezone TEXT NOT NULL,
                time_mode TEXT NOT NULL,
                longitude REAL,
                chart_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE calendars (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                rule_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_synced_at TEXT
            );
            """
        )
        connection.execute(
            """
            INSERT INTO profiles
                (id, name, birth_local, gender, timezone, time_mode, longitude,
                 chart_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy",
                "기존 프로필",
                "2001-02-03T04:05:06",
                "unspecified",
                "Asia/Seoul",
                "civil",
                None,
                json.dumps({"day": {"stem": "甲", "branch": "子"}}),
                datetime.now(UTC).isoformat(),
            ),
        )

    store = Store(database)
    store.initialize()
    store.initialize()

    profile = store.get_profile("legacy")
    assert profile is not None
    assert profile["birth_calendar"] == "solar"
    assert profile["birth_year"] == 2001
    assert profile["birth_month"] == 2
    assert profile["birth_day"] == 3
    assert profile["birth_time"] == "04:05:06"
    assert profile["is_leap_month"] == 0
