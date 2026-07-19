from datetime import date, datetime, time

import pytest

from app.events import generate_windows
from app.rules import validate_rule
from app.saju import calculate_chart


def _natal_chart():
    return calculate_chart(datetime(1990, 6, 15, 8, 30), "Asia/Seoul", "civil", None)


def _hai_day_ren_hour_rule():
    return validate_rule(
        {
            "logic": "all",
            "predicates": [
                {"field": "day.branch", "source": "natal", "value": "day.branch"},
                {"field": "hour.stem", "source": "literal", "value": "壬"},
            ],
        }
    )


def test_acceptance_rule_generates_the_renchen_window() -> None:
    windows = generate_windows(
        _hai_day_ren_hour_rule(),
        _natal_chart(),
        date(1990, 6, 15),
        date(1990, 6, 15),
        "Asia/Seoul",
        "civil",
        None,
    )

    assert len(windows) == 1
    assert windows[0].start.timetz().replace(tzinfo=None) == time(7)
    assert windows[0].end.timetz().replace(tzinfo=None) == time(9)
    assert windows[0].chart.day.ganzhi == "辛亥"
    assert windows[0].chart.hour.ganzhi == "壬辰"


def test_zi_hour_is_split_at_civil_midnight() -> None:
    rule = validate_rule(
        {
            "logic": "all",
            "predicates": [
                {"field": "hour.branch", "source": "literal", "value": "子"}
            ],
        }
    )

    windows = generate_windows(
        rule,
        _natal_chart(),
        date(1990, 6, 15),
        date(1990, 6, 15),
        "Asia/Seoul",
        "civil",
        None,
    )

    assert [(window.start.hour, window.end.hour) for window in windows] == [(0, 1), (23, 0)]


def test_true_solar_mode_shifts_civil_calendar_boundaries() -> None:
    windows = generate_windows(
        _hai_day_ren_hour_rule(),
        _natal_chart(),
        date(1990, 6, 15),
        date(1990, 6, 15),
        "Asia/Seoul",
        "true_solar",
        126.978,
    )

    assert len(windows) == 1
    assert time(7, 20) < windows[0].start.timetz().replace(tzinfo=None) < time(7, 45)


def test_generation_range_is_bounded() -> None:
    with pytest.raises(ValueError, match="730 days"):
        generate_windows(
            _hai_day_ren_hour_rule(),
            _natal_chart(),
            date(2026, 1, 1),
            date(2028, 1, 1),
            "Asia/Seoul",
            "civil",
            None,
        )

