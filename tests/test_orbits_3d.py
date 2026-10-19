"""The 3D orbit view: true orbit planes from the bundled elements, plain numbers for the page, and a page safe to embed."""
import json
import math

import numpy as np
import pandas as pd
import pytest

from analysis.bundled_run import load_bundled_gp_as_dataframes
from config.config import BEIDOU3_SATS
from ui import palette
from data.celestrak import as_history_row
from test_celestrak import IRNSS_1B
from ui.components.orbit_view import NOT_REACHED, hover_cards, orbit_view_html, orbit_view_payload
from ui.data import GENERATION
from ui.figures.constellation_3d import BELT_RADIUS
from ui.figures.fleet import fleet_rows, orbit_words, plane_letters
from ui.figures.orbits_3d import EARTH_KM, LAND_FILE, ORBIT_POINTS, latest_elements, orbit_points, position_at
from ui.figures.slot_rows import slot_rows
from ui.pages_data import load_master_map_data

HOSTILE = "</script><script>alert(1)</script>"


@pytest.fixture(scope="module")
def history():
    return pd.concat(load_bundled_gp_as_dataframes("beidou3", BEIDOU3_SATS), ignore_index=True)


@pytest.fixture(scope="module")
def beidou(history):
    return latest_elements(history)


def normal(el):
    loop = orbit_points(el)
    n = np.cross(loop[:, 0], loop[:, 45])
    return n / np.linalg.norm(n)


def node_deg(el):
    """Direction of the ascending node in the equator plane, worked out from the drawn orbit."""
    n = normal(el)
    return math.degrees(math.atan2(n[0], -n[1])) % 360


def test_beidou3_igso_orbits_lie_in_three_planes_with_nodes_120_degrees_apart(beidou):
    names = ["BeiDou-3 I1", "BeiDou-3 I2", "BeiDou-3 I3"]
    nodes = sorted(node_deg(beidou[n]) for n in names)
    gaps = [nodes[1] - nodes[0], nodes[2] - nodes[1], 360 - nodes[2] + nodes[0]]
    assert all(abs(gap - 120) < 10 for gap in gaps), gaps
    for first, second in [(0, 1), (1, 2), (0, 2)]:   # distinct planes: normals far apart
        angle = math.degrees(math.acos(np.dot(normal(beidou[names[first]]), normal(beidou[names[second]]))))
        assert angle > 60


def test_a_geo_orbit_lies_in_the_equator_plane_at_geostationary_height(beidou):
    el = beidou["BeiDou-3 G4"]
    loop = orbit_points(el)
    assert np.abs(loop[2]).max() < 0.3   # within a few degrees of the equator
    assert np.allclose(np.linalg.norm(loop, axis=0), 6.61, atol=0.05)
    here = position_at(el, el["epoch"])
    assert abs(np.linalg.norm(here) - 6.61) < 0.05 and abs(here[2]) < 0.3


def test_the_payload_has_one_entry_per_row_with_its_loop_position_slot_and_card(history):
    rows = slot_rows([{"Satellite": "BeiDou-3 G4", "Designated Lon (°)": 140.0, "Current Mean Lon (°)": 142.0,
                       "Lon Slot Deviation (°)": 2.0, "Lon Deviation Score": 50.0},
                      {"Satellite": "NO-ELEMENTS", "Designated Lon (°)": 10.0}])
    scene = orbit_view_payload(rows, history, None)
    geo, missing = scene["satellites"]
    assert len(geo["loop"]) == ORBIT_POINTS and all(len(p) == 3 for p in geo["loop"])
    assert abs(math.hypot(*geo["at"]) - 6.61) < 0.05
    assert geo["slot_at"][2] == 0 and abs(math.hypot(*geo["slot_at"]) - BELT_RADIUS) < 0.01
    assert geo["state"] == palette.SLOT_OFF and geo["slot"] == "off its slot, 2.00°" and geo["name"] == "BeiDou-3 G4"
    assert missing["loop"] is None and missing["at"] is None and missing["slot_at"] is not None
    assert scene["land"] and all(abs(math.hypot(*p) - 1) < 0.01 for p in scene["land"])


def test_the_page_gets_earths_turn_so_it_can_say_which_longitude_faces_the_viewer(history):
    rows = slot_rows([{"Satellite": "BeiDou-3 G4", "Designated Lon (°)": 140.0}])
    scene = orbit_view_payload(rows, history, None)
    x, y, _ = scene["satellites"][0]["slot_at"]
    assert (math.degrees(math.atan2(y, x)) - scene["turn"]) % 360 == pytest.approx(140.0, abs=0.01)
    assert scene["earth_km"] == EARTH_KM


def meo_row(norad):
    """A CelesTrak row for a MEO satellite in BeiDou-3's plane A."""
    return as_history_row({**IRNSS_1B, "NORAD_CAT_ID": norad, "MEAN_MOTION": 1.862, "INCLINATION": 54.2,
                           "RA_OF_ASC_NODE": 298.0})


def test_the_payload_holds_both_sets_with_plane_and_slot_words(history):
    rows = slot_rows([{"Satellite": "BeiDou-3 G4", "Designated Lon (°)": 140.0},
                      {"Satellite": "BeiDou-3 I1", "Designated Lon (°)": 111.0}])
    fleet = fleet_rows(GENERATION["BeiDou-3"], load_master_map_data())
    # CelesTrak lists G4 and M7 (43107); it leaves out the tracked I1 (44204) and M3-S (41315)
    live = {"rows": {43107: [meo_row(43107)], 41315: [meo_row(41315)]}, "listed": {56564, 43107}}
    payload = orbit_view_payload(rows, history, None, fleet, live)
    sats = {s["name"]: s for s in payload["satellites"]}

    assert list(sats) == ["BeiDou-3 G4", "BeiDou-3 I1", "Beidou-3 M3-S", "Beidou-3 M7"]
    g4, i1, m3s, m7 = sats.values()
    assert g4["tracked"] and g4["service"] and g4["group"] == "GEO" and g4["note"] == ""
    assert i1["tracked"] and not i1["service"] and i1["note"] == "not listed by CelesTrak"   # hidden under In service
    assert m7["orbit"] == "MEO · plane A, slot A-4" and m7["group"] == "Plane A" and len(m7["loop"]) == ORBIT_POINTS
    assert not m7["tracked"] and m7["service"] and m7["slot"] == "not scored" and m7["score"] is None
    assert m7["note"] == "listed by CelesTrak" and m7["slot_at"] is None
    assert not m3s["service"] and m3s["group"] == "Plane B" and m3s["note"] == "not listed by CelesTrak"
    assert payload["notes"] == {"service": "", "all": f"Orbits known for 4 of {len(fleet)}."}


def test_two_satellites_with_one_name_keep_their_own_orbit_and_plane():
    fleet = [{"norad": 58654, "name": "Beidou-3 M28", "group": "Plane B", "orbit": "MEO · plane B"},
             {"norad": 61187, "name": "Beidou-3 M28", "group": "Plane A", "orbit": "MEO · plane A"}]
    live = {"rows": {58654: [as_history_row({**IRNSS_1B, "NORAD_CAT_ID": 58654, "MEAN_MOTION": 1.862, "RA_OF_ASC_NODE": 58.0})],
                     61187: [meo_row(61187)]}, "listed": {58654, 61187}}
    b, a = orbit_view_payload([], None, None, fleet, live)["satellites"]

    assert (b["group"], a["group"]) == ("Plane B", "Plane A") and b["loop"] != a["loop"]


def test_before_celestrak_answers_in_service_means_the_tracked_satellites(history):
    rows = slot_rows([{"Satellite": "BeiDou-3 G4", "Designated Lon (°)": 140.0}])
    fleet = fleet_rows(GENERATION["BeiDou-3"], load_master_map_data())
    payload = orbit_view_payload(rows, history, None, fleet, {"rows": {}, "listed": None})

    assert [(s["name"], s["service"]) for s in payload["satellites"]] == [("BeiDou-3 G4", True)]
    assert payload["notes"]["service"] == NOT_REACHED


def test_plane_words_come_from_the_registry():
    registry = [{"plane": "1", "slot": "A-4"}, {"plane": "1", "slot": ""}, {"plane": "G", "slot": "140E"},
                {"plane": "", "slot": ""}]
    letters = plane_letters(registry)
    assert [orbit_words(row, letters) for row in registry] == ["MEO · plane A, slot A-4", "MEO · plane A",
                                                                "GEO · slot 140E", ""]


def test_hover_cards_say_the_state_in_words_and_band_the_score():
    rows = slot_rows([{"Satellite": "A", "Designated Lon (°)": 10.0, "Current Mean Lon (°)": 12.0,
                       "Lon Slot Deviation (°)": 2.0, "Lon Deviation Score": 50.0}],
                     [{"name": "B", "slot_lon": 20.0, "actual_lon": None, "note": "set aside, graveyard orbit"}])
    health = pd.DataFrame([{"Satellite": "A", "Type": "GEO", "Overall Score": 65.0}])
    a, b = hover_cards(rows, health)
    assert a == {"name": "A", "orbit": "GEO", "slot": "off its slot, 2.00°", "status": "warn", "score": 65.0, "band": "warn"}
    assert b["orbit"] == "set aside, graveyard orbit" and b["score"] is None and b["status"] == "bad"


def test_names_stay_out_of_the_markup_and_nothing_is_fetched():
    rows = slot_rows([{"Satellite": HOSTILE, "Designated Lon (°)": 10.0}])
    page = orbit_view_html(rows, None, None)
    assert HOSTILE not in page and "\\u003c/script\\u003e" in page
    assert "<script src" not in page and "__DATA__" not in page and "__ROOT__" not in page


def test_the_land_file_is_small_and_names_its_source():
    land = json.loads(LAND_FILE.read_text())
    assert "Natural Earth" in land["source"] and LAND_FILE.stat().st_size < 60_000
