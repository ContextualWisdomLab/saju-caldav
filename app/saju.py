"""Deterministic Four Pillars calendrical calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from lunar_python import Solar

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEM_ELEMENTS = dict(zip(STEMS, "木木火火土土金金水水", strict=True))
BRANCH_ELEMENTS = {
    "子": "水",
    "丑": "土",
    "寅": "木",
    "卯": "木",
    "辰": "土",
    "巳": "火",
    "午": "火",
    "未": "土",
    "申": "金",
    "酉": "金",
    "戌": "土",
    "亥": "水",
}
STEM_KOREAN = {
    "甲": ("갑목", "양의 성질을 가진 큰나무"),
    "乙": ("을목", "음의 성질을 가진 풀과 덩굴"),
    "丙": ("병화", "양의 성질을 가진 큰불"),
    "丁": ("정화", "음의 성질을 가진 작은불"),
    "戊": ("무토", "양의 성질을 가진 큰땅"),
    "己": ("기토", "음의 성질을 가진 부드러운 땅"),
    "庚": ("경금", "양의 성질을 가진 단단한 쇠"),
    "辛": ("신금", "음의 성질을 가진 세밀한 쇠"),
    "壬": ("임수", "양의 성질을 가진 큰물"),
    "癸": ("계수", "음의 성질을 가진 작은물"),
}
BRANCH_KOREAN = {
    "子": ("자수", "십이지의 쥐, 오행으로는 물"),
    "丑": ("축토", "십이지의 소, 오행으로는 흙"),
    "寅": ("인목", "십이지의 호랑이, 오행으로는 나무"),
    "卯": ("묘목", "십이지의 토끼, 오행으로는 나무"),
    "辰": ("진토", "십이지의 용, 오행으로는 흙"),
    "巳": ("사화", "십이지의 뱀, 오행으로는 불"),
    "午": ("오화", "십이지의 말, 오행으로는 불"),
    "未": ("미토", "십이지의 양, 오행으로는 흙"),
    "申": ("신금", "십이지의 원숭이, 오행으로는 쇠"),
    "酉": ("유금", "십이지의 닭, 오행으로는 쇠"),
    "戌": ("술토", "십이지의 개, 오행으로는 흙"),
    "亥": ("해수", "십이지의 돼지, 오행으로는 물"),
}


@dataclass(frozen=True, slots=True)
class Pillar:
    """Pair a heavenly stem with an earthly branch and Korean explanations."""

    stem: str
    branch: str

    @classmethod
    def from_ganzhi(cls, ganzhi: str) -> Pillar:
        """Create a pillar from its two-character ganzhi representation."""

        return cls(stem=ganzhi[0], branch=ganzhi[1])

    @property
    def ganzhi(self) -> str:
        """Return the traditional stem-and-branch pair."""

        return f"{self.stem}{self.branch}"

    @property
    def stem_element(self) -> str:
        """Return the five-element classification of the stem."""

        return STEM_ELEMENTS[self.stem]

    @property
    def branch_element(self) -> str:
        """Return the five-element classification of the branch."""

        return BRANCH_ELEMENTS[self.branch]

    @property
    def stem_korean(self) -> str:
        """Return the Korean name of the stem and its yin-yang polarity."""

        return STEM_KOREAN[self.stem][0]

    @property
    def stem_description(self) -> str:
        """Return a plain-Korean description of the stem imagery."""

        return STEM_KOREAN[self.stem][1]

    @property
    def branch_korean(self) -> str:
        """Return the Korean name of the earthly branch."""

        return BRANCH_KOREAN[self.branch][0]

    @property
    def branch_description(self) -> str:
        """Return a plain-Korean description of the branch imagery."""

        return BRANCH_KOREAN[self.branch][1]


@dataclass(frozen=True, slots=True)
class Chart:
    """Hold four pillars and the local wall time used for calculation."""

    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar
    calculation_local: datetime


def _hour_pillar(day_stem: str, hour: int) -> Pillar:
    branch_index = ((hour + 1) // 2) % 12
    stem_index = ((STEMS.index(day_stem) % 5) * 2 + branch_index) % 10
    return Pillar(STEMS[stem_index], BRANCHES[branch_index])


def _true_solar_time(birth_local: datetime, zone: ZoneInfo, longitude: float) -> datetime:
    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")

    aware = birth_local.replace(tzinfo=zone)
    utc_offset = aware.utcoffset()
    if utc_offset is None:
        raise ValueError("timezone has no UTC offset")
    daylight = aware.dst() or timedelta(0)
    standard_hours = (utc_offset - daylight).total_seconds() / 3600
    standard_meridian = 15 * standard_hours

    day_of_year = birth_local.timetuple().tm_yday
    angle = 2 * math.pi * (day_of_year - 81) / 364
    equation_of_time = (
        9.87 * math.sin(2 * angle) - 7.53 * math.cos(angle) - 1.5 * math.sin(angle)
    )
    correction_minutes = 4 * (longitude - standard_meridian) + equation_of_time
    return birth_local + timedelta(minutes=correction_minutes)


def calculate_chart(
    birth_local: datetime,
    timezone: str,
    time_mode: str,
    longitude: float | None,
) -> Chart:
    """Calculate a Four Pillars chart under the selected local-time convention."""

    zone = ZoneInfo(timezone)
    if time_mode not in {"civil", "true_solar"}:
        raise ValueError("time_mode must be civil or true_solar")
    if time_mode == "true_solar" and longitude is None:
        raise ValueError("longitude is required for true_solar mode")

    calculation_local = (
        _true_solar_time(birth_local, zone, longitude)
        if time_mode == "true_solar" and longitude is not None
        else birth_local
    )

    solar = Solar.fromYmdHms(
        calculation_local.year,
        calculation_local.month,
        calculation_local.day,
        calculation_local.hour,
        calculation_local.minute,
        calculation_local.second,
    )
    eight_char = solar.getLunar().getEightChar()
    day = Pillar.from_ganzhi(eight_char.getDay())
    return Chart(
        year=Pillar.from_ganzhi(eight_char.getYear()),
        month=Pillar.from_ganzhi(eight_char.getMonth()),
        day=day,
        hour=_hour_pillar(day.stem, calculation_local.hour),
        calculation_local=calculation_local,
    )


chart_for_local = calculate_chart
