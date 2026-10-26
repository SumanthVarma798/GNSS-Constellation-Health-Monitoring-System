"""Orbit record ages: source choice, age bands, and the overview strip/section markup."""
from datetime import datetime, timedelta, timezone

from ui import orbit_age
from ui.data import orbit_age_rows

NOW = datetime(2026, 10, 26, 3, 30, tzinfo=timezone.utc)


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


def test_section_markup_says_counts_space_track_note_and_stale_since_when():
    rows = [
        {"satellite": "IRNSS-1B", "epoch": datetime(2026, 10, 25, 9, 12, tzinfo=timezone.utc),
         "source": "CelesTrak", "age_days": 1.4, "status": "ok"},
        {"satellite": "IRNSS-1C", "epoch": datetime(2026, 10, 23, 9, 12, tzinfo=timezone.utc),
         "source": "Space-Track", "age_days": 3.1, "status": "bad"},
        {"satellite": "IRNSS-1D", "epoch": None, "source": "", "age_days": None, "status": "idle"},
    ]

    summary, body, stale_notice = orbit_age.section_markup(rows, spacetrack_note="busy")

    assert summary == "3 satellites · 1 under 2 days · 2 need a look · Space-Track: busy"
    assert "Satellite" in body and "Record from (date and time, UTC)" in body and "Age" in body and "Source" in body
    assert 'class="num bad"' in body and "3.1 days" in body
    assert stale_notice == "Stale orbit records: IRNSS-1C since 23 Oct 09:12 UTC."
