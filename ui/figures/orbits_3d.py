"""Each satellite's true orbit in 3D, in a space-fixed frame, at one common time.

The orbits come from each satellite's newest mean elements, moved to the common time
(the newest epoch of all of them) by plain two-body motion. Over a day or so that is
close enough for a picture. Earth is turned by sidereal time, so the land under each
satellite is right, and each slot sits on the equator at its own longitude.

orbit_scene() turns this into plain numbers for the page (ui/components/orbit_view.html),
which draws and projects them. Colours follow the slot state in the rows
(ui/figures/slot_rows.py), never worked out again here.
"""
import json
import math
from datetime import datetime
from functools import cache
from pathlib import Path

import numpy as np

from ui.figures.constellation_3d import BELT_RADIUS

EARTH_KM = 6378.137
MU_KM3_S2 = 398600.4418
J2000 = datetime(2000, 1, 1, 12)
LAND_FILE = Path(__file__).with_name("land.json")
GRID_DEG = 2                     # how finely land is told from sea
LAND_STEP = 2                    # a land dot every LAND_STEP grid points: Earth is small on screen
ORBIT_POINTS = 181


def gmst_deg(when):
    """Greenwich sidereal angle in degrees at a UTC datetime (no time zone)."""
    return (280.46061837 + 360.98564736629 * (when - J2000).total_seconds() / 86400) % 360


def latest_elements(history):
    """{satellite: elements} from each satellite's newest record in the history table."""
    newest = history.sort_values("EPOCH").groupby("satellite").tail(1)
    return {row["satellite"]: {
        "epoch": row["EPOCH"].to_pydatetime(), "n_rev_day": float(row["MEAN_MOTION"]),
        "e": float(row["ECCENTRICITY"]), "i": float(row["INCLINATION"]), "raan": float(row["RA_OF_ASC_NODE"]),
        "argp": float(row["ARG_OF_PERICENTER"]), "m": float(row["MEAN_ANOMALY"]),
    } for _, row in newest.iterrows()}


def _semimajor_er(n_rev_day):
    n = n_rev_day * 2 * math.pi / 86400
    return (MU_KM3_S2 / n ** 2) ** (1 / 3) / EARTH_KM


def _to_space(el, ecc_anomaly):
    """Points of the orbit at the given eccentric anomalies, in Earth radii, (3, N)."""
    a, e = _semimajor_er(el["n_rev_day"]), el["e"]
    x, y = a * (np.cos(ecc_anomaly) - e), a * math.sqrt(1 - e * e) * np.sin(ecc_anomaly)
    o, i, w = (math.radians(el[k]) for k in ("raan", "i", "argp"))
    co, so, ci, si, cw, sw = math.cos(o), math.sin(o), math.cos(i), math.sin(i), math.cos(w), math.sin(w)
    return np.array([(co * cw - so * sw * ci) * x - (co * sw + so * cw * ci) * y,
                     (so * cw + co * sw * ci) * x + (co * cw * ci - so * sw) * y,
                     sw * si * x + cw * si * y])


def orbit_points(el):
    """The whole orbit as a closed loop, (3, ORBIT_POINTS)."""
    return _to_space(el, np.linspace(0, 2 * math.pi, ORBIT_POINTS))


def position_at(el, when):
    """Where the satellite is at `when`, by two-body motion from its epoch. (3,)"""
    n = el["n_rev_day"] * 2 * math.pi / 86400
    m = math.radians(el["m"]) + n * (when - el["epoch"]).total_seconds()
    ecc = m
    for _ in range(8):   # Newton on Kepler's equation; e is small, so this settles fast
        ecc -= (ecc - el["e"] * math.sin(ecc) - m) / (1 - el["e"] * math.cos(ecc))
    return _to_space(el, np.array([ecc]))[:, 0]


@cache
def _land_mask():
    """1 where a grid point is on land, else 0, on a GRID_DEG (lat, lon) grid from -90, -180. Even-odd rule over all rings."""
    lat, lon = np.meshgrid(np.arange(-90, 90 + GRID_DEG, GRID_DEG), np.arange(-180, 180 + GRID_DEG, GRID_DEG), indexing="ij")
    inside = np.zeros(lat.shape, dtype=bool)
    for flat in json.loads(LAND_FILE.read_text())["rings"]:
        xs, ys = np.array(flat[0::2]), np.array(flat[1::2])
        x2, y2 = np.roll(xs, -1), np.roll(ys, -1)
        for x1, y1, xb, yb in zip(xs, ys, x2, y2):
            crosses = (y1 > lat) != (yb > lat)
            with np.errstate(divide="ignore", invalid="ignore"):
                at = x1 + (lat - y1) * (xb - x1) / (yb - y1)
            inside ^= crosses & (lon < at)
    return inside.astype(float)


def _land_points(turn_deg):
    """Land as points on a unit sphere, turned by sidereal time: every LAND_STEP-th grid point,
    with fewer per row toward the poles so the dots lie evenly."""
    mask, points = _land_mask(), []
    for i in range(0, mask.shape[0], LAND_STEP):
        lat = math.radians(-90 + i * GRID_DEG)
        step = LAND_STEP * max(1, round(1 / max(math.cos(lat), 0.01)))
        for j in range(0, mask.shape[1] - 1, step):   # the last column is -180 again
            if mask[i, j]:
                lon = math.radians(-180 + j * GRID_DEG + turn_deg)
                points.append([round(math.cos(lat) * math.cos(lon), 3), round(math.cos(lat) * math.sin(lon), 3),
                               round(math.sin(lat), 3)])
    return points


def orbit_scene(rows, elements):
    """Plain numbers for the page, in Earth radii, space-fixed, z along the pole.

    {"land": [[x, y, z], ...], "belt": radius of the slots' ring, "satellites": one entry per row, in row
    order, with its "state", its orbit "loop" and position "at" (None without elements), and its slot "slot_at" on
    the equator (None without one)}. rows come from slot_rows; elements from latest_elements.
    """
    known = [elements[r["name"]] for r in rows if r["name"] in elements]
    when = max(el["epoch"] for el in known) if known else J2000
    turn = gmst_deg(when)
    satellites = []
    for row in rows:
        el, slot = elements.get(row["name"]), None
        if row["slot_lon"] is not None:
            angle = math.radians(row["slot_lon"] + turn)
            slot = [round(BELT_RADIUS * math.cos(angle), 3), round(BELT_RADIUS * math.sin(angle), 3), 0.0]
        satellites.append({"state": row["state"], "slot_at": slot,
                           "loop": None if el is None else np.round(orbit_points(el).T, 3).tolist(),
                           "at": None if el is None else np.round(position_at(el, when), 3).tolist()})
    return {"land": _land_points(turn), "belt": BELT_RADIUS, "satellites": satellites}
