"""Validated, non-executable calendar matching rules."""

from __future__ import annotations

from dataclasses import dataclass

from app.saju import BRANCH_ELEMENTS, BRANCHES, STEM_ELEMENTS, STEMS, Chart

ALLOWED_FIELDS = frozenset(
    f"{pillar}.{attribute}"
    for pillar in ("day", "hour")
    for attribute in ("stem", "branch", "stem_element", "branch_element")
)


@dataclass(frozen=True, slots=True)
class Predicate:
    """Describe one field comparison against a literal or natal chart field."""

    field: str
    source: str
    value: str


@dataclass(frozen=True, slots=True)
class Rule:
    """Represent a validated conjunction or disjunction of predicates."""

    logic: str
    predicates: tuple[Predicate, ...]


def _field_value(chart: Chart, field: str) -> str:
    pillar_name, attribute = field.split(".", 1)
    return str(getattr(getattr(chart, pillar_name), attribute))


def _allowed_literals(field: str) -> set[str]:
    attribute = field.split(".", 1)[1]
    if attribute == "stem":
        return set(STEMS)
    if attribute == "branch":
        return set(BRANCHES)
    if attribute == "stem_element":
        return set(STEM_ELEMENTS.values())
    return set(BRANCH_ELEMENTS.values())


def validate_rule(data: dict[str, object]) -> Rule:
    """Validate untrusted JSON into the non-executable rule representation."""

    logic = data.get("logic")
    if logic not in {"all", "any"}:
        raise ValueError("logic must be all or any")

    raw_predicates = data.get("predicates")
    if not isinstance(raw_predicates, list) or not 1 <= len(raw_predicates) <= 8:
        raise ValueError("predicates must contain between 1 and 8 items")

    predicates: list[Predicate] = []
    for raw in raw_predicates:
        if not isinstance(raw, dict):
            raise ValueError("each predicate must be an object")
        field = raw.get("field")
        source = raw.get("source")
        value = raw.get("value")
        if not isinstance(field, str) or field not in ALLOWED_FIELDS:
            raise ValueError(f"unsupported field: {field}")
        if source not in {"literal", "natal"}:
            raise ValueError("predicate source must be literal or natal")
        if not isinstance(value, str):
            raise ValueError("predicate value must be a string")
        if source == "literal" and value not in _allowed_literals(field):
            raise ValueError(f"invalid literal for {field}: {value}")
        if source == "natal":
            if value not in ALLOWED_FIELDS:
                raise ValueError(f"unsupported natal field: {value}")
            if field.split(".", 1)[1] != value.split(".", 1)[1]:
                raise ValueError("natal field must have the same value type")
        predicates.append(Predicate(field=field, source=source, value=value))

    return Rule(logic=str(logic), predicates=tuple(predicates))


def matches(rule: Rule, natal: Chart, current: Chart) -> bool:
    """Evaluate a validated rule against natal and current charts."""

    results = (
        _field_value(current, predicate.field)
        == (
            predicate.value
            if predicate.source == "literal"
            else _field_value(natal, predicate.value)
        )
        for predicate in rule.predicates
    )
    return all(results) if rule.logic == "all" else any(results)
