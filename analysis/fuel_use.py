"""Fuel-use helpers for east-west and north-south station keeping."""

from __future__ import annotations

import math

from analysis.forecast_settings import (
    A_GEO_KM,
    FUEL_BUDGET_CONFIDENCE,
    FUEL_PRIOR_M_S_PER_YEAR,
    FUEL_PRIOR_RESERVE,
)

MU_KM3_S2 = 398600.4418
VC_GEO_KM_S = 3.0747


def _ew_dv_from_delta_a(delta_a_km, a_km):
    mean_motion_rad_s = math.sqrt(MU_KM3_S2 / (a_km ** 3))
    return abs((mean_motion_rad_s / 2.0) * delta_a_km * 1000.0)


def _ns_dv_from_delta_i(delta_i_deg):
    return VC_GEO_KM_S * abs(math.radians(delta_i_deg)) * 1000.0


def dv_from_burns(burns):
    """Sum total delta-v from mixed E-W and N-S burns.

    Burn entries:
      - E-W: {"type": "ew", "delta_a_km": ... , "a_km": optional}
      - N-S: {"type": "ns", "delta_i_deg": ...}
    """
    total = 0.0
    for burn in burns:
        kind = burn.get("type", "").lower()
        if kind == "ew":
            total += _ew_dv_from_delta_a(burn["delta_a_km"], burn.get("a_km", A_GEO_KM))
        elif kind == "ns":
            total += _ns_dv_from_delta_i(burn["delta_i_deg"])
    return total


def annual_rate(burns, days):
    """Scale observed burn usage to m/s per year."""
    if days <= 0:
        return 0.0
    return dv_from_burns(burns) * (365.25 / days)


def remaining_band(
    design_life_years,
    used_m_s,
    rate_m_s_per_year,
    prior=FUEL_PRIOR_M_S_PER_YEAR,
    reserve=FUEL_PRIOR_RESERVE,
):
    """Return conservative and optimistic years remaining under +/-35% budget uncertainty."""
    if rate_m_s_per_year <= 0:
        return (float("inf"), float("inf"), FUEL_BUDGET_CONFIDENCE)

    nominal_budget = design_life_years * prior * reserve
    low_budget = nominal_budget * 0.65
    high_budget = nominal_budget * 1.35

    low_years = max(0.0, (low_budget - used_m_s) / rate_m_s_per_year)
    high_years = max(0.0, (high_budget - used_m_s) / rate_m_s_per_year)
    return (low_years, high_years, FUEL_BUDGET_CONFIDENCE)
