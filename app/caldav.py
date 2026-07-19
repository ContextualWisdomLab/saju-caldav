"""RFC 5545 serialization and narrow CalDAV publishing."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

from icalendar import Calendar, Event

from app.events import MatchingWindow


def event_uid(calendar_id: str, window: MatchingWindow) -> str:
    identity = f"{calendar_id}|{window.start.isoformat()}|{window.end.isoformat()}|v1"
    return f"{hashlib.sha256(identity.encode()).hexdigest()[:32]}@saju-caldav"


def build_icalendar(
    calendar_id: str,
    calendar_name: str,
    window: MatchingWindow,
) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//ContextualWisdomLab//Saju CalDAV//KO")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("x-wr-calname", calendar_name)

    event = Event()
    event.add("uid", event_uid(calendar_id, window))
    event.add("dtstamp", window.start.astimezone(UTC))
    event.add("dtstart", window.start)
    event.add("dtend", window.end)
    event.add(
        "summary",
        f"{window.chart.day.ganzhi}일 · {window.chart.hour.ganzhi}시 — {calendar_name}",
    )
    event.add(
        "description",
        "\n".join(
            (
                f"규칙 캘린더: {calendar_name}",
                f"일주: {window.chart.day.ganzhi}",
                f"일지: {window.chart.day.branch}{window.chart.day.branch_element}",
                f"시주: {window.chart.hour.ganzhi}",
                f"시간: {window.chart.hour.stem}{window.chart.hour.stem_element}",
                "문화·역법 참고용이며 운세의 과학적 타당성을 주장하지 않습니다.",
            )
        ),
    )
    event.add("transp", "TRANSPARENT")
    event.add("class", "PRIVATE")
    event.add("categories", ["SAJU", "GANZHI"])
    event.add("x-saju-day-pillar", window.chart.day.ganzhi)
    event.add("x-saju-hour-pillar", window.chart.hour.ganzhi)
    calendar.add_component(event)
    return calendar.to_ical()


@dataclass(frozen=True, slots=True)
class SyncResult:
    collection_url: str
    event_count: int


class CalDavPublisher:
    def __init__(self, base_url: str, username: str, password: str, timeout: float = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout

    def _request(
        self,
        method: str,
        url: str,
        data: bytes,
        content_type: str,
        accepted: set[int],
    ) -> int:
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        request = Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": content_type,
                "Accept": "application/xml, text/calendar",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                status = response.status
        except HTTPError as error:
            if error.code in accepted:
                return error.code
            raise RuntimeError(f"CalDAV {method} failed with HTTP {error.code}") from error
        except URLError as error:
            raise RuntimeError(f"CalDAV {method} connection failed: {error.reason}") from error
        if status not in accepted:
            raise RuntimeError(f"CalDAV {method} returned unexpected HTTP {status}")
        return status

    def sync(
        self,
        calendar_id: str,
        slug: str,
        calendar_name: str,
        windows: list[MatchingWindow],
    ) -> SyncResult:
        user_path = quote(self.username, safe="")
        slug_path = quote(slug, safe="")
        collection_url = f"{self.base_url}/{user_path}/{slug_path}/"
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<c:mkcalendar xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            "<d:set><d:prop><d:resourcetype><d:collection/><c:calendar/>"
            f"</d:resourcetype><d:displayname>{escape(calendar_name)}</d:displayname>"
            "</d:prop></d:set></c:mkcalendar>"
        ).encode()
        self._request(
            "MKCALENDAR",
            collection_url,
            body,
            "application/xml; charset=utf-8",
            {200, 201, 204, 405},
        )

        for window in windows:
            uid = event_uid(calendar_id, window).split("@", 1)[0]
            self._request(
                "PUT",
                f"{collection_url}{uid}.ics",
                build_icalendar(calendar_id, calendar_name, window),
                "text/calendar; charset=utf-8",
                {200, 201, 204},
            )
        return SyncResult(collection_url=collection_url, event_count=len(windows))
