import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

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
        birth_city="seoul",
        birth_city_name="대한민국 · 서울",
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
        visibility="private",
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
    assert store.get_profile(profile["id"])["birth_time_known"] is True
    assert store.get_profile(profile["id"])["birth_city"] == "seoul"
    assert store.get_calendar(calendar["id"])["visibility"] == "private"
    assert store.get_calendar(calendar["id"])["rule"]["predicates"][1]["value"] == "戊"
    assert len(store.list_profiles()) == 1
    assert len(store.list_calendars(profile["id"])) == 1
    assert len(store.list_calendars()) == 1

    assert store.delete_profile(profile["id"])
    assert store.get_calendar(calendar["id"]) is None
    assert not store.delete_calendar(str(calendar["id"]))


def test_store_enables_wal_and_busy_timeout(tmp_path: Path) -> None:
    store = Store(tmp_path / "concurrency.db")
    store.initialize()

    with store._connect() as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

    assert journal_mode == "wal"
    assert busy_timeout == 10_000


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
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_redundant_profile_backfill
            BEFORE UPDATE ON profiles
            BEGIN
                SELECT RAISE(FAIL, 'fully backfilled profiles must not be updated');
            END
            """
        )
    store.initialize()

    profile = store.get_profile("legacy")
    assert profile is not None
    assert profile["birth_calendar"] == "solar"
    assert profile["birth_year"] == 2001
    assert profile["birth_month"] == 2
    assert profile["birth_day"] == 3
    assert profile["birth_time"] == "04:05:06"
    assert profile["birth_time_known"] is True
    assert profile["is_leap_month"] == 0
    assert profile["birth_city"] is None
    assert profile["birth_city_name"] is None

    calendar_columns = {
        row[1]
        for row in sqlite3.connect(database).execute("PRAGMA table_info(calendars)")
    }
    assert "visibility" in calendar_columns
    assert "kind" in calendar_columns
    assert "secondary_profile_id" in calendar_columns


def test_unknown_birth_time_round_trip_stays_unknown_after_reinitialize(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "unknown-time.db")
    store.initialize()
    profile = store.create_profile(
        name="태어난 시각 미상",
        birth_calendar="solar",
        birth_year=2000,
        birth_month=1,
        birth_day=2,
        birth_time=None,
        birth_time_known=False,
        is_leap_month=False,
        birth_local=datetime(2000, 1, 2, 12),
        birth_city="seoul",
        birth_city_name="대한민국 · 서울",
        gender="unspecified",
        timezone="Asia/Seoul",
        time_mode="civil",
        longitude=None,
        chart={"day": {"stem": "己", "branch": "未"}, "hour": None},
    )

    store.initialize()
    reloaded = store.get_profile(str(profile["id"]))

    assert reloaded is not None
    assert reloaded["birth_time"] is None
    assert reloaded["birth_time_known"] is False
    assert reloaded["chart"]["hour"] is None


def test_create_defensive_checks_and_calendar_delete(tmp_path: Path, monkeypatch) -> None:
    store = Store(tmp_path / "defensive.db")
    store.initialize()
    profile_arguments = {
        "name": "방어 경로",
        "birth_calendar": "solar",
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_time": "12:00:00",
        "is_leap_month": False,
        "birth_local": datetime(2000, 1, 1, 12),
        "birth_city": "seoul",
        "birth_city_name": "대한민국 · 서울",
        "gender": "unspecified",
        "timezone": "Asia/Seoul",
        "time_mode": "civil",
        "longitude": None,
        "chart": {},
    }
    with monkeypatch.context() as scoped:
        scoped.setattr(store, "get_profile", lambda profile_id: None)
        with pytest.raises(RuntimeError, match="created profile"):
            store.create_profile(**profile_arguments)

    profile = store.list_profiles()[0]
    with monkeypatch.context() as scoped:
        scoped.setattr(store, "get_calendar", lambda calendar_id: None)
        with pytest.raises(RuntimeError, match="created calendar"):
            store.create_calendar(
                profile_id=str(profile["id"]),
                name="방어 달력",
                slug="defensive-calendar",
                visibility="private",
                rule={},
            )

    calendar = store.list_calendars()[0]
    assert store.delete_calendar(str(calendar["id"]))
