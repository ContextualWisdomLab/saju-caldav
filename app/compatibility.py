"""Transparent, culturally grounded two-person date ranking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.events import MatchingWindow, iter_chart_windows
from app.saju import Chart

SIX_HARMONIES = (
    frozenset(("子", "丑")),
    frozenset(("寅", "亥")),
    frozenset(("卯", "戌")),
    frozenset(("辰", "酉")),
    frozenset(("巳", "申")),
    frozenset(("午", "未")),
)
THREE_HARMONIES = (
    frozenset(("申", "子", "辰")),
    frozenset(("亥", "卯", "未")),
    frozenset(("寅", "午", "戌")),
    frozenset(("巳", "酉", "丑")),
)
SIX_CLASHES = (
    frozenset(("子", "午")),
    frozenset(("丑", "未")),
    frozenset(("寅", "申")),
    frozenset(("卯", "酉")),
    frozenset(("辰", "戌")),
    frozenset(("巳", "亥")),
)

DAY_POINTS = {
    "six_harmony": 24,
    "three_harmony": 16,
    "same": 8,
    "neutral": 0,
    "clash": -32,
}
HOUR_POINTS = {
    "six_harmony": 12,
    "three_harmony": 8,
    "same": 4,
    "neutral": 0,
    "clash": -16,
}
MINIMUM_SCORE = 60


@dataclass(frozen=True, slots=True)
class CompatibilityCandidate:
    window: MatchingWindow
    score: int
    primary_score: int
    secondary_score: int
    label: str
    reasons: tuple[str, ...]


def _relation(left: str, right: str) -> str:
    if left == right:
        return "same"
    pair = frozenset((left, right))
    if pair in SIX_HARMONIES:
        return "six_harmony"
    if any(pair <= group for group in THREE_HARMONIES):
        return "three_harmony"
    if pair in SIX_CLASHES:
        return "clash"
    return "neutral"


def _bounded_score(day_relation: str, hour_relation: str) -> int:
    return max(
        0,
        min(100, 50 + DAY_POINTS[day_relation] + HOUR_POINTS[hour_relation]),
    )


def _reason(person: str, period: str, relation: str) -> str | None:
    relation_labels = {
        "six_harmony": "서로 짝을 이루는 육합",
        "three_harmony": "같은 흐름을 이루는 삼합 계열",
        "same": "같은 지지",
    }
    if relation not in relation_labels:
        return None
    return f"{period}의 기운이 {person}의 일지와 {relation_labels[relation]}입니다."


def _label(score: int) -> str:
    if score >= 80:
        return "두 사람 모두에게 조화가 큰 시간"
    if score >= 70:
        return "두 사람에게 고르게 잘 맞는 시간"
    return "두 사람에게 무난하게 어울리는 시간"


def score_window(
    window: MatchingWindow,
    primary: Chart,
    secondary: Chart,
    primary_name: str,
    secondary_name: str,
) -> CompatibilityCandidate | None:
    """Score one window without presenting the convention as a prediction."""

    current_day = window.chart.day.branch
    current_hour = window.chart.hour.branch
    primary_day_relation = _relation(current_day, primary.day.branch)
    secondary_day_relation = _relation(current_day, secondary.day.branch)
    primary_hour_relation = _relation(current_hour, primary.day.branch)
    secondary_hour_relation = _relation(current_hour, secondary.day.branch)
    relations = (
        primary_day_relation,
        secondary_day_relation,
        primary_hour_relation,
        secondary_hour_relation,
    )
    if "clash" in relations:
        return None

    primary_score = _bounded_score(primary_day_relation, primary_hour_relation)
    secondary_score = _bounded_score(secondary_day_relation, secondary_hour_relation)
    lower = min(primary_score, secondary_score)
    average = (primary_score + secondary_score) / 2
    score = round(lower * 0.7 + average * 0.3)
    if score < MINIMUM_SCORE or all(relation == "neutral" for relation in relations):
        return None

    reasons = tuple(
        reason
        for reason in (
            _reason(primary_name, "이 날짜", primary_day_relation),
            _reason(secondary_name, "이 날짜", secondary_day_relation),
            _reason(primary_name, "이 시간", primary_hour_relation),
            _reason(secondary_name, "이 시간", secondary_hour_relation),
        )
        if reason is not None
    )
    return CompatibilityCandidate(
        window=window,
        score=score,
        primary_score=primary_score,
        secondary_score=secondary_score,
        label=_label(score),
        reasons=reasons,
    )


def generate_compatibility_candidates(
    primary: Chart,
    secondary: Chart,
    primary_name: str,
    secondary_name: str,
    start_date: date,
    end_date: date,
    timezone: str,
    time_mode: str,
    longitude: float | None,
    limit: int = 24,
    not_before: datetime | None = None,
) -> list[CompatibilityCandidate]:
    """Return the highest-scoring candidate per day, breaking ties by start time."""

    if not 1 <= limit <= 96:
        raise ValueError("limit must be between 1 and 96")

    best_by_date: dict[date, CompatibilityCandidate] = {}
    for window in iter_chart_windows(
        start_date,
        end_date,
        timezone,
        time_mode,
        longitude,
    ):
        if not_before is not None and window.end <= not_before:
            continue
        candidate = score_window(
            window,
            primary,
            secondary,
            primary_name,
            secondary_name,
        )
        if candidate is None:
            continue
        candidate_date = candidate.window.start.date()
        previous = best_by_date.get(candidate_date)
        if previous is None or (
            candidate.score > previous.score
            or (
                candidate.score == previous.score
                and candidate.window.start < previous.window.start
            )
        ):
            best_by_date[candidate_date] = candidate

    return sorted(
        best_by_date.values(),
        key=lambda candidate: candidate.window.start,
    )[:limit]
