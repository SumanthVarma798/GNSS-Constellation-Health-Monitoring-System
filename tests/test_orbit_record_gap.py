"""Orbit record gap report helpers use one row model for markdown, JSON and summary text."""
import json
from datetime import date

from scripts import orbit_record_gap


ROWS = [
    {"satellite": "QZS-2", "signal_id": "J02", "record_epoch": "2026-10-18T00:00:00Z", "typical_km": 3.2, "largest_km": 41.0,
     "mostly": "ahead on its path", "note": "", "age_days": 0.5, "mean_longitude_deg": 139.74},
    {"satellite": "NavIC NVS-01", "signal_id": "I06", "record_epoch": None, "typical_km": None, "largest_km": None, "mostly": "",
     "note": "not in the day's broadcast file", "age_days": None, "mean_longitude_deg": None},
    {"satellite": "BeiDou-3 G8", "signal_id": "C58", "record_epoch": None, "typical_km": None, "largest_km": None, "mostly": "",
     "note": "not in the day's broadcast file", "age_days": None, "mean_longitude_deg": None},
]


def test_summary_words_cover_typical_worst_and_not_in_broadcast():
    said = orbit_record_gap.summary(ROWS)

    assert said == "3 satellites: orbit records off by 3.2 km typical, worst 41.0 km (QZS-2); 2 not in the broadcast file"


def test_json_payload_has_only_the_public_row_shape():
    payload = orbit_record_gap.json_payload(date(2026, 10, 17), "2026-10-18T06:00:00Z", ROWS)

    assert payload == {
        "day": "2026-10-17",
        "checked": "2026-10-18T06:00:00Z",
        "satellites": [
            {"satellite": "QZS-2", "signal_id": "J02", "record_epoch": "2026-10-18T00:00:00Z", "typical_km": 3.2,
             "largest_km": 41.0, "mostly": "ahead on its path", "note": "", "fitted_km": None},
            {"satellite": "NavIC NVS-01", "signal_id": "I06", "record_epoch": None, "typical_km": None, "largest_km": None,
             "mostly": "", "note": "not in the day's broadcast file", "fitted_km": None},
            {"satellite": "BeiDou-3 G8", "signal_id": "C58", "record_epoch": None, "typical_km": None, "largest_km": None,
             "mostly": "", "note": "not in the day's broadcast file", "fitted_km": None},
        ],
    }


def test_markdown_table_matches_the_existing_format_for_the_same_rows():
    text = orbit_record_gap.markdown_report(date(2026, 10, 17), 18, ROWS)

    expected = """# How far off each orbit record is, 2026-10-17

Gap = distance between where the orbit record nearest in time (rolled to the moment with SGP4) puts the satellite and where its own broadcast orbit puts it, every 15 minutes over the day (UTC) that a broadcast record covers. Along: + means the satellite is ahead of where the record says. Broadcast orbits are good to metres; a gap of kilometres is the record's.

| Satellite | Signal ID | Record from | Days between record and last sample | Typical gap | Largest gap | Mostly | Mean longitude (broadcast) | Yesterday's fitted record |
|---|---|---|---|---|---|---|---|---|
| QZS-2 | J02 | 18 Oct 00:00 | 0.5 days | 3.2 km | 41.0 km | ahead on its path | 139.74° |  |
| NavIC NVS-01 | I06 | | | | | not in the day's broadcast file | |  |
| BeiDou-3 G8 | C58 | | | | | not in the day's broadcast file | |  |

Broadcast file: IGS merged navigation file for the day, GPS - UTC = 18 s from its header. Orbit records: the bundled history plus CelesTrak's newest."""
    assert text == expected


def test_write_json_writes_the_public_payload(tmp_path):
    out = tmp_path / "gap.json"
    orbit_record_gap.write_json(out, date(2026, 10, 17), "2026-10-18T06:00:00Z", ROWS)

    assert json.loads(out.read_text())["satellites"][0]["satellite"] == "QZS-2"


def test_the_newest_day_falls_back_when_yesterdays_file_is_not_there_yet(monkeypatch, tmp_path):
    import requests
    from datetime import date
    monkeypatch.setattr(orbit_record_gap, "SAVED", tmp_path)
    asked = []

    class Reply:
        def __init__(self, status_code):
            self.status_code = status_code

    def head(url, timeout):
        asked.append(url)
        return Reply(404 if "2980000" in url else 200)

    monkeypatch.setattr(requests, "head", head)
    assert orbit_record_gap.newest_day(date(2026, 10, 26)) == date(2026, 10, 24)
    assert len(asked) == 2


def test_rows_for_day_fills_every_field_the_report_json_and_dashboard_read(monkeypatch):
    from datetime import datetime, timezone
    used = datetime(2026, 10, 24, 22, 0, tzinfo=timezone.utc)
    sample = lambda km, at: (km, km, 0.1, 0.0, 55.0, at)   # gap, along, cross, radial, longitude, UTC
    monkeypatch.setattr(orbit_record_gap, "navigation_text", lambda day, file=None: "text")
    monkeypatch.setattr(orbit_record_gap, "leap_seconds", lambda text: 18)
    monkeypatch.setattr(orbit_record_gap, "read_navigation", lambda text: {"I02": ["record"]})
    monkeypatch.setattr(orbit_record_gap, "read_status", lambda text: {
        "I02": {"health": 0, "accuracy_m": 3.1, "iod": 3, "newest": datetime(2026, 10, 24, 12, 0)}})
    monkeypatch.setattr(orbit_record_gap, "time_corrections", lambda text: {"GPUT": -1.86e-9})
    monkeypatch.setattr(orbit_record_gap, "read_glonass", lambda text: {})
    monkeypatch.setattr(orbit_record_gap, "tracked", lambda day: [("I002", "IRNSS-1B", 39635, "I02"),
                                                                  ("I003", "IRNSS-1C", 40269, "I03")])
    monkeypatch.setattr(orbit_record_gap, "orbit_records", lambda norads, now: {39635: ["record"]})
    monkeypatch.setattr(orbit_record_gap, "compare", lambda broadcast, records, signal_id, leap, day:
                        ([sample(2.0, used), sample(4.0, used)], used))

    rows, leap, checked, corrections = orbit_record_gap.rows_for_day(date(2026, 10, 24), now=datetime(2026, 10, 26, 6, tzinfo=timezone.utc))

    assert leap == 18 and checked == "2026-10-26T06:00:00Z"
    measured, missing = rows
    assert measured["record_epoch"] == "2026-10-24T22:00:00Z" and measured["typical_km"] == 3.0
    assert measured["largest_km"] == 4.0 and measured["mostly"] == "ahead on its path" and measured["age_days"] == 0.0
    assert measured["health"] == 0 and measured["accuracy_m"] == 3.1
    assert measured["broadcast_newest"] == "2026-10-24T12:00:00"
    assert missing["note"] == "not in the day's broadcast file" and missing["typical_km"] is None
    assert orbit_record_gap.json_payload(date(2026, 10, 24), checked, rows)["satellites"][0]["typical_km"] == 3.0


def test_a_probe_that_fails_tries_the_day_before(monkeypatch, tmp_path):
    import requests
    monkeypatch.setattr(orbit_record_gap, "SAVED", tmp_path)

    class Reply:
        status_code = 200

    def head(url, timeout):
        if "2980000" in url:
            raise requests.ConnectionError("blip")
        return Reply()

    monkeypatch.setattr(requests, "head", head)
    assert orbit_record_gap.newest_day(date(2026, 10, 26)) == date(2026, 10, 24)


def test_fitted_json_payload_has_the_fitted_row_shape_for_one_satellite(monkeypatch):
    nav = """\
     3.04           N: GNSS NAV DATA    M: MIXED            RINEX VERSION / TYPE
    18    18  1929     7                                    LEAP SECONDS
                                                            END OF HEADER
G05 2026 10 17 12 00 00-2.374444156890E-04-2.273736754430E-13 0.000000000000E+00
     7.900000000000E+01-3.321875000000E+01 4.205175162420E-09 1.338709451310E+00
    -1.775100827220E-06 5.256904172710E-03 4.507601261140E-06 5.153579437260E+03
     5.616000000000E+05-5.960464477540E-08 5.470402803660E-02-6.891787052150E-08
     9.824780880420E-01 3.054062500000E+02 1.514884101050E+00-7.996404510920E-09
     3.821587755900E-11 1.000000000000E+00 2.440000000000E+03 0.000000000000E+00
     2.000000000000E+00 0.000000000000E+00-1.024454832080E-08 7.900000000000E+01
     5.544180000000E+05 4.000000000000E+00
"""
    monkeypatch.setattr(orbit_record_gap, "tracked", lambda day: [("G005", "NAVSTAR 5", 56564, "G05")])
    monkeypatch.setattr(orbit_record_gap, "cospar_ids", lambda: {"G005": "2023-066A"})
    monkeypatch.setattr(orbit_record_gap, "broadcast_samples",
                        lambda broadcast, signal_id, leap, day: [(day.isoformat(), [0, 0, 0])] * 12)
    row = {"EPOCH": "2026-10-17T23:45:00.000000", "TLE_LINE1": "1 56564U 23066A   26290.98958333  .00000000  00000-0  00000+0 0  9999",
           "TLE_LINE2": "2 56564   0.4517   8.1717 0005748 207.1120 307.4819  1.00268485    02"}
    monkeypatch.setattr(orbit_record_gap, "fit_orbit",
                        lambda samples, norad, object_id, name: (row, 0.12))

    rows = orbit_record_gap.fitted_satellites(date(2026, 10, 17), nav, "2026-10-18T06:00:00Z")

    assert orbit_record_gap.fitted_json_payload(date(2026, 10, 17), "2026-10-18T06:00:00Z", rows) == {
        "day": "2026-10-17",
        "checked": "2026-10-18T06:00:00Z",
        "satellites": [{"satellite": "NAVSTAR 5", "signal_id": "G05", "norad": 56564,
                        "fit_km": 0.12, "row": row}],
    }
