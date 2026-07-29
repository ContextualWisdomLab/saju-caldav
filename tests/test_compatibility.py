from datetime import date, datetime

from app.compatibility import generate_compatibility_candidates, score_window
from app.events import MatchingWindow
from app.saju import Chart, Pillar, calculate_chart


def _chart(day_branch: str) -> Chart:
    return Chart(
        year=Pillar("甲", "子"),
        month=Pillar("丙", "寅"),
        day=Pillar("戊", day_branch),
        hour=Pillar("庚", "申"),
        calculation_local=datetime(2000, 1, 1, 12),
    )


def test_balanced_score_rewards_both_people_and_explains_it_in_korean() -> None:
    current = Chart(
        year=Pillar("己", "卯"),
        month=Pillar("丙", "子"),
        day=Pillar("戊", "午"),
        hour=Pillar("己", "未"),
        calculation_local=datetime(2000, 1, 1, 14),
    )
    window = MatchingWindow(
        start=datetime(2000, 1, 1, 13),
        end=datetime(2000, 1, 1, 15),
        chart=current,
    )

    candidate = score_window(
        window,
        _chart("午"),
        _chart("未"),
        "나",
        "상대",
    )

    assert candidate is not None
    assert candidate.score >= 70
    assert candidate.primary_score >= 60
    assert candidate.secondary_score >= 60
    assert any("나의 일지" in reason for reason in candidate.reasons)
    assert any("상대의 일지" in reason for reason in candidate.reasons)


def test_a_clash_for_either_person_is_not_recommended() -> None:
    current = Chart(
        year=Pillar("己", "卯"),
        month=Pillar("丙", "子"),
        day=Pillar("戊", "子"),
        hour=Pillar("戊", "午"),
        calculation_local=datetime(2000, 1, 1, 12),
    )
    window = MatchingWindow(
        start=datetime(2000, 1, 1, 11),
        end=datetime(2000, 1, 1, 13),
        chart=current,
    )

    assert score_window(window, _chart("午"), _chart("未"), "나", "상대") is None


def test_generator_returns_at_most_one_upcoming_time_per_day() -> None:
    primary = calculate_chart(
        datetime(2000, 1, 1, 12, 15),
        "Asia/Seoul",
        "civil",
        None,
    )
    secondary = calculate_chart(
        datetime(2000, 1, 2, 12, 15),
        "Asia/Seoul",
        "civil",
        None,
    )

    candidates = generate_compatibility_candidates(
        primary,
        secondary,
        "나",
        "상대",
        date(2000, 1, 1),
        date(2000, 1, 31),
        "Asia/Seoul",
        "civil",
        None,
        limit=12,
    )

    assert candidates
    assert len(candidates) <= 12
    assert len({candidate.window.start.date() for candidate in candidates}) == len(
        candidates
    )
    assert candidates == sorted(candidates, key=lambda candidate: candidate.window.start)
    assert all(candidate.score >= 60 for candidate in candidates)


def test_generator_defaults_to_practical_hours_and_can_include_overnight() -> None:
    practical = generate_compatibility_candidates(
        _chart("子"),
        _chart("子"),
        "나",
        "상대",
        date(2026, 7, 29),
        date(2027, 7, 29),
        "Asia/Seoul",
        "civil",
        None,
        limit=96,
    )
    all_day = generate_compatibility_candidates(
        _chart("子"),
        _chart("子"),
        "나",
        "상대",
        date(2026, 7, 29),
        date(2027, 7, 29),
        "Asia/Seoul",
        "civil",
        None,
        limit=96,
        include_overnight=True,
    )

    assert practical
    assert {
        (candidate.window.start.hour, candidate.window.end.hour)
        for candidate in practical
    } == {
        (15, 17),
    }
    assert any(candidate.window.start.hour == 1 for candidate in all_day)


def test_generator_applies_current_time_before_choosing_each_days_best() -> None:
    primary = calculate_chart(
        datetime(2000, 1, 1, 12, 15),
        "Asia/Seoul",
        "civil",
        None,
    )
    secondary = calculate_chart(
        datetime(2000, 1, 2, 12, 15),
        "Asia/Seoul",
        "civil",
        None,
    )
    original = generate_compatibility_candidates(
        primary,
        secondary,
        "나",
        "상대",
        date(2000, 1, 1),
        date(2000, 1, 31),
        "Asia/Seoul",
        "civil",
        None,
        limit=12,
    )
    assert original
    current = original[0].window.end

    upcoming = generate_compatibility_candidates(
        primary,
        secondary,
        "나",
        "상대",
        date(2000, 1, 1),
        date(2000, 1, 31),
        "Asia/Seoul",
        "civil",
        None,
        limit=12,
        not_before=current,
    )

    assert upcoming
    assert all(candidate.window.end > current for candidate in upcoming)


def test_generator_tie_breaks_with_the_full_start_time(monkeypatch) -> None:
    chart = _chart("午")
    candidate_chart = Chart(
        year=chart.year,
        month=chart.month,
        day=chart.day,
        hour=Pillar("己", "未"),
        calculation_local=chart.calculation_local,
    )
    later = MatchingWindow(
        start=datetime(2000, 1, 1, 11, 40),
        end=datetime(2000, 1, 1, 13, 40),
        chart=candidate_chart,
    )
    earlier = MatchingWindow(
        start=datetime(2000, 1, 1, 11, 20),
        end=datetime(2000, 1, 1, 13, 20),
        chart=candidate_chart,
    )
    monkeypatch.setattr(
        "app.compatibility.iter_chart_windows",
        lambda *args, **kwargs: iter((later, earlier)),
    )

    candidates = generate_compatibility_candidates(
        chart,
        chart,
        "나",
        "상대",
        date(2000, 1, 1),
        date(2000, 1, 1),
        "Asia/Seoul",
        "civil",
        None,
    )

    assert len(candidates) == 1
    assert candidates[0].window.start == earlier.start
