import pytest

from app.locations import list_birth_cities, resolve_birth_place


def test_birth_city_catalog_has_korean_labels_and_no_latitude() -> None:
    cities = list_birth_cities()
    seoul = next(city for city in cities if city["id"] == "seoul")

    assert seoul == {
        "id": "seoul",
        "label": "대한민국 · 서울",
        "timezone": "Asia/Seoul",
    }
    assert all("latitude" not in city and "longitude" not in city for city in cities)


def test_city_resolves_timezone_and_true_solar_longitude_internally() -> None:
    place = resolve_birth_place("seoul", "Etc/UTC", "true_solar", None)

    assert place.city_id == "seoul"
    assert place.city_name == "대한민국 · 서울"
    assert place.timezone == "Asia/Seoul"
    assert place.longitude == pytest.approx(126.978)


def test_custom_timezone_uses_civil_time_without_coordinates() -> None:
    place = resolve_birth_place(None, "Europe/London", "civil", None)

    assert place.city_id is None
    assert place.city_name is None
    assert place.timezone == "Europe/London"
    assert place.longitude is None


def test_custom_true_solar_time_requires_a_catalog_city() -> None:
    with pytest.raises(ValueError, match="도시 목록"):
        resolve_birth_place(None, "Asia/Seoul", "true_solar", None)


def test_unknown_birth_city_is_rejected() -> None:
    with pytest.raises(ValueError, match="지원하지 않는 출생 도시"):
        resolve_birth_place("atlantis", "Etc/UTC", "civil", None)
