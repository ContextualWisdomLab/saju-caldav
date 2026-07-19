"""RFC 5545 serialization and narrow CalDAV publishing."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC
from urllib.parse import quote, urlsplit
from xml.sax.saxutils import escape

import httpx
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
    event.add("summary", calendar_name)
    event.add("description", "사용자가 설정한 맞춤 시간입니다.")
    event.add("transp", "TRANSPARENT")
    event.add("class", "PRIVATE")
    calendar.add_component(event)
    return calendar.to_ical()


@dataclass(frozen=True, slots=True)
class SyncResult:
    collection_url: str
    event_count: int


class CalDavPublisher:
    def __init__(self, base_url: str, username: str, password: str, timeout: float = 10) -> None:
        normalized_url = base_url.rstrip("/")
        parsed = urlsplit(normalized_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("CalDAV base URL must be an http or https origin")
        self.base_url = normalized_url
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
        try:
            response = httpx.request(
                method,
                url,
                content=data,
                headers={
                    "Content-Type": content_type,
                    "Accept": "application/xml, text/calendar",
                },
                auth=(self.username, self.password),
                timeout=self.timeout,
                follow_redirects=False,
            )
        except httpx.RequestError as error:
            raise RuntimeError(f"CalDAV {method} connection failed") from error
        status = response.status_code
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
