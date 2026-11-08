"""A new satellite on its way to its slot is moving there on purpose, not failing.

A geosynchronous satellite is launched into a transfer orbit, raised over days, then drifted along the belt to its slot
and parked. Until it parks, its orbit records show what the health scores read as faults: a fast longitude drift, a
burn every day, an inclination that has not settled. Scored like a working satellite it shows "critical, drifting
away" when it is doing exactly what its operator planned.

Nothing here is kept by hand. A satellite is on its way when it is new (its first orbit record is lately) and its
newest record is still in a transfer orbit or still drifting. Once its records stay settled, the first settled record
is the day it was commissioned: the scores read from there, so the burns that raised it are not counted as station-keeping.
For SETTLING_DAYS after that day it is still left out: days of settled records cannot show a station-keeping cadence,
and its drift and burn history are still mostly the move (QZS-7, parked 3 Nov 2026, read as critical).
A satellite that is still not settled after COMMISSIONING_DAYS is scored like any other, so a stranded one does not
hide behind this: it never parks, so it never settles.
"""
import pandas as pd

COMMISSIONING_DAYS = 90            # how long after its first record a satellite may be on its way
SETTLING_DAYS = 30                 # our choice: about one station-keeping cycle of settled records before it is scored
SETTLED_DRIFT_DEG_PER_DAY = 0.25   # a parked satellite drifts less than this along the belt
TRANSFER_ECCENTRICITY = 0.2        # a transfer orbit is far more eccentric than any working geosynchronous one (QZSS stays under 0.1)
GEOSYNCHRONOUS_MOTION = (0.8, 1.3)  # revolutions a day: a medium Earth orbit satellite (1.7 to 2.1) is never judged by this


def under_way(row):
    """Whether one orbit record is of a satellite still on its way to a geosynchronous slot."""
    eccentricity, motion = float(row["ECCENTRICITY"]), float(row["MEAN_MOTION"])
    if eccentricity > TRANSFER_ECCENTRICITY:
        return True
    low, high = GEOSYNCHRONOUS_MOTION
    return low < motion < high and abs(float(row["LonDrift_deg_per_day"])) > SETTLED_DRIFT_DEG_PER_DAY


def _records(history, name):
    sat = history[history["satellite"] == name].sort_values("EPOCH")
    for column in ("ECCENTRICITY", "MEAN_MOTION", "LonDrift_deg_per_day"):
        sat = sat.assign(**{column: pd.to_numeric(sat[column], errors="coerce")})
    return sat.dropna(subset=["ECCENTRICITY", "MEAN_MOTION", "LonDrift_deg_per_day"])


def moving_to_slot(history, now):
    """{satellite: its first orbit record} for each one on its way, or parked less than SETTLING_DAYS ago, from the whole
    bundled history. `now` is timezone-aware."""
    moving, today = {}, pd.Timestamp(now).tz_localize(None)
    for name in history["satellite"].unique():
        sat = _records(history, name)
        if sat.empty:
            continue
        first = sat["EPOCH"].iloc[0]
        if under_way(sat.iloc[-1]):
            if today - first <= pd.Timedelta(days=COMMISSIONING_DAYS):
                moving[name] = first
        elif (parked := commissioned_on(history, name)) is not None and today - parked < pd.Timedelta(days=SETTLING_DAYS):
            moving[name] = first
    return moving


def commissioned_on(history, name):
    """The first orbit record after the last one on its way, for a satellite seen on its way and now parked; else None.

    A satellite whose records start settled (it was parked before the history begins) has no date: nothing is skipped.
    """
    sat = _records(history, name)
    if sat.empty or not under_way(sat.iloc[0]) or under_way(sat.iloc[-1]):
        return None
    flags = [under_way(row) for _, row in sat.iterrows()]
    last_moving = max(i for i, moving in enumerate(flags) if moving)
    return sat["EPOCH"].iloc[last_moving + 1]
