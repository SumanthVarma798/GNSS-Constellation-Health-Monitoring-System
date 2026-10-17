"""The new dashboard (dashboard.py): a top bar and the Overview page, with no side panel.

These drive the real script without a browser, with the clock frozen as tests/test_dashboard_notices.py does.
"""
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import requests
import time_machine
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import ButtonGroup

from data import celestrak
from test_celestrak import IRNSS_1B
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


@pytest.fixture(autouse=True)
def celestrak_answers_with_nothing_new(monkeypatch):
    """No network in tests: CelesTrak 'answers' with no rows unless a test says otherwise."""
    monkeypatch.setattr(celestrak, "state", {"rows": {}, "listed": None, "tried": None, "fetched": None, "ok": True})
    monkeypatch.setattr(celestrak, "fetch", lambda norads: ({}, set()))


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


def groups(at):
    return [body.split('class="gt">')[1].split("<")[0] for body in htmls(at) if 'class="gt">' in body]


def table_rows(at):
    """The row names of each table on the page, in order."""
    return [[r.split("</th>")[0] for r in body.split('<th scope="row">')[1:]]
            for body in htmls(at) if '<table class="grid">' in body]


def test_the_overview_groups_satellites_by_orbit_type_each_with_its_table():
    at = run()

    assert groups(at) == ["GEO", "IGSO"]
    tables = table_rows(at)
    assert tables[:2] == [["IRNSS-1C", "IRNSS-1F", "IRNSS-1G", "NVS-01"],
                                                  ["IRNSS-1B", "IRNSS-1E", "IRNSS-1I"]]   # IRNSS-1D is set aside
    assert len(tables[2]) == 8   # how each was classed from the window, the set-aside one too
    assert len(tiles(at)) == 8


def test_qzss_has_its_quasi_zenith_satellites_in_their_own_group():
    at = run(lambda at: at.session_state.__setitem__("scope", "QZSS"))

    assert groups(at) == ["GEO", "QZO"]


def test_the_overview_says_the_window_and_the_status_counts():
    body = next(b for b in htmls(run()) if 'class="facts"' in b)

    assert "90 days: " in body and "orbit records" in body and "scores read" in body
    assert all(word in body for word in ("healthy", "fair", "degraded", "critical"))


def _compare(picks=None, constellations=None):
    """Turn Compare on with its button, then set the picks and constellation chips (AppTest cannot click pills)."""
    def setup(at):
        at.button(key="compare_toggle").click().run()
        if picks is not None:
            at.session_state["compare_picks"] = picks
        if constellations is not None:
            at.session_state["compare_constellations"] = constellations
        at.session_state["picker_open"] = True
    return setup


def _offered(at):
    return [w.label for w in at.get("button_group") if w.label in ("NavIC", "QZSS", "BeiDou-3")]


def test_compare_is_its_own_button_and_starts_empty_with_one_prompt():
    at = run(_compare())

    assert at.session_state["compare"] is True
    labels = [getattr(w, "label", None) for w in at.get("button_group")]
    assert "Constellations" in labels and "Constellation" not in labels   # the chips now take several
    assert tiles(at) == []
    assert any("Add satellites to compare" in body for body in htmls(at))
    assert _offered(at) == ["NavIC", "QZSS", "BeiDou-3"]                 # none chosen: all offered


def test_the_list_opens_with_add_and_stays_open_while_picking():
    at = run(lambda at: at.button(key="compare_toggle").click())
    assert _offered(at) == []

    at = run(lambda at: (at.button(key="compare_toggle").click().run(), at.button(key="picker_toggle").click()))
    assert _offered(at) == ["NavIC", "QZSS", "BeiDou-3"]


def test_the_picker_offers_only_the_constellations_chosen_and_drops_picks_from_the_others():
    at = run(_compare(picks={"NavIC": ["IRNSS-1B"], "QZSS": ["QZS-3 (Michibiki-3)"]}, constellations=["QZSS"]))

    assert _offered(at) == ["QZSS"]
    assert at.session_state["compare_picks"] == {"QZSS": ["QZS-3 (Michibiki-3)"]}
    assert len(tiles(at)) == 1


def test_compare_two_satellites_from_different_constellations():
    at = run(_compare(picks={"NavIC": ["IRNSS-1B"], "QZSS": ["QZS-3 (Michibiki-3)"]}))

    assert len(tiles(at)) == 2
    matrix = next(body for body in htmls(at) if 'class="matrix"' in body)
    assert matrix.count('class="mrow"') == 5            # the five score parts
    assert matrix.count('class="mc ') == 10             # each for the two satellites


def test_clicking_a_picked_chip_removes_it():
    def setup(at):
        _compare(picks={"NavIC": ["IRNSS-1B", "IRNSS-1C"]})(at)
        at.run()
        at.button(key="drop_IRNSS-1B").click()

    at = run(setup)

    assert at.session_state["compare_picks"] == {"NavIC": ["IRNSS-1C"]}
    assert len(tiles(at)) == 1


def test_a_satellite_set_aside_has_no_scores_in_the_comparison():
    matrix = next(body for body in htmls(run(_compare(picks={"NavIC": ["IRNSS-1B", "IRNSS-1D"]})))
                  if 'class="matrix"' in body)

    assert matrix.count('class="mc idle"') == 5


def test_station_keeping_under_compare_reads_the_same_picks():
    def setup(at):
        _compare(picks={"NavIC": ["IRNSS-1B"], "QZSS": ["QZS-3 (Michibiki-3)"]})(at)
        at.session_state["page"] = "Station-keeping"

    at = run(setup)
    lines = [b for body in htmls(at) for b in body.split('<div class="rh">')[1:]]

    assert len(lines) == 2


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
    assert "Refresh failed" not in fresh


def test_rows_from_celestrak_make_the_chip_say_today_and_its_time(monkeypatch):
    monkeypatch.setattr(celestrak, "fetch", lambda norads: ({39635: celestrak.as_history_row(IRNSS_1B)}, {39635}))
    at = run()
    chips = " ".join(htmls(at))

    assert 'class="chip ok">Orbit data 6 Oct 12:00' in chips   # the frozen clock's time, in UTC without a browser
    assert len(tiles(at)) == 8


def test_the_bar_says_when_the_next_automatic_refresh_is():
    chips = " ".join(htmls(run()))

    assert '<span class="next">next update 14:00</span>' in chips   # tried at the frozen 12:00 UTC, every two hours


def test_a_failed_refresh_keeps_the_archive_and_says_so(monkeypatch):
    def down(norads):
        raise requests.ConnectionError("no route")
    monkeypatch.setattr(celestrak, "fetch", down)
    at = run(lambda at: at.button(key="refresh_button").click())
    chips = " ".join(htmls(at))

    assert 'class="chip ok">Orbit data 4 Oct, 2 days old' in chips
    assert 'class="chip warn">Refresh failed' in chips
    assert len(tiles(at)) == 8


def test_age_words():
    taken = "2026-10-04T04:19:57.724789+00:00"
    now = datetime.fromisoformat("2026-10-14T10:00:00+00:00")

    assert age_words(taken, now) == ("Orbit data 4 Oct, 10 days old", "warn")
    assert age_words(taken, now.replace(day=11)) == ("Orbit data 4 Oct, 7 days old", "ok")
    assert age_words(taken, now.replace(day=5)) == ("Orbit data 4 Oct, 1 day old", "ok")
    assert age_words(taken, now.replace(day=4)) == ("Orbit data 4 Oct 04:19", "ok")
    assert age_words("Unknown", now)[1] == "idle"


def _on(page):
    return lambda at: at.session_state.__setitem__("page", page)


def test_station_keeping_shows_a_rhythm_line_per_satellite_and_two_charts():
    at = run(_on("Station-keeping"))
    lines = [b for body in htmls(at) for b in body.split('<div class="rh">')[1:]]

    assert len(lines) == 8
    assert len(at.get("plotly_chart")) == 2
    counts = table_rows(at)[0]
    assert len(counts) == 8 and "IRNSS-1D" in counts   # burns in the window, the set-aside one included


def test_the_master_map_draws_its_canvas_and_hides_the_constellation_controls():
    with time_machine.travel(FROZEN, tick=False):
        at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=600).run()
        at.switch_page("views/master_map.py").run()
    assert not at.exception, [e.value for e in at.exception]

    labels = [getattr(w, "label", None) for w in at.get("button_group")]
    assert "Constellation" not in labels and "Page" in labels
