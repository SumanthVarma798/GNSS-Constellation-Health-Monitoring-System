"""The pages for GPS, GLONASS and Galileo, driven without a browser, and what they ask CelesTrak for. No network."""
import pytest

from data import celestrak
from test_dashboard_shell import htmls, run, segmented_controls_rerun, tiles  # noqa: F401 (a fixture)
from test_meo_data import GSAT0101, GSAT0102


@pytest.fixture(autouse=True)
def celestrak_answers_with_two_galileo_satellites(monkeypatch):
    rows = {row["NORAD_CAT_ID"]: celestrak.as_history_row(row) for row in (GSAT0101, GSAT0102)}
    monkeypatch.setattr(celestrak, "state", {"rows": {}, "listed": None, "tried": None, "fetched": None, "ok": True})
    monkeypatch.setattr(celestrak, "fetch", lambda norads: (rows, set(rows)))


def scope(name, page="Overview"):
    def setup(at):
        at.session_state["scope"], at.session_state["page"] = name, page
    return setup


def test_the_constellation_chips_offer_the_three_meo_systems_after_the_others():
    from ui.shell import CONSTELLATIONS

    assert CONSTELLATIONS == ("NavIC", "QZSS", "BeiDou-3", "GPS", "GLONASS", "Galileo")


def test_galileo_shows_its_planes_and_says_what_is_missing():
    at = run(scope("Galileo"))
    bodies = htmls(at)

    assert any('<div class="part-title">Plane B · 2</div>' in body for body in bodies)
    assert any("2 of 2</span>" in body and "healthy and in step" in body for body in bodies)
    assert any("Orbit history: only the newest element set" in body for body in bodies)
    assert any("No orbit data: GSAT0210" in body for body in bodies)


def test_a_recent_addition_is_shown_in_a_coloured_notice_before_warnings(monkeypatch):
    from evidence import registry_tables

    monkeypatch.setattr(registry_tables, "recently_added", lambda constellation, today: [("GSAT0999", "2026-10-26")])
    bodies = htmls(run(scope("Galileo")))
    new_at = next(i for i, body in enumerate(bodies) if "New on the dashboard: GSAT0999" in body)
    missing_at = next(i for i, body in enumerate(bodies) if "No orbit data: GSAT0210" in body)

    assert "notice accent" in bodies[new_at]
    assert "New on the dashboard: GSAT0999 (added 26 Oct 2026 after an approved registry proposal)." in bodies[new_at]
    assert new_at < missing_at


def test_a_system_with_no_orbit_data_yet_says_so_and_the_page_still_runs():
    bodies = htmls(run(scope("GPS")))

    assert any("No orbit data for GPS yet" in body for body in bodies)


def gps_row(norad, name, mean_anomaly):
    """A made-up GPS element set: circular, plane D's node, at argument of latitude `mean_anomaly`."""
    return {**GSAT0101, "OBJECT_NAME": name, "NORAD_CAT_ID": norad, "MEAN_MOTION": 2.00563, "ECCENTRICITY": 0.0001,
            "INCLINATION": 55.0, "RA_OF_ASC_NODE": 100.0, "ARG_OF_PERICENTER": 0.0, "MEAN_ANOMALY": mean_anomaly}


def test_gps_opens_on_its_planes_without_tiles_and_the_switch_shows_the_tiles(monkeypatch):
    rows = {row["NORAD_CAT_ID"]: celestrak.as_history_row(row)
            for row in (gps_row(62339, "NAVSTAR 83", 258.0), gps_row(39741, "NAVSTAR 70", 167.4))}   # D2A, D4
    monkeypatch.setattr(celestrak, "fetch", lambda norads: (rows, set(rows)))

    at = run(scope("GPS"))
    bodies = htmls(at)
    assert at.session_state["meo_view"] == "Planes"
    assert tiles(at) == []
    card = next(body for body in bodies if '<div class="part-title">Plane D · 2</div>' in body)
    assert all(words in card for words in ("2 of 2", "none", "0.0° · within 5°", "steady", "· within 8°"))
    assert any("Measured against limits, every satellite" in str(e.label) for e in at.checkbox)

    at.button_group(key="meo_view").set_value("Satellites").run()
    assert len(tiles(at)) == 2
    assert any("Plane D</span><span class=\"muted\">2 satellites · 2 in step" in body for body in htmls(at))
    assert not any("part-title\">Plane D" in body for body in htmls(at))


def test_a_plane_card_says_which_way_its_node_drifts():
    from ui import meo_overview

    members = [{"plane": "A", "plane_agrees": True, "signal_id": "G01", "name": "S", "u": 10.0, "slot": "A1",
                "slot_at": 10.0, "checks": [("plane", 0.0, 1.2, 1.2, 100), ("spacing", 60.0, 61.0, 1.0, 100)]}]
    drift = {"offset": 1.2, "offset_limit": 2.0, "rate": 0.3, "gap": 1.0, "gap_limit": 8.0}

    assert "0.30° a year, away" in meo_overview._plane_card("A", members, drift)
    assert "0.30° a year, back" in meo_overview._plane_card("A", members, {**drift, "rate": -0.3})
    assert "6.0° · over 2°" in meo_overview._plane_card("A", members, {**drift, "offset": -6.0})


def test_station_keeping_says_how_much_history_there_is():
    bodies = htmls(run(scope("Galileo", "Station-keeping")))

    assert any("Galileo. Orbit history: only the newest element set" in body for body in bodies)


def test_the_dashboard_asks_for_the_meo_satellites_it_tracks_and_not_the_retired_ones(monkeypatch):
    from ui import data

    asked = []
    monkeypatch.setattr(
        celestrak, "refresh",
        lambda norads, now, clicked: (asked.extend(norads),
                                      {"rows": {}, "listed": set(), "tried": now, "fetched": None, "ok": True,
                                       "failing_since": None})[1],
    )
    monkeypatch.setattr(data.spacetrack, "refresh", lambda norads, now, login: None)
    data.refresh()
    assert {37846, 39533, 100460} <= set(asked)   # GSAT0101, NAVSTAR 69 and COSMOS 2619
    assert 10893 not in asked                     # a GPS-I satellite, retired


def test_a_listed_slot_without_a_spacing_check_says_why_not_that_the_slot_is_unlisted():
    from ui import meo_overview, palette

    def row(height_score, slot_at):
        return {"plane_agrees": True, "plane": "B", "slot": "B2", "slot_at": slot_at,
                "checks": [("plane", 0.0, 0.1, 0.1, 100), ("height", 26560.0, 26900.0, 340.0, height_score)]}

    assert meo_overview.state_of(row(40, 12.0)) == (palette.SLOT_UNKNOWN, "away from its working height", None)
    assert meo_overview.state_of(row(100, 12.0)) == (palette.SLOT_UNKNOWN, "no neighbour to space against", None)
    assert meo_overview.state_of(row(100, None)) == (palette.SLOT_UNKNOWN, "slot B2 not listed", None)


def test_the_geometry_page_says_it_does_not_cover_a_global_system_yet():
    bodies = htmls(run(scope("Galileo", "Geometry")))

    assert any("Geometry covers NavIC, QZSS and BeiDou-3 only, not yet Galileo" in body for body in bodies)
