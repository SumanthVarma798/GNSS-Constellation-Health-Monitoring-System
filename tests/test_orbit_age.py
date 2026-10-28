"""Orbit record ages: source choice, age bands, the tile tags, and the details section."""
from datetime import datetime, timedelta, timezone

import requests

from ui import orbit_age
from ui import data as dashboard_data
from ui.data import orbit_age_rows

ORBIT_GAP = dashboard_data.orbit_gap   # the real one: tests/conftest.py puts a stand-in in its place for every test

NOW = datetime(2026, 10, 26, 3, 30, tzinfo=timezone.utc)
GAP = {
    "day": "2026-10-25",
    "checked": "2026-10-26T06:00:00Z",
    "satellites": [
        {"satellite": "IRNSS-1B", "signal_id": "I01", "record_epoch": "2026-10-25T00:00:00Z",
         "typical_km": 3.2, "largest_km": 41.0, "mostly": "ahead on its path", "note": ""},
    ],
}


def epoch(days):
    return (NOW - timedelta(days=days)).isoformat()


def test_newest_row_wins_and_source_is_celestrak_spacetrack_or_history():
    rows = orbit_age_rows(
        [("A", 1), ("B", 2), ("C", 3), ("D", 4)],
        history_rows_by_satellite={
            "A": [{"EPOCH": epoch(2.5), "COMMENT": "GENERATED VIA SPACE-TRACK.ORG API"}],
            "C": [{"EPOCH": epoch(1.5), "COMMENT": "GENERATED VIA SPACE-TRACK.ORG API"}],
        },
        celestrak_rows={1: [{"EPOCH": epoch(1.0)}], 2: [{"EPOCH": epoch(2.5)}]},
        spacetrack_rows={2: [{"EPOCH": epoch(0.5)}]},
        now=NOW,
    )
    named = {row["satellite"]: row for row in rows}

    assert named["A"]["source"] == "CelesTrak"
    assert named["B"]["source"] == "Space-Track"
    assert named["C"]["source"] == "Space-Track history"
    assert named["D"]["source"] == ""
    assert named["D"]["epoch"] is None and named["D"]["age_days"] is None and named["D"]["status"] == "idle"


def test_statuses_are_ok_warn_bad_at_1_9_2_0_3_0_days_and_oldest_first():
    rows = orbit_age_rows(
        [("OK", 11), ("Warn", 12), ("Bad", 13), ("None", 14)],
        history_rows_by_satellite={},
        celestrak_rows={
            11: [{"EPOCH": epoch(1.9)}],
            12: [{"EPOCH": epoch(2.0)}],
            13: [{"EPOCH": epoch(3.0)}],
        },
        spacetrack_rows={},
        now=NOW,
    )
    by_name = {row["satellite"]: row for row in rows}

    assert by_name["OK"]["status"] == "ok"
    assert by_name["Warn"]["status"] == "warn"
    assert by_name["Bad"]["status"] == "bad"
    assert by_name["None"]["status"] == "idle"
    assert [row["satellite"] for row in rows] == ["Bad", "Warn", "OK", "None"]


def test_tag_says_its_age_source_and_limits_and_is_coloured_by_status():
    rows = [
        {"satellite": "IRNSS-1B", "epoch": datetime(2026, 10, 25, 9, 12, tzinfo=timezone.utc),
         "source": "CelesTrak", "age_days": 1.4, "status": "ok"},
        {"satellite": "IRNSS-1C", "epoch": datetime(2026, 10, 23, 9, 12, tzinfo=timezone.utc),
         "source": "Space-Track", "age_days": 3.1, "status": "bad"},
        {"satellite": "IRNSS-1D", "epoch": None, "source": "", "age_days": None, "status": "idle"},
    ]

    ok = orbit_age.tag(rows[0])
    bad = orbit_age.tag(rows[1])
    idle = orbit_age.tag(rows[2])

    assert 'class="chip ok">orbit 1.4 days old' in ok
    assert "Orbit record from 25 Oct 09:12 UTC, CelesTrak" in ok
    assert "alert at 2 days, stale at 3" in ok
    assert "off by" not in ok

    assert 'class="chip bad">orbit 3.1 days old' in bad
    assert "Orbit record from 23 Oct 09:12 UTC, Space-Track" in bad
    assert "alert at 2 days, stale at 3" in bad

    assert 'class="chip idle">no orbit record' in idle
    assert "No orbit record" in idle


def test_tag_and_table_add_the_broadcast_gap_when_one_is_published():
    rows = [
        {"satellite": "IRNSS-1B", "epoch": datetime(2026, 10, 25, 9, 12, tzinfo=timezone.utc),
         "source": "CelesTrak", "age_days": 1.4, "status": "ok"},
        {"satellite": "IRNSS-1C", "epoch": datetime(2026, 10, 23, 9, 12, tzinfo=timezone.utc),
         "source": "Space-Track", "age_days": 3.1, "status": "bad"},
    ]

    html = orbit_age.tag(rows[0], orbit_age._gap_by_satellite(GAP)["IRNSS-1B"])
    summary, body, stale_notice = orbit_age.section_markup(rows, gap=GAP)

    assert "Orbit record from 25 Oct 09:12 UTC, CelesTrak · off by 3.2 km on 25 Oct · alert at 2 days, stale at 3" in html
    assert summary.endswith(" · broadcast check 25 Oct")
    assert "Off from its broadcast orbit" in body
    assert 'class="num idle">3.2 km</b><span class="nt">25 Oct</span>' in body
    assert 'class="idle">–</b>' in body
    assert stale_notice == "Stale orbit records: IRNSS-1C since 23 Oct 09:12 UTC."


def test_section_markup_says_counts_space_track_note_and_stale_since_when():
    rows = [
        {"satellite": "IRNSS-1B", "epoch": datetime(2026, 10, 25, 9, 12, tzinfo=timezone.utc),
         "source": "CelesTrak", "age_days": 1.4, "status": "ok"},
        {"satellite": "IRNSS-1C", "epoch": datetime(2026, 10, 23, 9, 12, tzinfo=timezone.utc),
         "source": "Space-Track", "age_days": 3.1, "status": "bad"},
        {"satellite": "IRNSS-1D", "epoch": None, "source": "", "age_days": None, "status": "idle"},
    ]

    summary, body, stale_notice = orbit_age.section_markup(rows, spacetrack_note="busy")

    assert summary == ("3 satellites · 1 under 2 days · 2 need a look · Space-Track: busy"
                       " · broadcast check not available")
    assert "Satellite" in body and "Record from (date and time, UTC)" in body and "Age" in body and "Source" in body
    assert "Off from its broadcast orbit" in body
    assert 'class="num bad"' in body and "3.1 days" in body
    assert stale_notice == "Stale orbit records: IRNSS-1C since 23 Oct 09:12 UTC."


def test_orbit_gap_reads_the_published_json_and_falls_back_to_empty(monkeypatch):
    ORBIT_GAP.clear()

    class Reply:
        def json(self):
            return GAP

    monkeypatch.setattr(dashboard_data.requests, "get", lambda url, timeout: Reply())
    assert ORBIT_GAP() == GAP

    ORBIT_GAP.clear()
    monkeypatch.setattr(dashboard_data.requests, "get",
                        lambda url, timeout: (_ for _ in ()).throw(requests.Timeout("down")))
    assert ORBIT_GAP() == {}


def test_a_gap_that_is_not_a_number_is_left_out_not_a_crash():
    assert orbit_age._gap_by_satellite({"day": "2026-10-24", "satellites": [{"satellite": "IRNSS-1B", "typical_km": "9"},
                                                                            {"satellite": "QZS-2", "typical_km": 3.2}]}) \
        == {"QZS-2": (3.2, "24 Oct")}


BROADCAST_GAP = {
    **GAP,
    "satellites": [
        {**GAP["satellites"][0], "health": 0, "accuracy_m": 2.0},
        {"satellite": "IRNSS-1C", "signal_id": "I03", "record_epoch": None, "typical_km": None, "largest_km": None,
         "mostly": "", "note": "", "health": 130, "accuracy_m": 3.12},
        {"satellite": "IRNSS-1D", "signal_id": "I04", "record_epoch": None, "typical_km": None, "largest_km": None,
         "mostly": "", "note": "not in the day's broadcast file", "health": None, "accuracy_m": None},
    ],
    "leap_seconds": 18,
    "time_corrections": {"GPUT": -1.86, "GAGP": -0.32, "IRUT": 5.0},
}
BROADCAST_ROWS = [
    {"satellite": "IRNSS-1B", "epoch": datetime(2026, 10, 25, 9, 12, tzinfo=timezone.utc),
     "source": "CelesTrak", "age_days": 1.4, "status": "ok"},
    {"satellite": "IRNSS-1C", "epoch": None, "source": "", "age_days": None, "status": "idle"},
    {"satellite": "IRNSS-1D", "epoch": None, "source": "", "age_days": None, "status": "idle"},
]


def test_broadcast_health_accuracy_and_system_times_show_and_unhealthy_satellites_are_named():
    _, body, _ = orbit_age.section_markup(BROADCAST_ROWS, gap=BROADCAST_GAP)

    assert "Broadcast health" in body and "Signal accuracy" in body
    assert "healthy</b>" in body and "unhealthy (code 130)" in body and "not in the day" in body
    assert "2.0 m" in body and "3.1 m" in body
    assert "System times from the broadcast file: GPS−UTC -1.86 ns · Galileo−GPS -0.32 ns · 18 leap seconds" in body
    assert orbit_age._unhealthy_notice(BROADCAST_GAP, BROADCAST_ROWS) == (
        "Broadcasting unhealthy: IRNSS-1C (I03). From the IGS broadcast file of 25 Oct; "
        "work in progress, not yet part of the score.")
    assert orbit_age._missing_notice(BROADCAST_GAP, BROADCAST_ROWS) == "Not in the day's broadcast file: IRNSS-1D (I04)."
    assert "Broadcast health: unhealthy (code 130) · accuracy 3.1 m" in orbit_age.tag(
        BROADCAST_ROWS[1], status=orbit_age._status_by_satellite(BROADCAST_GAP)["IRNSS-1C"])


def test_an_old_payload_without_broadcast_fields_still_renders_without_notices_or_system_times():
    _, body, _ = orbit_age.section_markup(BROADCAST_ROWS, gap=GAP)

    assert "System times" not in body and "unhealthy" not in body
    assert orbit_age._unhealthy_notice(GAP, BROADCAST_ROWS) is None and orbit_age._missing_notice(GAP, BROADCAST_ROWS) is None


def test_official_status_links_only_where_there_is_one():
    from ui import official_status

    assert 'href="https://www.gsc-europa.eu/system-service-status/constellation-information"' in official_status.line("Galileo")
    assert 'target="_blank"' in official_status.line("NavIC")
    assert official_status.line("GLONASS") == "" and official_status.line("BeiDou-3") == ""


def test_a_qzss_code_is_flags_set_not_unhealthy():
    qzss = {"satellite": "QZS-3", "signal_id": "J07", "health": 1, "accuracy_m": 2.0, "note": ""}
    gap = {**GAP, "satellites": [qzss]}
    rows = [{"satellite": "QZS-3", "epoch": None, "source": "", "age_days": None, "status": "idle"}]

    _, body, _ = orbit_age.section_markup(rows, gap=gap)
    assert "flags set (code 1)" in body and "unhealthy" not in body
    assert orbit_age._unhealthy_notice(gap, rows) is None
