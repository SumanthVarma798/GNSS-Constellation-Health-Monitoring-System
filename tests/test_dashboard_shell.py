"""The new dashboard (dashboard.py): a top bar and the Overview page, with no side panel.

These drive the real script without a browser, with the clock frozen as tests/test_dashboard_notices.py does.
"""
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import time_machine
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import ButtonGroup

from test_golden_scores import GOLDEN
from ui.shell import age_words

ROOT = Path(__file__).resolve().parent.parent
FROZEN = datetime.fromisoformat(GOLDEN["frozen_utc"])


@pytest.fixture(autouse=True)
def segmented_controls_rerun(monkeypatch):
    """AppTest 1.45 reads a segmented control's single value (a string or number) as a list of choices and
    fails on the next run. This reads it as one choice."""
    def indices(self):
        chosen = self.value if isinstance(self.value, list) else [] if self.value is None else [self.value]
        return [self.options.index(self.format_func(v)) for v in chosen]
    monkeypatch.setattr(ButtonGroup, "indices", property(indices))


def run(setup=lambda at: None, now=FROZEN):
    """Open the dashboard, let `setup` change the state or widgets, and run it again."""
    with time_machine.travel(now, tick=False):
        at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=600).run()
        setup(at)
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def htmls(at):
    return [part.proto.body for part in at.get("html")]


def tiles(at):
    return [h for body in htmls(at) for h in body.split('<div class="tile ')[1:]]


def healthy_in_slot(constellation):
    """The count the header should show, from the scores recorded from app.py."""
    sats = GOLDEN["satellites"][constellation].values()
    return sum(1 for s in sats if (s.get("Overall Score") or 0) >= 80 and s.get("Lon Deviation Score") == 100)


def test_runs_with_no_side_panel():
    at = run()

    assert len(at.sidebar) == 0


def test_navic_is_the_default_and_shows_a_tile_per_satellite_with_its_count():
    at = run()

    assert at.session_state["scope"] == "NavIC"
    assert len(tiles(at)) == 8   # 7 scored, and IRNSS-1D set aside
    assert any(f"{healthy_in_slot('NavIC')} of 8</span>" in body and "healthy and in their slot" in body for body in htmls(at))


def test_a_satellite_set_aside_is_a_tile_that_says_so():
    set_aside = [t for t in tiles(run()) if "IRNSS-1D" in t]

    assert len(set_aside) == 1
    assert "set aside" in set_aside[0] and "left its slot" in set_aside[0]


def test_switching_to_qzss_shows_its_five():
    at = run(lambda at: at.session_state.__setitem__("scope", "QZSS"))

    assert len(tiles(at)) == 5
    assert any(f"{healthy_in_slot('QZSS')} of 5</span>" in body for body in htmls(at))


def test_compare_starts_empty_with_one_prompt():
    at = run(lambda at: at.session_state.__setitem__("scope", "Compare"))

    assert tiles(at) == []
    assert any("Pick satellites to compare" in body for body in htmls(at))


def test_compare_two_satellites_from_different_constellations():
    def pick(at):
        at.session_state["scope"] = "Compare"
        at.run()   # the pickers exist only once the scope is Compare
        at.multiselect(key="pick_NavIC").set_value(["IRNSS-1B"])
        at.multiselect(key="pick_QZSS").set_value(["QZS-3 (Michibiki-3)"])

    at = run(pick)

    assert len(tiles(at)) == 2
    matrix = next(body for body in htmls(at) if 'class="matrix"' in body)
    assert matrix.count('class="mrow"') == 5            # the five score parts
    assert matrix.count('class="mc ') == 10             # each for the two satellites


def test_a_satellite_set_aside_has_no_scores_in_the_comparison():
    def pick(at):
        at.session_state["scope"] = "Compare"
        at.run()
        at.multiselect(key="pick_NavIC").set_value(["IRNSS-1B", "IRNSS-1D"])

    matrix = next(body for body in htmls(run(pick)) if 'class="matrix"' in body)

    assert matrix.count('class="mc idle"') == 5


def test_the_gear_thresholds_reach_params():
    assert run().session_state["params"] == {}

    at = run(lambda at: at.number_input(key="th_z_threshold_NavIC").set_value(5.0))

    assert at.session_state["params"] == {"z_threshold": 5.0}


def test_the_window_is_kept_for_pages_to_read():
    at = run(lambda at: at.session_state.__setitem__("window_days", 365))

    assert at.session_state["window_days"] == 365
    assert len(tiles(at)) == 8


def test_the_data_chip_is_amber_after_a_week():
    fresh = " ".join(htmls(run()))
    stale = " ".join(htmls(run(now=FROZEN + timedelta(days=8))))

    assert 'class="chip ok">Orbit data 4 Oct, 2 days old' in fresh
    assert 'class="chip warn">Orbit data 4 Oct, 10 days old' in stale


def test_age_words():
    taken = "2026-10-04T04:19:57.724789+00:00"
    now = datetime.fromisoformat("2026-10-14T10:00:00+00:00")

    assert age_words(taken, now) == ("Orbit data 4 Oct, 10 days old", "warn")
    assert age_words(taken, now.replace(day=11)) == ("Orbit data 4 Oct, 7 days old", "ok")
    assert age_words(taken, now.replace(day=5)) == ("Orbit data 4 Oct, 1 day old", "ok")
    assert age_words(taken, now.replace(day=4)) == ("Orbit data 4 Oct, today", "ok")
    assert age_words("Unknown", now)[1] == "idle"


def _on(page):
    return lambda at: at.session_state.__setitem__("page", page)


def test_station_keeping_shows_a_rhythm_card_per_satellite_and_two_charts():
    at = run(_on("Station-keeping"))
    cards = [b for body in htmls(at) for b in body.split('class="raised"')[1:]]

    assert len(cards) == 8
    assert len(at.get("plotly_chart")) == 2


def test_the_master_map_draws_its_canvas_and_hides_the_constellation_controls():
    with time_machine.travel(FROZEN, tick=False):
        at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=600).run()
        at.switch_page("views/master_map.py").run()
    assert not at.exception, [e.value for e in at.exception]

    labels = [getattr(w, "label", None) for w in at.get("button_group")]
    assert "Constellation" not in labels and "Page" in labels
