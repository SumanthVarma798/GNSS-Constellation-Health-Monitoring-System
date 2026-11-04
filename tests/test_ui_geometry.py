"""The Geometry page: its numbers (ui/geometry_data.py), its pictures and grids (ui/figures/geometry.py), and the page."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from analysis.dop_calculations import parse_tle_data
from analysis.raan_analysis import analyze_raan_spacing
from config.config import BEIDOU3_SATS, CHINA_KEY_POINTS, R_EARTH
from data.tle_cache import load_bundled_tles
from test_dashboard_shell import (_compare, _on, celestrak_answers_with_nothing_new, htmls,  # noqa: F401 (fixtures)
                                  run, segmented_controls_rerun)
from ui import geometry_data as gd
from ui import geometry_settings as gs
from ui import shell
from ui.figures import geometry as gf

WHEN = datetime(2026, 10, 4, 6, 0, tzinfo=timezone.utc)   # just after the bundled element sets
MASK = 5
INDIA = ZoneInfo("Asia/Kolkata")


@pytest.fixture(scope="module")
def beidou():
    return parse_tle_data(load_bundled_tles("beidou3")["tle_data"], BEIDOU3_SATS)


TYPES = {"BeiDou-3 G1": "GEO", "BeiDou-3 G2": "GEO", "BeiDou-3 G3": "GEO", "BeiDou-3 G4": "GEO",
         "BeiDou-3 I1": "IGSO", "BeiDou-3 I2": "IGSO", "BeiDou-3 I3": "IGSO"}


# ---- numbers ----

def test_a_dop_row_per_place_with_the_values_in_order(beidou):
    rows = gd.dop_rows(beidou, CHINA_KEY_POINTS, WHEN, MASK)

    assert [r["place"] for r in rows] == list(CHINA_KEY_POINTS)
    for r in rows:
        assert 4 <= r["seen"] <= len(beidou)
        assert r["GDOP"] >= r["PDOP"] >= max(r["HDOP"], r["VDOP"])


def test_too_few_satellites_give_no_values(beidou):
    three = dict(list(beidou.items())[:3])

    row = gd.dop_rows(three, {"Beijing": CHINA_KEY_POINTS["Capital (Beijing)"]}, WHEN, MASK)[0]

    assert row["seen"] <= 3 and all(row[k] is None for k in gd.DOP_KEYS)


def test_the_series_steps_through_the_last_day(beidou):
    series = gd.dop_series(beidou, 39.9, 116.4, WHEN, MASK)

    assert len(series) == gs.TREND_HOURS * 60 // gs.TREND_STEP_MINUTES + 1
    assert series["time"].iloc[-1] == WHEN and series["GDOP"].notna().all()


def test_sky_frames_hold_only_satellites_above_the_mask(beidou):
    frames = gd.sky_frames(beidou, 39.9, 116.4, WHEN, MASK)

    assert len(frames) == gs.SKY_HOURS * 60 // gs.SKY_STEP_MINUTES + 1
    assert all(el > MASK for f in frames for _, _, el in f["satellites"])
    assert {n for n, _, _ in frames[0]["satellites"]} <= set(beidou)


class _Unplaceable:
    """A satellite whose position cannot be worked out: calculate_satellite_position skips it."""
    def __sub__(self, other):
        raise ValueError("no position")


def test_a_satellite_without_a_position_does_not_shift_the_others(beidou):
    alone = gd.sky_frames(beidou, 39.9, 116.4, WHEN, MASK, hours=0)[0]["satellites"]

    with_broken = gd.sky_frames({"Broken": _Unplaceable(), **beidou}, 39.9, 116.4, WHEN, MASK, hours=0)[0]["satellites"]

    assert with_broken == alone


def test_a_geostationary_track_stays_near_its_slot(beidou):
    tracks, here = gd.ground_tracks(beidou, WHEN, gs.TRACK_WINDOWS[0])

    track = tracks["BeiDou-3 G2"]
    assert max(abs(x) for x in track["lat"]) < 5 and max(track["lon"]) - min(track["lon"]) < 5
    assert all(35_000 < h < 36_500 for h in track["height"]) and track["time"][0] == WHEN
    assert set(here) == set(beidou)


class _Made:
    """A made-up satellite whose elevation at one place is set by hand: elevation(minutes after WHEN) in degrees."""
    def __init__(self, elevation):
        self.elevation = elevation

    def __sub__(self, observer):
        return self

    def at(self, t):
        self.minutes = [(d - WHEN).total_seconds() / 60 for d in t.utc_datetime()]
        return self

    def altaz(self):
        return (SimpleNamespace(degrees=np.array([self.elevation(m) for m in self.minutes])),)


def test_next_visible_finds_when_each_satellite_comes_into_view_or_leaves_it():
    made = {"rises": _Made(lambda m: 10 if m >= 150 else 0), "sets": _Made(lambda m: 20 if m < 61 else 0),
            "always": _Made(lambda m: 40), "never": _Made(lambda m: -5), "at the mask": _Made(lambda m: MASK)}

    rows = {r["satellite"]: r for r in gd.next_visible(made, 0, 0, WHEN, MASK)}

    assert rows["rises"] == {"satellite": "rises", "in_view": False, "change": WHEN + timedelta(minutes=150)}
    assert rows["sets"] == {"satellite": "sets", "in_view": True, "change": WHEN + timedelta(minutes=61)}
    assert rows["always"]["in_view"] and rows["always"]["change"] is None
    assert not rows["never"]["in_view"] and rows["never"]["change"] is None
    assert not rows["at the mask"]["in_view"]   # exactly on the mask is not above it


def test_next_visible_for_real_satellites_stays_inside_the_day(beidou):
    rows = gd.next_visible(beidou, 39.9, 116.4, WHEN, MASK)

    assert {r["satellite"] for r in rows} == set(beidou)
    assert all(WHEN < r["change"] <= WHEN + timedelta(hours=gs.NEXT_HOURS) for r in rows if r["change"])
    assert rows == [r for r in rows if not (r["satellite"].startswith("BeiDou-3 G") and r["change"])]   # GEO stay put


@pytest.mark.parametrize("text, place", [("28.61, 77.21", (28.61, 77.21)), ("28.61 77.21", (28.61, 77.21)),
                                         ("33.9 S, 151.2 E", (-33.9, 151.2)), ("-33.9;-70.6", (-33.9, -70.6)),
                                         (" 0,0 ", (0.0, 0.0)), ("90 N, 180 W", (90.0, -180.0)), ("12.5°N 80°E", (12.5, 80.0))])
def test_a_typed_place_is_read_in_degrees(text, place):
    assert gd.parse_place(text) == place


@pytest.mark.parametrize("text, words", [("", "Enter a latitude and a longitude"), ("28.61", "Enter two numbers"),
                                         ("1, 2, 3", "Enter two numbers"), ("abc, 77", "“abc” is not a number"),
                                         ("95, 77", "Latitude must be between -90 and 90"),
                                         ("28, 181", "Longitude must be between -180 and 180"),
                                         ("77 E, 28 N", "Latitude is N or S, not E"), ("-28 S, 77", "not both")])
def test_a_typed_place_that_cannot_be_read_says_why(text, words):
    with pytest.raises(ValueError, match=words):
        gd.parse_place(text)


def test_in_service_leaves_out_satellites_set_aside_or_marked_not_in_service():
    names = ["IRNSS-1B", "IRNSS-1C", "IRNSS-1D", "NVS-01"]

    assert gd.chosen_satellites(names, ["IRNSS-1D"], "In service") == ["IRNSS-1B", "NVS-01"]
    assert gd.chosen_satellites(names, ["IRNSS-1D"], "All") == names


def _history(rows):
    return pd.DataFrame(rows, columns=["satellite", "EPOCH", "TLE_LINE1", "TLE_LINE2", "type"])


def test_satellites_are_placed_from_their_newest_element_set():
    tle = load_bundled_tles("beidou3")["tle_data"].strip().split("\n")
    first = next(i for i in range(0, len(tle), 3) if int(tle[i + 1][2:7]) == BEIDOU3_SATS["BeiDou-3 G2"])
    line1, line2 = tle[first + 1].strip(), tle[first + 2].strip()
    history = _history([("BeiDou-3 G2", pd.Timestamp("2026-01-01"), None, None, "GEO"),
                        ("BeiDou-3 G2", pd.Timestamp("2026-10-01"), line1, line2, "GEO"),
                        ("Other", pd.Timestamp("2026-10-01"), line1, line2, "GEO")])

    placed = gd.satellites_from_history(history, ["BeiDou-3 G2"])

    assert list(placed) == ["BeiDou-3 G2"] and placed["BeiDou-3 G2"].model.satnum == BEIDOU3_SATS["BeiDou-3 G2"]


def test_central_longitude_is_weekly_and_sits_at_the_slot_for_a_geostationary_satellite():
    from analysis.bundled_run import load_bundled_gp_as_dataframes
    history = pd.concat(load_bundled_gp_as_dataframes("beidou3", BEIDOU3_SATS), ignore_index=True)
    since = history["EPOCH"].max() - pd.Timedelta(days=28)

    table = gd.central_longitudes(history, ["BeiDou-3 G2"], since)

    assert 4 <= len(table) <= 5
    slot = gd.targets("BeiDou-3", "BeiDou-3 G2", "GEO", {})["central_lon"]
    assert all(slot[0] - 2 <= lon <= slot[1] + 2 for lon in table["central_lon"])


def test_targets_come_from_config_and_the_thresholds():
    qzss = gd.targets("QZSS", "QZS-2 (Michibiki-2)", "QZO", {})
    navic = gd.targets("NavIC", "IRNSS-1B", "IGSO", {"inclination_tolerance": 2.0, "drift_tolerance_gso": 0.1})
    geo = gd.targets("NavIC", "NVS-01", "GEO", {"drift_tolerance_gso": 0.1})

    assert qzss["INCLINATION"] == (39.0, 47.0)
    assert qzss["altitude_km"] == (42164.0 - R_EARTH - 10, 42164.0 - R_EARTH + 10)
    assert qzss["central_lon"] == (134.0, 144.0)
    assert navic["INCLINATION"] == (27.0, 31.0) and "altitude_km" not in navic
    assert navic["central_lon"] == (55.0, 55.0)
    assert navic["LonDrift_deg_per_day"] == (-gs.DRIFT_TOLERANCE_IGSO, gs.DRIFT_TOLERANCE_IGSO)
    assert geo["LonDrift_deg_per_day"] == (-0.1, 0.1)


def test_a_satellites_own_inclination_tolerance_comes_before_the_constellation_one():
    qzs3 = gd.targets("QZSS", "QZS-3 (Michibiki-3)", "GEO", {"inclination_tolerance": 4.0})

    assert qzs3["INCLINATION"] == (-0.5, 0.5)


def test_orbit_types_fall_back_to_the_history_for_satellites_set_aside():
    health = pd.DataFrame({"Satellite": ["A"], "Type": ["QZO"]})
    history = _history([("A", pd.Timestamp("2026-01-01"), "", "", "IGSO"), ("B", pd.Timestamp("2026-01-01"), "", "", "GEO")])

    assert gd.orbit_types(health, history) == {"A": "QZO", "B": "GEO"}


# ---- grids ----

def test_quality_words_and_status():
    assert gf.quality("GDOP", 1.5) == ("excellent", "ok")
    assert gf.quality("GDOP", 7.0) == ("moderate", "warn")
    assert gf.quality("VDOP", 16.0) == ("poor", "bad")
    assert gf.quality("PDOP", None, seen=3) == ("no fix", "bad")
    assert gf.quality("PDOP", None, seen=4) == ("unusable", "bad")
    assert gf.quality("TDOP", 1.2) == ("", "idle")


def test_should_be_comes_from_the_bands_and_tdop_has_none():
    assert gf.should_be("GDOP") == "below 5, 2 excellent"
    assert gf.should_be("VDOP") == "below 5, 3 excellent"
    assert gf.should_be("TDOP") == ""


def test_the_key_names_every_measure_with_its_meaning():
    key = gf.dop_key()

    assert all(f"<b>{k}</b>" in key for k, _, _ in gs.DOP_MEASURES)
    assert key.count("Should be") == 4 and "No set target." in key


def test_the_grid_has_a_line_per_place_escapes_names_and_marks_too_few():
    rows = [{"place": "<b>X</b>", "seen": 3, **{k: None for k in gd.DOP_KEYS}},
            {"place": "Y", "seen": 7, "GDOP": 3.1, "PDOP": 2.8, "HDOP": 1.5, "VDOP": 2.3, "TDOP": 1.4}]

    grid = gf.dop_grid(rows)

    assert grid.count('<div class="gr">') == 2
    assert "&lt;b&gt;X&lt;/b&gt;" in grid and "<b>X</b>" not in grid
    assert '<span class="gc bad"><b class="num">3</b>' in grid and "no fix" in grid
    assert "3.10" in grid and "good" in grid


def test_the_summary_says_best_worst_and_average_or_nothing():
    series = pd.DataFrame({"GDOP": [2.0, 4.0, None]})

    summary = gf.gdop_summary(series)

    assert "2.00" in summary and "4.00" in summary and "3.00" in summary
    assert gf.gdop_summary(pd.DataFrame({"GDOP": [None]})) == ""


def test_short_names_drop_the_bracketed_part():
    assert gf.short("QZS-2 (Michibiki-2)") == "QZS-2" and gf.short("IRNSS-1B") == "IRNSS-1B"


def test_by_orbit_puts_geostationary_first():
    assert gf.by_orbit(["I1", "G1", "I2"], {"I1": "IGSO", "G1": "GEO", "I2": "IGSO"}) == [("GEO", ["G1"]), ("IGSO", ["I1", "I2"])]


# ---- pictures ----

def test_the_trend_draws_four_dop_lines_and_the_count(beidou):
    fig = gf.dop_trend(gd.dop_series(beidou, 39.9, 116.4, WHEN, MASK), "Beijing")

    assert [t.name for t in fig.data] == ["GDOP", "PDOP", "HDOP", "VDOP", "In view"]


def test_the_sky_page_gets_every_step_and_every_satellite_with_its_path(beidou):
    from ui.components.sky_view import sky_payload, sky_view_html

    frames = gd.sky_frames(beidou, 39.9, 116.4, WHEN, MASK)
    paths = gd.sky_paths(beidou, 39.9, 116.4, WHEN)

    payload = sky_payload(frames, paths, TYPES, MASK, INDIA)

    assert len(payload["steps"]) == len(frames) == gs.SKY_HOURS * 60 // gs.SKY_STEP_MINUTES + 1
    assert payload["steps"][0]["when"].startswith("4 Oct 11:30 IST") and payload["steps"][0]["tick"] == "11:30"
    assert {s["name"] for s in payload["satellites"]} == set(beidou)
    assert all(len(s["az"]) == len(s["el"]) == len(frames) for s in payload["satellites"])
    first = {s["name"]: s["el"][0] for s in payload["satellites"]}
    assert {n for n, _, _ in frames[0]["satellites"]} == {n for n, e in first.items() if e > MASK}   # the same sky
    assert [k["words"] for k in payload["key"]] == ["geostationary", "inclined geosynchronous"]
    page = sky_view_html(frames, paths, {**TYPES, "BeiDou-3 G1": "<GEO>"}, MASK, INDIA)
    assert "__" not in page.split("const DATA")[0] and "<GEO>" not in page


def test_a_track_across_the_date_line_is_broken():
    lats, lons, words = gf._unwrapped([0, 1, 2], [179.0, -179.0, -178.0], ["a", "b", "c"])

    assert lons == [179.0, None, -179.0, -178.0] and lats == [0, None, 1, 2] and words == ["a", None, "b", "c"]


def test_the_map_holds_land_tracks_now_places_a_click_grid_and_the_chosen_place(beidou):
    tracks, here = gd.ground_tracks(beidou, WHEN, gs.TRACK_WINDOWS[1])

    fig = gf.ground_map(tracks, here, TYPES, CHINA_KEY_POINTS, ("Lhasa", 29.7, 91.1))

    assert [t.name for t in fig.data[-3:]] == ["key places", "click", "chosen place"]
    assert len(fig.data) == 1 + len(tracks) + 4 and len(fig.data[-3].x) == len(CHINA_KEY_POINTS)
    track = fig.data[1]
    assert "height %{customdata[2]:,.0f} km" in track.hovertemplate and track.customdata[0][0].endswith("UTC")
    cells, step = fig.data[-2], gs.CLICK_GRID_DEG
    x_range, y_range = fig.layout.xaxis.range, fig.layout.yaxis.range
    assert min(cells.x) - step / 2 <= x_range[0] and max(cells.x) + step / 2 >= x_range[1]
    assert min(cells.base) <= y_range[0] and max(cells.base) + step >= y_range[1]
    assert all(lat == base + step / 2 and lon == x for (lat, lon), base, x in zip(cells.customdata, cells.base, cells.x))


def test_a_chosen_place_far_away_widens_the_map(beidou):
    tracks, here = gd.ground_tracks(beidou, WHEN, gs.TRACK_WINDOWS[0])

    fig = gf.ground_map(tracks, here, TYPES, CHINA_KEY_POINTS, ("Sydney", -33.9, 151.2))

    assert fig.layout.yaxis.range[0] < -33.9 and fig.layout.xaxis.range[1] > 151.2


def test_one_satellites_trends_share_one_time_axis_so_a_hover_reads_them_all():
    epochs = pd.to_datetime(["2026-09-01", "2026-09-15"])
    series = {"INCLINATION": pd.DataFrame({"satellite": ["A", "A"], "EPOCH": epochs, "INCLINATION": [29.0, 29.1]}),
              "altitude_km": pd.DataFrame({"satellite": ["A", "B"], "EPOCH": epochs, "altitude_km": [35786.0, 1.0]})}
    bands = {"INCLINATION": (28.0, 30.0), "central_lon": (55.0, 55.0)}

    fig = gf.satellite_trends(series, "A", "GEO", bands, epochs[0], epochs[1])

    assert fig.layout.hovermode == "x unified" and fig.layout.hoversubplots == "axis"
    assert {t.xaxis or "x" for t in fig.data} == {"x"} and fig.layout.xaxis.showspikes
    lines = [t for t in fig.data if t.hoverinfo != "skip"]
    assert [t.name for t in lines] == ["Tilt", "Height"] and list(lines[1].y) == [35786.0]
    assert "(should be 28 to 30)" in lines[0].hovertemplate and "km" in lines[1].hovertemplate
    assert sum(t.fill == "toself" for t in fig.data) == 1 and sum(1 for t in fig.data if t.line.dash == "dash") == 1
    titles = [fig.layout[f"yaxis{'' if i == 0 else i + 1}"].title.text for i in range(len(gs.TRENDS))]
    assert titles == [f"{name}<br>{unit}" for _, name, unit, _ in gs.TRENDS]


# ---- when each satellite is in view, in words ----

def test_next_words_say_until_when_or_when_next_in_the_viewers_time_and_utc():
    later = WHEN + timedelta(minutes=150)

    assert gf.next_words({"in_view": False, "change": later}, "IGSO", WHEN, INDIA) == (
        "not in view", "idle", "next in view 4 Oct 14:00 IST · 08:30 UTC, in 2 h 30 min")
    assert gf.next_words({"in_view": True, "change": WHEN + timedelta(minutes=20)}, "IGSO", WHEN, timezone.utc) == (
        "in view", "ok", "until 4 Oct 06:20 UTC, in 20 min")


def test_next_words_say_plainly_that_a_geostationary_satellite_stays_put():
    assert gf.next_words({"in_view": True, "change": None}, "GEO", WHEN, INDIA)[2].startswith("always in view: geostationary")
    assert gf.next_words({"in_view": False, "change": None}, "GEO", WHEN, INDIA)[2].startswith("never in view from here")
    assert gf.next_words({"in_view": False, "change": None}, "IGSO", WHEN, INDIA)[2] == "not in the next 24 hours"
    assert gf.next_words({"in_view": True, "change": None}, "QZO", WHEN, INDIA)[2] == "in view for all of the next 24 hours"


def test_the_in_view_table_puts_those_in_view_first_then_the_soonest():
    rows = [{"satellite": "never", "in_view": False, "change": None},
            {"satellite": "<late>", "in_view": False, "change": WHEN + timedelta(hours=5)},
            {"satellite": "soon", "in_view": False, "change": WHEN + timedelta(hours=1)},
            {"satellite": "up", "in_view": True, "change": None}]

    table = gf.next_table(rows, {}, WHEN, timezone.utc)

    order = [line.split("<small>")[0] for line in table.split('<div class="nr"><b>')[1:]]
    assert order == ["up", "soon", "&lt;late&gt;", "never"]
    assert gf.next_summary(rows, WHEN, timezone.utc) == "1 of 4 in view now · next: soon 4 Oct 07:00 UTC"


def test_spacing_card_and_wheel(beidou):
    group = analyze_raan_spacing(beidou)[0]

    card, table = gf.spacing_card(group), gf.spacing_table(group)
    wheel = gf.spacing_wheel(group)

    assert f'{group["ideal_spacing_deg"]:g}° apart' in card and table.count('<div class="sr">') == group["satellite_count"]
    assert len(wheel.data[-2].theta) == group["satellite_count"]   # the even-spacing rings


# ---- the page ----

def test_the_page_sits_between_station_keeping_and_news():
    titles = [title for title, _ in shell.PAGES]

    assert titles.index("Geometry") == titles.index("Station-keeping") + 1 == titles.index("News") - 1


@pytest.mark.parametrize("section", gs.SECTIONS)
def test_every_section_runs_for_beidou(section):
    def setup(at):
        at.session_state["scope"] = "BeiDou-3"
        at.session_state["geo_section"] = section
        _on("Geometry")(at)

    at = run(setup)

    if section == "Position quality":
        lines = [b for body in htmls(at) for b in body.split('<div class="gr">')[1:]]
        assert len(lines) == len(CHINA_KEY_POINTS)


def test_navic_in_service_says_who_is_left_out():
    at = run(_on("Geometry"))

    assert any("Left out as not in service" in body for body in htmls(at))


def test_compare_draws_a_part_per_constellation_and_trends_only_for_the_picks():
    def setup(at):
        _compare(picks={"NavIC": ["IRNSS-1B"], "QZSS": ["QZS-3 (Michibiki-3)", "QZS-6 (Michibiki-6)"]})(at)
        at.session_state["geo_section"] = "Orbit trends"
        _on("Geometry")(at)

    at = run(setup)

    heads = [b for b in htmls(at) if b.startswith('<div class="geo-head">')]
    assert heads == ['<div class="geo-head">NavIC</div>', '<div class="geo-head">QZSS</div>']
    figures = [chart.proto.spec for chart in at.get("plotly_chart")]
    assert len(figures) == 3   # one per picked satellite
    assert "IRNSS-1B" in figures[0] and "IRNSS-1I" not in "".join(figures)
    assert "QZS-3" in figures[1] and "QZS-6" in figures[2] and "QZS-2" not in "".join(figures)


def _sky_and_ground(at):
    at.session_state["scope"] = "BeiDou-3"
    at.session_state["geo_section"] = "Sky and ground"
    _on("Geometry")(at)


def _heads(at):
    return [b for b in htmls(at) if b.startswith('<div class="geo-head">')]


def test_sky_and_ground_starts_at_the_capital_and_says_when_each_satellite_is_in_view():
    at = run(_sky_and_ground)

    assert _heads(at)[0] == '<div class="geo-head">The sky above Capital (Beijing)</div>'
    assert any(body.count('<div class="nr"><b>') == len(BEIDOU3_SATS) for body in htmls(at))
    assert any("always in view: geostationary" in body for body in htmls(at))


def test_a_typed_place_moves_the_sky_there_and_a_bad_one_says_why():
    def typed(text):
        def setup(at):
            at.session_state["geo_section"] = "Sky and ground"
            _on("Geometry")(at)
            at.run()
            at.switch_page("views/geometry.py")   # AppTest's next run starts from the dashboard's first page otherwise
            at.text_input(key="geo_coords_NavIC").input(text)
        return setup

    moved = run(typed("12.5 N, 80.25 E"))
    wrong = run(typed("120, 80"))

    assert _heads(moved)[0] == '<div class="geo-head">The sky above 12.50° N, 80.25° E</div>'
    assert moved.selectbox(key="geo_pick_NavIC").value is None
    assert any("Latitude must be between -90 and 90" in body for body in htmls(wrong))
    assert _heads(wrong)[0] == '<div class="geo-head">The sky above Capital (Delhi)</div>'


def test_coming_back_to_the_section_the_inputs_show_the_place_still_chosen():
    def setup(at):   # as after another section: the place is kept, the inputs' own state is gone
        _sky_and_ground(at)
        at.session_state["geo_where_BeiDou-3"] = ("Westernmost (Wuqia, Xinjiang)", 39.7, 75.3)

    at = run(setup)

    assert at.selectbox(key="geo_pick_BeiDou-3").value == "Westernmost (Wuqia, Xinjiang)"
    assert at.text_input(key="geo_coords_BeiDou-3").value == "39.7, 75.3"


def test_a_click_on_a_satellite_marker_uses_its_position_not_its_words():
    from ui import geometry_data
    assert geometry_data.clicked_place({"customdata": [12.0, 80.0], "x": 1, "y": 2}) == (12.0, 80.0)            # a square
    assert geometry_data.clicked_place({"customdata": ["NVS-01", "0.0° N, 129.5° E"], "x": 129.5, "y": 0.0}) == (0.0, 129.5)
    assert geometry_data.clicked_place({"customdata": ["2026-10-20 05:00", "over …", "35,800 km"], "x": 55, "y": 9}) == (9, 55)
    assert geometry_data.clicked_place({"x": 55, "y": 9}) == (9, 55)
