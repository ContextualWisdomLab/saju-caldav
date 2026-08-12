"""Transparent, culturally grounded two-person date ranking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal

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
CompatibilityMode = Literal["pair_relation_activation", "shared_branch_relations"]
PAIR_RELATION_MODE: CompatibilityMode = "pair_relation_activation"
SHARED_RELATIONS_MODE: CompatibilityMode = "shared_branch_relations"
LEGACY_SHARED_METHOD = "balanced_branch_harmony"
POSITIVE_RELATIONS = frozenset(("six_harmony", "three_harmony", "same"))
PAIR_BASE_POINTS = {
    "six_harmony": 18,
    "three_harmony": 12,
    "same": 8,
    "neutral": 0,
    "clash": -30,
}


@dataclass(frozen=True, slots=True)
class CompatibilityCandidate:
    """Represent one transparent, non-predictive two-person time candidate."""

    window: MatchingWindow
    score: int
    primary_score: int
    secondary_score: int
    personal_score: int
    relationship_score: int
    label: str
    reasons: tuple[str, ...]


def normalize_compatibility_mode(value: str | None) -> CompatibilityMode:
    """Normalize the public mode names and the pre-ADR legacy method."""

    if value in (None, LEGACY_SHARED_METHOD, SHARED_RELATIONS_MODE):
        return SHARED_RELATIONS_MODE
    if value == PAIR_RELATION_MODE:
        return PAIR_RELATION_MODE
    raise ValueError(
        "지원하지 않는 두 사람 시간 기준입니다: "
        f"{value!r}; 사용할 수 있는 값: {PAIR_RELATION_MODE}, {SHARED_RELATIONS_MODE}"
    )


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


def _pair_activation(candidate: str, primary: str, secondary: str) -> str:
    """Return a relation only when one candidate branch connects both people."""

    primary_relation = _relation(candidate, primary)
    secondary_relation = _relation(candidate, secondary)
    if (
        primary_relation not in POSITIVE_RELATIONS
        or secondary_relation not in POSITIVE_RELATIONS
    ):
        return "neutral"
    return min(
        (primary_relation, secondary_relation),
        key=lambda relation: DAY_POINTS[relation],
    )


def _relationship_score(
    baseline: str,
    day_activation: str,
    hour_activation: str,
) -> int:
    return max(
        0,
        min(
            100,
            50
            + PAIR_BASE_POINTS[baseline]
            + DAY_POINTS[day_activation]
            + HOUR_POINTS[hour_activation],
        ),
    )


def _reason(person: str, period: str, relation: str) -> str | None:
    relation_labels = {
        "six_harmony": "육합 관계",
        "three_harmony": "삼합 계열 관계",
        "same": "같은 지지 관계",
    }
    if relation not in relation_labels:
        return None
    return f"{period}의 지지가 {person}의 일지와 {relation_labels[relation]}입니다."


def _label(score: int) -> str:
    if score >= 80:
        return "공통 관계 기준이 많이 겹치는 시간"
    if score >= 70:
        return "두 사람의 관계 기준이 고르게 겹치는 시간"
    return "두 사람의 관계 기준을 함께 참고할 시간"


def _relationship_label(score: int) -> str:
    if score >= 80:
        return "두 사람의 관계 작용이 함께 활성화되는 시간"
    if score >= 70:
        return "두 사람의 관계 연결을 함께 살피는 시간"
    return "두 사람의 관계와 개인 조건을 함께 참고할 시간"


def _pair_reason(primary_name: str, secondary_name: str, relation: str) -> str | None:
    relation_labels = {
        "six_harmony": "육합 관계",
        "three_harmony": "삼합 계열 관계",
        "same": "같은 지지 관계",
    }
    label = relation_labels.get(relation)
    if label is None:
        return None
    return f"{primary_name}과 {secondary_name}의 일지가 {label}입니다."


def _activation_reason(period: str, relation: str) -> str | None:
    relation_labels = {
        "six_harmony": "두 사람의 일지를 함께 잇는 육합 관계",
        "three_harmony": "두 사람의 일지를 함께 잇는 삼합 계열 관계",
        "same": "두 사람의 일지와 같은 지지 관계",
    }
    label = relation_labels.get(relation)
    if label is None:
        return None
    return f"{period}의 지지가 {label}로 작용합니다."


def _personal_scores(
    window: MatchingWindow,
    primary: Chart,
    secondary: Chart,
) -> tuple[int, int, tuple[str, ...]]:
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
    return (
        _bounded_score(primary_day_relation, primary_hour_relation),
        _bounded_score(secondary_day_relation, secondary_hour_relation),
        relations,
    )


def score_window(
    window: MatchingWindow,
    primary: Chart,
    secondary: Chart,
    primary_name: str,
    secondary_name: str,
    mode: str = PAIR_RELATION_MODE,
) -> CompatibilityCandidate | None:
    """Score one window using a named, non-predictive interpretation mode."""

    normalized_mode = normalize_compatibility_mode(mode)
    current_day = window.chart.day.branch
    current_hour = window.chart.hour.branch
    primary_score, secondary_score, relations = _personal_scores(
        window,
        primary,
        secondary,
    )
    if "clash" in relations:
        return None

    personal_lower = min(primary_score, secondary_score)
    personal_average = (primary_score + secondary_score) / 2
    personal_score = round(personal_lower * 0.7 + personal_average * 0.3)
    baseline = _relation(primary.day.branch, secondary.day.branch)
    day_activation = _pair_activation(
        current_day, primary.day.branch, secondary.day.branch
    )
    hour_activation = _pair_activation(
        current_hour, primary.day.branch, secondary.day.branch
    )
    relationship_score = _relationship_score(
        baseline,
        day_activation,
        hour_activation,
    )

    if normalized_mode == SHARED_RELATIONS_MODE:
        if (
            personal_score < MINIMUM_SCORE
            or all(relation == "neutral" for relation in relations)
        ):
            return None
        reasons = tuple(
            reason
            for reason in (
                _reason(primary_name, "이 날짜", relations[0]),
                _reason(secondary_name, "이 날짜", relations[1]),
                _reason(primary_name, "이 시간", relations[2]),
                _reason(secondary_name, "이 시간", relations[3]),
            )
            if reason is not None
        )
        return CompatibilityCandidate(
            window=window,
            score=personal_score,
            primary_score=primary_score,
            secondary_score=secondary_score,
            personal_score=personal_score,
            relationship_score=relationship_score,
            label=_label(personal_score),
            reasons=reasons,
        )

    if (
        baseline == "clash"
        or personal_lower < MINIMUM_SCORE
        or (
            day_activation == "neutral"
            and hour_activation == "neutral"
        )
        or relationship_score < MINIMUM_SCORE
    ):
        return None

    reasons = tuple(
        reason
        for reason in (
            _pair_reason(primary_name, secondary_name, baseline),
            _activation_reason("이 날짜", day_activation),
            _activation_reason("이 시간", hour_activation),
            _reason(primary_name, "이 날짜", relations[0]),
            _reason(secondary_name, "이 날짜", relations[1]),
        )
        if reason is not None
    )
    return CompatibilityCandidate(
        window=window,
        score=relationship_score,
        primary_score=primary_score,
        secondary_score=secondary_score,
        personal_score=personal_score,
        relationship_score=relationship_score,
        label=_relationship_label(relationship_score),
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
    include_overnight: bool = False,
    mode: str = PAIR_RELATION_MODE,
) -> list[CompatibilityCandidate]:
    """Return the highest-scoring candidate per day for the selected mode."""

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
        if not include_overnight and (
            window.start.date() != window.end.date()
            or window.start.time() < time(9)
            or window.end.time() > time(23)
        ):
            continue
        candidate = score_window(
            window,
            primary,
            secondary,
            primary_name,
            secondary_name,
            mode,
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
