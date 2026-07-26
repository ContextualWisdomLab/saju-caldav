"""Generate bounded calendar windows from validated Saju rules."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.rules import Rule, matches
from app.saju import Chart, _hour_pillar, _true_solar_time, calculate_chart

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

    return [
        window
        for window in iter_chart_windows(
            start_date,
            end_date,
            timezone,
            time_mode,
            longitude,
        )
        if matches(rule, natal=natal, current=window.chart)
    ]


def iter_chart_windows(
    start_date: date,
    end_date: date,
    timezone: str,
    time_mode: str,
    longitude: float | None,
) -> Iterator[MatchingWindow]:
    """Yield every local double-hour window with its calculated chart."""

    if end_date < start_date:
        raise ValueError("end_date must not be before start_date")
    if (end_date - start_date).days + 1 > 730:
        raise ValueError("generation range must not exceed 730 days")

    zone = ZoneInfo(timezone)
    for day_offset in range((end_date - start_date).days + 1):
        calculation_date = start_date + timedelta(days=day_offset)
        midnight = datetime.combine(calculation_date, time.min)
        end_of_day = midnight + timedelta(days=1, microseconds=-1)
        civil_midnight = _civil_from_calculation_time(
            midnight,
            zone,
            time_mode,
            longitude,
        )
        civil_end_of_day = _civil_from_calculation_time(
            end_of_day,
            zone,
            time_mode,
            longitude,
        )
        start_chart = calculate_chart(civil_midnight, timezone, time_mode, longitude)
        end_chart = calculate_chart(civil_end_of_day, timezone, time_mode, longitude)
        has_pillar_transition = (
            start_chart.year != end_chart.year
            or start_chart.month != end_chart.month
        )
        for start_hour, end_hour in SEGMENTS:
            calculation_start = midnight + timedelta(hours=start_hour)
            calculation_end = midnight + timedelta(hours=end_hour)
            civil_start = _civil_from_calculation_time(
                calculation_start, zone, time_mode, longitude
            )
            civil_end = _civil_from_calculation_time(calculation_end, zone, time_mode, longitude)
            calculation_midpoint = calculation_start + (
                calculation_end - calculation_start
            ) / 2
            civil_midpoint = _civil_from_calculation_time(
                calculation_midpoint,
                zone,
                time_mode,
                longitude,
            )
            current = (
                calculate_chart(civil_midpoint, timezone, time_mode, longitude)
                if has_pillar_transition
                else Chart(
                    year=start_chart.year,
                    month=start_chart.month,
                    day=start_chart.day,
                    hour=_hour_pillar(
                        start_chart.day.stem,
                        calculation_midpoint.hour,
                    ),
                    calculation_local=calculation_midpoint,
                )
            )
            yield MatchingWindow(
                start=civil_start.replace(tzinfo=zone),
                end=civil_end.replace(tzinfo=zone),
                chart=current,
            )
