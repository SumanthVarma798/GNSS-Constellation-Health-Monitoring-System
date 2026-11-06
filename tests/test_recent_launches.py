"""Space-Track's list of recent launches is kept in the archive, and the weekly registry build picks out the payloads in a
navigation orbit that no table lists yet. No network: Space-Track's replies are canned."""
import csv
import json
import sys
from pathlib import Path

import pytest

from data import spacetrack
from evidence import recent_launches
from evidence.archive import FetchFailed, latest_version, object_path, record
from evidence.settings import REGISTRY_DIR, REGISTRY_UNIDENTIFIED_COLUMNS, REGISTRY_UNIDENTIFIED_FILE
from evidence.sources import ARCHIVED_SOURCES, SPACE_TRACK_RECENT_LAUNCHES_URL
from test_spacetrack import FakeSession, install_session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import archive_sources  # noqa: E402
import build_registry  # noqa: E402

ARCHIVE_WORKFLOW = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "archive.yml").read_text()


def payload(norad, name, period, inclination):
    return {"NORAD_CAT_ID": str(norad), "OBJECT_NAME": name, "OBJECT_ID": f"2026-{norad % 1000:03d}A",
            "LAUNCH": "2026-10-20", "PERIOD": period, "INCLINATION": inclination}


LISTED = [
    payload(70002, "OBJECT B", "1436.10", "55.20"),   # inclined geosynchronous: the tilt of a BeiDou satellite in that orbit
    payload(70001, "OBJECT A", "773.10", "55.02"),    # medium Earth orbit, tilted like BeiDou's
    payload(70003, "OBJECT C", "95.40", "53.00"),     # low orbit: a Starlink
    payload(70004, "OBJECT D", "640.00", "27.00"),    # transfer orbit to geostationary
    payload(70005, "OBJECT E", "1436.00", "0.05"),    # geostationary: a communications satellite or a navigation one
    {"NORAD_CAT_ID": "70006", "OBJECT_NAME": "NO ORBIT YET", "PERIOD": "", "INCLINATION": ""},
]
BODY = json.dumps(LISTED).encode()


class Page:
    def __init__(self, status, content=b"", text=""):
        self.status_code, self.content, self.text = status, content, text


def test_only_payloads_in_a_navigation_orbit_are_picked_out_by_catalogue_number():
    assert recent_launches.candidates(BODY) == [
        ["70001", "OBJECT A", "2026-001A", "2026-10-20", "medium Earth orbit", "773.1", "55.02"],
        ["70002", "OBJECT B", "2026-002A", "2026-10-20", "inclined geosynchronous orbit", "1436.1", "55.2"]]


def test_a_copy_with_nothing_in_a_navigation_orbit_gives_no_rows():
    assert recent_launches.candidates(json.dumps(LISTED[2:]).encode()) == []


def test_the_list_is_fetched_with_the_login_and_kept_as_json():
    seen = []

    def read(address, username, password):
        seen.append((address, username, password))
        return BODY

    env = {"SPACETRACK_USERNAME": "member@example.com", "SPACETRACK_PASSWORD": "secret"}
    assert recent_launches.fetch(SPACE_TRACK_RECENT_LAUNCHES_URL, env, read) == (200, BODY, "application/json")
    assert seen == [(SPACE_TRACK_RECENT_LAUNCHES_URL, "member@example.com", "secret")]


@pytest.mark.parametrize("error", [spacetrack.LoginRefused("Space-Track login refused."), spacetrack.Busy("Space-Track is busy.")])
def test_a_refused_login_or_a_busy_server_is_a_failed_fetch_that_never_shows_the_password(error):
    def read(*_):
        raise error

    with pytest.raises(FetchFailed) as failure:
        recent_launches.fetch("https://space-track.example/x", {"SPACETRACK_USERNAME": "u", "SPACETRACK_PASSWORD": "secret"}, read)
    assert str(error) in str(failure.value) and "secret" not in str(failure.value)


def test_without_a_login_nothing_is_asked_of_space_track():
    def read(*_):
        raise AssertionError("must not be called")

    with pytest.raises(FetchFailed, match="no Space-Track login"):
        recent_launches.fetch("https://space-track.example/x", {"SPACETRACK_USERNAME": "u"}, read)


def test_read_logs_in_once_asks_for_the_page_and_logs_out(monkeypatch):
    session = FakeSession(Page(200, text="{}"), query=Page(200, BODY))
    install_session(monkeypatch, session)

    assert spacetrack.read("https://space-track.example/page", "u", "p") == BODY
    assert [call[:2] for call in session.calls] == [("POST", spacetrack.LOGIN), ("GET", "https://space-track.example/page"),
                                                    ("GET", spacetrack.LOGOUT)]


def test_read_logs_out_when_the_server_is_busy_and_never_asks_after_a_refused_login(monkeypatch):
    busy = FakeSession(Page(200, text="{}"), query=Page(429))
    install_session(monkeypatch, busy)
    with pytest.raises(spacetrack.Busy):
        spacetrack.read("https://space-track.example/page", "u", "p")
    assert busy.calls[-1][:2] == ("GET", spacetrack.LOGOUT)

    refused = FakeSession(Page(200, text="Login Failed"))
    install_session(monkeypatch, refused)
    with pytest.raises(spacetrack.LoginRefused):
        spacetrack.read("https://space-track.example/page", "u", "p")
    assert not [call for call in refused.calls if call[0] == "GET" and call[1] != spacetrack.LOGOUT]


def test_the_launches_group_keeps_a_copy_and_a_missing_login_fails_the_run_with_a_log_line(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["archive_sources.py", "--archive", str(tmp_path), "--group", "launches"])
    monkeypatch.setattr(recent_launches, "fetch", lambda address: (200, BODY, "application/json"))
    archive_sources.main()
    kept = latest_version(tmp_path, SPACE_TRACK_RECENT_LAUNCHES_URL)
    assert object_path(tmp_path, kept["sha256"]).read_bytes() == BODY

    monkeypatch.setattr(recent_launches, "fetch", lambda address: (_ for _ in ()).throw(FetchFailed("no login")))
    with pytest.raises(SystemExit):
        archive_sources.main()
    assert latest_version(tmp_path, SPACE_TRACK_RECENT_LAUNCHES_URL) == kept   # the last good copy stays
    assert "failed" in (tmp_path / "runs" / "archive.csv").read_text().splitlines()[-1]


def test_the_login_goes_only_to_the_runs_that_read_space_track():
    for name in ("SPACETRACK_USERNAME", "SPACETRACK_PASSWORD"):
        line = next(line for line in ARCHIVE_WORKFLOW.splitlines() if line.strip().startswith(f"{name}:"))
        assert "== 'launches'" in line and "== 'all'" in line and "|| ''" in line
    assert ARCHIVED_SOURCES["launches"] == [SPACE_TRACK_RECENT_LAUNCHES_URL]


def test_payloads_the_igs_file_or_the_sightings_list_already_has_are_not_proposed(tmp_path):
    record(tmp_path, SPACE_TRACK_RECENT_LAUNCHES_URL, "2026-11-05T02:20:00Z", 200, BODY, "application/json")

    rows, read_on = build_registry.unidentified_update(tmp_path, [], [])
    assert [row[0] for row in rows] == ["70001", "70002"] and read_on == "2026-11-05"

    rows, _ = build_registry.unidentified_update(tmp_path, [{"catalogue_no": "70001"}], [{"catalogue_no": "70002"}])
    assert rows == []


def test_with_no_archived_copy_the_table_is_left_as_it_is(tmp_path):
    assert build_registry.unidentified_update(tmp_path, [], []) == (None, "")
    assert build_registry.unidentified_update(None, [], []) == (None, "")


def test_the_committed_table_has_the_columns_the_build_writes():
    with open(REGISTRY_DIR / REGISTRY_UNIDENTIFIED_FILE, newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == REGISTRY_UNIDENTIFIED_COLUMNS
