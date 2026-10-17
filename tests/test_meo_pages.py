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


def test_galileo_shows_its_planes_with_a_tile_per_satellite_and_says_what_is_missing():
    at = run(scope("Galileo"))
    bodies = htmls(at)

    assert len(tiles(at)) == 2
    assert any('<div class="part-title">Plane B · 2</div>' in body for body in bodies)
    assert any("2 of 2</span>" in body and "healthy and in step" in body for body in bodies)
    assert any("Orbit history: only the newest element set" in body for body in bodies)
    assert any("No orbit data: GSAT0210" in body for body in bodies)


def test_a_system_with_no_orbit_data_yet_says_so_and_the_page_still_runs():
    bodies = htmls(run(scope("GPS")))

    assert any("No orbit data for GPS yet" in body for body in bodies)


def test_station_keeping_says_how_much_history_there_is():
    bodies = htmls(run(scope("Galileo", "Station-keeping")))

    assert any("Galileo. Orbit history: only the newest element set" in body for body in bodies)


def test_the_dashboard_asks_for_the_meo_satellites_it_tracks_and_not_the_retired_ones(monkeypatch):
    from ui import data

    asked = []
    monkeypatch.setattr(celestrak, "refresh", lambda norads, now, clicked: asked.extend(norads))
    data.refresh()
    assert {37846, 39533, 100460} <= set(asked)   # GSAT0101, NAVSTAR 69 and COSMOS 2619
    assert 10893 not in asked                     # a GPS-I satellite, retired
