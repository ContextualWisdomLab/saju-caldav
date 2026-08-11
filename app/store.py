"""Small parameterized SQLite metadata store."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.identity import TenantScope


class Store:
    """Persist profiles and calendar definitions in a small SQLite database."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        """Create or migrate the local schema without rewriting stored data."""

        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
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
                    owner_subject TEXT NOT NULL DEFAULT 'legacy:operator',
                    tenant_organization TEXT NOT NULL DEFAULT 'legacy',
                    tenant_workspace TEXT NOT NULL DEFAULT 'legacy',
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
            if "owner_subject" not in profile_columns:
                connection.execute(
                    "ALTER TABLE profiles ADD COLUMN owner_subject TEXT "
                    "NOT NULL DEFAULT 'legacy:operator'"
                )
            if "tenant_organization" not in profile_columns:
                connection.execute(
                    "ALTER TABLE profiles ADD COLUMN tenant_organization TEXT "
                    "NOT NULL DEFAULT 'legacy'"
                )
            if "tenant_workspace" not in profile_columns:
                connection.execute(
                    "ALTER TABLE profiles ADD COLUMN tenant_workspace TEXT "
                    "NOT NULL DEFAULT 'legacy'"
                )
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
                CREATE INDEX IF NOT EXISTS profiles_owner_scope
                ON profiles(owner_subject, tenant_organization, tenant_workspace)
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
        for private_field in ("owner_subject", "tenant_organization", "tenant_workspace"):
            result.pop(private_field, None)
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
        owner_subject: str = "legacy:operator",
        tenant_organization: str = "legacy",
        tenant_workspace: str = "legacy",
    ) -> dict[str, object]:
        """Insert a profile and return its normalized stored representation."""

        profile_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO profiles
                    (id, name, birth_local, birth_calendar, birth_year, birth_month,
                     birth_day, birth_time, birth_time_known, is_leap_month,
                     birth_city, birth_city_name,
                     gender, timezone, time_mode, longitude,
                     owner_subject, tenant_organization, tenant_workspace,
                     chart_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    owner_subject,
                    tenant_organization,
                    tenant_workspace,
                    json.dumps(chart, ensure_ascii=False, separators=(",", ":")),
                    datetime.now(UTC).isoformat(),
                ),
            )
        profile = self.get_profile(profile_id)
        if profile is None:
            raise RuntimeError("created profile was not found")
        return profile

    def get_profile(
        self,
        profile_id: str,
        scope: TenantScope | None = None,
    ) -> dict[str, object] | None:
        """Load one profile by identifier, or return ``None`` when absent."""

        with self._connect() as connection:
            if scope is None:
                row = connection.execute(
                    "SELECT * FROM profiles WHERE id = ?", (profile_id,)
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT * FROM profiles
                    WHERE id = ? AND owner_subject = ?
                      AND tenant_organization = ? AND tenant_workspace = ?
                    """,
                    (
                        profile_id,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                    ),
                ).fetchone()
        return self._profile(row)

    def list_profiles(self, scope: TenantScope | None = None) -> list[dict[str, object]]:
        """Return profiles in deterministic creation order."""

        with self._connect() as connection:
            if scope is None:
                rows = connection.execute(
                    "SELECT * FROM profiles ORDER BY created_at, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM profiles
                    WHERE owner_subject = ? AND tenant_organization = ?
                      AND tenant_workspace = ?
                    ORDER BY created_at, id
                    """,
                    (scope.subject, scope.organization, scope.workspace),
                ).fetchall()
        return [profile for row in rows if (profile := self._profile(row)) is not None]

    def delete_profile(
        self,
        profile_id: str,
        scope: TenantScope | None = None,
    ) -> bool:
        """Delete a profile and compatibility calendars that reference it secondarily."""

        with self._connect() as connection:
            if scope is not None:
                owned = connection.execute(
                    """
                    SELECT 1 FROM profiles
                    WHERE id = ? AND owner_subject = ?
                      AND tenant_organization = ? AND tenant_workspace = ?
                    """,
                    (
                        profile_id,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                    ),
                ).fetchone() is not None
                if not owned:
                    return False
            if scope is None:
                connection.execute(
                    "DELETE FROM calendars WHERE secondary_profile_id = ?",
                    (profile_id,),
                )
            else:
                connection.execute(
                    """
                    DELETE FROM calendars
                    WHERE secondary_profile_id = ? AND profile_id IN (
                        SELECT id FROM profiles
                        WHERE owner_subject = ? AND tenant_organization = ?
                          AND tenant_workspace = ?
                    )
                    """,
                    (
                        profile_id,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                    ),
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
        scope: TenantScope | None = None,
    ) -> dict[str, object]:
        """Insert a rule or compatibility calendar and return its stored form."""

        if secondary_profile_id == profile_id:
            raise ValueError("primary and secondary profiles must differ")
        calendar_id = str(uuid4())
        with self._connect() as connection:
            if scope is not None:
                if secondary_profile_id is None:
                    owned = connection.execute(
                        """
                        SELECT count(*) FROM profiles
                        WHERE id = ? AND owner_subject = ?
                          AND tenant_organization = ? AND tenant_workspace = ?
                        """,
                        (
                            profile_id,
                            scope.subject,
                            scope.organization,
                            scope.workspace,
                        ),
                    ).fetchone()[0]
                    expected_profiles = 1
                else:
                    owned = connection.execute(
                        """
                        SELECT count(*) FROM profiles
                        WHERE id IN (?, ?) AND owner_subject = ?
                          AND tenant_organization = ? AND tenant_workspace = ?
                        """,
                        (
                            profile_id,
                            secondary_profile_id,
                            scope.subject,
                            scope.organization,
                            scope.workspace,
                        ),
                    ).fetchone()[0]
                    expected_profiles = 2
                if owned != expected_profiles:
                    raise PermissionError("profile is outside the caller tenant")
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
        # Keep the legacy Basic call shape for integrations that override the
        # unscoped lookup; tenant-aware callers still pass the verified scope.
        calendar = (
            self.get_calendar(calendar_id)
            if scope is None
            else self.get_calendar(calendar_id, scope)
        )
        if calendar is None:
            raise RuntimeError("created calendar was not found")
        return calendar

    def get_calendar(
        self,
        calendar_id: str,
        scope: TenantScope | None = None,
    ) -> dict[str, object] | None:
        """Load one calendar by identifier, or return ``None`` when absent."""

        with self._connect() as connection:
            if scope is None:
                row = connection.execute(
                    "SELECT * FROM calendars WHERE id = ?", (calendar_id,)
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT c.* FROM calendars AS c
                    JOIN profiles AS p ON p.id = c.profile_id
                    LEFT JOIN profiles AS sp ON sp.id = c.secondary_profile_id
                    WHERE c.id = ? AND p.owner_subject = ?
                      AND p.tenant_organization = ? AND p.tenant_workspace = ?
                      AND (c.secondary_profile_id IS NULL OR (
                          sp.owner_subject = ? AND sp.tenant_organization = ?
                          AND sp.tenant_workspace = ?
                      ))
                    """,
                    (
                        calendar_id,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                    ),
                ).fetchone()
        return self._calendar(row)

    def list_calendars(
        self,
        profile_id: str | None = None,
        scope: TenantScope | None = None,
    ) -> list[dict[str, object]]:
        """Return calendars in deterministic order, optionally by primary profile."""

        with self._connect() as connection:
            if scope is not None:
                rows = connection.execute(
                    """
                    SELECT c.* FROM calendars AS c
                    JOIN profiles AS p ON p.id = c.profile_id
                    LEFT JOIN profiles AS sp ON sp.id = c.secondary_profile_id
                    WHERE p.owner_subject = ?
                      AND p.tenant_organization = ?
                      AND p.tenant_workspace = ?
                      AND (? IS NULL OR c.profile_id = ?)
                      AND (c.secondary_profile_id IS NULL OR (
                          sp.owner_subject = ? AND sp.tenant_organization = ?
                          AND sp.tenant_workspace = ?
                      ))
                    ORDER BY c.created_at, c.id
                    """,
                    [
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                        profile_id,
                        profile_id,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                    ],
                ).fetchall()
            elif profile_id is None:
                rows = connection.execute(
                    "SELECT * FROM calendars ORDER BY created_at, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM calendars WHERE profile_id = ? ORDER BY created_at, id",
                    (profile_id,),
                ).fetchall()
        return [calendar for row in rows if (calendar := self._calendar(row)) is not None]

    def list_calendars_for_profile(
        self,
        profile_id: str,
        scope: TenantScope | None = None,
    ) -> list[dict[str, object]]:
        """Return calendars where a profile is either person in the match."""

        with self._connect() as connection:
            if scope is None:
                rows = connection.execute(
                    """
                    SELECT * FROM calendars
                    WHERE profile_id = ? OR secondary_profile_id = ?
                    ORDER BY created_at, id
                    """,
                    (profile_id, profile_id),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT c.* FROM calendars AS c
                    JOIN profiles AS p ON p.id = c.profile_id
                    LEFT JOIN profiles AS sp ON sp.id = c.secondary_profile_id
                    WHERE (c.profile_id = ? OR c.secondary_profile_id = ?)
                      AND p.owner_subject = ?
                      AND p.tenant_organization = ? AND p.tenant_workspace = ?
                      AND (c.secondary_profile_id IS NULL OR (
                          sp.owner_subject = ? AND sp.tenant_organization = ?
                          AND sp.tenant_workspace = ?
                      ))
                    ORDER BY c.created_at, c.id
                    """,
                    (
                        profile_id,
                        profile_id,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                    ),
                ).fetchall()
        return [calendar for row in rows if (calendar := self._calendar(row)) is not None]

    def delete_calendar(
        self,
        calendar_id: str,
        scope: TenantScope | None = None,
    ) -> bool:
        """Delete one local calendar metadata record."""

        with self._connect() as connection:
            if scope is None:
                cursor = connection.execute(
                    "DELETE FROM calendars WHERE id = ?", (calendar_id,)
                )
            else:
                cursor = connection.execute(
                    """
                    DELETE FROM calendars
                    WHERE id = ? AND profile_id IN (
                        SELECT id FROM profiles
                        WHERE owner_subject = ? AND tenant_organization = ?
                          AND tenant_workspace = ?
                    ) AND (secondary_profile_id IS NULL OR secondary_profile_id IN (
                        SELECT id FROM profiles
                        WHERE owner_subject = ? AND tenant_organization = ?
                          AND tenant_workspace = ?
                    ))
                    """,
                    (
                        calendar_id,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                    ),
                )
        return cursor.rowcount == 1

    def mark_synced(
        self,
        calendar_id: str,
        scope: TenantScope | None = None,
    ) -> None:
        """Record the UTC time at which a calendar was last published."""

        with self._connect() as connection:
            if scope is None:
                connection.execute(
                    "UPDATE calendars SET last_synced_at = ? WHERE id = ?",
                    (datetime.now(UTC).isoformat(), calendar_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE calendars SET last_synced_at = ?
                    WHERE id = ? AND profile_id IN (
                        SELECT id FROM profiles
                        WHERE owner_subject = ? AND tenant_organization = ?
                          AND tenant_workspace = ?
                    ) AND (secondary_profile_id IS NULL OR secondary_profile_id IN (
                        SELECT id FROM profiles
                        WHERE owner_subject = ? AND tenant_organization = ?
                          AND tenant_workspace = ?
                    ))
                    """,
                    (
                        datetime.now(UTC).isoformat(),
                        calendar_id,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                        scope.subject,
                        scope.organization,
                        scope.workspace,
                    ),
                )
