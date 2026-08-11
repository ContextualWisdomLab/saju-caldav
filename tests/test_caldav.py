from __future__ import annotations

import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import httpx
import pytest
from icalendar import Calendar

from app.caldav import CalDavPublisher, build_icalendar
from app.events import generate_windows
from app.rules import validate_rule
from app.saju import calculate_chart


def test_publisher_rejects_non_http_caldav_url() -> None:
    with pytest.raises(ValueError, match="http or https"):
        CalDavPublisher("file:///tmp/calendar", "caluser", "secret")


def test_publisher_accepts_base_path_and_describes_url_contract() -> None:
    publisher = CalDavPublisher("https://example.com/caldav", "caluser", "secret")

    assert publisher.base_url == "https://example.com/caldav"
    with pytest.raises(ValueError, match="without credentials, query, or fragment"):
        CalDavPublisher("https://example.com/caldav?token=hidden", "caluser", "secret")


def test_request_error_reports_sanitized_reason(monkeypatch) -> None:
    publisher = CalDavPublisher(
        "https://example.com/caldav", "caluser", "password-value"
    )

    def fail_request(*args, **kwargs):
        del args, kwargs
        raise httpx.ConnectError("dial failed for caluser with password-value")

    monkeypatch.setattr(httpx, "request", fail_request)

    with pytest.raises(RuntimeError) as captured:
        publisher.sync(
            "calendar-1",
            "my-custom-hours",
            "나의 맞춤 시간",
            "private",
            [],
        )

    message = str(captured.value)
    assert "ConnectError" in message
    assert "dial failed" in message
    assert "caluser" not in message
    assert "password-value" not in message


def test_request_error_without_credentials_or_details_is_still_clear(monkeypatch) -> None:
    publisher = CalDavPublisher("https://example.com/caldav", "", "")

    def fail_request(*args, **kwargs):
        del args, kwargs
        raise httpx.ConnectError("")

    monkeypatch.setattr(httpx, "request", fail_request)

    with pytest.raises(
        RuntimeError,
        match=r"CalDAV MKCALENDAR connection failed \(ConnectError\)",
    ):
        publisher.sync(
            "calendar-1",
            "my-custom-hours",
            "나의 맞춤 시간",
            "private",
            [],
        )


def test_unexpected_http_status_is_rejected(monkeypatch) -> None:
    publisher = CalDavPublisher("https://example.com/caldav", "caluser", "password-value")
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: httpx.Response(418),
    )

    with pytest.raises(RuntimeError, match="unexpected HTTP 418"):
        publisher.sync(
            "calendar-1",
            "my-custom-hours",
            "나의 맞춤 시간",
            "private",
            [],
        )


def _public_window():
    natal = calculate_chart(datetime(2000, 1, 1, 12, 15), "Asia/Seoul", "civil", None)
    rule = validate_rule(
        {
            "logic": "all",
            "predicates": [
                {"field": "day.branch", "source": "natal", "value": "day.branch"},
                {"field": "hour.stem", "source": "literal", "value": "戊"},
            ],
        }
    )
    return generate_windows(
        rule,
        natal,
        date(2000, 1, 1),
        date(2000, 1, 1),
        "Asia/Seoul",
        "civil",
        None,
    )[0]


def test_build_icalendar_emits_stable_private_transparent_event() -> None:
    window = _public_window()
    first = build_icalendar("calendar-1", "나의 맞춤 시간", "private", window)
    second = build_icalendar("calendar-1", "나의 맞춤 시간", "private", window)
    parsed = Calendar.from_ical(first)
    event = next(component for component in parsed.walk() if component.name == "VEVENT")

    assert first == second
    assert event["UID"].endswith("@saju-caldav")
    assert event.decoded("DTSTART") == window.start
    assert event.decoded("DTEND") == window.end
    assert str(event["SUMMARY"]) == "나의 맞춤 시간"
    assert event["TRANSP"] == "TRANSPARENT"
    assert event["CLASS"] == "PRIVATE"
    assert str(event["DESCRIPTION"]) == "사용자가 설정한 맞춤 시간입니다."
    assert event.get("CATEGORIES") is None
    assert not any(str(key).startswith("X-SAJU") for key in event)
    assert window.chart.day.ganzhi.encode() not in first
    assert window.chart.hour.ganzhi.encode() not in first


@pytest.mark.parametrize(
    ("visibility", "ical_class"),
    [
        ("private", "PRIVATE"),
        ("confidential", "CONFIDENTIAL"),
        ("public", "PUBLIC"),
    ],
)
def test_build_icalendar_maps_user_visibility_to_rfc_class(
    visibility: str, ical_class: str
) -> None:
    parsed = Calendar.from_ical(
        build_icalendar("calendar-1", "일정 공개 수준", visibility, _public_window())
    )
    event = next(component for component in parsed.walk() if component.name == "VEVENT")

    assert event["CLASS"] == ical_class
    assert str(event["DESCRIPTION"]) == "사용자가 설정한 맞춤 시간입니다."


def test_build_icalendar_describes_invalid_visibility() -> None:
    with pytest.raises(ValueError) as captured:
        build_icalendar("calendar-1", "일정 공개 수준", "secret", _public_window())

    message = str(captured.value)
    assert "secret" in message
    assert "private, confidential, public" in message


class _Recorder(BaseHTTPRequestHandler):
    requests: ClassVar[list[tuple[str, str, bytes]]] = []

    def _record(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.requests.append((self.command, self.path, self.rfile.read(length)))
        self.send_response(201 if self.command == "MKCALENDAR" else 204)
        self.end_headers()

    do_MKCALENDAR = _record
    do_PUT = _record
    do_DELETE = _record

    def log_message(self, format: str, *args: object) -> None:
        return


def test_publisher_creates_collection_and_puts_stable_resource() -> None:
    _Recorder.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        publisher = CalDavPublisher(
            f"http://127.0.0.1:{server.server_port}", "caluser", "secret", timeout=2
        )
        result = publisher.sync(
            "calendar-1",
            "my-custom-hours",
            "나의 맞춤 시간",
            "confidential",
            [_public_window()],
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.event_count == 1
    assert result.collection_url.endswith("/caluser/my-custom-hours/")
    assert [request[0] for request in _Recorder.requests] == ["MKCALENDAR", "PUT"]
    assert _Recorder.requests[0][1] == "/caluser/my-custom-hours/"
    assert _Recorder.requests[1][1].endswith(".ics")
    assert b"BEGIN:VEVENT" in _Recorder.requests[1][2]
    assert b"CLASS:CONFIDENTIAL" in _Recorder.requests[1][2]


def test_publisher_deletes_collection_idempotently() -> None:
    _Recorder.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        publisher = CalDavPublisher(
            f"http://127.0.0.1:{server.server_port}", "caluser", "secret", timeout=2
        )
        publisher.delete("calendar-1", "my-custom-hours")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert _Recorder.requests == [("DELETE", "/caluser/my-custom-hours/", b"")]
