"""What each detected burn happened to, read from the satellite's own orbit records (no score, no page).

Input is the burns table of analysis/bundled_run.burns_detailed and the bundled history frame
(analysis/bundled_run.load_bundled_gp_as_dataframes). Output is the same table with the context a classifier
(analysis/burn_classes.py) needs: the persistent change in semi-major axis and inclination, the drift, inclination,
eccentricity and altitude either side, where the satellite stood against its slot just before, and how long since its
own previous burn.

Mean longitude comes from the elements, lambda = RAAN + argument of perigee + mean anomaly - GMST(epoch); for a tilted
orbit that is the centre of its figure-eight. Longitudes are in degrees east.
"""
import numpy as np
import pandas as pd

from analysis import burn_class_settings as S
from analysis import score_rules
from config.config import (
    BEIDOU3_SERVICE_REQUIREMENTS, NAVIK_SERVICE_REQUIREMENTS, QZSS_SERVICE_REQUIREMENTS, R_EARTH,
)

_J2000 = pd.Timestamp("2000-01-01 12:00:00")


def designated_longitude(name):
    """The longitude of a satellite's own slot in degrees east, or None. As ui/orbit_section.designated_longitude, which
    cannot be imported here: it pulls in the whole page."""
    if name in NAVIK_SERVICE_REQUIREMENTS:
        return NAVIK_SERVICE_REQUIREMENTS[name]["longitude"]
    for requirements in (QZSS_SERVICE_REQUIREMENTS, BEIDOU3_SERVICE_REQUIREMENTS):
        if name in requirements:
            return requirements[name]["central_longitude_deg"]
    return None


def gmst_deg(epoch):
    """Greenwich mean sidereal time in degrees at UTC epochs (array of datetime64); the IAU 1982 series to its T^2 term
    (UT1 taken as UTC: a second is 0.004 degrees)."""
    days = ((pd.to_datetime(pd.Series(epoch)) - _J2000).dt.total_seconds() / 86400.0).to_numpy()
    t = days / 36525.0
    return (280.46061837 + 360.98564736629 * days + 0.000387933 * t * t) % 360.0


def wrap180(x):
    """Degrees wrapped to [-180, 180)."""
    return (np.asarray(x, dtype=float) + 180.0) % 360.0 - 180.0


def longitude_series(sat):
    """Mean longitude east of each record of one satellite's history frame, in degrees, vectorised."""
    raan, argp, anomaly = (pd.to_numeric(sat[c], errors="coerce").to_numpy(float)
                           for c in ("RA_OF_ASC_NODE", "ARG_OF_PERICENTER", "MEAN_ANOMALY"))
    return (raan + argp + anomaly - gmst_deg(sat["EPOCH"])) % 360.0


def _median(values):
    values = values[np.isfinite(values)]
    return float(np.median(values)) if len(values) else np.nan


def _around(epoch_ns, t0, t1, column, days_before, days_after):
    """Medians of `column` over the records in the days_before up to and including t0, and from t1 for days_after (the record at t0 == t1 on neither side)."""
    lo = np.searchsorted(epoch_ns, t0 - days_before * 86400e9, side="right")
    same = t0 == t1     # a zero-length window sits on one record: it belongs to neither side
    mid = np.searchsorted(epoch_ns, t0, side="left" if same else "right")
    hi = np.searchsorted(epoch_ns, t1 + days_after * 86400e9, side="right")
    first = np.searchsorted(epoch_ns, t1, side="right" if same else "left")
    return _median(column[lo:mid]), _median(column[first:hi])


def add_context(burns, history, constellation):
    """`burns` with context columns added (the table is not changed; rows keep their order).

    Added: when (middle of the window), delta_a_km and delta_i_deg (persistent, signed: after minus before), drift_before
    and drift_after in degrees a day, delta_drift, slot_lon, pos_before (degrees from its slot, east positive, NaN
    without a slot) and pos_later (the same, LATER_FROM_DAYS to LATER_TO_DAYS after the burn), inc_before, inc_after,
    ecc_before, ecc_after, alt_before_km, alt_after_km, orbit_type, days_since_prev (since the previous burn of the same kind by the same satellite in `burns`, NaN for the first).
    """
    out = burns.copy()
    cols = ["when", "delta_a_km", "delta_i_deg", "drift_before", "drift_after", "delta_drift", "slot_lon", "pos_before",
            "pos_later", "inc_before", "inc_after", "ecc_before", "ecc_after", "alt_before_km", "alt_after_km",
            "orbit_type", "days_since_prev"]
    for c in cols:
        out[c] = np.nan
    out["orbit_type"] = ""
    out["when"] = out["window_start"] + (out["window_end"] - out["window_start"]) / 2

    for name, group in out.groupby("satellite"):
        sat = history[history["satellite"] == name].sort_values("EPOCH").reset_index(drop=True)
        if sat.empty:
            continue
        epoch_ns = pd.to_datetime(sat["EPOCH"]).to_numpy("datetime64[ns]").astype("int64")
        slot = designated_longitude(name)
        series = {c: pd.to_numeric(sat[c], errors="coerce").to_numpy(float)
                  for c in ("LonDrift_deg_per_day", "INCLINATION", "ECCENTRICITY", "SEMIMAJOR_AXIS")}
        series["pos"] = wrap180(longitude_series(sat) - slot) if slot is not None else np.full(len(sat), np.nan)
        for i in group.index:
            t0 = int(pd.Timestamp(out.at[i, "window_start"]).value)
            t1 = int(pd.Timestamp(out.at[i, "window_end"]).value)
            drift = _around(epoch_ns, t0, t1, series["LonDrift_deg_per_day"], S.BEFORE_DAYS, S.AFTER_DAYS)
            incl = _around(epoch_ns, t0, t1, series["INCLINATION"], S.BEFORE_DAYS, S.AFTER_DAYS)
            ecc = _around(epoch_ns, t0, t1, series["ECCENTRICITY"], S.BEFORE_DAYS, S.AFTER_DAYS)
            sma = _around(epoch_ns, t0, t1, series["SEMIMAJOR_AXIS"], S.BEFORE_DAYS, S.AFTER_DAYS)
            pos = _around(epoch_ns, t0, t1, series["pos"], S.BEFORE_DAYS, S.AFTER_DAYS)
            da = out.at[i, "post_sma_med"] - out.at[i, "pre_sma_med"]
            di = out.at[i, "post_inc_med"] - out.at[i, "pre_inc_med"]
            out.at[i, "delta_a_km"] = da if np.isfinite(da) else out.at[i, "d_sma_km"]
            out.at[i, "delta_i_deg"] = di if np.isfinite(di) else out.at[i, "d_inc_deg"]
            out.at[i, "drift_before"], out.at[i, "drift_after"] = drift
            out.at[i, "delta_drift"] = drift[1] - drift[0]
            out.at[i, "slot_lon"] = np.nan if slot is None else slot
            out.at[i, "pos_before"] = pos[0]
            out.at[i, "pos_later"] = _median(series["pos"][np.searchsorted(epoch_ns, t1 + S.LATER_FROM_DAYS * 86400e9):
                                                           np.searchsorted(epoch_ns, t1 + S.LATER_TO_DAYS * 86400e9)])
            out.at[i, "inc_before"], out.at[i, "inc_after"] = incl
            out.at[i, "ecc_before"], out.at[i, "ecc_after"] = ecc
            out.at[i, "alt_before_km"], out.at[i, "alt_after_km"] = sma[0] - R_EARTH, sma[1] - R_EARTH
            out.at[i, "orbit_type"] = score_rules.orbit_type(
                incl[0] if np.isfinite(incl[0]) else incl[1], "QZSS" if constellation == "QZSS" else constellation)

    out = out.sort_values(["satellite", "kind", "when"]).copy()
    out["days_since_prev"] = out.groupby(["satellite", "kind"])["when"].diff().dt.total_seconds() / 86400
    return out.sort_index()


def position_records(history, name):
    """(epoch_ns, position, drift) of one satellite's records, position in degrees from its slot (as pos_before)."""
    sat = history[history["satellite"] == name].sort_values("EPOCH").reset_index(drop=True)
    slot = designated_longitude(name)
    pos = wrap180(longitude_series(sat) - slot) if slot is not None else np.full(len(sat), np.nan)
    epoch = pd.to_datetime(sat["EPOCH"]).to_numpy("datetime64[ns]").astype("int64")
    return epoch, pos, pd.to_numeric(sat["LonDrift_deg_per_day"], errors="coerce").to_numpy(float)
