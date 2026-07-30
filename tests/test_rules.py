from datetime import datetime

import pytest

from app.rules import matches, validate_rule
from app.saju import calculate_chart


def _acceptance_chart():
    return calculate_chart(datetime(2000, 1, 1, 12, 15), "Asia/Seoul", "civil", None)


def test_natal_day_branch_and_literal_hour_stem_match() -> None:
    natal = _acceptance_chart()
    rule = validate_rule(
        {
            "logic": "all",
            "predicates": [
                {"field": "day.branch", "source": "natal", "value": "day.branch"},
                {"field": "hour.stem", "source": "literal", "value": "戊"},
            ],
        }
    )

    assert matches(rule, natal=natal, current=natal)


def test_unknown_rule_fields_are_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported field"):
        validate_rule(
            {
                "logic": "all",
                "predicates": [
                    {"field": "python.eval", "source": "literal", "value": "壬"}
                ],
            }
        )


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"logic": "neither", "predicates": [{}]}, "logic"),
        ({"logic": "all", "predicates": []}, "predicates"),
        ({"logic": "all", "predicates": ["bad"]}, "object"),
        (
            {
                "logic": "all",
                "predicates": [{"field": "day.stem", "source": "bad", "value": "甲"}],
            },
            "source",
        ),
        (
            {
                "logic": "all",
                "predicates": [{"field": "day.stem", "source": "literal", "value": 1}],
            },
            "string",
        ),
        (
            {
                "logic": "all",
                "predicates": [{"field": "day.stem", "source": "literal", "value": "子"}],
            },
            "invalid literal",
        ),
        (
            {
                "logic": "all",
                "predicates": [{"field": "day.stem", "source": "natal", "value": "bad"}],
            },
            "unsupported natal",
        ),
        (
            {
                "logic": "all",
                "predicates": [{"field": "day.stem", "source": "natal", "value": "hour.branch"}],
            },
            "same value type",
        ),
    ],
)
def test_invalid_rule_shapes_are_rejected(data: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_rule(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [("day.stem_element", "土"), ("day.branch_element", "火")],
)
def test_element_literals_are_supported(field: str, value: str) -> None:
    assert validate_rule(
        {
            "logic": "any",
            "predicates": [{"field": field, "source": "literal", "value": value}],
        }
    )
