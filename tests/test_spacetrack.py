"""Space-Track fetches one newest orbit row per satellite and always logs out. No network."""
from datetime import datetime, timedelta, timezone
import json

import pytest
import requests

from data import spacetrack
from test_celestrak import IRNSS_1B

NOW = datetime(2026, 10, 26, 3, 30, tzinfo=timezone.utc)


def gp_row(norad, epoch):
    """One GP JSON row in the shape Space-Track returns: keys as in OMM, values as text."""
    row = {}
    for key, value in {**IRNSS_1B, "NORAD_CAT_ID": norad, "EPOCH": epoch}.items():
        row[key] = value if value is None or isinstance(value, str) else str(value)
    return row


class Reply:
    def __init__(self, status, rows=None, text=""):
        self.status_code = status
        self._rows = rows if rows is not None else []
        self.text = text

    def json(self):
        return self._rows


class FakeSession:
    def __init__(self, login, query=None, query_error=None, logout_error=None):
        self.login = login
        self.query = query or Reply(200, [])
        self.query_error = query_error
        self.logout_error = logout_error
        self.calls = []
        self.headers = {}

    def post(self, url, data, timeout):
        self.calls.append(("POST", url, data, timeout))
        return self.login

    def get(self, url, timeout):
        self.calls.append(("GET", url, timeout))
        if url == spacetrack.LOGOUT and self.logout_error:
            raise self.logout_error
        if url == spacetrack.LOGOUT:
            return Reply(200, [])
        if self.query_error:
            raise self.query_error
        return self.query


def install_session(monkeypatch, session):
    made = []

    def make():
        made.append(True)
        return session

    monkeypatch.setattr(spacetrack.requests, "Session", make)
    return made


def empty_state():
    return {"rows": {}, "tried": None, "fetched": None, "refused_until": None, "note": "ok"}


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch, tmp_path):
    monkeypatch.setattr(spacetrack, "state", empty_state())
    monkeypatch.setattr(spacetrack, "SAVED", tmp_path / "spacetrack.json")


def test_login_refused_from_a_200_reply_body_raises_and_never_queries(monkeypatch):
    session = FakeSession(Reply(200, text="Login Failed"))
    made = install_session(monkeypatch, session)

    with pytest.raises(spacetrack.LoginRefused):
        spacetrack.fetch("member@example.com", "very-secret", [39635, 40547])

    queried = [call for call in session.calls if call[0] == "GET" and call[1] != spacetrack.LOGOUT]
    assert len(made) == 1
    assert not queried


def test_one_query_for_many_satellites_uses_sorted_ids_and_keeps_the_newest_epoch(monkeypatch):
    rows = [
        gp_row(40547, "2026-10-07T10:00:00.000000"),
        gp_row(39635, "2026-10-07T09:00:00.000000"),
        gp_row(39635, "2026-10-07T11:00:00.000000"),
    ]
    session = FakeSession(Reply(200, text="{}"), query=Reply(200, rows=rows))
    install_session(monkeypatch, session)

    found = spacetrack.fetch("member@example.com", "secret", [40547, 39635, 40547])

    query_calls = [call for call in session.calls if call[0] == "GET" and call[1] != spacetrack.LOGOUT]
    assert len(query_calls) == 1
    assert "/NORAD_CAT_ID/39635,40547/" in query_calls[0][1]
    assert set(found) == {39635, 40547}
    assert found[39635]["EPOCH"] == "2026-10-07T11:00:00.000000"


def test_a_429_reply_is_busy_and_is_not_retried(monkeypatch):
    session = FakeSession(Reply(200, text="{}"), query=Reply(429, []))
    install_session(monkeypatch, session)

    with pytest.raises(spacetrack.Busy):
        spacetrack.fetch("member@example.com", "secret", [39635])

    query_calls = [call for call in session.calls if call[0] == "GET" and call[1] != spacetrack.LOGOUT]
    assert len(query_calls) == 1


def test_logout_is_attempted_even_when_the_query_fails(monkeypatch):
    session = FakeSession(Reply(200, text="{}"), query_error=requests.Timeout("slow"), logout_error=OSError("offline"))
    install_session(monkeypatch, session)

    with pytest.raises(spacetrack.Busy):
        spacetrack.fetch("member@example.com", "secret", [39635])

    assert session.calls[-1][1] == spacetrack.LOGOUT


@pytest.mark.parametrize("login,query,error", [
    (Reply(200, text="Login Failed"), None, spacetrack.LoginRefused),
    (Reply(200, text="{}"), Reply(429, []), spacetrack.Busy),
    (Reply(401, text="refused"), None, spacetrack.LoginRefused),
])
def test_password_never_appears_in_an_error_message(monkeypatch, login, query, error):
    secret = "no-leaks-please"
    session = FakeSession(login=login, query=query or Reply(200, []))
    install_session(monkeypatch, session)

    with pytest.raises(error) as raised:
        spacetrack.fetch("member@example.com", secret, [39635])

    assert secret not in str(raised.value)


def test_no_ids_returns_empty_without_a_request(monkeypatch):
    session = FakeSession(Reply(200, text="{}"))
    made = install_session(monkeypatch, session)

    assert spacetrack.fetch("member@example.com", "secret", []) == {}
    assert not made and session.calls == []


def test_any_network_error_is_busy_and_a_403_on_the_query_is_not_a_refused_login(monkeypatch):
    install_session(monkeypatch, FakeSession(Reply(200), query_error=requests.TooManyRedirects("loop")))
    with pytest.raises(spacetrack.Busy):
        spacetrack.fetch("user", "pass", [39635])
    install_session(monkeypatch, FakeSession(Reply(200), Reply(403)))
    with pytest.raises(spacetrack.SpaceTrackError) as raised:
        spacetrack.fetch("user", "pass", [39635])
    assert not isinstance(raised.value, spacetrack.LoginRefused)


def test_requests_name_us(monkeypatch):
    session = FakeSession(Reply(200), Reply(200, [gp_row(39635, "2026-10-25T01:00:00.000000")]))
    install_session(monkeypatch, session)
    spacetrack.fetch("user", "pass", [39635])
    assert session.headers["User-Agent"].startswith("gnss-evidence-archive")


def test_no_login_makes_no_request_and_marks_the_note(monkeypatch):
    called = []
    monkeypatch.setattr(spacetrack, "fetch", lambda username, password, norads: called.append((username, password, norads)))

    live = spacetrack.refresh([39635], NOW, None)

    assert called == []
    assert live["note"] == "no login"
    assert live["tried"] is None


def test_refresh_tries_at_most_once_per_hour_and_passes_exact_ids(monkeypatch):
    asked = []

    def fetch(username, password, norads):
        asked.append(list(norads))
        return {39635: gp_row(39635, "2026-10-25T01:00:00.000000")}

    monkeypatch.setattr(spacetrack, "fetch", fetch)
    login = ("member@example.com", "secret")
    spacetrack.refresh([40547, 39635], NOW, login)
    spacetrack.refresh([39635], NOW + timedelta(minutes=30), login)
    live = spacetrack.refresh([39635], NOW + timedelta(hours=1), login)

    assert asked == [[40547, 39635], [39635]]
    assert live["note"] == "ok"
    assert len(live["rows"][39635]) == 1


def test_login_refused_waits_a_day_before_the_next_try(monkeypatch):
    asked = []

    def fetch(username, password, norads):
        asked.append(list(norads))
        raise spacetrack.LoginRefused("no")

    monkeypatch.setattr(spacetrack, "fetch", fetch)
    login = ("member@example.com", "secret")
    first = spacetrack.refresh([39635], NOW, login)
    second = spacetrack.refresh([39635], NOW + timedelta(hours=1), login)
    third = spacetrack.refresh([39635], NOW + timedelta(hours=23, minutes=59), login)
    fourth = spacetrack.refresh([39635], NOW + timedelta(hours=24), login)

    assert asked == [[39635], [39635]]
    assert first["note"] == second["note"] == third["note"] == fourth["note"] == "login refused"


def test_saved_state_never_contains_login_details(monkeypatch):
    monkeypatch.setattr(spacetrack, "fetch", lambda username, password, norads: {
        39635: gp_row(39635, "2026-10-25T01:00:00.000000")
    })
    username, password = "member@example.com", "no-leaks-please"
    spacetrack.refresh([39635], NOW, (username, password))
    saved = spacetrack.SAVED.read_text(encoding="utf-8")
    loaded = json.loads(saved)

    assert username not in saved and password not in saved
    assert "username" not in loaded and "password" not in loaded
