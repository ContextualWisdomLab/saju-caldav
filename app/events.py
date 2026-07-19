"""Generate bounded calendar windows from validated Saju rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.rules import Rule, matches
from app.saju import Chart, _true_solar_time, calculate_chart

SEGMENTS = ((0, 1),) + tuple((hour, hour + 2) for hour in range(1, 22, 2)) + ((23, 24),)


@dataclass(frozen=True, slots=True)
class MatchingWindow:
    start: datetime
    end: datetime
    chart: Chart


def _civil_from_calculation_time(
    calculation_local: datetime,
    zone: ZoneInfo,
    time_mode: str,
    longitude: float | None,
) -> datetime:
    if time_mode == "civil":
        return calculation_local
    if time_mode != "true_solar" or longitude is None:
        raise ValueError("true_solar mode requires longitude")

    guess = calculation_local
    for _ in range(4):
        corrected = _true_solar_time(guess, zone, longitude)
        guess += calculation_local - corrected
    return guess


def generate_windows(
    rule: Rule,
    natal: Chart,
    start_date: date,
    end_date: date,
    timezone: str,
    time_mode: str,
    longitude: float | None,
) -> list[MatchingWindow]:
    """Return matching local-time intervals, inclusive of both boundary dates."""

    if end_date < start_date:
        raise ValueError("end_date must not be before start_date")
    if (end_date - start_date).days + 1 > 730:
        raise ValueError("generation range must not exceed 730 days")

    zone = ZoneInfo(timezone)
    windows: list[MatchingWindow] = []
    for day_offset in range((end_date - start_date).days + 1):
        calculation_date = start_date + timedelta(days=day_offset)
        midnight = datetime.combine(calculation_date, time.min)
        for start_hour, end_hour in SEGMENTS:
            calculation_start = midnight + timedelta(hours=start_hour)
            calculation_end = midnight + timedelta(hours=end_hour)
            civil_start = _civil_from_calculation_time(
                calculation_start, zone, time_mode, longitude
            )
            civil_end = _civil_from_calculation_time(calculation_end, zone, time_mode, longitude)
            civil_midpoint = civil_start + (civil_end - civil_start) / 2
            current = calculate_chart(civil_midpoint, timezone, time_mode, longitude)
            if matches(rule, natal=natal, current=current):
                windows.append(
                    MatchingWindow(
                        start=civil_start.replace(tzinfo=zone),
                        end=civil_end.replace(tzinfo=zone),
                        chart=current,
                    )
                )
    return windows

