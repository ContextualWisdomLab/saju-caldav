from datetime import datetime, time

import pytest

from app.birth import BirthInput, normalize_birth


def test_korean_lunar_new_year_normalizes_to_gregorian_local_time():
    value = BirthInput("lunar", 2024, 1, 1, time(8, 30), False)

    assert normalize_birth(value) == datetime(2024, 2, 10, 8, 30)


def test_impossible_leap_month_is_rejected():
    value = BirthInput("lunar", 2024, 1, 1, time(8, 30), True)

    with pytest.raises(ValueError, match="윤달"):
        normalize_birth(value)


def test_solar_input_rejects_leap_month_flag():
    value = BirthInput("solar", 2024, 2, 10, time(8, 30), True)

    with pytest.raises(ValueError, match="양력"):
        normalize_birth(value)


def test_solar_input_rejects_impossible_date():
    value = BirthInput("solar", 2024, 2, 30, time(8, 30), False)

    with pytest.raises(ValueError, match="유효하지 않은 양력"):
        normalize_birth(value)
