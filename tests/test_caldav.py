from __future__ import annotations

import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

from icalendar import Calendar

from app.caldav import CalDavPublisher, build_icalendar
from app.events import generate_windows
from app.rules import validate_rule
from app.saju import calculate_chart


def _acceptance_window():
    natal = calculate_chart(datetime(1990, 6, 15, 8, 30), "Asia/Seoul", "civil", None)
    rule = validate_rule(
        {
            "logic": "all",
            "predicates": [
                {"field": "day.branch", "source": "natal", "value": "day.branch"},
                {"field": "hour.stem", "source": "literal", "value": "壬"},
            ],
        }
    )
    return generate_windows(
        rule,
        natal,
        date(1990, 6, 15),
        date(1990, 6, 15),
        "Asia/Seoul",
        "civil",
        None,
    )[0]


def test_build_icalendar_emits_stable_private_transparent_event() -> None:
    window = _acceptance_window()
    first = build_icalendar("calendar-1", "내 亥日의 壬時", window)
    second = build_icalendar("calendar-1", "내 亥日의 壬時", window)
    parsed = Calendar.from_ical(first)
    event = next(component for component in parsed.walk() if component.name == "VEVENT")

    assert first == second
    assert event["UID"].endswith("@saju-caldav")
    assert event.decoded("DTSTART") == window.start
    assert event.decoded("DTEND") == window.end
    assert "辛亥일 · 壬辰시" in str(event["SUMMARY"])
    assert event["TRANSP"] == "TRANSPARENT"
    assert event["CLASS"] == "PRIVATE"
    assert "일지: 亥水" in str(event["DESCRIPTION"])
    assert "시간: 壬水" in str(event["DESCRIPTION"])


class _Recorder(BaseHTTPRequestHandler):
    requests: ClassVar[list[tuple[str, str, bytes]]] = []

    def _record(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.requests.append((self.command, self.path, self.rfile.read(length)))
        self.send_response(201 if self.command == "MKCALENDAR" else 204)
        self.end_headers()

    do_MKCALENDAR = _record
    do_PUT = _record

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
            "calendar-1", "my-hai-ren-hours", "내 亥日의 壬時", [_acceptance_window()]
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.event_count == 1
    assert result.collection_url.endswith("/caluser/my-hai-ren-hours/")
    assert [request[0] for request in _Recorder.requests] == ["MKCALENDAR", "PUT"]
    assert _Recorder.requests[0][1] == "/caluser/my-hai-ren-hours/"
    assert _Recorder.requests[1][1].endswith(".ics")
    assert b"BEGIN:VEVENT" in _Recorder.requests[1][2]

