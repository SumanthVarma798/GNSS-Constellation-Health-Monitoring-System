"""The Geometry page: its numbers (ui/geometry_data.py), its pictures and grids (ui/figures/geometry.py), and the page."""
from datetime import datetime, timezone

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


def test_a_geostationary_track_stays_near_its_slot(beidou):
    tracks, here = gd.ground_tracks(beidou, WHEN, gs.TRACK_WINDOWS[0])

    lats, lons = tracks["BeiDou-3 G2"]
    assert max(abs(x) for x in lats) < 5 and max(lons) - min(lons) < 5
    assert set(here) == set(beidou)


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


def test_the_sky_view_has_a_frame_per_step_with_the_same_traces(beidou):
    frames = gd.sky_frames(beidou, 39.9, 116.4, WHEN, MASK)

    fig = gf.sky_view(frames, TYPES, MASK)

    assert len(fig.frames) == len(frames)
    assert [t.name for t in fig.data[1:]] == ["GEO", "IGSO"]
    assert all(len(f.data) == 2 and list(f.traces) == [1, 2] for f in fig.frames)


def test_a_track_across_the_date_line_is_broken():
    xs, ys = gf._unwrapped([0, 1, 2], [179.0, -179.0, -178.0])

    assert xs == [179.0, None, -179.0, -178.0] and ys == [0, None, 1, 2]


def test_the_map_holds_land_tracks_now_and_places(beidou):
    tracks, here = gd.ground_tracks(beidou, WHEN, gs.TRACK_WINDOWS[1])

    fig = gf.ground_map(tracks, here, TYPES, CHINA_KEY_POINTS)

    assert len(fig.data) == 1 + len(tracks) + 2
    assert fig.data[-1].name == "places" and len(fig.data[-1].x) == len(CHINA_KEY_POINTS)


def test_trends_draw_a_row_per_satellite_with_its_bands():
    epochs = pd.to_datetime(["2026-09-01", "2026-09-15"])
    series = {"INCLINATION": pd.DataFrame({"satellite": ["A", "A"], "EPOCH": epochs, "INCLINATION": [29.0, 29.1]})}
    bands = {"A": {"INCLINATION": (28.0, 30.0), "central_lon": (55.0, 55.0)}, "B": {}}

    fig = gf.orbit_trends(series, ["B", "A"], {"A": "GEO", "B": "IGSO"}, bands, epochs[0], epochs[1])

    names = [a.text for a in fig.layout.annotations if a.text.startswith("<b>")]
    assert names[0].startswith("<b>A</b>") and names[1].startswith("<b>B</b>")   # GEO first
    assert sum(t.fill == "toself" for t in fig.data) == 1 and sum(1 for t in fig.data if t.line.dash == "dash") == 1


def test_spacing_card_and_wheel(beidou):
    group = analyze_raan_spacing(beidou)[0]

    card = gf.spacing_card(group)
    wheel = gf.spacing_wheel(group)

    assert f'{group["ideal_spacing_deg"]:g}° apart' in card and card.count('<div class="sr">') == group["satellite_count"]
    assert len(wheel.data[-2].theta) == group["satellite_count"]   # the even-spacing rings


# ---- the page ----

def test_the_page_sits_between_station_keeping_and_the_master_map():
    titles = [title for title, _ in shell.PAGES]

    assert titles.index("Geometry") == titles.index("Station-keeping") + 1 == titles.index("Master map") - 1


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
    assert len(figures) == 2
    assert "IRNSS-1B" in figures[0] and "IRNSS-1I" not in figures[0]
    assert "QZS-6" in figures[1] and "QZS-2" not in figures[1]


def test_every_constellation_in_the_bar_has_places():
    from ui import geometry_settings, shell
    assert set(shell.CONSTELLATIONS) <= set(geometry_settings.PLACES)



def test_plane_spacing_points_medium_orbit_systems_to_the_overview():
    def setup(at):
        at.session_state["scope"] = "GPS"
        at.session_state["geo_section"] = "Plane spacing"
        _on("Geometry")(at)

    assert any("spread over orbital planes" in body for body in htmls(run(setup)))
