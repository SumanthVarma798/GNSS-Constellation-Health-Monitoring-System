"""Space-Track's list of recent launches is kept in the archive, and the weekly registry build picks out the payloads in a
navigation orbit that no table lists yet. No network: Space-Track's replies are canned."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
import requests

from evidence import recent_launches
from evidence.archive import FetchFailed, latest_version, object_path, record
from evidence.settings import REGISTRY_DIR, REGISTRY_UNIDENTIFIED_COLUMNS, REGISTRY_UNIDENTIFIED_FILE
from evidence.sources import ARCHIVED_SOURCES, SPACE_TRACK_RECENT_LAUNCHES_URL
from test_spacetrack import FakeSession, install_session

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import archive_sources  # noqa: E402
import build_registry  # noqa: E402

ARCHIVE_WORKFLOW = (ROOT / ".github" / "workflows" / "archive.yml").read_text()
ENV = {"SPACETRACK_USERNAME": "member@example.com", "SPACETRACK_PASSWORD": "very-secret"}


def payload(norad, name, period, inclination):
    return {"NORAD_CAT_ID": str(norad), "OBJECT_NAME": name, "OBJECT_ID": f"2026-{norad % 1000:03d}A",
            "LAUNCH": "2026-10-20", "PERIOD": period, "INCLINATION": inclination}


LISTED = [
    payload(70002, "OBJECT B", "1436.10", "55.20"),   # inclined geosynchronous: the tilt of a BeiDou satellite in that orbit
    payload(70007, "OBJECT G", "1407.18", "29.89"),   # NVS-03 as Space-Track listed it a week after launch, still being raised
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
        ["70002", "OBJECT B", "2026-002A", "2026-10-20", "inclined geosynchronous orbit", "1436.1", "55.2"],
        ["70007", "OBJECT G", "2026-007A", "2026-10-20", "inclined geosynchronous orbit", "1407.18", "29.89"]]


def test_a_copy_with_nothing_in_a_navigation_orbit_gives_no_rows():
    assert recent_launches.candidates(json.dumps(LISTED[3:]).encode()) == []


def test_the_list_is_fetched_after_one_login_and_the_session_always_logs_out(monkeypatch):
    session = FakeSession(Page(200, text="{}"), query=Page(200, BODY))
    install_session(monkeypatch, session)

    assert recent_launches.fetch(SPACE_TRACK_RECENT_LAUNCHES_URL, ENV) == (200, BODY, "application/json")
    assert [call[:2] for call in session.calls] == [("POST", recent_launches.LOGIN), ("GET", SPACE_TRACK_RECENT_LAUNCHES_URL),
                                                    ("GET", recent_launches.LOGOUT)]
    assert session.calls[0][2] == {"identity": "member@example.com", "password": "very-secret"}


def test_a_refused_login_is_one_try_that_never_asks_for_the_list_or_shows_the_password(monkeypatch):
    session = FakeSession(Page(200, text="Login Failed"))
    install_session(monkeypatch, session)

    with pytest.raises(FetchFailed, match="refused the login") as failure:
        recent_launches.fetch(SPACE_TRACK_RECENT_LAUNCHES_URL, ENV)
    assert "very-secret" not in str(failure.value)
    assert [call[:2] for call in session.calls] == [("POST", recent_launches.LOGIN), ("GET", recent_launches.LOGOUT)]


@pytest.mark.parametrize("session, words", [
    (FakeSession(Page(200, text="{}"), query=Page(429)), "answered 429"),
    (FakeSession(Page(200, text="{}"), query_error=requests.ConnectionError("reset")), "could not be reached"),
    (FakeSession(Page(403, text="")), "refused the login")])
def test_a_busy_or_unreachable_space_track_is_a_failed_fetch_and_still_logs_out(monkeypatch, session, words):
    install_session(monkeypatch, session)

    with pytest.raises(FetchFailed, match=words):
        recent_launches.fetch(SPACE_TRACK_RECENT_LAUNCHES_URL, ENV)
    assert session.calls[-1][:2] == ("GET", recent_launches.LOGOUT)


def test_without_a_login_nothing_is_asked_of_space_track(monkeypatch):
    session = FakeSession(Page(200, text="{}"))
    install_session(monkeypatch, session)

    with pytest.raises(FetchFailed, match="no Space-Track login"):
        recent_launches.fetch(SPACE_TRACK_RECENT_LAUNCHES_URL, {"SPACETRACK_USERNAME": "u"})
    assert session.calls == []


def test_the_archive_script_imports_with_only_requests_installed():
    # archive.yml installs one library. The first real run failed because this reached for sgp4 through data/.
    blocked = ("sgp4", "numpy", "pandas", "scipy", "streamlit", "plotly")
    code = (f"import sys; sys.path[:0] = [{str(ROOT)!r}, {str(ROOT / 'scripts')!r}]\n"
            f"for name in {blocked!r}: sys.modules[name] = None\n"
            "import archive_sources")
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-600:]


def test_the_launches_group_keeps_a_copy_and_a_failed_read_fails_the_run_with_a_log_line(monkeypatch, tmp_path):
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
    assert [row[0] for row in rows] == ["70001", "70002", "70007"] and read_on == "2026-11-05"

    rows, _ = build_registry.unidentified_update(tmp_path, [{"catalogue_no": "70001"}, {"catalogue_no": "70007"}],
                                                 [{"catalogue_no": "70002"}])
    assert rows == []


def test_with_no_archived_copy_the_table_is_left_as_it_is(tmp_path):
    assert build_registry.unidentified_update(tmp_path, [], []) == (None, "")
    assert build_registry.unidentified_update(None, [], []) == (None, "")


def test_the_committed_table_has_the_columns_the_build_writes():
    with open(REGISTRY_DIR / REGISTRY_UNIDENTIFIED_FILE, newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == REGISTRY_UNIDENTIFIED_COLUMNS
