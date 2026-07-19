from datetime import datetime

import pytest

from app.rules import matches, validate_rule
from app.saju import calculate_chart


def _acceptance_chart():
    return calculate_chart(datetime(1990, 6, 15, 8, 30), "Asia/Seoul", "civil", None)


def test_natal_day_branch_and_literal_hour_stem_match() -> None:
    natal = _acceptance_chart()
    rule = validate_rule(
        {
            "logic": "all",
            "predicates": [
                {"field": "day.branch", "source": "natal", "value": "day.branch"},
                {"field": "hour.stem", "source": "literal", "value": "壬"},
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

