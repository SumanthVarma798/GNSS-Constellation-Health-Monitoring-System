"""The slot pictures on the Health Overview tab: judged against each satellite's OWN slot, and never able to break the page.

The full-page tests drive the real app (app.py) as tests/test_dashboard_notices.py does.
"""
import json
from datetime import datetime
from functools import cache
from pathlib import Path

import pandas as pd
import pytest
import time_machine
from streamlit.testing.v1 import AppTest

from data.tle_cache import DATA_DIR
from test_golden_scores import GOLDEN
from ui import orbit_section
from ui.orbit_section import designated_longitude, set_aside_positions, set_aside_rows

ROOT = Path(__file__).resolve().parent.parent
HISTORY = json.loads((DATA_DIR / "navic_gp_history.json").read_text())["satellites"]
BOOM = "boom: this picture failed"


def html_parts(at):
    """The HTML strings the page put on screen, in order."""
    return [part.proto.body for part in at.get("html")]


@cache
def page_parts(constellation):
    """The HTML parts of the dashboard for one constellation, bundled data, frozen clock."""
    with time_machine.travel(datetime.fromisoformat(GOLDEN["frozen_utc"]), tick=False):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=600)
        at.run()
        at.sidebar.selectbox[0].set_value(constellation).run()
        next(b for b in at.button if "Load Bundled" in b.label).click().run()
        assert not at.exception, [e.value for e in at.exception]
        return tuple(html_parts(at))


def card_for(parts, name):
    return next(part for part in parts if f">{name}: " in part)


def history_for(*names):
    """A history table like the app's, with the bundled records of the named satellites."""
    records = [{**record, "satellite": name, "EPOCH": pd.Timestamp(record["EPOCH"]),
                "MEAN_MOTION": float(record["MEAN_MOTION"])} for name in names for record in HISTORY[name]]
    return pd.DataFrame(records)


def test_navic_page_says_where_each_satellite_stands_in_words():
    parts = page_parts("NavIC")

    assert "off its slot" in card_for(parts, "NVS-01")
    assert "left its slot" in card_for(parts, "IRNSS-1D")
    assert "position not known" in card_for(parts, "IRNSS-1F")
    assert any("data:image/svg+xml" in part for part in parts)        # the flat belt, as an image: st.html drops svg
    assert sum("sparts-card" in part for part in parts) >= 7          # a score card per scored satellite


@pytest.mark.parametrize("constellation", ["QZSS", "BeiDou-3"])
def test_other_constellations_draw_without_error(constellation):
    assert any("data:image/svg+xml" in part for part in page_parts(constellation))


@pytest.mark.parametrize("name, slot", [
    ("NVS-01", 131.5), ("IRNSS-1D", 111.75),            # NavIC: the config's longitude
    ("QZS-3 (Michibiki-3)", 127.0),                     # QZSS: its central longitude
    ("BeiDou-3 I1", 118.0),                             # BeiDou-3: its central longitude
])
def test_designated_longitude_reads_the_config(name, slot):
    assert designated_longitude(name) == slot


def test_designated_longitude_is_none_for_a_name_the_config_does_not_know():
    assert designated_longitude("NOT-A-SATELLITE") is None


def test_a_set_aside_satellite_with_history_has_left_its_slot_and_its_position_is_known():
    positions = set_aside_positions({"IRNSS-1D"}, history_for("IRNSS-1D"))
    [item] = set_aside_rows(positions, designated_longitude)

    assert item["name"] == "IRNSS-1D" and item["slot_lon"] == 111.75
    assert item["actual_lon"] == pytest.approx(-25.1, abs=0.1)       # over the Atlantic, nowhere near its slot
    assert positions["IRNSS-1D"]["altitude_km"] > 35786


def test_a_set_aside_satellite_without_history_still_has_left_its_slot_but_no_position():
    for history in (None, history_for("IRNSS-1B")):                  # no table, or none of its records
        positions = set_aside_positions({"IRNSS-1D"}, history)
        [item] = set_aside_rows(positions, designated_longitude)

        assert positions == {"IRNSS-1D": None}
        assert item["actual_lon"] is None and item["slot_lon"] == 111.75


def test_a_set_aside_satellite_with_no_slot_is_left_out_of_the_rows():
    assert set_aside_rows({"NOT-A-SATELLITE": None}, designated_longitude) == []


def draw_with_one_satellite():
    import pandas as pd
    from ui import orbit_section
    health = pd.DataFrame([{"Satellite": "IRNSS-1B", "Designated Lon (°)": 55.0, "Current Mean Lon (°)": 55.1,
                            "Lon Slot Deviation (°)": 0.1, "Lon Deviation Score": 100.0, "Overall Score": 90.0,
                            "Health Status": "🟢 Healthy", "_inc_score": 90.0, "_maintenance_score": 90.0,
                            "_uniformity_score": 90.0, "_drift_score": 90.0}])
    orbit_section.render_slot_pictures(health, set(), orbit_section.designated_longitude, None, "NavIC")


def test_the_pictures_draw_for_a_single_satellite_with_its_status_in_words():
    at = AppTest.from_function(draw_with_one_satellite).run()

    assert not at.exception
    assert any("IRNSS-1B" in part and "Healthy" in part and "🟢" not in part for part in html_parts(at))


@pytest.mark.parametrize("figure", ["slot_belt", "score_parts", "constellation_3d"])
def test_a_figure_that_raises_gives_one_notice_and_the_page_carries_on(monkeypatch, figure):
    def boom(*args, **kwargs):
        raise RuntimeError(BOOM)
    monkeypatch.setattr(orbit_section, figure, boom)

    at = AppTest.from_function(draw_with_one_satellite).run()

    assert not at.exception
    assert sum("could not be drawn" in part and BOOM in part for part in html_parts(at)) == 1
