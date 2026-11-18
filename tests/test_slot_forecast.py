"""Numerical checks for slot-forecast and fuel-use pure functions."""

from __future__ import annotations

import math
from datetime import date

import pytest

from analysis.forecast_settings import (
    A_GEO_KM,
    DRIFT_PER_KM,
    DRIFT_PER_MS,
    FUEL_PRIOR_M_S_PER_YEAR,
    FUEL_PRIOR_RESERVE,
    NS_DV_PER_DEG,
)
from analysis.fuel_use import remaining_band
from analysis.slot_forecast import (
    forecast,
    longitude_acceleration,
    meo_phase_correction,
    ns_forecast,
    own_box_half_width,
    routine_interval_days,
    time_to_edge,
)


def _derived_triax_k_deg_per_day2():
    """Derive the longitude-acceleration amplitude from J22 and lambda22 model."""
    mu = 398600.4418  # km^3/s^2
    re = 6378.137  # km
    r = 42164.0  # km
    j22 = 1.8157e-6
    # |lambda_ddot| amplitude = 18 * mu * Re^2 * J22 / r^5 in rad/s^2.
    amp_rad_s2 = 18.0 * mu * (re**2) * j22 / (r**5)
    return amp_rad_s2 * (180.0 / math.pi) * (86400.0**2)


def _row_by_kind(rows, kind):
    return next(row for row in rows if row["kind"] == kind)


def test_triax_k_derivation_matches_0p0017_within_five_percent():
    assert _derived_triax_k_deg_per_day2() == pytest.approx(0.0017, rel=0.05)


def test_nvs01_drift_burn_interval_and_own_box():
    acc = longitude_acceleration(131.5)
    assert acc == pytest.approx(-0.00157, rel=0.05)

    drift_change = DRIFT_PER_KM * -3.7
    assert drift_change == pytest.approx(0.0475, rel=0.02)
    assert abs(drift_change) / DRIFT_PER_MS == pytest.approx(0.135, rel=0.03)

    interval_days = routine_interval_days(drift_change, acc)
    assert interval_days == pytest.approx(30.0, rel=0.15)

    own_half = own_box_half_width(drift_change, acc)
    assert own_half == pytest.approx(0.09, rel=0.15)


def test_nvs01_worked_forecast_ideal_last_chance_and_too_late():
    today = date(2026, 1, 1)
    acc = longitude_acceleration(131.5)
    drift_change = DRIFT_PER_KM * -3.7
    own_half = own_box_half_width(drift_change, acc)

    # Start at own-box crossing with outward drift.
    x0 = -own_half
    v0 = -(drift_change / 2.0)
    rows = forecast(x0, v0, acc, own_half, 0.5, today)

    ideal = _row_by_kind(rows, "ideal")
    assert ideal["delta_v_m_s"] == pytest.approx(0.135, rel=0.10)

    dash_cross_days = time_to_edge(x0, v0, acc, 0.5)
    assert dash_cross_days == pytest.approx(12.3, rel=0.10)

    last_chance = _row_by_kind(rows, "last_chance")
    assert last_chance["delta_v_m_s"] == pytest.approx(0.235, rel=0.10)

    too_late_rows = forecast(-1.51, -0.071, acc, own_half, 0.5, today)
    too_late = _row_by_kind(too_late_rows, "too_late")
    assert too_late["delta_v_m_s"] == pytest.approx(0.40, rel=0.10)


def test_beidou3_g4_example_interval():
    acc = longitude_acceleration(140.0)
    assert acc == pytest.approx(-0.0013, rel=0.10)

    drift_change = DRIFT_PER_KM * -2.7
    interval_days = routine_interval_days(drift_change, acc)
    assert interval_days == pytest.approx(26.5, rel=0.15)


def test_behavior_near_stable_point_and_edges():
    assert longitude_acceleration(80.0) == pytest.approx(-0.0003, rel=0.20)
    assert time_to_edge(0.6, -0.01, -0.001, 0.5) == 0.0
    assert time_to_edge(0.0, 0.1, 0.0, 0.5) == pytest.approx(5.0, rel=1e-6)
    assert time_to_edge(0.0, 0.0, 0.0, 0.5) is None

    scale_ratio = longitude_acceleration(131.5, 55.0) / longitude_acceleration(131.5, 0.0)
    assert scale_ratio == pytest.approx(0.62, rel=0.05)


def test_ns_station_keeping_numbers():
    assert NS_DV_PER_DEG == pytest.approx(53.7, rel=1e-6)
    ns = ns_forecast(0.1, 0.0, 0.5, 0.85, date(2026, 1, 1))
    assert ns["delay_cost_m_s_per_day"] == pytest.approx(0.12, rel=0.10)


def test_meo_phase_example_from_spec():
    correction = meo_phase_correction(error_deg=2.0, days=30.0, a_km=26560.0)
    assert correction["delta_a_km"] == pytest.approx(1.64, rel=0.10)
    assert correction["delta_v_total_m_s"] == pytest.approx(0.24, rel=0.10)


def test_fuel_band_has_label_and_uncertainty_spread():
    low, high, label = remaining_band(design_life_years=15, used_m_s=120, rate_m_s_per_year=40)
    assert "typical for this class of satellite" in label
    assert high > low

    nominal_budget = 15 * FUEL_PRIOR_M_S_PER_YEAR * FUEL_PRIOR_RESERVE
    nominal_years = max(0.0, (nominal_budget - 120) / 40.0)
    assert low < nominal_years < high
