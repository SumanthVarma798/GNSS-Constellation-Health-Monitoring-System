"""The 3D orbit view: true orbit planes from the bundled elements, colours from the rows, and a page safe to embed."""
import json
import math

import numpy as np
import pandas as pd
import pytest

from analysis.bundled_run import load_bundled_gp_as_dataframes
from config.config import BEIDOU3_SATS
from ui import palette
from ui.components.orbit_view import hover_cards, orbit_view_html
from ui.figures.orbits_3d import LAND_FILE, latest_elements, orbit_points, orbits_3d, position_at
from ui.figures.slot_rows import slot_rows

HOSTILE = "</script><script>alert(1)</script>"


@pytest.fixture(scope="module")
def beidou():
    return latest_elements(pd.concat(load_bundled_gp_as_dataframes("beidou3", BEIDOU3_SATS), ignore_index=True))


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


def test_each_satellite_its_orbit_and_its_slot_share_one_meta_and_take_the_rows_colours(beidou):
    rows = slot_rows([{"Satellite": "BeiDou-3 G4", "Designated Lon (°)": 140.0, "Current Mean Lon (°)": 142.0,
                       "Lon Slot Deviation (°)": 2.0, "Lon Deviation Score": 50.0}])
    figure = orbits_3d(rows, beidou)
    mine = [t for t in figure.data if t.meta == 0]
    assert len(mine) == 3   # slot, orbit, satellite
    orbit = next(t for t in mine if t.mode == "lines")
    assert orbit.line.color == palette.SLOT_COLOURS[palette.SLOT_OFF]
    assert next(t for t in mine if t.marker.symbol == "circle-open").marker.color == palette.SLOT_EMPTY


def test_a_satellite_with_no_elements_keeps_only_its_slot():
    rows = slot_rows([{"Satellite": "NO-ELEMENTS", "Designated Lon (°)": 10.0}])
    figure = orbits_3d(rows, {})
    assert [t.meta for t in figure.data if t.meta is not None] == [0]


def test_hover_cards_say_the_state_in_words_and_band_the_score():
    rows = slot_rows([{"Satellite": "A", "Designated Lon (°)": 10.0, "Current Mean Lon (°)": 12.0,
                       "Lon Slot Deviation (°)": 2.0, "Lon Deviation Score": 50.0}],
                     [{"name": "B", "slot_lon": 20.0, "actual_lon": None, "note": "set aside, graveyard orbit"}])
    health = pd.DataFrame([{"Satellite": "A", "Type": "GEO", "Overall Score": 65.0}])
    a, b = hover_cards(rows, health)
    assert a == {"name": "A", "orbit": "GEO", "slot": "off its slot, 2.00°", "status": "warn", "score": 65.0, "band": "warn"}
    assert b["orbit"] == "set aside, graveyard orbit" and b["score"] is None and b["status"] == "bad"


def test_the_page_carries_plotly_and_no_raw_hostile_name():
    rows = slot_rows([{"Satellite": HOSTILE, "Designated Lon (°)": 10.0}])
    page = orbit_view_html(rows, None, None)
    assert HOSTILE not in page
    assert "<script src" not in page   # plotly is inline: the demo may be offline
    assert "Plotly" in page and "__DATA__" not in page and "__PLOTLY__" not in page


def test_the_land_file_is_small_and_names_its_source():
    land = json.loads(LAND_FILE.read_text())
    assert "Natural Earth" in land["source"] and LAND_FILE.stat().st_size < 60_000
