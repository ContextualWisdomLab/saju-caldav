"""Run an opt-in private chart and future-window regression without logging inputs."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.events import generate_windows
from app.rules import validate_rule
from app.saju import calculate_chart


def main() -> None:
    birth_local = datetime.fromisoformat(os.environ["PRIVATE_BIRTH_LOCAL"])
    if birth_local.tzinfo is not None:
        raise ValueError("PRIVATE_BIRTH_LOCAL must be a local wall time without an offset")

    timezone = os.environ.get("PRIVATE_TIMEZONE", "Asia/Seoul")
    expected_day_branch = os.environ["PRIVATE_EXPECT_DAY_BRANCH"]
    expected_hour_stem = os.environ["PRIVATE_EXPECT_HOUR_STEM"]
    chart = calculate_chart(birth_local, timezone, "civil", None)

    assert chart.day.branch == expected_day_branch
    assert chart.hour.stem == expected_hour_stem

    today = datetime.now(ZoneInfo(timezone)).date()
    rule = validate_rule(
        {
            "logic": "all",
            "predicates": [
                {"field": "day.branch", "source": "natal", "value": "day.branch"},
                {
                    "field": "hour.stem",
                    "source": "literal",
                    "value": expected_hour_stem,
                },
            ],
        }
    )
    windows = generate_windows(
        rule,
        chart,
        today,
        today + timedelta(days=365),
        timezone,
        "civil",
        None,
    )
    assert windows
    assert all(window.start.date() >= today for window in windows)
    print(f"PRIVATE_REGRESSION_OK matched_windows={len(windows)}")


if __name__ == "__main__":
    main()
