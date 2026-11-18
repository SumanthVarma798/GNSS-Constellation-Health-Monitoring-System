"""analysis/burn_classes.py: synthetic series with a known answer, then the same questions put to the bundled data.

The synthetic satellites follow the physics the classifier leans on: a burn of delta-a km changes the drift by
-0.012842 * delta-a degrees a day, the longitude acceleration pulls the drift on between burns, longitude is the
integral of the drift, and the mean anomaly is set so the elements give that longitude back (analysis/burn_context.py).
"""
from datetime import datetime, timezone
from functools import cache

import numpy as np
import pandas as pd
import pytest

from analysis import burn_class_settings as S
from analysis import burn_classes as C
from analysis.burn_context import gmst_deg
from analysis.bundled_run import BURN_COLUMNS, assess_constellation, burns, burns_detailed
from config.config import DEFAULT_PARAMS

A_SYNC = 42164.17
START = pd.Timestamp("2026-01-01")


def accel(longitude):
    return -S.LON_ACCEL_K * np.sin(np.deg2rad(2 * (longitude - S.LON_ACCEL_STABLE)))


def make_history(name, lon0, days, burns=(), inc=0.05, drift0=0.0, per_day=6, inc_spikes=()):
    """One satellite's element sets every 1/per_day days. `burns` is [(day, delta-a km)]; `inc_spikes` is
    [(first record, last record, extra degrees)] of wrong inclination."""
    n = int(days * per_day)
    day = np.arange(n) / per_day
    drift = drift0 + accel(lon0) * day
    for when, dsma in burns:
        drift[day >= when] += S.DRIFT_PER_KM * dsma
    lon = lon0 + np.cumsum(drift) / per_day
    sma = A_SYNC + drift / S.DRIFT_PER_KM
    epoch = START + pd.to_timedelta(day, unit="D")
    raan, argp = 100.0, 0.0
    inclination = np.full(n, inc, dtype=float)
    for first, last, extra in inc_spikes:
        inclination[first:last + 1] += extra
    return pd.DataFrame({
        "EPOCH": epoch, "satellite": name, "SEMIMAJOR_AXIS": sma, "INCLINATION": inclination,
        "ECCENTRICITY": 2e-4, "MEAN_MOTION": 1.0027, "LonDrift_deg_per_day": drift,
        "RA_OF_ASC_NODE": raan, "ARG_OF_PERICENTER": argp,
        "MEAN_ANOMALY": (lon + gmst_deg(epoch) - raan - argp) % 360.0,
    })


def run(history, constellation="NavIC"):
    detailed = burns_detailed(history, DEFAULT_PARAMS)
    return C.classify(detailed, history, constellation)


def sawtooth(lon0, count, edge=0.0237):
    """The routine east-west cycle at a longitude: from a drift of +edge the acceleration takes it to -edge in one period,
    where a burn of dsma flips it back. Returns the burns [(day, dsma)] (the k-th at (k + 1) periods), the period, dsma."""
    a_l = accel(lon0)
    dsma = -2 * edge / abs(S.DRIFT_PER_KM)
    period = 2 * edge / abs(a_l)
    return [(period * (k + 1), dsma) for k in range(count)], period, dsma


def routine_history(name, lon0, count):
    plan, period, dsma = sawtooth(lon0, count)
    return make_history(name, lon0, period * (count + 1), plan, drift0=0.0237), plan, period


def test_nvs01_like_cycle_is_routine_and_high():
    """The model interval at 131.5 E is about 30 days, and every burn after the third is judged on its own history."""
    history, plan, period = routine_history("NVS-01", 131.5, 9)
    t = run(history)
    ew = t[t["kind"] == "east-west"]
    assert 27 <= period <= 33
    assert len(ew) >= 8
    assert (ew["burn_class"].iloc[:3] == C.UNEXPLAINED).all()          # alone and with fewer than three earlier burns
    assert (ew["burn_class"].iloc[3:] == C.ROUTINE_EW).all()
    assert (ew["confidence"].iloc[3:] == "high").all()
    assert (ew["basis"].iloc[3:] == "own").all()
    assert ew["delta_a_km"].between(-4.0, -3.4).all()


def test_g1_relocation_pair_is_one_relocation_not_two_irregular_burns():
    plan, period, dsma = sawtooth(140.0, 4)
    days = 20.0 / 1.36
    start = period * 4.5
    big = [(start, -105.9), (start + days, 106.8)]
    history = make_history("BeiDou-3 G1", 140.0, start + days + 40, plan + big, drift0=0.0237)
    t = run(history, "BeiDou-3")
    pair = t[t["delta_a_km"].abs() > 50]
    assert len(pair) == 2
    assert (pair["burn_class"] == C.RELOCATION).all() and (pair["confidence"] == "high").all()
    assert pair["delta_a_km"].round().tolist() == [-106, 107]
    assert pair["drift_after"].iloc[0] == pytest.approx(1.36, abs=0.05)
    assert not t["counted"][pair.index].any()


def test_reversing_inclination_step_is_an_artefact():
    """Three wrong records give +3.87 degrees then -3.87 back: more than a degree, and undone."""
    history = make_history("BeiDou-3 I3", 118.0, 40, inc=55.2, inc_spikes=[(60, 62, 3.87)])
    t = run(history, "BeiDou-3")
    steps = t[t["delta_i_deg"].abs() > 1]
    assert len(steps) >= 2
    assert (t.loc[t["delta_i_deg"].abs() > 1, "burn_class"] == C.ARTEFACT).all()
    assert (~t["counted"]).all()


def test_small_inclination_step_that_is_undone_is_an_artefact_by_reversal():
    history = make_history("BeiDou-3 G2", 80.0, 60, inc=2.0, inc_spikes=[(60, 63, 0.6)])
    t = run(history, "BeiDou-3")
    ns = t[t["kind"] == "north-south"]
    assert len(ns) == 2 and (ns["delta_i_deg"].abs() < S.NS_MAX_DEG).all()
    assert (ns["burn_class"] == C.ARTEFACT).all()
    assert "undone" in ns["note"].iloc[0]


def test_four_burns_in_three_days_are_a_response():
    plan, period, dsma = sawtooth(131.5, 6)
    cluster = [(period * 7 + d, a) for d, a in ((0.0, -6.7), (0.7, 5.2), (1.4, 11.7), (2.3, -4.5))]
    history = make_history("NVS-01", 131.5, period * 7 + 25, plan + cluster, drift0=0.0237, per_day=8)
    t = run(history)
    late = t[t["when"] >= START + pd.Timedelta(days=period * 6.9)]
    assert len(late) >= 3
    assert (late["burn_class"] == C.RESPONSE).all()
    assert late["counted"].all()
    assert (late["confidence"] == "high").all()


def test_a_raise_into_the_graveyard_is_end_of_life():
    plan, period, dsma = sawtooth(131.5, 4)
    last = period * 4.2
    history = make_history("NVS-01", 131.5, last + 30, plan + [(last, 100.0), (last + 3, 100.0)], drift0=0.0237)
    t = run(history)
    raises = t[t["delta_a_km"] > 50]
    assert len(raises) == 2
    assert (raises["burn_class"] == C.DISPOSAL).all()
    assert raises["alt_after_km"].iloc[-1] >= 35986.0
    assert not raises["counted"].any()


def test_right_direction_and_timing_but_triple_size_is_medium_routine():
    """2 of 3 tests pass (T1 interval, T3 direction); T2 size fails at three times its norm."""
    plan, period, dsma = sawtooth(131.5, 8)
    plan[6] = (plan[6][0], dsma * 3)
    history = make_history("NVS-01", 131.5, period * 8.5, plan, drift0=0.0237)
    t = run(history)
    big = t[t["delta_a_km"] < dsma * 2]
    assert len(big) == 1
    assert big["burn_class"].iloc[0] == C.ROUTINE_EW
    assert big["confidence"].iloc[0] == "medium"
    assert "T2 size: fail" in big["tests"].iloc[0] and "T1 interval: pass" in big["tests"].iloc[0]


def test_wrong_way_burn_is_off_pattern_and_late_burn_is_off_cycle_timing():
    plan, period, dsma = sawtooth(131.5, 9)
    wrong = list(plan)
    wrong[6] = (wrong[6][0], -dsma)                      # raises the orbit while it is already drifting west
    t = run(make_history("NVS-01", 131.5, period * 9.5, wrong, drift0=0.0237))
    flipped = t[t["delta_a_km"] > 0]
    assert flipped["burn_class"].tolist() == [C.OFF_PATTERN] and flipped["counted"].all()

    late = list(plan)
    late[6] = (late[6][0] + 12.0, dsma)                  # right size and direction, 12 days late
    t = run(make_history("NVS-01", 131.5, period * 9.5 + 12, late, drift0=0.0237))
    timing = t[t["burn_class"] == C.OFF_CYCLE]
    assert len(timing) >= 1 and not timing["counted"].any()


def test_wilson_interval():
    low, high = C.wilson(0, 10)
    assert low == 0.0 and high == pytest.approx(0.2775, abs=1e-3)
    low, high = C.wilson(5, 10)
    assert (low, high) == pytest.approx((0.2366, 0.7634), abs=1e-3)
    assert all(np.isnan(C.wilson(0, 0)))


def test_summary_counts_and_too_few_to_rate():
    history, plan, period = routine_history("NVS-01", 131.5, 12)
    t = run(history)
    by_sat, overall = C.summarise(t, START + pd.Timedelta(days=400))
    assert overall["decided"] == int(t["counted"].sum()) >= S.MIN_DECIDED
    assert overall["irregular"] == 0 and overall["share"] == 0.0 and overall["rating"] == "rated"
    few, only = C.summarise(t.head(5), START + pd.Timedelta(days=400))
    assert only["rating"] == "too few to rate"


# ---- the bundled data (tests/fixtures/bundled_data, ending 4 Oct 2026) -------------------------------------------

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)


@cache
def real(constellation):
    return assess_constellation(constellation, NOW)


def test_one_list_of_burns():
    """burns() is burns_detailed() less its extra columns, and the class table is the same burns."""
    result = real("NavIC")
    assert list(result["burns"].columns) == BURN_COLUMNS
    classes = result["burn_classes"]
    assert len(classes) == len(result["burns"])
    key = ["satellite", "kind", "window_end", "d_sma_km"]
    assert classes[key].sort_values(key).reset_index(drop=True).equals(result["burns"][key].sort_values(key).reset_index(drop=True))


def test_g1_april_pair_is_a_relocation():
    t = real("BeiDou-3")["burn_classes"]
    g1 = t[(t["satellite"] == "BeiDou-3 G1") & (t["kind"] == "east-west")]
    pair = g1[g1["delta_a_km"].abs() > 50]
    assert pair["delta_a_km"].round().tolist() == [-107, 107]
    assert (pair["burn_class"] == C.RELOCATION).all()
    assert pair["drift_after"].iloc[0] == pytest.approx(1.35, abs=0.05)
    assert (pair["when"].dt.month == 4).all()


def test_nvs01_2026_burns_are_routine_east_west():
    t = real("NavIC")["burn_classes"]
    nvs = t[(t["satellite"] == "NVS-01") & (t["when"] >= "2026-01-01")]
    assert len(nvs) >= 10
    assert (nvs["burn_class"] == C.ROUTINE_EW).all()
    assert (nvs["confidence"] == "high").all()
    assert nvs["delta_a_km"].between(-5, -1.8).all()
    assert nvs["days_since_prev"].dropna().between(14, 37).all()


def test_i3_inclination_pair_is_an_artefact():
    t = real("BeiDou-3")["burn_classes"]
    i3 = t[(t["satellite"] == "BeiDou-3 I3") & (t["delta_i_deg"].abs() > 0.1) & (t["when"] < "2026-03-01")]
    assert len(i3) >= 2
    assert (i3["burn_class"] == C.ARTEFACT).all()


def test_g2_north_south_burns_are_routine():
    t = real("BeiDou-3")["burn_classes"]
    g2 = t[(t["satellite"] == "BeiDou-3 G2") & (t["kind"] == "north-south")]
    assert g2["delta_i_deg"].round(2).tolist() == [-0.5, -0.45]
    assert (g2["burn_class"] == C.ROUTINE_NS).all()


def test_g1_july_cluster_is_a_response():
    t = real("BeiDou-3")["burn_classes"]
    july = t[(t["satellite"] == "BeiDou-3 G1") & (t["kind"] == "east-west") & (t["when"].dt.month == 7)]
    assert len(july) == 4 and (july["burn_class"] == C.RESPONSE).all()


def test_irnss_1d_is_end_of_life_and_nothing_unclassified():
    t = real("NavIC")["burn_classes"]
    assert (t.loc[t["satellite"] == "IRNSS-1D", "burn_class"] == C.DISPOSAL).all()
    assert t["burn_class"].isin(C.CLASSES).all() and t["confidence"].notna().all()
