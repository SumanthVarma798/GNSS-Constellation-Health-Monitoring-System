"""The Geometry page: its numbers (ui/geometry_data.py), its pictures and grids (ui/figures/geometry.py), and the page."""
import json
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
from ui import palette, shell
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


def test_view_windows_find_each_stretch_above_the_mask():
    made = {"rises": _Made(lambda m: 10 if m >= 150 else 0), "sets": _Made(lambda m: 20 if m < 61 else 0),
            "twice": _Made(lambda m: 20 if m < 30 or 100 <= m < 200 else 0),
            "always": _Made(lambda m: 40), "never": _Made(lambda m: -5), "at the mask": _Made(lambda m: MASK)}

    rows = {r["satellite"]: r for r in gd.view_windows(made, 0, 0, WHEN, MASK)}
    at = lambda minutes: WHEN + timedelta(minutes=minutes)   # noqa: E731
    end = at(gs.NEXT_HOURS * 60)

    assert rows["rises"]["windows"] == [(at(150), end)] and not rows["rises"]["in_view"]
    assert rows["sets"]["windows"] == [(WHEN, at(61))] and rows["sets"]["in_view"]   # to the first step below the mask
    assert rows["twice"]["windows"] == [(WHEN, at(30)), (at(100), at(200))]
    assert rows["always"]["windows"] == [(WHEN, end)] and rows["always"]["in_view"]
    assert rows["never"]["windows"] == [] and not rows["never"]["in_view"]
    assert rows["at the mask"]["windows"] == []   # exactly on the mask is not above it
    assert gd.next_rise(rows["rises"]) == at(150) and gd.next_rise(rows["twice"]) == at(100)
    assert gd.next_rise(rows["sets"]) is None and gd.next_rise(rows["never"]) is None   # a set one does not rise again in the day


def test_view_windows_for_real_satellites_stay_inside_the_day(beidou):
    rows = gd.view_windows(beidou, 39.9, 116.4, WHEN, MASK)

    assert {r["satellite"] for r in rows} == set(beidou)
    end = WHEN + timedelta(hours=gs.NEXT_HOURS)
    assert all(WHEN <= a <= b <= end for r in rows for a, b in r["windows"])
    geo = [r for r in rows if r["satellite"].startswith("BeiDou-3 G")]
    assert all(len(r["windows"]) <= 1 for r in geo)   # geostationary: up all day or never


def test_the_timeline_puts_those_in_view_first_then_by_the_next_rise_and_never_last():
    at = lambda hours: WHEN + timedelta(hours=hours)   # noqa: E731
    rows = [{"satellite": "never", "in_view": False, "windows": []},
            {"satellite": "late", "in_view": False, "windows": [(at(5), at(8))]},
            {"satellite": "soon", "in_view": False, "windows": [(at(1), at(3)), (at(20), at(22))]},
            {"satellite": "sets late", "in_view": True, "windows": [(WHEN, at(6))]},
            {"satellite": "sets soon", "in_view": True, "windows": [(WHEN, at(2)), (at(9), at(12))]}]

    assert [r["satellite"] for r in gd.timeline_order(rows)] == ["sets soon", "sets late", "soon", "late", "never"]


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


def test_the_limit_lines_sit_above_the_data_and_their_words_have_a_backing(beidou):
    fig = gf.dop_trend(gd.dop_series(beidou, 39.9, 116.4, WHEN, MASK), "Beijing")
    limits = [s for s in fig.layout.shapes if s.line.dash == "dot"]
    words = [a for a in fig.layout.annotations if "below" in a.text]

    assert len(limits) == len(words) == len(gf.BAND_LINES)
    assert all(s.layer == "above" for s in limits)
    assert all(a.bgcolor.startswith("rgba(32, 36, 43") or a.bgcolor.startswith("rgba(32,36,43") for a in words)
    assert all(a.borderpad > 0 for a in words)


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
    assert "Height</span>  %{customdata[2]:,.0f} km" in track.hovertemplate and track.customdata[0][0].endswith("UTC")
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

    fig = gf.satellite_trends(series, "A", bands, epochs[0], epochs[1])

    assert fig.layout.hovermode == "x unified" and fig.layout.hoversubplots == "axis"
    assert {t.xaxis or "x" for t in fig.data} == {"x"} and fig.layout.xaxis.showspikes
    lines = [t for t in fig.data if t.hoverinfo != "skip"]
    assert [t.name for t in lines] == ["Tilt", "Height"] and list(lines[1].y) == [35786.0]
    assert "(should be 28 to 30)" in lines[0].hovertemplate and "Height</span>  %{y:,.1f}" in lines[1].hovertemplate
    assert sum(t.fill == "toself" for t in fig.data) == 1 and sum(1 for t in fig.data if t.line.dash == "dash") == 1
    labels = [a.text.split("  ")[0] for a in fig.layout.annotations if a.x == 0]
    assert labels == [name for _, name, _, _ in gs.TRENDS]          # each strip named, with its unit, above it
    assert [a.text for a in fig.layout.annotations if a.x == 1] == ["now 29.100", "now 35,786.0"]   # latest beside the name
    assert fig.layout.height == gf.TREND_ROW_PX * len(gs.TRENDS) + gf.TREND_PAD_PX   # the same for every satellite


def test_trends_mark_readings_outside_the_band_and_name_them_when_the_latest_is_outside():
    epochs = pd.to_datetime(["2026-09-01", "2026-09-08", "2026-09-15"])
    series = {"INCLINATION": pd.DataFrame({"satellite": ["A"] * 3, "EPOCH": epochs, "INCLINATION": [29.0, 31.0, 30.5]}),
              "central_lon": pd.DataFrame({"satellite": ["A"] * 3, "EPOCH": epochs, "central_lon": [54.0, 56.0, 55.0]})}
    bands = {"INCLINATION": (28.0, 30.0), "central_lon": (55.0, 55.0)}   # one value: no tolerance, so never outside

    fig = gf.satellite_trends(series, "A", bands, epochs[0], epochs[-1])

    off = [t for t in fig.data if t.name and t.name.endswith("outside")]
    assert [t.name for t in off] == ["Tilt outside"] and list(off[0].y) == [31.0, 30.5]
    assert off[0].marker.color == palette.BAD and off[0].hoverinfo == "skip"
    ends = {a.text: a.font.color for a in fig.layout.annotations if a.x == 1}
    assert ends == {"now 30.500": palette.BAD, "now 55.000": palette.INK}
    assert any(a.text == "now outside: Tilt" and a.font.color == palette.BAD for a in fig.layout.annotations)


# ---- when each satellite is in view ----

def test_the_timeline_has_a_bar_per_stretch_with_the_rise_time_and_a_lane_for_every_satellite():
    at = lambda hours: WHEN + timedelta(hours=hours)   # noqa: E731
    rows = [{"satellite": "never <b>", "in_view": False, "windows": []},
            {"satellite": "QZS-2 (Michibiki-2)", "in_view": False, "windows": [(at(1.5), at(3)), (at(20), at(24))]},
            {"satellite": "up", "in_view": True, "windows": [(WHEN, at(2))]}]

    fig = gf.view_timeline(rows, {"up": "GEO"}, WHEN, INDIA)

    bars = fig.data[0]
    assert list(bars.y) == ["up · GEO", f"QZS-2 · {gs.OTHER_ORBIT}", f"QZS-2 · {gs.OTHER_ORBIT}"] and list(bars.text) == ["in view", "13:00", "07:30"]
    assert list(bars.base)[0] == datetime(2026, 10, 4, 6, 0) and bars.x[0] == 2 * 3600 * 1000   # placed in UTC; labels in the viewer's clock
    assert fig.layout.yaxis.categoryarray == ("up · GEO", f"QZS-2 · {gs.OTHER_ORBIT}", f"never <b> · {gs.OTHER_ORBIT}") and fig.layout.yaxis.autorange == "reversed"
    assert any(t.type == "scatter" and t.mode == "text" and list(t.y) == [f"never <b> · {gs.OTHER_ORBIT}"] for t in fig.data)   # a lane without a bar says so
    assert fig.layout.height == gf.LANE_PX * 3 + 70 and fig.layout.xaxis.fixedrange   # a lane each: the page scrolls
    assert any(s.line.color == palette.ACCENT for s in fig.layout.shapes)               # the line for now


def test_the_timelines_one_line_says_how_many_are_in_view_and_the_next_to_rise():
    rows = [{"satellite": "never", "in_view": False, "windows": []},
            {"satellite": "soon", "in_view": False, "windows": [(WHEN + timedelta(hours=1), WHEN + timedelta(hours=2))]},
            {"satellite": "up", "in_view": True, "windows": [(WHEN, WHEN + timedelta(hours=1))]}]

    assert gf.next_summary(rows, WHEN, timezone.utc) == "1 of 3 in view now · next: soon 4 Oct 07:00 UTC"


# ---- position quality in metres ----

def test_error_in_metres_is_the_dop_times_one_distance_error():
    assert gd.error_metres(2.0, 5.0) == 10.0 and gd.error_metres(None) is None
    assert gd.error_metres(1.0) == gs.UERE_M


def test_the_bands_in_metres_follow_the_configured_pdop_bands():
    rows = {band: (dop, metres) for band, dop, metres, _ in gf.band_rows()}

    assert rows["Excellent"] == ("1 to 2", f"{1 * gs.UERE_M:g} to {2 * gs.UERE_M:g} m")
    assert rows["Poor"] == ("over 20", f"over {20 * gs.UERE_M:g} m")
    assert set(rows) == set(gs.DOP_BANDS["PDOP"]) == set(gs.BAND_LIKE)
    assert gf.metres_words(6.46) == "6.5 m" and gf.metres_words(12.4) == "12 m" and gf.metres_words(None) == "no position"


def test_every_city_is_on_the_earth_and_every_default_place_is_a_city():
    assert len(gs.CITIES) >= 50 and len(set(gs.CITIES)) == len(gs.CITIES)
    assert all(-90 <= lat <= 90 and -180 <= lon <= 180 for lat, lon in gs.CITIES.values())
    assert {"Hyderabad, India", "Chongqing, China"} <= set(gs.CITIES)
    assert all(city in gs.CITIES for pair in [*gs.DEFAULT_PLACES.values(), gs.GLOBAL_DEFAULT_PLACES] for city in pair)
    assert gs.default_places("GPS") == gs.GLOBAL_DEFAULT_PLACES and gs.default_places("NavIC")[0] == "Hyderabad, India"


def _row(place, seen, pdop):
    return {"place": place, "lat": 17.39, "lon": 78.49, "seen": seen, "PDOP": pdop, "metres": gd.error_metres(pdop)}


def test_place_cards_show_satellites_in_view_and_metres_and_compare_the_two():
    here, there = _row("Hyderabad, India", 9, 1.5), _row("<Chongqing>", 6, 3.0)

    cards = gf.place_cards(here, there)

    assert cards.count('class="geo-place ') == 2 and "&asymp; 7.5 m" in cards and "&asymp; 15 m" in cards
    assert "9 satellites in view" in cards and "&lt;Chongqing&gt;" in cards and "<Chongqing>" not in cards
    assert "Hyderabad, India is pinned down about 2.0 times more tightly than &lt;Chongqing&gt;" in cards
    assert "no position" in gf.place_cards(_row("A", 3, None), here) and "cannot be compared" in gf.compare_words(_row("A", 3, None), here)
    assert "about equally" in gf.compare_words(here, _row("Same", 9, 1.5))


def test_bunched_satellites_leave_a_bigger_patch_where_the_receiver_could_be():
    assert gf.overlap_area(gs.BUNCHED_ANGLES) > 2 * gf.overlap_area(gs.SPREAD_ANGLES) > 0
    corners = gf.where_you_could_be(gs.SPREAD_ANGLES)
    assert len(corners) == 4 and all(abs(x) < 0.3 and abs(y) < 0.3 for x, y in corners)   # the patch sits round the receiver
    fig = gf.spread_sketch(gs.BUNCHED_ANGLES)
    assert [t.fillcolor for t in fig.data if t.fill == "toself"] == [palette.TRACK, palette.TRACK, palette.WARN]
    assert "times bigger when they are bunched" in gf.spread_words()


def test_the_quality_map_draws_a_dot_per_city_by_its_band_and_rings_the_two_chosen(beidou):
    rows = gd.dop_rows(beidou, {"Beijing, China": (39.9, 116.4), "Chongqing, China": (29.56, 106.55)}, WHEN, MASK)

    fig = gf.quality_map(rows, rows[0], rows[1], ([90, 130], [15, 50]))

    dots = [t for t in fig.data if t.mode == "markers" and t.hovertemplate]
    assert sum(len(t.x) for t in dots) == 2 and {t.marker.symbol for t in dots} == {"circle", "diamond", "square"}
    assert [a.text for a in fig.layout.annotations] == ["<b>Beijing</b>", "<b>Chongqing</b>"]   # city only, on a backing
    assert all(a.bgcolor for a in fig.layout.annotations) and {"Your place", "Compare with"} <= {t.name for t in fig.data}
    assert [t.name for t in dots] == [words for _, _, words in gf.quality_legend()]


# ---- orbit trends in a line ----

def _readings(column, values, start="2026-09-01"):
    epochs = pd.date_range(start, periods=len(values), freq="7D")
    return pd.DataFrame({"satellite": ["A"] * len(values), "EPOCH": epochs, column: values})


def test_the_trend_line_says_steady_rising_or_falling_and_when_outside_its_range():
    series = {"altitude_km": _readings("altitude_km", [35786.0, 35786.4, 35785.9, 35786.2]),
              "INCLINATION": _readings("INCLINATION", [1.00, 1.05, 1.10, 1.15]),
              "central_lon": _readings("central_lon", [60.0, 59.8, 59.6, 59.0])}
    measures = [m for m in gs.TRENDS if m[0] in series]

    line = gf.trend_line(series, "A", {"central_lon": (59.5, 60.5)}, 90, measures)

    assert line == ("Over the last 90 days: tilt rising 0.15° over 21 days; height steady within 0.5 km; "
                    "centre falling 0.96° over 21 days, now outside its range.")
    assert gf.trend_line(series, "B", {}, 90, measures) == ""


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
    cards = [b for b in htmls(at) if b.startswith('<div class="geo-card-head">')]
    assert [c.split("</b>")[0].split("<b>")[1] for c in cards] == ["IRNSS-1B", "QZS-3 (Michibiki-3)", "QZS-6 (Michibiki-6)"]
    assert all('class="geo-say">Over the last' in c for c in cards)


def _sky_and_ground(at):
    at.session_state["scope"] = "BeiDou-3"
    at.session_state["geo_section"] = "Sky and ground"
    _on("Geometry")(at)


def _heads(at):
    return [b for b in htmls(at) if b.startswith('<div class="geo-head">')]


def test_sky_and_ground_starts_at_your_place_and_says_when_each_satellite_is_in_view():
    at = run(_sky_and_ground)

    assert _heads(at)[0] == '<div class="geo-head">The sky above Beijing, China</div>'
    # Every tracked satellite is either a row or named as having no orbit data (the three added on 8 Nov 2026 have
    # none in the frozen test data).
    no_data = [n for body in htmls(at) if "No orbit data, so not drawn: " in body
               for n in body.split("No orbit data, so not drawn: ")[1].split("<")[0].split(", ")]
    timeline = next(chart.proto.spec for chart in at.get("plotly_chart") if '"categoryarray"' in chart.proto.spec)
    assert len(json.loads(timeline)["layout"]["yaxis"]["categoryarray"]) == len(BEIDOU3_SATS) - len(no_data)   # a lane each
    assert set(no_data) <= {"BeiDou-2 IGSO-6", "BeiDou-2 IGSO-7", "BeiDou-3S IGSO-2S"}
    assert any("in view now" in body and "position error about" in body for body in htmls(at))   # the place, in a line


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
    assert _heads(wrong)[0] == '<div class="geo-head">The sky above Hyderabad, India</div>'


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


def test_too_few_satellites_say_so_once_for_the_constellation_and_name_them():
    line = gf.too_few_line("NavIC", ["IRNSS-1B", "NVS-01", "<x>"], "In service", more=True)

    assert "NavIC has" in line and "3 satellites</span>" in line and "needs 4" in line and "Choose All" in line
    assert "IRNSS-1B<br>NVS-01<br>&lt;x&gt;" in line
    assert "Choose All" not in gf.too_few_line("NavIC", ["A"], "In service") and "1 satellite<" in gf.too_few_line("NavIC", ["A"], "All")
    assert gf.too_few_line("NavIC", list("ABCD"), "All") == ""


def test_the_city_map_is_exactly_as_wide_as_the_card_shape_and_stays_on_the_earth():
    for places, picks in (([(6, 68), (35, 97)], [(17, 78), (29, 106)]), ([(30, 130), (45, 145)], [(17, 78)]),
                          ([(-30, 30), (60, 170)], [(51, -0.1)]), ([(36, 120)], [(37, 125)])):
        (x0, x1), (y0, y1) = gf.map_ranges(places, picks)
        assert abs((x1 - x0) - gf.MAP_ASPECT * (y1 - y0)) < 1e-9 and -180 <= x0 and x1 <= 180 and -90 <= y0 and y1 <= 90
        assert x0 <= min(lon for _, lon in [*places, *picks]) and x1 >= max(lon for _, lon in [*places, *picks])
        assert y0 <= min(lat for lat, _ in [*places, *picks]) and y1 >= max(lat for lat, _ in [*places, *picks])
    assert gf.map_ranges([(-30, 30), (60, 170)], [(51, -0.1)]) == ([-180, 180], [-90, 90])


def test_the_maps_key_is_a_row_of_marks_with_words_and_no_hex():
    key = gf.quality_legend_html()

    assert key.count("<li>") == 5 and "swatch diamond" in key and "swatch square" in key and "swatch ring" in key
    assert "under 25 m" in key and "Your place" in key and "#" not in key


def test_a_one_step_pass_has_a_width_and_a_stretch_ends_at_the_first_step_below():
    from datetime import datetime, timedelta, timezone

    times = [datetime(2026, 11, 18, tzinfo=timezone.utc) + timedelta(minutes=10 * i) for i in range(6)]
    assert gd.windows_from([False, True, False, False, True, True], times) == [(times[1], times[2]), (times[4], times[5])]


def test_a_measure_without_a_range_is_never_called_outside_it():
    from ui.figures.geometry import outside

    assert not outside(5.0, None) and not outside(5.0, (3.0, 3.0)) and outside(5.0, (0.0, 4.0))


def test_a_pass_seen_only_at_the_last_step_still_has_a_bar():
    rows = [{"satellite": "late", "in_view": False, "windows": [(WHEN + timedelta(hours=24), WHEN + timedelta(hours=24))]}]
    fig = gf.view_timeline(rows, {}, WHEN, INDIA)
    bars = fig.data[0]
    assert bars.x[0] == gs.NEXT_STEP_MINUTES * 60 * 1000
    right = fig.layout.xaxis.range[1]
    right = datetime.fromisoformat(right) if isinstance(right, str) else right
    assert bars.base[0] + timedelta(milliseconds=bars.x[0]) <= right   # inside the axis, not clipped


def test_the_timeline_axis_is_labelled_in_the_viewers_clock():
    fig = gf.view_timeline([{"satellite": "up", "in_view": True, "windows": [(WHEN, WHEN + timedelta(hours=2))]}], {}, WHEN, INDIA)
    assert fig.layout.xaxis.ticktext[0].startswith(f"{WHEN.astimezone(INDIA):%H:%M}")


def test_a_bar_keeps_its_length_across_a_clock_change():
    """New York leaves daylight saving at 06:00 UTC on 1 Nov 2026: a 4-hour pass across it is still 4 hours long and
    starts where it does in UTC; only the labels are in the viewer's clock."""
    from zoneinfo import ZoneInfo

    now = datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc)
    rows = [{"satellite": "up", "in_view": False, "windows": [(datetime(2026, 11, 1, 4, 0, tzinfo=timezone.utc),
                                                             datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc))]}]
    fig = gf.view_timeline(rows, {}, now, ZoneInfo("America/New_York"))
    bars = fig.data[0]
    assert bars.x[0] == 4 * 3600 * 1000 and bars.base[0] == datetime(2026, 11, 1, 4, 0)
    assert list(bars.text) == ["00:00"]   # 04:00 UTC is midnight in New York, still on daylight time
