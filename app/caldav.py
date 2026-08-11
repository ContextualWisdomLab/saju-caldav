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

VISIBILITY_CLASSES = {
    "private": "PRIVATE",
    "confidential": "CONFIDENTIAL",
    "public": "PUBLIC",
}


def event_uid(calendar_id: str, window: MatchingWindow) -> str:
    """Build a stable iCalendar event identifier for one matching window."""

    identity = f"{calendar_id}|{window.start.isoformat()}|{window.end.isoformat()}|v1"
    return f"{hashlib.sha256(identity.encode()).hexdigest()[:32]}@saju-caldav"


def build_icalendar(
    calendar_id: str,
    calendar_name: str,
    visibility: str,
    window: MatchingWindow,
) -> bytes:
    """Serialize one matching window as an RFC 5545 calendar document."""

    try:
        ical_class = VISIBILITY_CLASSES[visibility]
    except KeyError as error:
        allowed = ", ".join(VISIBILITY_CLASSES)
        raise ValueError(
            f"지원하지 않는 캘린더 공개 수준: {visibility!r}; "
            f"사용할 수 있는 값: {allowed}"
        ) from error
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
    event.add("class", ical_class)
    calendar.add_component(event)
    return calendar.to_ical()


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Report the remote collection and number of events written."""

    collection_url: str
    event_count: int


class CalDavPublisher:
    """Publish the small CalDAV surface required by the operator console."""

    def __init__(self, base_url: str, username: str, password: str, timeout: float = 10) -> None:
        """Validate the endpoint and retain credentials for request authentication."""

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
            raise ValueError(
                "CalDAV base URL must be an http or https URL without credentials, "
                "query, or fragment"
            )
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
            summary = " ".join(str(error).split())
            for sensitive in (self.username, self.password):
                if sensitive:
                    summary = summary.replace(sensitive, "<redacted>")
            reason = type(error).__name__
            if summary:
                reason = f"{reason}: {summary[:240]}"
            raise RuntimeError(
                f"CalDAV {method} connection failed ({reason})"
            ) from error
        status = response.status_code
        if status not in accepted:
            raise RuntimeError(f"CalDAV {method} returned unexpected HTTP {status}")
        return status

    def sync(
        self,
        calendar_id: str,
        slug: str,
        calendar_name: str,
        visibility: str,
        windows: list[MatchingWindow],
    ) -> SyncResult:
        """Create or reuse a collection and replace its matching event resources."""

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
                build_icalendar(calendar_id, calendar_name, visibility, window),
                "text/calendar; charset=utf-8",
                {200, 201, 204},
            )
        return SyncResult(collection_url=collection_url, event_count=len(windows))

    def delete(self, calendar_id: str, slug: str) -> None:
        """Remove a published collection before its local metadata is erased."""

        del calendar_id
        user_path = quote(self.username, safe="")
        slug_path = quote(slug, safe="")
        collection_url = f"{self.base_url}/{user_path}/{slug_path}/"
        self._request(
            "DELETE",
            collection_url,
            b"",
            "application/octet-stream",
            {200, 204, 404},
        )
