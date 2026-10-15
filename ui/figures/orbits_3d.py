"""Each satellite's true orbit in 3D, in a space-fixed frame, at one common time.

The orbits come from each satellite's newest mean elements, moved to the common time
(the newest epoch of all of them) by plain two-body motion. Over a day or so that is
close enough for a picture. Earth is turned by sidereal time, so the land under each
satellite is right, and each slot sits on the equator at its own longitude.

Colours follow the slot state in the rows (ui/figures/slot_rows.py), never worked out
again here. Every trace for a satellite carries meta = its row's index, so the page can
pick out one satellite with its orbit and slot.
"""
import json
import math
from datetime import datetime
from functools import cache
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from ui import palette
from ui.figures.constellation_3d import BELT_RADIUS, CLEAR, slot_colour

EARTH_KM = 6378.137
MU_KM3_S2 = 398600.4418
J2000 = datetime(2000, 1, 1, 12)
LAND_FILE = Path(__file__).with_name("land.json")
GRID_DEG = 2                     # Earth's mesh, and how finely land is told from sea
ORBIT_POINTS = 181
SCENE_RANGE = 7.6                # Earth radii: room for the highest apogee
CAMERA = {"eye": {"x": 0.82, "y": -0.82, "z": 0.46}}
# Light from up and to the left as seen from CAMERA, as on every raised surface of the page.
LIGHT = {"x": 0.08e5, "y": -0.9e5, "z": 0.9e5}
MATTE = {"ambient": 0.55, "diffuse": 0.75, "specular": 0.04, "roughness": 0.95, "fresnel": 0.05}


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
    """1 where a grid point is on land, else 0, on the (lat, lon) grid of _earth. Even-odd rule over all rings."""
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


def _earth(turn_deg):
    """A matte sphere, land a shade lighter than sea, turned by sidereal time."""
    lat = np.radians(np.arange(-90, 90 + GRID_DEG, GRID_DEG))[:, None]
    lon = np.radians(np.arange(-180, 180 + GRID_DEG, GRID_DEG) + turn_deg)[None, :]
    xyz = (np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat) * np.ones_like(lon))
    x, y, z = (np.round(v, 3) for v in xyz)   # finer than a pixel; keeps the page small
    return go.Surface(x=x, y=y, z=z,
                      surfacecolor=_land_mask(), cmin=0, cmax=1, showscale=False, hoverinfo="skip",
                      colorscale=[[0, palette.PLATFORM], [1, palette.FILL]], lighting=MATTE, lightposition=LIGHT)


def _slot(index, row, turn_deg):
    angle = math.radians(row["slot_lon"] + turn_deg)
    colour = slot_colour(row)
    return go.Scatter3d(mode="markers", x=[BELT_RADIUS * math.cos(angle)], y=[BELT_RADIUS * math.sin(angle)], z=[0.0],
                        meta=index, hoverinfo="none",
                        marker={"size": 8, "symbol": "circle-open", "color": colour, "line": {"width": 3, "color": colour}})


def _satellite(index, row, el, when):
    colour = palette.SLOT_COLOURS[row["state"]]
    loop, here = np.round(orbit_points(el), 3), position_at(el, when)
    return [go.Scatter3d(mode="lines", x=loop[0], y=loop[1], z=loop[2], meta=index, hoverinfo="none",
                         line={"color": colour, "width": 3}),
            go.Scatter3d(mode="markers", x=[here[0]], y=[here[1]], z=[here[2]], meta=index, hoverinfo="none",
                         marker={"size": 6, "color": colour, "line": {"width": 0}})]


def orbits_3d(rows, elements):
    """A Plotly figure: Earth, then for each row its slot and, where elements are known, its orbit and satellite.

    rows come from slot_rows; elements from latest_elements. Traces carry meta = row index.
    """
    known = [elements[r["name"]] for r in rows if r["name"] in elements]
    when = max(el["epoch"] for el in known) if known else J2000
    turn = gmst_deg(when)
    traces = [_earth(turn)]
    for index, row in enumerate(rows):
        if row["slot_lon"] is not None:
            traces.append(_slot(index, row, turn))
        if row["name"] in elements:
            traces += _satellite(index, row, elements[row["name"]], when)
    axis = {"visible": False, "range": [-SCENE_RANGE, SCENE_RANGE]}
    figure = go.Figure(traces)
    figure.update_layout(
        paper_bgcolor=CLEAR, showlegend=False, margin={"l": 0, "r": 0, "t": 0, "b": 0}, hovermode="closest",
        scene={"xaxis": axis, "yaxis": axis, "zaxis": axis, "aspectmode": "cube", "bgcolor": CLEAR, "camera": CAMERA})
    return figure


def orbit_legend():
    """(colour, words) for the 3D view's hover legend."""
    return [
        *((palette.SLOT_COLOURS[state], f"{state}: the satellite and its orbit")
          for state in (palette.SLOT_IN, palette.SLOT_OFF, palette.SLOT_LEFT, palette.SLOT_UNKNOWN)),
        (palette.ACCENT, "hollow ring on the equator: a slot with its own satellite on it"),
        (palette.SLOT_EMPTY, "hollow ring in this colour: its own satellite is not on it"),
    ]
