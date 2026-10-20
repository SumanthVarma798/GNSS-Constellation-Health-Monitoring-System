"""The Geometry page's numbers, worked out with the existing analysis functions (analysis/dop_calculations.py,
analysis/raan_analysis.py). Nothing here draws, and nothing reads the clock: the caller passes the time.

Satellites are placed from each one's newest element set in the history (bundled data plus any fresh rows),
the same rows the other pages use.
"""
import re
from datetime import timedelta, timezone

import numpy as np
import pandas as pd
from skyfield.api import EarthSatellite, load, wgs84

from analysis.dop_calculations import calculate_dop_for_location
from analysis.raan_analysis import _circular_mean_deg
from config.config import (BEIDOU3_SERVICE_REQUIREMENTS, DEFAULT_PARAMS, NAVIK_SERVICE_REQUIREMENTS, R_EARTH,
                           QZSS_SERVICE_REQUIREMENTS)
from ui import geometry_settings as gs

REQUIREMENTS = {"NavIC": NAVIK_SERVICE_REQUIREMENTS, "QZSS": QZSS_SERVICE_REQUIREMENTS,
                "BeiDou-3": BEIDOU3_SERVICE_REQUIREMENTS}
DOP_KEYS = [key for key, _, _ in gs.DOP_MEASURES]
_ts = load.timescale()


def satellites_from_history(history, names):
    """{name: EarthSatellite} from each named satellite's newest element set that has its two lines."""
    rows = history[history["satellite"].isin(names)].dropna(subset=["TLE_LINE1", "TLE_LINE2"])
    newest = rows.loc[rows.groupby("satellite")["EPOCH"].idxmax()]
    return {row.satellite: EarthSatellite(row.TLE_LINE1, row.TLE_LINE2, row.satellite, _ts)
            for row in newest.itertuples()}


def orbit_types(health, history):
    """{name: 'GEO' | 'IGSO' | 'QZO'}: the health table's type, else the history's own (for satellites set aside)."""
    types = {row["satellite"]: row["type"] for row in history.sort_values("EPOCH").to_dict("records")}
    types.update(dict(zip(health["Satellite"], health["Type"])))
    return types


def chosen_satellites(names, set_aside, choice):
    """The satellites the page counts: all of them, or ("In service") without those set aside or marked not in service."""
    if choice == "All":
        return list(names)
    return [n for n in names if n not in set_aside and n not in gs.NOT_IN_SERVICE]


def dop_rows(satellites, places, when, mask_deg):
    """One row per place: place, lat, lon, seen (satellites in view) and each DOP value (None without a position)."""
    rows = []
    for place, (lat, lon) in places.items():
        dop, seen, _ = calculate_dop_for_location(satellites, lat, lon, when, elevation_mask_deg=mask_deg)
        rows.append({"place": place, "lat": lat, "lon": lon, "seen": len(seen),
                     **{key: (dop[key] if dop else None) for key in DOP_KEYS}})
    return rows


def _steps(start, hours, step_minutes):
    return [start + timedelta(minutes=i * step_minutes) for i in range(int(hours * 60 / step_minutes) + 1)]


def dop_series(satellites, lat, lon, end, mask_deg, hours=gs.TREND_HOURS, step_minutes=gs.TREND_STEP_MINUTES):
    """DOP and satellites in view at one place over the `hours` before `end`: a table with a row per step."""
    rows = []
    for when in _steps(end - timedelta(hours=hours), hours, step_minutes):
        dop, seen, _ = calculate_dop_for_location(satellites, lat, lon, when, elevation_mask_deg=mask_deg)
        rows.append({"time": when, "seen": len(seen), **{key: (dop[key] if dop else None) for key in DOP_KEYS}})
    return pd.DataFrame(rows)


def sky_frames(satellites, lat, lon, start, mask_deg, hours=gs.SKY_HOURS, step_minutes=gs.SKY_STEP_MINUTES):
    """Where each satellite in view sits in the sky at one place, a frame per step from `start`.

    [{"time", "gdop" (None without a position), "satellites": [(name, azimuth, elevation), ...]}]."""
    frames = []
    for when in _steps(start, hours, step_minutes):
        dop, names, positions = calculate_dop_for_location(satellites, lat, lon, when, elevation_mask_deg=mask_deg)
        # positions leaves out satellites it could not place, so pair the ones in view with the names in view
        above = [p for p in positions if p["elevation"] > mask_deg]
        seen = [(name, p["azimuth"], p["elevation"]) for name, p in zip(names, above)]
        frames.append({"time": when, "gdop": dop["GDOP"] if dop else None, "satellites": seen})
    return frames


def sky_paths(satellites, lat, lon, start, hours=gs.SKY_HOURS, step_minutes=gs.SKY_STEP_MINUTES):
    """Where each satellite sits in the sky at one place, a step at a time from `start` (the steps of sky_frames):
    {name: (azimuths, elevations)} in degrees, below the horizon as well."""
    steps, observer = _ts.from_datetimes(_steps(start, hours, step_minutes)), wgs84.latlon(lat, lon)
    paths = {}
    for name, sat in satellites.items():
        elevation, azimuth, _ = (sat - observer).at(steps).altaz()
        paths[name] = (list(azimuth.degrees), list(elevation.degrees))
    return paths


def ground_tracks(satellites, now, window, hours=gs.TRACK_HOURS, step_minutes=gs.TRACK_STEP_MINUTES):
    """({name: {"time", "lat", "lon", "height"}} over the next or past day, {name: (lat, lon) now}).

    lat and lon are the point on the ground under the satellite, in degrees; height is km above the ground there."""
    start = now if window == gs.TRACK_WINDOWS[0] else now - timedelta(hours=hours)
    times = _steps(start, hours, step_minutes)
    steps, at_now = _ts.from_datetimes(times), _ts.from_datetime(now)
    tracks, here = {}, {}
    for name, sat in satellites.items():
        under = wgs84.geographic_position_of(sat.at(steps))
        tracks[name] = {"time": times, "lat": list(under.latitude.degrees), "lon": list(under.longitude.degrees),
                        "height": list(under.elevation.km)}
        point = wgs84.subpoint_of(sat.at(at_now))
        here[name] = (point.latitude.degrees, point.longitude.degrees)
    return tracks, here


def next_visible(satellites, lat, lon, start, mask_deg, hours=gs.NEXT_HOURS, step_minutes=gs.NEXT_STEP_MINUTES):
    """Whether each satellite is in view at one place at `start`, and when that next changes within `hours`.

    [{"satellite", "in_view" (above the mask at `start`), "change" (the first step at which it has risen above the
    mask, or set below it; None when it does not within the window)}], to the step."""
    times = _steps(start, hours, step_minutes)
    steps, observer = _ts.from_datetimes(times), wgs84.latlon(lat, lon)
    rows = []
    for name, sat in satellites.items():
        above = (sat - observer).at(steps).altaz()[0].degrees > mask_deg   # strictly above, as position quality counts
        flips = np.flatnonzero(above != above[0])
        rows.append({"satellite": name, "in_view": bool(above[0]), "change": times[flips[0]] if len(flips) else None})
    return rows


_COORDINATE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*°?\s*([NSEW]?)", re.IGNORECASE)


def parse_place(text):
    """(latitude, longitude) in degrees from what a reader typed: '28.61, 77.21', '28.61 77.21' or
    '28.61 N, 77.21 E'. South and west are negative. Anything else raises a ValueError that says, in plain words,
    what to change."""
    parts = [p for p in re.split(r"\s*[,;]\s*|\s+(?=[+-]?\d)", (text or "").strip()) if p]
    if not parts:
        raise ValueError(f"Enter a latitude and a longitude, for example {gs.PLACE_EXAMPLE}.")
    if len(parts) != 2:
        raise ValueError(f"Enter two numbers, latitude then longitude, for example {gs.PLACE_EXAMPLE}.")
    values = []
    for part, (name, signs, limit) in zip(parts, (("Latitude", "NS", 90), ("Longitude", "EW", 180))):
        found = _COORDINATE.fullmatch(part)
        if not found:
            raise ValueError(f"{name}: “{part}” is not a number of degrees.")
        value, letter = float(found[1]), found[2].upper()
        if letter and letter not in signs:
            raise ValueError(f"{name} is {' or '.join(signs)}, not {letter}: latitude first, then longitude.")
        if letter and value < 0:
            raise ValueError(f"{name}: use a minus sign or {signs[1]}, not both.")
        value = -value if letter == signs[1] else value
        if abs(value) > limit:
            raise ValueError(f"{name} must be between -{limit} and {limit} degrees; {value:g} is outside that.")
        values.append(value)
    return tuple(values)


def central_longitudes(history, names, since):
    """The central longitude of each satellite's ground track, from one element set a week since `since`.

    As app.py's historical central longitude: a day of track around the element set's epoch, its circular mean.
    A table: satellite, EPOCH, central_lon (degrees east, -180 to 180)."""
    rows = history[history["satellite"].isin(names) & (history["EPOCH"] >= since)].dropna(subset=["TLE_LINE1", "TLE_LINE2"])
    out = []
    for name, own in rows.groupby("satellite"):
        week = own["EPOCH"].dt.isocalendar()
        for row in own.groupby([week["year"], week["week"]]).first().itertuples():
            epoch = row.EPOCH.tz_localize(timezone.utc) if row.EPOCH.tzinfo is None else row.EPOCH
            times = _steps(epoch - timedelta(hours=gs.CENTRAL_LON_HALF_HOURS), 2 * gs.CENTRAL_LON_HALF_HOURS,
                           gs.CENTRAL_LON_STEP_MINUTES)[:-1]
            sat = EarthSatellite(row.TLE_LINE1, row.TLE_LINE2, name, _ts)
            lons = wgs84.subpoint(sat.at(_ts.from_datetimes(times))).longitude.degrees
            out.append({"satellite": name, "EPOCH": row.EPOCH, "central_lon": (_circular_mean_deg(lons) + 180) % 360 - 180})
    return pd.DataFrame(out, columns=["satellite", "EPOCH", "central_lon"])


def targets(constellation, name, orbit_type, params):
    """What each trend should be for one satellite: {history column: (low, high)}, only where a target is set.

    Tilt: the configured range, else the target plus or minus the satellite's own inclination tolerance, else the
    constellation's. Height: the configured semi-major axis, less Earth's radius, plus or minus its tolerance.
    Drift: within the drift tolerance for its orbit type. Centre: its slot's longitude plus or minus the configured
    tolerance."""
    p = {**DEFAULT_PARAMS, **params}
    req = REQUIREMENTS.get(constellation, {}).get(name, {})
    out = {}
    target = req.get("inclination", req.get("inclination_target_deg"))
    if "inclination_target_deg_range" in req:
        out["INCLINATION"] = tuple(req["inclination_target_deg_range"])
    elif target is not None:
        tol = req.get("inclination_tol_deg", p["inclination_tolerance"])
        out["INCLINATION"] = (target - tol, target + tol)
    if "sma_km" in req:
        out["altitude_km"] = (req["sma_km"] - R_EARTH - req["sma_tol_km"], req["sma_km"] - R_EARTH + req["sma_tol_km"])
    drift = p["drift_tolerance_gso"] if orbit_type == "GEO" else gs.DRIFT_TOLERANCE_IGSO
    out["LonDrift_deg_per_day"] = (-drift, drift)
    slot = req.get("longitude", req.get("central_longitude_deg"))
    if slot is not None and "longitude_tol_deg" in req:
        out["central_lon"] = (slot - req["longitude_tol_deg"], slot + req["longitude_tol_deg"])
    elif slot is not None:
        out["central_lon"] = (slot, slot)
    return out


def clicked_place(point):
    """(latitude, longitude) of a click on the ground map. The click layer's squares carry their (lat, lon); tracks and
    markers carry words, so for those the point's own position is used."""
    custom = point.get("customdata")
    numbers = custom is not None and len(custom) == 2 and all(isinstance(v, (int, float)) for v in custom)
    return tuple(custom) if numbers else (point["y"], point["x"])
