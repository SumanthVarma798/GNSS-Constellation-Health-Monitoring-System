"""Orbit record ages: source choice, age bands, and the overview strip/section markup."""
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


def test_strip_markup_has_a_dot_tip_per_satellite_and_legend_uses_thresholds():
    rows = [
        {"satellite": "IRNSS-1B", "epoch": datetime(2026, 10, 25, 9, 12, tzinfo=timezone.utc),
         "source": "CelesTrak", "age_days": 1.4, "status": "ok"},
        {"satellite": "IRNSS-1C", "epoch": datetime(2026, 10, 23, 9, 12, tzinfo=timezone.utc),
         "source": "Space-Track", "age_days": 3.1, "status": "bad"},
    ]

    html = orbit_age.strip_html(rows)

    assert "Orbit record age" in html
    assert "under 2 days" in html
    assert "2 days or more: alert" in html
    assert "3 days or more: stale" in html
    assert "no record" in html
    assert "IRNSS-1B · 1.4 days old · CelesTrak · 25 Oct 09:12 UTC" in html
    assert "IRNSS-1C · 3.1 days old · Space-Track · 23 Oct 09:12 UTC" in html
    assert html.count('class="oa-dot ') == 2


def test_strip_and_table_add_the_broadcast_gap_when_one_is_published():
    rows = [
        {"satellite": "IRNSS-1B", "epoch": datetime(2026, 10, 25, 9, 12, tzinfo=timezone.utc),
         "source": "CelesTrak", "age_days": 1.4, "status": "ok"},
        {"satellite": "IRNSS-1C", "epoch": datetime(2026, 10, 23, 9, 12, tzinfo=timezone.utc),
         "source": "Space-Track", "age_days": 3.1, "status": "bad"},
    ]

    html = orbit_age.strip_html(rows, GAP)
    summary, body, stale_notice = orbit_age.section_markup(rows, gap=GAP)

    assert "IRNSS-1B · 1.4 days old · CelesTrak · 25 Oct 09:12 UTC · off by 3.2 km on 25 Oct" in html
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
