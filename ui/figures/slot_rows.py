"""Plain rows for the orbit pictures, built from the dashboard's own columns.

A satellite is judged only against its OWN slot, never the nearest one: a satellite
that drifts onto another satellite's slot must not look fine. A row looks like

    {"name": str, "slot_lon": float or None, "actual_lon": float or None,
     "state": one of palette.SLOT_*, "deviation_deg": float or None, "note": str}

Longitudes are degrees east, negative for west. Nothing here reads a file or the clock.
"""
import math
from datetime import datetime, timezone

from skyfield.api import EarthSatellite, load, wgs84

from config.config import GEOSYNC_MEAN_MOTION
from ui import palette

LON_SCORE_IN_SLOT = 100  # the dashboard's own judgement: a full longitude score means in slot
SAME_SPOT_DEG = 1.5      # satellites closer than this share one label in the pictures

_TIMESCALE = load.timescale()


def as_number(value):
    """A float, or None for None, NaN, 'N/A' and anything else that is not a number."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def angle_between(first, second):
    """Shortest distance in degrees between two longitudes, or None if either is missing."""
    if first is None or second is None:
        return None
    return abs((first - second + 180) % 360 - 180)


def _state(score, actual_lon):
    if score is None or actual_lon is None:
        return palette.SLOT_UNKNOWN
    return palette.SLOT_IN if score >= LON_SCORE_IN_SLOT else palette.SLOT_OFF


def slot_rows(health_rows, set_aside=()):
    """Satellite rows from the dashboard's health rows, plus satellites set aside.

    A longitude score of 100 means in slot, a lower score means off its slot, and a
    slot with no current longitude means position not known. Rows with no slot are
    left out. Each set-aside item ({name, slot_lon, actual_lon, note}) has left the belt.
    """
    rows = []
    for health in health_rows:
        slot = as_number(health.get("Designated Lon (°)"))
        if slot is None:
            continue
        actual = as_number(health.get("Current Mean Lon (°)"))
        deviation = as_number(health.get("Lon Slot Deviation (°)"))
        rows.append({
            "name": str(health["Satellite"]),
            "slot_lon": slot,
            "actual_lon": actual,
            "state": _state(as_number(health.get("Lon Deviation Score")), actual),
            "deviation_deg": None if deviation is None else abs(deviation),
            "note": "",
        })
    for gone in set_aside:
        slot, actual = as_number(gone.get("slot_lon")), as_number(gone.get("actual_lon"))
        rows.append({
            "name": str(gone["name"]),
            "slot_lon": slot,
            "actual_lon": actual,
            "state": palette.SLOT_LEFT,
            "deviation_deg": angle_between(slot, actual),
            "note": str(gone.get("note", "")),
        })
    return rows


def empty_slots(rows):
    """Slots to draw as empty: one per row that has a slot but is not on it.

    Even if another satellite happens to sit on the spot, the slot is empty because
    its own satellite is not there.
    """
    return [{"slot_lon": row["slot_lon"], "owner": row["name"]}
            for row in rows if row["slot_lon"] is not None and row["state"] != palette.SLOT_IN]


def deviation_of(row):
    """Degrees from the satellite's own slot: the row's figure, else worked out from the longitudes."""
    if row["deviation_deg"] is not None:
        return row["deviation_deg"]
    return angle_between(row["slot_lon"], row["actual_lon"])


def state_words(row):
    """One plain sentence about a satellite: its state in words, so colour is never the only signal."""
    deviation = deviation_of(row)
    text = f"{row['name']}: {row['state']}"
    if row["state"] == palette.SLOT_UNKNOWN:
        text += ", no current longitude"
    elif deviation is not None:
        text += f", {deviation:.2f} degrees from its own slot"
    return f"{text}. {row['note']}" if row["note"] else text


def group_by_position(rows, max_gap=SAME_SPOT_DEG):
    """Rows with a known position, grouped when neighbours are within max_gap degrees.

    Used to merge labels that would sit on top of each other. Groups run west to east.
    """
    placed = sorted((row for row in rows if row["actual_lon"] is not None), key=lambda r: r["actual_lon"])
    groups = []
    for row in placed:
        if groups and row["actual_lon"] - groups[-1][-1]["actual_lon"] <= max_gap:
            groups[-1].append(row)
        else:
            groups.append([row])
    return groups


def last_known_position(records):
    """Where a satellite last was, from its newest orbit record, or None without records.

    Returns {date, lon, altitude_km, drift_deg_per_day}. The position is the point under
    the satellite at the element set's own epoch. Drift is how far the satellite slides
    each day against a perfect geostationary orbit, west positive.
    """
    if not records:
        return None
    newest = max(records, key=lambda record: record["EPOCH"])
    satellite = EarthSatellite(newest["TLE_LINE1"], newest["TLE_LINE2"], ts=_TIMESCALE)
    point = wgs84.subpoint(satellite.at(satellite.epoch))
    epoch = datetime.fromisoformat(newest["EPOCH"]).replace(tzinfo=timezone.utc)
    return {
        "date": epoch.strftime("%Y-%m-%d"),
        "lon": float(point.longitude.degrees),
        "altitude_km": float(point.elevation.km),
        "drift_deg_per_day": (GEOSYNC_MEAN_MOTION - float(newest["MEAN_MOTION"])) * 360,
    }
