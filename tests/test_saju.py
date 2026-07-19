from datetime import datetime
from zoneinfo import ZoneInfoNotFoundError

import pytest

from app.saju import calculate_chart


def test_acceptance_birth_chart_is_xinhai_and_renchen() -> None:
    chart = calculate_chart(datetime(1990, 6, 15, 8, 30), "Asia/Seoul", "civil", None)

    assert chart.year.ganzhi == "庚午"
    assert chart.month.ganzhi == "壬午"
    assert chart.day.ganzhi == "辛亥"
    assert chart.day.branch == "亥"
    assert chart.day.branch_element == "水"
    assert chart.hour.ganzhi == "壬辰"
    assert chart.hour.stem == "壬"
    assert chart.hour.stem_element == "水"


def test_true_solar_time_requires_longitude() -> None:
    with pytest.raises(ValueError, match="longitude is required"):
        calculate_chart(datetime(1990, 6, 15, 8, 30), "Asia/Seoul", "true_solar", None)


def test_true_solar_time_applies_seoul_longitude_correction() -> None:
    chart = calculate_chart(
        datetime(1990, 6, 15, 8, 30),
        "Asia/Seoul",
        "true_solar",
        126.978,
    )

    assert datetime(1990, 6, 15, 7, 45) < chart.calculation_local < datetime(
        1990, 6, 15, 8, 5
    )
    assert chart.day.ganzhi == "辛亥"
    assert chart.hour.ganzhi == "壬辰"


def test_invalid_timezone_and_longitude_are_rejected() -> None:
    with pytest.raises(ZoneInfoNotFoundError):
        calculate_chart(datetime(1990, 6, 15, 8, 30), "Mars/Olympus", "civil", None)
    with pytest.raises(ValueError, match="between -180 and 180"):
        calculate_chart(datetime(1990, 6, 15, 8, 30), "Asia/Seoul", "true_solar", 181)


def test_midnight_changes_the_day_inside_the_split_zi_hour() -> None:
    before_midnight = calculate_chart(
        datetime(1990, 6, 15, 23, 30), "Asia/Seoul", "civil", None
    )
    after_midnight = calculate_chart(
        datetime(1990, 6, 16, 0, 30), "Asia/Seoul", "civil", None
    )

    assert before_midnight.hour.branch == after_midnight.hour.branch == "子"
    assert before_midnight.day != after_midnight.day
    assert before_midnight.hour.stem != after_midnight.hour.stem
