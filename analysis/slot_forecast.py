"""Pure forecast functions for GEO/IGSO slot control and fuel timing."""

from __future__ import annotations

import math
from datetime import timedelta

from analysis.forecast_settings import (
    DRIFT_PER_KM,
    DRIFT_PER_MS,
    NS_DV_PER_DEG,
    PLANNING_LEAD_DAYS,
    STABLE_LON,
    TRIAX_K,
    igso_k_scale,
)

EPS = 1e-12


def longitude_acceleration(lon_deg, inclination_deg=0):
    """Longitude acceleration in deg/day^2 from triaxial GEO forcing."""
    angle_deg = 2.0 * (lon_deg - STABLE_LON)
    scale = igso_k_scale(inclination_deg)
    return -TRIAX_K * math.sin(math.radians(angle_deg)) * scale


def position(t, x0, v0, acc):
    """Position under constant acceleration."""
    return x0 + (v0 * t) + (0.5 * acc * t * t)


def time_to_edge(x0, v0, acc, half_width):
    """Smallest non-negative time to reach either box edge, else None."""
    if abs(x0) >= half_width:
        return 0.0

    candidates = []
    for target in (-half_width, half_width):
        c = x0 - target
        if abs(acc) <= EPS:
            if abs(v0) <= EPS:
                continue
            t = -c / v0
            if t >= 0:
                candidates.append(t)
            continue

        a_q = 0.5 * acc
        b_q = v0
        d = (b_q * b_q) - (4.0 * a_q * c)
        if d < 0:
            continue
        sqrt_d = math.sqrt(d)
        t1 = (-b_q - sqrt_d) / (2.0 * a_q)
        t2 = (-b_q + sqrt_d) / (2.0 * a_q)
        if t1 >= 0:
            candidates.append(t1)
        if t2 >= 0:
            candidates.append(t2)

    if not candidates:
        return None
    return min(candidates)


def routine_interval_days(drift_change, acc):
    """Return nominal station-keeping interval from drift change and acceleration."""
    if abs(acc) <= EPS:
        return None
    return abs(drift_change) / abs(acc)


def own_box_half_width(drift_change, acc):
    """Return own-box half-width implied by burn drift change and acceleration."""
    if abs(acc) <= EPS:
        return None
    return ((drift_change / 4.0) ** 2) / abs(acc)


def _sign(value):
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0


def _offset_date(today, days):
    if hasattr(today, "__add__"):
        return today + timedelta(days=float(days))
    return today


def time_to_outbound_edge(x0, v0, acc, half_width):
    """Smallest non-negative time at which the satellite is on an edge of the box and moving out through it, else None.

    Inside its box and heading to an edge, the pull may stop it there (it turns round at the edge, as a routine cycle
    does), so only a crossing with speed still outward counts."""
    found = []
    for target in (-half_width, half_width):
        c = x0 - target
        if abs(acc) <= EPS:
            roots = [] if abs(v0) <= EPS else [-c / v0]
        else:
            d = v0 * v0 - 2.0 * acc * c
            roots = [] if d < 0 else [(-v0 - math.sqrt(d)) / acc, (-v0 + math.sqrt(d)) / acc]
        found += [t for t in roots if t >= 0 and (v0 + acc * t) * target > 1e-9]
    return min(found) if found else None


def _turn_back(x, v, acc, own_half_width):
    """The signed drift change that sends a satellite at `x` drifting at `v` to stop at the edge of its own box on the
    side away from the pull (`acc`), so the pull itself stops it there: a speed w towards that edge, against the pull,
    with w² = 2·|acc|·distance. If that edge lies on the pull's side, w is 0: stopping it is enough, the pull brings it back."""
    target = -(_sign(acc) or 1.0) * own_half_width
    w_sq = -2.0 * acc * (target - x)
    if w_sq <= 0.0:   # beyond that edge: the pull already brings it back, so only drift away from the box is cancelled
        return 0.0 if v * acc > 0.0 else -v
    return -math.copysign(math.sqrt(w_sq), acc) - v


def _burn_row(kind, when, delta_lambda_dot, reason):
    # DRIFT_PER_KM is negative (a lower orbit drifts east): +0.0475 °/day of drift needs Δa ≈ -3.7 km
    delta_a_km = None if delta_lambda_dot is None else delta_lambda_dot / DRIFT_PER_KM
    delta_v_m_s = None if delta_lambda_dot is None else abs(delta_lambda_dot) / DRIFT_PER_MS
    return {
        "kind": kind,
        "date": when,
        "delta_lambda_dot_deg_per_day": delta_lambda_dot,
        "delta_a_km": delta_a_km,
        "delta_v_m_s": delta_v_m_s,
        "reason": reason,
    }


def forecast(x0, v0, acc, own_half_width, dashboard_half_width, today, dashboard_center=0.0):
    """Build ideal, last-chance, and too-late correction rows.

    x0 is measured from the centre of the satellite's own box (its station). The dashboard box is centred
    `dashboard_center` from there (its designated slot, when the station is not on it)."""
    rows = []

    # Ideal: burn as soon as own box is breached, else where it next leaves it.
    t_ideal = 0.0 if abs(x0) >= own_half_width else time_to_outbound_edge(x0, v0, acc, own_half_width)
    if t_ideal is None or abs(acc) <= EPS:
        rows.append(_burn_row("ideal", today, None, "No outward forcing; no ideal burn from this model."))
    else:
        x_ideal = position(t_ideal, x0, v0, acc)
        v_ideal = v0 + (acc * t_ideal)
        outward = _sign(v_ideal) or _sign(x_ideal) or _sign(acc) or 1.0
        delta_mag = 4.0 * math.sqrt(abs(acc) * own_half_width)
        delta = -outward * delta_mag
        rows.append(
            _burn_row(
                "ideal",
                _offset_date(today, t_ideal),
                delta,
                "Burn at own-box edge to target the far edge and restore routine cycle.",
            )
        )

    t_dashboard = time_to_edge(x0 - dashboard_center, v0, acc, dashboard_half_width)

    # Last chance: planning lead before dashboard edge, steer to opposite own edge.
    if t_dashboard is None or abs(acc) <= EPS:
        rows.append(
            _burn_row(
                "last_chance",
                today,
                None,
                "Trajectory does not naturally hit dashboard edge in this constant-acceleration model.",
            )
        )
    else:
        t_last = max(t_dashboard - PLANNING_LEAD_DAYS, 0.0)
        x_last = position(t_last, x0, v0, acc)
        v_last = v0 + (acc * t_last)
        delta = _turn_back(x_last, v_last, acc, own_half_width)
        desired_velocity = v_last + delta

        new_time_to_dashboard = time_to_edge(x_last - dashboard_center, desired_velocity, acc, dashboard_half_width)
        base_remaining = max(t_dashboard - t_last, 0.0)
        if new_time_to_dashboard is None:
            buys = None
            buys_note = "buys a bounded return inside this model horizon"
        else:
            buys = max(new_time_to_dashboard - base_remaining, 0.0)
            buys_note = f"buys {buys:.1f} days"

        rows.append(
            _burn_row(
                "last_chance",
                _offset_date(today, t_last),
                delta,
                f"Last lead-time turn-back burn ({buys_note}) before dashboard edge.",
            )
        )

    # Too late: once outside dashboard edge, re-entry needs larger change.
    if abs(acc) <= EPS:
        # No pull to bring it back: one burn cannot recover it (it takes a drift back and a later stop), so no row
        # value; heading back already needs nothing.
        delta_too_late = 0.0 if v0 * x0 < 0.0 else None
        t_too_late = 0.0
        x_too_late = x0
    else:
        if abs(x0 - dashboard_center) > dashboard_half_width:
            t_too_late = 0.0
            x_too_late = x0
            v_too_late = v0
        else:
            if t_dashboard is None:
                t_too_late = 0.0
            else:
                t_too_late = t_dashboard + PLANNING_LEAD_DAYS
            x_too_late = position(t_too_late, x0, v0, acc)
            v_too_late = v0 + (acc * t_too_late)
        delta_too_late = _turn_back(x_too_late, v_too_late, acc, own_half_width)

    rows.append(
        _burn_row(
            "too_late",
            _offset_date(today, t_too_late),
            delta_too_late,
            "No pull brings it back, so no single burn recovers it: a drift back and a later stop."
            if delta_too_late is None else
            "After dashboard exit, recovery burn rises quickly with both drift rate and distance.",
        )
    )
    return rows


def ns_forecast(inclination_now, target, tolerance, growth_deg_per_year, today):
    """Forecast N-S tolerance crossing and correction delta-v."""
    error_now = abs(inclination_now - target)
    if isinstance(growth_deg_per_year, (tuple, list)):
        growth_low, growth_high = float(growth_deg_per_year[0]), float(growth_deg_per_year[1])
        growth_mid = (growth_low + growth_high) / 2.0
    else:
        growth_low = growth_high = growth_mid = float(growth_deg_per_year)

    reach_days = 0.0
    if error_now < tolerance and growth_mid > EPS:
        reach_days = ((tolerance - error_now) / growth_mid) * 365.25

    delay_cost_mid = (NS_DV_PER_DEG * growth_mid) / 365.25
    delay_cost_band = ((NS_DV_PER_DEG * growth_low) / 365.25, (NS_DV_PER_DEG * growth_high) / 365.25)
    correction_delta_v = NS_DV_PER_DEG * max(tolerance, error_now)

    return {
        "reach_date": _offset_date(today, reach_days),
        "reach_days": reach_days,
        "correction_delta_v_m_s": correction_delta_v,
        "delay_cost_m_s_per_day": delay_cost_mid,
        "delay_cost_band_m_s_per_day": delay_cost_band,
    }


def meo_phase_correction(error_deg, days, a_km):
    """Delta-a and delta-v for closing MEO phase error over a chosen horizon."""
    mu = 398600.4418  # km^3/s^2
    mean_motion_rad_s = math.sqrt(mu / (a_km ** 3))
    mean_motion_deg_day = mean_motion_rad_s * 86400.0 * 180.0 / math.pi
    drift_per_km = -1.5 * mean_motion_deg_day / a_km
    delta_a_km = -error_deg / (drift_per_km * days)
    dv_per_burn_m_s = abs((mean_motion_rad_s / 2.0) * delta_a_km * 1000.0)
    total_dv_m_s = 2.0 * dv_per_burn_m_s

    return {
        "delta_a_km": delta_a_km,
        "delta_v_per_burn_m_s": dv_per_burn_m_s,
        "delta_v_total_m_s": total_dv_m_s,
    }
