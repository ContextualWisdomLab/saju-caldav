"""Curated birth-city presets without exposing coordinates to the client."""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class BirthCity:
    id: str
    label: str
    timezone: str
    longitude: float


@dataclass(frozen=True, slots=True)
class ResolvedBirthPlace:
    city_id: str | None
    city_name: str | None
    timezone: str
    longitude: float | None


_BIRTH_CITIES = (
    BirthCity("seoul", "대한민국 · 서울", "Asia/Seoul", 126.978),
    BirthCity("busan", "대한민국 · 부산", "Asia/Seoul", 129.0756),
    BirthCity("daegu", "대한민국 · 대구", "Asia/Seoul", 128.6014),
    BirthCity("incheon", "대한민국 · 인천", "Asia/Seoul", 126.7052),
    BirthCity("gwangju", "대한민국 · 광주", "Asia/Seoul", 126.8526),
    BirthCity("daejeon", "대한민국 · 대전", "Asia/Seoul", 127.3845),
    BirthCity("ulsan", "대한민국 · 울산", "Asia/Seoul", 129.3114),
    BirthCity("jeju", "대한민국 · 제주", "Asia/Seoul", 126.5312),
    BirthCity("tokyo", "일본 · 도쿄", "Asia/Tokyo", 139.6917),
    BirthCity("beijing", "중국 · 베이징", "Asia/Shanghai", 116.4074),
    BirthCity("hong-kong", "홍콩 · 홍콩", "Asia/Hong_Kong", 114.1694),
    BirthCity("singapore", "싱가포르 · 싱가포르", "Asia/Singapore", 103.8198),
    BirthCity("london", "영국 · 런던", "Europe/London", -0.1276),
    BirthCity("paris", "프랑스 · 파리", "Europe/Paris", 2.3522),
    BirthCity("new-york", "미국 · 뉴욕", "America/New_York", -74.006),
    BirthCity("los-angeles", "미국 · 로스앤젤레스", "America/Los_Angeles", -118.2437),
    BirthCity("sydney", "호주 · 시드니", "Australia/Sydney", 151.2093),
)
_BIRTH_CITY_BY_ID = {city.id: city for city in _BIRTH_CITIES}


def list_birth_cities() -> list[dict[str, str]]:
    """Return client-safe labels and timezones; coordinates stay server-side."""

    return [
        {"id": city.id, "label": city.label, "timezone": city.timezone}
        for city in _BIRTH_CITIES
    ]


def resolve_birth_place(
    city_id: str | None,
    timezone: str,
    time_mode: str,
    manual_longitude: float | None,
) -> ResolvedBirthPlace:
    """Resolve the effective timezone and optional true-solar longitude."""

    normalized_city_id = city_id.strip() if city_id else None
    if normalized_city_id:
        city = _BIRTH_CITY_BY_ID.get(normalized_city_id)
        if city is None:
            raise ValueError("지원하지 않는 출생 도시입니다")
        return ResolvedBirthPlace(
            city_id=city.id,
            city_name=city.label,
            timezone=city.timezone,
            longitude=city.longitude if time_mode == "true_solar" else None,
        )

    ZoneInfo(timezone)
    if time_mode == "true_solar" and manual_longitude is None:
        raise ValueError("진태양시는 출생 도시 목록에서 도시를 선택해야 합니다")
    return ResolvedBirthPlace(
        city_id=None,
        city_name=None,
        timezone=timezone,
        longitude=manual_longitude if time_mode == "true_solar" else None,
    )
