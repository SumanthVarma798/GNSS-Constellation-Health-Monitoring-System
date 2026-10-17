"""Each satellite's measures as "is" next to "should be", for the tables on Overview and Station-keeping.

Everything is read from assess_constellation's result and the settings: nothing here works out a score.
A cell is {"now", "should", "status", "note"}; status is a surfaces status, and the words always say it too.
No Streamlit and no clock: the caller passes `today`.
"""
from collections import Counter

import pandas as pd

from config.config import (BEIDOU3_SERVICE_REQUIREMENTS, DEFAULT_PARAMS, NAVIK_SERVICE_REQUIREMENTS,
                           QZSS_SERVICE_REQUIREMENTS)
from ui import limits
from ui.figures.burns import EAST_WEST, NORTH_SOUTH
from ui.figures.slot_rows import as_number

# (heading, one plain line) for each column of the Overview table, after the satellite's name.
COLUMNS = [
    ("Drift per day", "How fast it slides east or west"),
    ("Inclination", "Tilt of the orbit against the equator"),
    ("Longitude", "Where it sits, against its own slot"),
    ("Eccentricity", "How far the orbit is from a circle"),
    ("Height", "Above the equator"),
    ("Upkeep", "Burns over the year scored"),
]
# The Station-keeping table's columns: burns in the window, then the year the score reads.
BURN_COLUMNS = [
    ("East-west", "Burns that hold the longitude"),
    ("North-south", "Burns that hold the tilt"),
    ("Days observed", "In the window"),
    ("East-west pattern", "Over the year scored"),
    ("North-south pattern", "Over the year scored"),
]


def cell(now, should="", status="idle", note=""):
    return {"now": now, "should": should, "status": status, "note": note}


def requirement(name):
    """The service requirements the config holds for a satellite, or {}."""
    for table in (NAVIK_SERVICE_REQUIREMENTS, QZSS_SERVICE_REQUIREMENTS, BEIDOU3_SERVICE_REQUIREMENTS):
        if name in table:
            return table[name]
    return {}


def thresholds(constellation, params):
    """The thresholds assess_constellation used: the defaults with the gear's changes."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    if constellation == "QZSS" and "inclination_tolerance" not in (params or {}):
        p["inclination_tolerance"] = limits.QZSS_INCLINATION_TOLERANCE
    return p


def in_window(history, window_days, today):
    """The history rows in the window, as assess_constellation takes it: from `window_days` before today to its end."""
    start = pd.Timestamp(today) - pd.Timedelta(days=window_days)
    epoch = pd.to_datetime(history["EPOCH"])
    return history[(epoch >= start) & (epoch <= pd.Timestamp(today) + pd.Timedelta(days=1))]


def orbit_type(tilt, constellation):
    """GEO under 10 degrees of tilt, else QZO for QZSS and IGSO otherwise: the health assessment's rule."""
    if tilt is None:
        return "Unclassified"
    if tilt < limits.TILT_GEO_BELOW:
        return "GEO"
    return "QZO" if constellation == "QZSS" else "IGSO"


def grouped(types):
    """{orbit type: [satellite, ...]} for {satellite: type}, the known types first in ORBIT_TYPES order."""
    order = list(limits.ORBIT_TYPES)
    groups = {}
    for name, kind in types.items():
        groups.setdefault(kind, []).append(name)
    return dict(sorted(groups.items(), key=lambda g: (order.index(g[0]) if g[0] in order else len(order), g[0])))


def newest(history, name, column):
    """The satellite's newest value of `column` in the history, or None."""
    own = history[history["satellite"] == name]
    if own.empty or column not in own.columns:
        return None
    return as_number(own.loc[pd.to_datetime(own["EPOCH"]).idxmax(), column])


def _lon(lon):
    return f"{abs(lon):.2f}°{'E' if lon >= 0 else 'W'}"


def _outside(should, within):
    return should if within else should + " · outside"


def drift(health, p, spread=None):
    now = as_number(health.get("Current Drift (°/day)"))
    allowed = p["drift_tolerance_gso"] if health.get("Type") == "GEO" else limits.DRIFT_ALLOWED_TILTED
    note = "" if spread is None else f"±{spread:.4f} spread"
    if now is None:
        return cell("not known", f"allowed ±{allowed:g}°/day", note=note)
    way = " east" if now > 0 else " west" if now < 0 else ""
    within = abs(now) <= allowed
    return cell(f"{now:+.4f}°{way}", _outside(f"allowed ±{allowed:g}°/day", within), "ok" if within else "warn", note)


def inclination(health, need, p):
    """Against the band when the requirements give one, else the target plus or minus the tolerance (as the score)."""
    now, off = as_number(health.get("Incl. (°)")), as_number(health.get("Incl. Dev. (°)"))
    tol = p["inclination_tolerance"]
    if "inclination" not in need and "inclination_target_deg_range" in need:
        low, high = need["inclination_target_deg_range"]
        should, within = (f"under {high:g}°" if low <= 0 else f"{low:g} to {high:g}°"), off == 0
    else:
        target = as_number(health.get("Target Incl. (°)"))
        if target is None:
            return cell("not known" if now is None else f"{now:.2f}°", "no target set")
        should, within = f"{target:g}° ±{tol:g}°", off is not None and off <= tol
    if now is None:
        return cell("not known", should)
    return cell(f"{now:.2f}°", _outside(should, within), "ok" if within else "warn")


def longitude(health):
    slot, now = as_number(health.get("Designated Lon (°)")), as_number(health.get("Current Mean Lon (°)"))
    if slot is None:
        return cell("not known" if now is None else _lon(now), "no slot set")
    allowed = limits.SLOT_ALLOWED.get(health.get("Type"), limits.SLOT_ALLOWED_TILTED)
    should = f"slot {_lon(slot)} ±{allowed:g}°"
    if now is None:
        return cell("not known", should, note="scored without this part")
    off = as_number(health.get("Lon Slot Deviation (°)"))
    within = as_number(health.get("Lon Deviation Score")) == 100
    return cell(_lon(now), _outside(should, within), "ok" if within else "warn", f"{off:+.2f}° from its slot")


def eccentricity(now, need):
    limit = need.get("ecc_max")
    if now is None:
        return cell("not known", "" if limit is None else f"under {limit:g}")
    if limit is None:
        return cell(f"{now:.5f}", "no limit set")
    within = now < limit
    return cell(f"{now:.5f}", _outside(f"under {limit:g}", within), "ok" if within else "warn")


def height(health):
    now = as_number(health.get("Altitude (km)"))
    should = f"{limits.NOMINAL_HEIGHT_KM:,.0f} nominal"
    if now is None:
        return cell("not known", should)
    gone = now >= limits.SET_ASIDE_HEIGHT_KM
    return cell(f"{now:,.1f} km", should + (" · graveyard height" if gone else ""), "bad" if gone else "idle")


def upkeep(health):
    """The rhythm the upkeep part reads: a burn expected every N days, the last one M days ago."""
    every, since = as_number(health.get("Expected Interval (days)")), as_number(health.get("Days Since Last"))
    score = as_number(health.get("_maintenance_score"))
    status = "idle" if score is None else "ok" if score >= 80 else "warn" if score >= 60 else "bad"
    counts = f"{health.get('EW Maneuvers', 0)} east-west, {health.get('NS Maneuvers', 0)} north-south"
    return cell("no burns" if since is None else f"{since:.0f} d ago", _every(every, since), status, counts)


def _every(every, since):
    """'every 48 d, overdue after 72', 'every 48 d · overdue since day 72' once that has passed, or 'no pattern yet'."""
    if every is None:
        return "no pattern yet"
    due = every * limits.OVERDUE_AFTER
    return f"every {every:.0f} d · overdue since day {due:.0f}" if since is not None and since > due \
        else f"every {every:.0f} d, overdue after {due:.0f}"


def row(health, constellation, params, history, spread=None):
    """The Overview table's cells for one health row, in COLUMNS order."""
    name, p = str(health["Satellite"]), thresholds(constellation, params)
    need = requirement(name)
    return [drift(health, p, spread), inclination(health, need, p), longitude(health),
            eccentricity(newest(history, name, "ECCENTRICITY"), need), height(health), upkeep(health)]


def spreads(window_history):
    """{satellite: standard deviation of its longitude drift in the window}."""
    if "LonDrift_deg_per_day" not in window_history.columns:
        return {}
    return {name: as_number(s) for name, s in window_history.groupby("satellite")["LonDrift_deg_per_day"].std().items()}


def status_counts(health_df):
    """[(status word, count), ...] in STATUS_FROM order, from the scores."""
    scores = [as_number(s) for s in health_df["Overall Score"]] if len(health_df) else []
    words = Counter(next(word for word, low in limits.STATUS_FROM if s >= low) for s in scores if s is not None)
    return [(word, words[word]) for word, _ in limits.STATUS_FROM]


def classified(window_history, constellation):
    """One row per satellite in the window: mean tilt, mean height and newest drift, and the type they give."""
    out = []
    for name, own in window_history.sort_values("EPOCH").groupby("satellite", sort=True):
        tilt = as_number(own["INCLINATION"].mean())
        out.append({"satellite": name, "tilt": tilt, "height": as_number(own["altitude_km"].mean()),
                    "drift": as_number(own["LonDrift_deg_per_day"].iloc[-1]) if "LonDrift_deg_per_day" in own else None,
                    "type": orbit_type(tilt, constellation)})
    return out


def _pattern(health, kind):
    every = as_number(health.get(f"{kind} Expected Interval (days)"))
    since = as_number(health.get(f"{kind} Days Since Last"))
    sure = str(health.get(f"{kind} Pattern Confidence") or "None")
    if since is None:
        return cell("no burns", "no pattern yet")
    if every is None:
        return cell(f"{since:.0f} d ago", "no pattern yet")
    late = since > every * limits.OVERDUE_AFTER
    return cell(f"{since:.0f} d ago", _every(every, since), "warn" if late else "ok", f"confidence {sure.lower()}")


def burn_row(name, burns_in_window, days_observed, health):
    """The Station-keeping table's cells for one satellite, in BURN_COLUMNS order. health may be None (set aside)."""
    own = burns_in_window[burns_in_window["satellite"] == name]
    counts = [cell(str(int((own["kind"] == kind).sum()))) for kind in (EAST_WEST, NORTH_SOUTH)]
    seen = cell("–" if days_observed is None else str(days_observed))
    if health is None:
        return counts + [seen, cell("set aside"), cell("set aside")]
    return counts + [seen, _pattern(health, "EW"), _pattern(health, "NS")]
