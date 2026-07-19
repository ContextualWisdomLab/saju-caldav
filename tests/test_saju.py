from datetime import datetime
from zoneinfo import ZoneInfoNotFoundError

import pytest

from app.saju import Pillar, calculate_chart


def test_public_example_chart_is_deterministic() -> None:
    chart = calculate_chart(datetime(2000, 1, 1, 12, 15), "Asia/Seoul", "civil", None)

    assert chart.year.ganzhi == "己卯"
    assert chart.month.ganzhi == "丙子"
    assert chart.day.ganzhi == "戊午"
    assert chart.hour.ganzhi == "戊午"


def test_pillar_explains_symbols_in_korean() -> None:
    pillar = Pillar("壬", "亥")

    assert pillar.stem_korean == "임수"
    assert pillar.stem_description == "양의 성질을 가진 큰물"
    assert pillar.branch_korean == "해수"
    assert pillar.branch_description == "십이지의 돼지, 오행으로는 물"


def test_true_solar_time_requires_longitude() -> None:
    with pytest.raises(ValueError, match="longitude is required"):
        calculate_chart(datetime(2000, 1, 1, 12, 15), "Asia/Seoul", "true_solar", None)


def test_true_solar_time_applies_seoul_longitude_correction() -> None:
    chart = calculate_chart(
        datetime(2000, 1, 1, 12, 15),
        "Asia/Seoul",
        "true_solar",
        126.978,
    )

    assert datetime(2000, 1, 1, 11, 30) < chart.calculation_local < datetime(
        2000, 1, 1, 11, 50
    )
    assert chart.day.ganzhi == "戊午"
    assert chart.hour.ganzhi == "戊午"


def test_invalid_timezone_and_longitude_are_rejected() -> None:
    with pytest.raises(ZoneInfoNotFoundError):
        calculate_chart(datetime(2000, 1, 1, 12, 15), "Mars/Olympus", "civil", None)
    with pytest.raises(ValueError, match="between -180 and 180"):
        calculate_chart(datetime(2000, 1, 1, 12, 15), "Asia/Seoul", "true_solar", 181)


def test_midnight_changes_the_day_inside_the_split_zi_hour() -> None:
    before_midnight = calculate_chart(
        datetime(2000, 1, 1, 23, 30), "Asia/Seoul", "civil", None
    )
    after_midnight = calculate_chart(
        datetime(2000, 1, 2, 0, 30), "Asia/Seoul", "civil", None
    )

    assert before_midnight.hour.branch == after_midnight.hour.branch == "子"
    assert before_midnight.day != after_midnight.day
    assert before_midnight.hour.stem != after_midnight.hour.stem


def test_ipchun_changes_year_and_month_pillars_at_the_solar_term() -> None:
    before = calculate_chart(
        datetime(2024, 2, 4, 16, 20), "Asia/Seoul", "civil", None
    )
    after = calculate_chart(
        datetime(2024, 2, 4, 17, 20), "Asia/Seoul", "civil", None
    )

    assert before.year.ganzhi == "癸卯"
    assert before.month.ganzhi == "乙丑"
    assert after.year.ganzhi == "甲辰"
    assert after.month.ganzhi == "丙寅"
