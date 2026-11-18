"""ui/next_step.py: the look ahead from a satellite's own element sets, and the words it is said in."""
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from analysis import burn_classes, burn_context
from analysis.forecast_settings import DRIFT_PER_KM
from analysis.slot_forecast import longitude_acceleration, own_box_half_width
from ui import next_step as N
from ui.figures import forecast_marks

NOW = pd.Timestamp("2026-11-18 12:00")
CLASS_COLUMNS = ["satellite", "kind", "window_end", "when", "burn_class", "delta_a_km", "delta_i_deg"]


def history(name, station=0.0, x0=0.0, v0=0.0, days=6, per_day=4, inc=0.05, kink=None):
    """Element sets whose mean longitude follows its station + x0 + v0 t + a t^2 / 2 (t in days before the newest).
    With `kink` it sits on its station until then (days before the newest) and drifts from it to x0 after."""
    slot = burn_context.designated_longitude(name)
    acc = longitude_acceleration(slot + station, inc)
    epoch = NOW - pd.to_timedelta(np.arange(days * per_day, -1, -1) / per_day, unit="D")
    t = -(NOW - epoch).total_seconds().to_numpy() / 86400
    lon = slot + station + x0 + v0 * t + 0.5 * acc * t ** 2
    if kink:
        lon = slot + station + np.where(t < -kink, 0.0, x0 * (t + kink) / kink)
    return pd.DataFrame({"satellite": name, "EPOCH": epoch, "RA_OF_ASC_NODE": 0.0, "ARG_OF_PERICENTER": 0.0,
                         "MEAN_ANOMALY": (lon + burn_context.gmst_deg(epoch)) % 360, "INCLINATION": inc,
                         "LonDrift_deg_per_day": 0.0}), acc


def burns(name, sizes_km, kind="east-west"):
    """Routine east-west burns, one every 25 days up to a week ago."""
    when = [NOW - pd.Timedelta(days=7 + 25 * i) for i in range(len(sizes_km))]
    return pd.DataFrame({"satellite": name, "kind": kind, "window_end": when, "when": when,
                         "burn_class": burn_classes.ROUTINE_EW, "delta_a_km": sizes_km, "delta_i_deg": 0.0})


NO_BURNS = pd.DataFrame(columns=CLASS_COLUMNS)
NAME = "IRNSS-1C"   # a GEO slot at 83 E, where the pull is gentle


def test_the_fit_finds_where_it_is_and_how_fast_it_drifts_with_the_pull_taken_out():
    frame, acc = history(NAME, station=0.1, x0=0.12, v0=-0.03)
    f = N.satellite_forecast(NAME, frame, NO_BURNS, NOW, constellation="NavIC")
    assert f["status"] == "ok"
    assert f["v0"] == pytest.approx(-0.03, abs=2e-3)
    assert f["pos"] == pytest.approx(0.1 + 0.12, abs=0.05)
    assert f["as_of"] == NOW


def test_nothing_due():
    frame, _ = history(NAME, x0=0.0, v0=0.0)
    f = N.satellite_forecast(NAME, frame, NO_BURNS, NOW, constellation="NavIC")
    text, tone, as_of = N.satellite_line(f, NOW)
    assert text.startswith(f"Nothing due for {NAME} in 30 days")
    assert tone == "ok" and as_of == "18 Nov"
    assert "assumed" in text                      # no burns to read its own box from
    assert N.constellation_line([f], NOW)[0].startswith("Nothing due in 30 days across 1 satellite")


def test_due_soon_says_when_it_reaches_the_edge_and_the_last_chance():
    frame, _ = history(NAME, x0=0.0, v0=-0.04)    # about 12 days to the edge
    f = N.satellite_forecast(NAME, frame, NO_BURNS, NOW, constellation="NavIC")
    text, tone, _ = N.satellite_line(f, NOW)
    assert f"{NAME} reaches the ±0.5° box edge in 1" in text and "last chance" in text
    assert tone in ("warn", "accent")
    assert "1 of 1 satellites reaches the ±0.5° box edge within 30 days" in N.constellation_line([f], NOW)[0]
    short = N.tile_line(f, NOW)
    assert short and short[0].startswith("Box edge in")


def test_already_outside_our_box_is_said_without_blame():
    frame, _ = history(NAME, x0=-0.8, days=60, kink=7.5)   # parked on its slot, then drifting west
    f = N.satellite_forecast(NAME, frame, NO_BURNS, NOW, constellation="NavIC")
    assert abs(f["station"]) < 0.05 and f["pos"] == pytest.approx(-0.8, abs=0.1)
    text, tone, _ = N.satellite_line(f, NOW)
    assert f"{NAME} is 0.8° west of its slot, outside the ±0.5° box; a correction of about" in text and tone == "warn"
    assert N.tile_line(f, NOW) == ("Outside its box", "warn")


def test_parked_steadily_off_the_slot_in_our_table_is_a_slot_to_confirm_not_a_fault():
    frame, _ = history(NAME, station=-1.98, x0=0.0, days=100, kink=0.01)   # parked on it
    f = N.satellite_forecast(NAME, frame, NO_BURNS, NOW, constellation="NavIC")
    assert f["confirm"] and f["station_lon"] == pytest.approx(81.02, abs=0.05)
    text, tone, _ = N.satellite_line(f, NOW)
    assert text.startswith(f"{NAME} is kept at 81.0° E, 2.0° west of the 83° E in our slot table; "
                           "the table may be out of date (to confirm). Its next east-west burn")
    assert "outside" not in text and "last chance" not in text and tone == "idle"
    assert N.geometry_line(f, NOW).endswith("(to confirm).")
    assert N.burn_cells(f, NOW)[1][1] == "slot to confirm"
    line = N.constellation_line([f], NOW)[0]
    assert "slot to confirm" in line and "outside" not in line


def test_off_the_slot_for_less_than_90_days_is_still_outside_the_box():
    frame, _ = history(NAME, station=-1.98, x0=0.0, days=20, kink=0.01)
    f = N.satellite_forecast(NAME, frame, NO_BURNS, NOW, constellation="NavIC")
    assert not f["confirm"] and "outside the ±0.5° box" in N.satellite_line(f, NOW)[0]


def test_too_few_routine_burns_assume_a_share_of_our_box_and_three_give_its_own():
    frame, acc = history(NAME, x0=0.0, v0=0.0)
    few = N.satellite_forecast(NAME, frame, burns(NAME, [-2.0, -2.0]), NOW, constellation="NavIC")
    assert few["own_known"] is False and few["own_half"] == pytest.approx(0.4)
    known = N.satellite_forecast(NAME, frame, burns(NAME, [-2.0, -2.2, -1.8]), NOW, constellation="NavIC")
    assert known["own_known"] is True
    assert known["own_half"] == pytest.approx(own_box_half_width(2.0 * abs(DRIFT_PER_KM), acc), rel=0.01)
    assert "assumed" not in N.satellite_line(known, NOW)[0]


def test_just_burned_waits_for_more_element_sets():
    frame, _ = history(NAME)
    recent = burns(NAME, [-2.0])
    recent["window_end"] = NOW - pd.Timedelta(hours=6)
    f = N.satellite_forecast(NAME, frame, recent, NOW, constellation="NavIC")
    assert f["status"] == "settling" and "next step follows" in N.satellite_line(f, NOW)[0]


def test_old_orbit_data_gives_no_look_ahead():
    frame, _ = history(NAME)
    f = N.satellite_forecast(NAME, frame, NO_BURNS, NOW + pd.Timedelta(days=30), constellation="NavIC")
    assert f["status"] == "stale" and "too little recent orbit data" in N.satellite_line(f, NOW)[0]


def test_burn_cells_and_the_ghost_marks():
    frame, _ = history(NAME, x0=0.0, v0=-0.04)
    f = N.satellite_forecast(NAME, frame, NO_BURNS, NOW, constellation="NavIC")
    ideal, last = N.burn_cells(f, NOW)
    assert "m/s" in ideal[1] and "Δa" in ideal[1] and last[2] in ("warn", "ok")
    marks = N.expected_burns({NAME: f}, NOW)
    assert {m[1] for m in marks} == {"ideal", "last chance"}
    import plotly.graph_objects as go
    base = go.Figure(go.Scatter(x=[NOW - pd.Timedelta(days=90), NOW], y=[0, 0]))
    base.update_layout(xaxis={"range": [NOW - pd.Timedelta(days=90), NOW]})
    out = forecast_marks.add_expected(base, marks, [NAME], NOW)
    assert len(out.data) == 3 and len(base.data) == 1                    # the kept figure is left as it was
    assert pd.Timestamp(out.layout.xaxis.range[1]) > NOW


MEO = {"A": {"offset": 0.5, "offset_limit": 5.0, "rate": 0.6}, "B": {"offset": -0.2, "offset_limit": 5.0, "rate": -0.1}}


def test_a_plane_s_years_to_its_limit():
    text, tone, as_of = N.meo_line("Galileo", MEO, "2026-11-15")
    assert text == "Galileo plane A reaches its 5° node limit in about 8 years at today's rate. No action needed."
    assert tone == "ok" and as_of == "15 Nov"
    steady = {"A": {"offset": 0.5, "offset_limit": 5.0, "rate": -0.3}}   # moving back towards the pattern
    assert N.meo_line("GPS", steady, "2026-11-15")[0].startswith("No plane of GPS is moving towards its node limit")
    soon = {"C": {"offset": 4.8, "offset_limit": 5.0, "rate": 0.4}}
    text, tone, _ = N.meo_line("GLONASS", soon, "2026-11-15")
    assert "about 6 months" in text and tone == "warn"


def test_fuel_words_say_what_is_a_guess():
    words = N.fuel_line({"rate": 3.2, "years": (12.2, 18.7), "from_budget": False})
    assert words == ("about 3.2 m/s a year; about 12–19 more years at this rate "
                     "(typical for this class; the operator's real budget is not public).")
    assert "more than 30 more years" in N.fuel_line({"rate": 0.5, "years": (40.0, 90.0), "from_budget": False})
    assert N.fuel_line(None) == ""


def test_the_line_always_says_as_of():
    html = N.line_html(("x", "ok", "15 Nov"))
    assert "as of 15 Nov" in html and "it changes if the operator burns" in html
    assert N.line_html(("x", "ok", "15 Nov"), short=True).count("as of 15 Nov") == 1


def test_the_explainer_is_one_line_a_picture_and_its_sources():
    from ui import forecast_explainer as E
    assert E.diagram().count("<polyline") == 4 and "<svg" in E.diagram()
    body = E.body()
    assert "Soop, Handbook of Geostationary Orbits" in body and "What we cannot know" in body


def test_a_real_constellation_gets_a_line_per_satellite_and_for_the_constellation():
    from ui import data, next_step_data
    result = data.load("NavIC", 90)
    line = next_step_data.constellation_line("NavIC", result)
    assert line[1] in ("ok", "accent", "warn", "idle") and line[0]   # the frozen test data is old: words, maybe no date
    lines = next_step_data.satellite_lines("NavIC", result)
    assert set(lines) == set(result["health"]["Satellite"]) and all(text for text, _, _ in lines.values())
    assert next_step_data.look_ahead("NavIC", result) == next_step_data.look_ahead("NavIC", result)   # kept, not redone


def test_home_reads_the_published_line_while_the_copy_is_fresh(monkeypatch):
    from ui import home_data
    made = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    monkeypatch.setattr(home_data, "_snapshot", lambda: {"made": made, "window_days": 90, "parts": {},
                                                         "next_steps": {"NavIC": ["Nothing due.", "ok", "17 Nov"]}})
    assert home_data.next_line("NavIC", 90) == ("Nothing due.", "ok", "17 Nov")
    assert home_data.next_line("NavIC", 30) != ("Nothing due.", "ok", "17 Nov")   # another time range: worked out here

