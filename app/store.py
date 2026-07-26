"""Small parameterized SQLite metadata store."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    birth_local TEXT NOT NULL,
                    birth_calendar TEXT NOT NULL DEFAULT 'solar',
                    birth_year INTEGER,
                    birth_month INTEGER,
                    birth_day INTEGER,
                    birth_time TEXT,
                    birth_time_known INTEGER NOT NULL DEFAULT 1,
                    is_leap_month INTEGER NOT NULL DEFAULT 0,
                    birth_city TEXT,
                    birth_city_name TEXT,
                    gender TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    time_mode TEXT NOT NULL,
                    longitude REAL,
                    chart_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS calendars (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    visibility TEXT NOT NULL DEFAULT 'private',
                    rule_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_synced_at TEXT
                );
                """
            )
            profile_columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(profiles)")
            }
            if "birth_calendar" not in profile_columns:
                connection.execute(
                    "ALTER TABLE profiles ADD COLUMN birth_calendar "
                    "TEXT NOT NULL DEFAULT 'solar'"
                )
            if "birth_year" not in profile_columns:
                connection.execute("ALTER TABLE profiles ADD COLUMN birth_year INTEGER")
            if "birth_month" not in profile_columns:
                connection.execute("ALTER TABLE profiles ADD COLUMN birth_month INTEGER")
            if "birth_day" not in profile_columns:
                connection.execute("ALTER TABLE profiles ADD COLUMN birth_day INTEGER")
            if "birth_time" not in profile_columns:
                connection.execute("ALTER TABLE profiles ADD COLUMN birth_time TEXT")
            if "birth_time_known" not in profile_columns:
                connection.execute(
                    "ALTER TABLE profiles ADD COLUMN birth_time_known "
                    "INTEGER NOT NULL DEFAULT 1"
                )
            if "is_leap_month" not in profile_columns:
                connection.execute(
                    "ALTER TABLE profiles ADD COLUMN is_leap_month "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            if "birth_city" not in profile_columns:
                connection.execute("ALTER TABLE profiles ADD COLUMN birth_city TEXT")
            if "birth_city_name" not in profile_columns:
                connection.execute("ALTER TABLE profiles ADD COLUMN birth_city_name TEXT")
            calendar_columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(calendars)")
            }
            if "visibility" not in calendar_columns:
                connection.execute(
                    "ALTER TABLE calendars ADD COLUMN visibility "
                    "TEXT NOT NULL DEFAULT 'private'"
                )
            if "kind" not in calendar_columns:
                connection.execute(
                    "ALTER TABLE calendars ADD COLUMN kind "
                    "TEXT NOT NULL DEFAULT 'rule'"
                )
            if "secondary_profile_id" not in calendar_columns:
                connection.execute(
                    "ALTER TABLE calendars ADD COLUMN secondary_profile_id TEXT"
                )
            connection.execute(
                """
                UPDATE profiles
                SET birth_year = COALESCE(
                        birth_year, CAST(substr(birth_local, 1, 4) AS INTEGER)
                    ),
                    birth_month = COALESCE(
                        birth_month, CAST(substr(birth_local, 6, 2) AS INTEGER)
                    ),
                    birth_day = COALESCE(
                        birth_day, CAST(substr(birth_local, 9, 2) AS INTEGER)
                    )
                WHERE birth_year IS NULL
                   OR birth_month IS NULL
                   OR birth_day IS NULL
                """
            )
            connection.execute(
                """
                UPDATE profiles
                SET birth_time = substr(birth_local, 12)
                WHERE birth_time_known = 1
                  AND birth_time IS NULL
                """
            )

    @staticmethod
    def _profile(row: sqlite3.Row | None) -> dict[str, object] | None:
        if row is None:
            return None
        result = dict(row)
        result["birth_time_known"] = bool(result["birth_time_known"])
        result["chart"] = json.loads(str(result.pop("chart_json")))
        return result

    @staticmethod
    def _calendar(row: sqlite3.Row | None) -> dict[str, object] | None:
        if row is None:
            return None
        result = dict(row)
        result["rule"] = json.loads(str(result.pop("rule_json")))
        return result

    def create_profile(
        self,
        *,
        name: str,
        birth_calendar: str,
        birth_year: int,
        birth_month: int,
        birth_day: int,
        birth_time: str | None,
        is_leap_month: bool,
        birth_local: datetime,
        birth_city: str | None,
        birth_city_name: str | None,
        gender: str,
        timezone: str,
        time_mode: str,
        longitude: float | None,
        chart: dict[str, object],
        birth_time_known: bool = True,
    ) -> dict[str, object]:
        profile_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO profiles
                    (id, name, birth_local, birth_calendar, birth_year, birth_month,
                     birth_day, birth_time, birth_time_known, is_leap_month,
                     birth_city, birth_city_name,
                     gender, timezone, time_mode, longitude, chart_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    name,
                    birth_local.isoformat(),
                    birth_calendar,
                    birth_year,
                    birth_month,
                    birth_day,
                    birth_time,
                    int(birth_time_known),
                    int(is_leap_month),
                    birth_city,
                    birth_city_name,
                    gender,
                    timezone,
                    time_mode,
                    longitude,
                    json.dumps(chart, ensure_ascii=False, separators=(",", ":")),
                    datetime.now(UTC).isoformat(),
                ),
            )
        profile = self.get_profile(profile_id)
        if profile is None:
            raise RuntimeError("created profile was not found")
        return profile

    def get_profile(self, profile_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM profiles WHERE id = ?", (profile_id,)
            ).fetchone()
        return self._profile(row)

    def list_profiles(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM profiles ORDER BY created_at, id").fetchall()
        return [profile for row in rows if (profile := self._profile(row)) is not None]

    def delete_profile(self, profile_id: str) -> bool:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM calendars WHERE secondary_profile_id = ?",
                (profile_id,),
            )
            cursor = connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        return cursor.rowcount == 1

    def create_calendar(
        self,
        *,
        profile_id: str,
        name: str,
        slug: str,
        visibility: str,
        rule: dict[str, object],
        kind: str = "rule",
        secondary_profile_id: str | None = None,
    ) -> dict[str, object]:
        calendar_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO calendars
                    (id, profile_id, secondary_profile_id, name, slug, visibility,
                     kind, rule_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    calendar_id,
                    profile_id,
                    secondary_profile_id,
                    name,
                    slug,
                    visibility,
                    kind,
                    json.dumps(rule, ensure_ascii=False, separators=(",", ":")),
                    datetime.now(UTC).isoformat(),
                ),
            )
        calendar = self.get_calendar(calendar_id)
        if calendar is None:
            raise RuntimeError("created calendar was not found")
        return calendar

    def get_calendar(self, calendar_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM calendars WHERE id = ?", (calendar_id,)
            ).fetchone()
        return self._calendar(row)

    def list_calendars(self, profile_id: str | None = None) -> list[dict[str, object]]:
        with self._connect() as connection:
            if profile_id is None:
                rows = connection.execute(
                    "SELECT * FROM calendars ORDER BY created_at, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM calendars WHERE profile_id = ? ORDER BY created_at, id",
                    (profile_id,),
                ).fetchall()
        return [calendar for row in rows if (calendar := self._calendar(row)) is not None]

    def delete_calendar(self, calendar_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM calendars WHERE id = ?", (calendar_id,))
        return cursor.rowcount == 1

    def mark_synced(self, calendar_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE calendars SET last_synced_at = ? WHERE id = ?",
                (datetime.now(UTC).isoformat(), calendar_id),
            )
