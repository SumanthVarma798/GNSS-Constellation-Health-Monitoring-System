"""The World map's payload: health per satellite, the NavIC area, tracks split at the antimeridian, and its page."""
from datetime import datetime, timezone

from ui import shell
from ui.components.world_view import payload, split_track

GAP = {"day": "2026-10-27", "satellites": [
    {"satellite": "GSAT0202", "signal_id": "E14", "health": 130, "accuracy_m": 3.12, "note": ""},
    {"satellite": "QZS-3", "signal_id": "J07", "health": 1, "accuracy_m": 2.0, "note": ""},
    {"satellite": "IRNSS-1C", "signal_id": "I03", "health": None, "accuracy_m": None,
     "note": "not in the day's broadcast file"},
]}
SYSTEMS = [
    {"name": "Galileo", "satellites": [{"name": "GSAT0202", "lat": 10.0, "lon": 170.0, "height": 23222.0}],
     "tracks": {"GSAT0202": {"lat": [10.0, 11.0, 12.0], "lon": [170.0, 179.0, -172.0], "height": [1, 1, 1]}}},
    {"name": "QZSS", "satellites": [{"name": "QZS-3", "lat": 0.1, "lon": 127.0, "height": 35786.0}], "tracks": {}},
    {"name": "NavIC", "satellites": [{"name": "IRNSS-1C", "lat": 4.0, "lon": 83.0, "height": 35786.0}], "tracks": {}},
]


def test_each_satellite_carries_its_broadcast_health_as_the_orbit_age_section_words_it():
    page = payload(SYSTEMS, GAP, datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc))
    sats = {s["name"]: s for system in page["systems"] for s in system["satellites"]}

    assert (sats["GSAT0202"]["health_words"], sats["GSAT0202"]["health_status"]) == ("unhealthy (code 130)", "bad")
    assert (sats["QZS-3"]["health_words"], sats["QZS-3"]["health_status"]) == ("healthy (sends L1C/A)", "ok")
    assert sats["IRNSS-1C"]["health_status"] == "idle" and sats["GSAT0202"]["accuracy_words"] == "3.1 m"
    assert any(key["words"] == "some signals off" and key["status"] == "warn" for key in page["health_key"])
    assert page["area"]["west"] == 30.0 and page["area"]["east"] == 130.0 and "NavIC" in page["area"]["label"]
    assert page["as_of"] == "14:00" and page["day"] == "27 Oct"


def test_a_track_over_the_antimeridian_is_split_so_no_line_crosses_the_map():
    segments = split_track({"lat": [10.0, 11.0, 12.0], "lon": [170.0, 179.0, -172.0], "height": [1, 1, 1]})
    assert [s["lon"] for s in segments] == [[170.0, 179.0], [-172.0]]


def test_the_world_map_is_a_whole_system_page_after_master_map():
    titles = [title for title, _ in shell.PAGES]
    assert titles.index("World map") == titles.index("Master map") + 1
    assert ("World map", "views/world_map.py") in shell.PAGES and "World map" in shell.OWN_FILTERS
