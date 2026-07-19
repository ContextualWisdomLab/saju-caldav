"""Normalize solar and Korean lunar birth input to Gregorian local time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal

from korean_lunar_calendar import KoreanLunarCalendar


@dataclass(frozen=True, slots=True)
class BirthInput:
    calendar: Literal["solar", "lunar"]
    year: int
    month: int
    day: int
    at: time
    is_leap_month: bool = False


def normalize_birth(value: BirthInput) -> datetime:
    """Return a naive Gregorian wall time for a validated birth input."""

    if value.calendar == "solar":
        if value.is_leap_month:
            raise ValueError("양력에는 윤달을 지정할 수 없습니다")
        try:
            solar_date = date(value.year, value.month, value.day)
        except ValueError as error:
            raise ValueError("유효하지 않은 양력 날짜입니다") from error
        return datetime.combine(solar_date, value.at)

    converter = KoreanLunarCalendar()
    if not converter.setLunarDate(
        value.year,
        value.month,
        value.day,
        value.is_leap_month,
    ):
        raise ValueError("지원하지 않거나 존재하지 않는 한국 음력·윤달 날짜입니다")
    return datetime(
        converter.solarYear,
        converter.solarMonth,
        converter.solarDay,
        value.at.hour,
        value.at.minute,
        value.at.second,
    )
