from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.events import generate_windows, iter_chart_windows
from app.main import DateRange, _resolve_date_range
from app.rules import validate_rule
from app.saju import calculate_chart


def _natal_chart():
    return calculate_chart(datetime(2000, 1, 1, 12, 15), "Asia/Seoul", "civil", None)


def _public_example_rule():
    return validate_rule(
        {
            "logic": "all",
            "predicates": [
                {"field": "day.branch", "source": "natal", "value": "day.branch"},
                {"field": "hour.stem", "source": "literal", "value": "戊"},
            ],
        }
    )


def test_rule_generates_the_expected_public_example_window() -> None:
    windows = generate_windows(
        _public_example_rule(),
        _natal_chart(),
        date(2000, 1, 1),
        date(2000, 1, 1),
        "Asia/Seoul",
        "civil",
        None,
    )

    assert len(windows) == 1
    assert windows[0].start.timetz().replace(tzinfo=None) == time(11)
    assert windows[0].end.timetz().replace(tzinfo=None) == time(13)
    assert windows[0].chart.day.ganzhi == "戊午"
    assert windows[0].chart.hour.ganzhi == "戊午"


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
        date(2000, 1, 1),
        date(2000, 1, 1),
        "Asia/Seoul",
        "civil",
        None,
    )

    assert [(window.start.hour, window.end.hour) for window in windows] == [(0, 1), (23, 0)]


def test_true_solar_mode_shifts_civil_calendar_boundaries() -> None:
    windows = generate_windows(
        _public_example_rule(),
        _natal_chart(),
        date(2000, 1, 1),
        date(2000, 1, 1),
        "Asia/Seoul",
        "true_solar",
        126.978,
    )

    assert len(windows) == 1
    assert time(11, 20) < windows[0].start.timetz().replace(tzinfo=None) < time(11, 50)


def test_generation_range_is_bounded() -> None:
    with pytest.raises(ValueError, match="730 days"):
        generate_windows(
            _public_example_rule(),
            _natal_chart(),
            date(2026, 1, 1),
            date(2028, 1, 1),
            "Asia/Seoul",
            "civil",
            None,
        )


def test_generation_range_uses_inclusive_boundaries() -> None:
    assert next(
        iter_chart_windows(
            date(2026, 1, 1),
            date(2026, 1, 1),
            "Asia/Seoul",
            "civil",
            None,
        )
    ).start.date() == date(2026, 1, 1)
    assert next(
        iter_chart_windows(
            date(2026, 1, 1),
            date(2026, 1, 1) + timedelta(days=729),
            "Asia/Seoul",
            "civil",
            None,
        )
    ).start.date() == date(2026, 1, 1)
    with pytest.raises(ValueError, match="730 days"):
        next(
            iter_chart_windows(
                date(2026, 1, 1),
                date(2026, 1, 1) + timedelta(days=730),
                "Asia/Seoul",
                "civil",
                None,
            )
        )


def test_default_range_uses_profile_timezone_at_utc_date_boundary() -> None:
    start, end = _resolve_date_range(
        DateRange(),
        ZoneInfo("Asia/Seoul"),
        datetime(2026, 1, 1, 23, 30, tzinfo=UTC),
    )
    assert start == date(2026, 1, 2)
    assert end == date(2027, 1, 2)


@pytest.mark.parametrize(
    ("transition_date", "expected_start_offset", "expected_end_offset"),
    [
        (date(2024, 3, 10), timedelta(hours=-5), timedelta(hours=-4)),
        (date(2024, 11, 3), timedelta(hours=-4), timedelta(hours=-5)),
    ],
)
def test_dst_windows_follow_zoneinfo_default_fold_and_gap_semantics(
    transition_date: date,
    expected_start_offset: timedelta,
    expected_end_offset: timedelta,
) -> None:
    window = next(
        candidate
        for candidate in iter_chart_windows(
            transition_date,
            transition_date,
            "America/New_York",
            "civil",
            None,
        )
        if candidate.start.hour == 1
    )
    assert window.start.fold == 0
    assert window.start.utcoffset() == expected_start_offset
    assert window.end.utcoffset() == expected_end_offset


def test_generation_rejects_reversed_range_and_incomplete_true_solar_mode() -> None:
    with pytest.raises(ValueError, match="before start_date"):
        list(
            iter_chart_windows(
                date(2000, 1, 2),
                date(2000, 1, 1),
                "Asia/Seoul",
                "civil",
                None,
            )
        )
    with pytest.raises(ValueError, match="requires longitude"):
        list(
            iter_chart_windows(
                date(2000, 1, 1),
                date(2000, 1, 1),
                "Asia/Seoul",
                "true_solar",
                None,
            )
        )


@pytest.mark.parametrize(
    ("time_mode", "longitude"),
    [("civil", None), ("true_solar", 126.978)],
)
def test_optimized_window_charts_match_direct_midpoint_calculation(
    time_mode: str,
    longitude: float | None,
) -> None:
    windows = list(
        iter_chart_windows(
            date(2000, 1, 1),
            date(2000, 1, 1),
            "Asia/Seoul",
            time_mode,
            longitude,
        )
    )

    for window in windows:
        civil_midpoint = window.start.replace(tzinfo=None) + (
            window.end.replace(tzinfo=None) - window.start.replace(tzinfo=None)
        ) / 2
        direct = calculate_chart(
            civil_midpoint,
            "Asia/Seoul",
            time_mode,
            longitude,
        )
        assert window.chart.year == direct.year
        assert window.chart.month == direct.month
        assert window.chart.day == direct.day
        assert window.chart.hour == direct.hour


def test_window_charts_follow_an_intraday_solar_term_transition() -> None:
    windows = list(
        iter_chart_windows(
            date(2024, 2, 4),
            date(2024, 2, 4),
            "Asia/Seoul",
            "civil",
            None,
        )
    )

    before = next(window for window in windows if window.start.hour == 15)
    after = next(window for window in windows if window.start.hour == 17)

    assert before.chart.year.ganzhi == "癸卯"
    assert before.chart.month.ganzhi == "乙丑"
    assert after.chart.year.ganzhi == "甲辰"
    assert after.chart.month.ganzhi == "丙寅"
