"""The new dashboard (dashboard.py): a top bar and the Overview page, with no side panel.

These drive the real script without a browser, with the clock frozen as tests/test_dashboard_notices.py does.
"""
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import requests
import time_machine
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import ButtonGroup

from data import celestrak, spacetrack
from test_celestrak import IRNSS_1B
from test_golden_scores import GOLDEN
from ui import time_range
from ui.shell import age_words, clock_words, failing_words, next_words

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
    monkeypatch.setattr(celestrak, "state", {"rows": {}, "listed": None, "tried": None, "fetched": None, "ok": True,
                                             "failing_since": None, "copy_at": None})
    monkeypatch.setattr(celestrak, "fetch", lambda norads: ({}, set()))
    monkeypatch.setattr(spacetrack, "state", {"rows": {}, "tried": None, "fetched": None,
                                              "refused_until": None, "note": "ok"})
    monkeypatch.setattr(spacetrack, "refresh",
                        lambda norads, now, login: {"rows": {}, "tried": now if login else None, "fetched": None,
                                                    "refused_until": None, "note": "ok" if login else "no login"})


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


def test_every_navic_tile_carries_an_orbit_record_age_tag():
    at = run()

    assert len(tiles(at)) == 8
    for tile in tiles(at):
        assert ("orbit " in tile and "days old" in tile) or "no orbit record" in tile


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
    assert len(tables[0]) == 8 and "IRNSS-1D" in tables[0]   # orbit record age: every satellite, set-aside too
    assert tables[1:3] == [["IRNSS-1C", "IRNSS-1F", "IRNSS-1G", "NVS-01"],
                           ["IRNSS-1B", "IRNSS-1E", "IRNSS-1I"]]   # IRNSS-1D is set aside
    assert len(tables[3]) == 8   # how each was classed from the window, the set-aside one too
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


def test_the_data_chip_turns_warn_then_bad_at_the_orbit_age_limits():
    fresh = " ".join(htmls(run()))
    stale = " ".join(htmls(run(now=FROZEN + timedelta(days=8))))

    assert 'class="chip warn">Orbit data 4 Oct, 2 days old' in fresh
    assert 'class="chip bad">Orbit data 4 Oct, 10 days old' in stale
    assert "failing" not in fresh


def test_rows_from_celestrak_make_the_chip_say_today_and_its_time(monkeypatch):
    monkeypatch.setattr(celestrak, "fetch", lambda norads: ({39635: celestrak.as_history_row(IRNSS_1B)}, {39635}))
    at = run()
    chips = " ".join(htmls(at))

    assert 'class="chip ok">Orbit data 6 Oct 12:00' in chips   # the frozen clock's time, in UTC without a browser
    assert len(tiles(at)) == 8


def test_the_bar_says_how_long_to_the_next_automatic_refresh_and_the_time_in_utc():
    chips = " ".join(htmls(run()))

    assert '<span class="next">Next update in 2 h</span>' in chips   # tried at the frozen 12:00 UTC, every two hours
    assert '<span class="clock num">12:00 UTC</span>' in chips


def test_next_words_say_hours_and_minutes_rounded_up():
    assert next_words(1 * 3600 + 41 * 60 + 5) == "Next update in 1 h 42 m"
    assert next_words(7200) == "Next update in 2 h"
    assert next_words(42 * 60) == "Next update in 42 m"
    assert next_words(20) == "Next update in 1 m"
    assert next_words(0) == "Next update due now"


def test_clock_words_are_utc():
    assert clock_words(datetime.fromisoformat("2026-10-20T19:35:59+05:30")) == "14:05 UTC"


def test_the_range_presets_and_custom_dates_are_bounded_by_the_records_held():
    today = date(2026, 10, 20)

    assert time_range.held_days(date(2025, 10, 4), today) == 381 and time_range.held_days(None, today) == 0
    assert all(time_range.too_long(days, 381, ["NavIC"]) is None for days in time_range.PRESETS)
    assert time_range.too_long(90, 28, ["GPS"]) == "Only 28 days of orbit records are held for GPS."
    assert time_range.too_long(30, 0, ["GPS", "Galileo"]) == "No orbit records are yet held for GPS, Galileo."
    assert time_range.from_bounds(date(2025, 10, 4), today) == (date(2025, 10, 4), date(2026, 10, 6))   # 14 days at least
    assert time_range.from_bounds(date(2026, 10, 10), today) is None    # under 14 days held: no custom range
    assert time_range.from_bounds(None, today) is None
    assert time_range.words(182) == "6 months" and time_range.words(47) == "47 days"


def test_the_range_offers_every_preset_for_navics_year_and_a_custom_start_inside_it():
    at = run()

    assert not any(at.button(key=f"window_{days}").disabled for days in time_range.PRESETS)
    start = at.date_input(key="_window_from")
    assert (start.min, start.max) == (date(2025, 10, 4), date(2026, 9, 22))   # oldest record held; 14 days before today
    assert start.value == date(2026, 7, 8)                                     # the 90 days chosen


def test_a_constellation_with_no_records_held_greys_every_preset_and_says_why():
    at = run(lambda at: at.session_state.__setitem__("scope", "GPS"))

    assert all(at.button(key=f"window_{days}").disabled for days in time_range.PRESETS)
    assert at.button(key="window_30").help == "No orbit records are yet held for GPS."
    assert not at.get("date_input")
    assert any("No orbit records are held yet." in body for body in htmls(at))


def test_a_custom_start_sets_the_range_to_now_on_every_page():
    at = run(lambda at: at.date_input(key="_window_from").set_value(date(2026, 8, 20)))

    assert at.session_state["window_days"] == 47
    assert any("47 days: 20 Aug 2026 to 6 Oct 2026" in body for body in htmls(at))
    at.session_state["page"] = "Station-keeping"
    at.run()
    assert not at.exception and any("47 days" in body for body in htmls(at))


def test_a_preset_button_sets_the_range():
    at = run(lambda at: at.button(key="window_182").click())

    assert at.session_state["window_days"] == 182
    assert any("6 months: " in body for body in htmls(at))


def test_the_pages_across_all_systems_are_set_apart_without_words():
    assert not any("Across all systems" in body for body in htmls(run()))


def test_a_failed_refresh_keeps_the_archive_and_says_so(monkeypatch):
    def down(norads):
        raise requests.ConnectionError("no route")
    monkeypatch.setattr(celestrak, "fetch", down)
    at = run(lambda at: at.button(key="refresh_button").click())
    chips = " ".join(htmls(at))

    assert 'class="chip warn">Orbit data 4 Oct, 2 days old' in chips
    assert 'class="chip warn">CelesTrak failing since 12:00' in chips   # the frozen clock's time, in UTC
    assert len(tiles(at)) == 8


def test_while_the_archive_jobs_copy_stands_in_the_chip_says_so_not_failing(monkeypatch):
    def down(norads):
        raise requests.HTTPError(403)
    monkeypatch.setattr(celestrak, "fetch", down)
    monkeypatch.setattr(celestrak, "fetch_copy", lambda norads: ({}, set(), FROZEN - timedelta(hours=1)))
    chips = " ".join(htmls(run(lambda at: at.button(key="refresh_button").click())))

    assert 'class="chip idle">CelesTrak via the archive job' in chips
    assert "CelesTrak failing" not in chips
    assert 'class="chip warn">Orbit data 4 Oct, 2 days old' in chips   # the age chip keeps its colour


def test_a_source_failing_since_yesterday_says_since_when(monkeypatch):
    def down(norads):
        raise requests.HTTPError(403)
    monkeypatch.setattr(celestrak, "fetch", down)
    celestrak.state.update(tried=FROZEN, ok=False, failing_since=FROZEN)
    chips = " ".join(htmls(run(now=FROZEN + timedelta(days=1))))   # due again: tried, and refused again

    assert 'class="chip warn">CelesTrak failing since 6 Oct 12:00' in chips
    assert 'class="chip bad">Orbit data 4 Oct, 3 days old' in chips   # the saved copies stay in use


def test_age_words():
    taken = "2026-10-04T04:19:57.724789+00:00"
    now = datetime.fromisoformat("2026-10-14T10:00:00+00:00")

    assert age_words(taken, now) == ("Orbit data 4 Oct, 10 days old", "bad")
    assert age_words(taken, now.replace(day=11)) == ("Orbit data 4 Oct, 7 days old", "bad")
    assert age_words(taken, now.replace(day=5)) == ("Orbit data 4 Oct, 1 day old", "ok")
    assert age_words(taken, now.replace(day=4)) == ("Orbit data 4 Oct 04:19", "ok")
    assert age_words("Unknown", now)[1] == "idle"


def test_failing_words():
    now = datetime.fromisoformat("2026-10-19T10:00:00+00:00")

    assert failing_words(now.replace(hour=8, minute=2), now) == "CelesTrak failing since 08:02"
    assert failing_words(now.replace(day=18, hour=23), now) == "CelesTrak failing since 18 Oct 23:00"


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


def test_under_compare_the_range_fits_the_constellation_with_least_history(monkeypatch):
    from datetime import date
    from ui import time_range
    monkeypatch.setattr(time_range, "firsts", lambda names, w, p: {"NavIC": date(2025, 10, 4), "GPS": date(2026, 9, 22)})
    assert time_range.oldest(["NavIC", "GPS"], 90, {}) == date(2026, 9, 22)
