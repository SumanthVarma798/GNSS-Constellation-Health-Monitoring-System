"""The belt in 3D, seen from above the pole: Earth in the middle, slots as hollow rings.

Each satellite is tied to ITS OWN slot. A slot whose own satellite is not on it is
drawn in the empty colour, even if another satellite sits there. A satellite that has
left its slot rides a wider dotted ring, with a dashed line back to its own slot.

constellation_3d(rows, caption) takes the rows described in ui/figures/slot_rows.py and
returns a Plotly figure. Names and notes come from outside, so they are escaped.
"""
import math
from html import escape

import plotly.graph_objects as go

from ui import palette
from ui.figures.slot_rows import group_by_position, state_words
from ui.tooltip import PLOTLY_HOVER

EARTH_RADIUS = 1.0
BELT_RADIUS = 6.62   # the geostationary belt, in Earth radii
# Satellites that left the belt ride a ring this much further out. The real gap is far
# smaller than this: it is exaggerated on purpose so the eye can see them apart.
LEFT_RING_EXTRA = 0.78
CAMERA = {"eye": {"x": -0.25, "y": -0.75, "z": 0.95}}
RING_STEP_DEG = 2
CLEAR = "rgba(0,0,0,0)"


def _point(lon, radius):
    """(x, y, z) of a longitude on a ring in the equator plane."""
    angle = math.radians(lon)
    return radius * math.cos(angle), radius * math.sin(angle), 0.0


def _ring(radius):
    points = [_point(lon, radius) for lon in range(0, 360 + RING_STEP_DEG, RING_STEP_DEG)]
    return [p[0] for p in points], [p[1] for p in points], [0.0] * len(points)


def _earth():
    """Earth as a sphere of radius 1, a quiet surface that lets the belt stand out."""
    rings, steps = 18, 36
    x, y, z = [], [], []
    for i in range(rings + 1):
        theta = math.pi * i / rings
        x.append([math.sin(theta) * math.cos(2 * math.pi * j / steps) for j in range(steps + 1)])
        y.append([math.sin(theta) * math.sin(2 * math.pi * j / steps) for j in range(steps + 1)])
        z.append([math.cos(theta)] * (steps + 1))
    return go.Surface(x=x, y=y, z=z, showscale=False, opacity=0.9, hoverinfo="skip",
                      colorscale=[[0, palette.LIFT], [1, palette.TRACK]], lighting={"ambient": 0.9})


def _line(xs, ys, colour, width, dash=None, **extra):
    return go.Scatter3d(mode="lines", x=xs, y=ys, z=[0.0] * len(xs), hoverinfo="skip",
                        line={"color": colour, "width": width, **({"dash": dash} if dash else {})}, **extra)


def _ties(rows, state, radius, dash):
    """One trace holding a line from each satellite of this state back to its own slot."""
    xs, ys = [], []
    for row in rows:
        if row["state"] == state and row["slot_lon"] is not None and row["actual_lon"] is not None:
            (sx, sy, _), (ax, ay, _) = _point(row["slot_lon"], BELT_RADIUS), _point(row["actual_lon"], radius)
            xs += [ax, sx, None]
            ys += [ay, sy, None]
    return _line(xs, ys, palette.SLOT_COLOURS[state], 2, dash)


def _slot_owner_words(row):
    if row["state"] == palette.SLOT_UNKNOWN:
        return f"belongs to {row['name']}, whose position is not known"
    if row["state"] == palette.SLOT_IN:
        return f"{row['name']} is on it"
    return f"empty, it belongs to {row['name']} ({row['state']})"


def slot_colour(row):
    """Blue when its own satellite is on it, the idle colour when that satellite's position is not known, else the empty colour."""
    if row["state"] == palette.SLOT_IN:
        return palette.ACCENT
    return palette.SLOT_COLOURS[palette.SLOT_UNKNOWN] if row["state"] == palette.SLOT_UNKNOWN else palette.SLOT_EMPTY


def _slot_markers(rows):
    placed = [r for r in rows if r["slot_lon"] is not None]
    points = [_point(r["slot_lon"], BELT_RADIUS) for r in placed]
    hover = [escape(f"Slot {r['slot_lon']:g} degrees east: {_slot_owner_words(r)}") for r in placed]
    colours = [slot_colour(r) for r in placed]
    return go.Scatter3d(mode="markers", x=[p[0] for p in points], y=[p[1] for p in points], z=[0.0] * len(points),
                        hovertext=hover, hoverinfo="text",
                        marker={"size": 9, "symbol": "circle-open", "color": colours, "line": {"width": 3, "color": colours}})


def _satellite_markers(rows):
    """Satellites coloured by state, with one merged label where several share a spot."""
    placed = [r for r in rows if r["actual_lon"] is not None]
    labels = {}
    for group in group_by_position(placed):
        labels[id(group[0])] = ", ".join(r["name"] for r in group)
    points = [_point(r["actual_lon"], BELT_RADIUS + (LEFT_RING_EXTRA if r["state"] == palette.SLOT_LEFT else 0))
              for r in placed]
    colours = [palette.SLOT_COLOURS[r["state"]] for r in placed]
    return go.Scatter3d(
        mode="markers+text", x=[p[0] for p in points], y=[p[1] for p in points], z=[0.0] * len(points),
        text=[escape(labels.get(id(r), "")) for r in placed], textposition="top center",
        textfont={"color": [palette.INK if c == palette.OK else c for c in colours], "size": 11},
        hovertext=[escape(state_words(r)) for r in placed], hoverinfo="text",
        marker={"size": 5, "color": colours})


def constellation_3d(rows, caption=""):
    """A Plotly figure of the belt: slots, satellites by state, ties, and a ring for those that left."""
    left_ring = any(r["state"] == palette.SLOT_LEFT for r in rows)
    traces = [_earth(), _line(*_ring(BELT_RADIUS)[:2], palette.FILL, 3)]
    if left_ring:
        traces.append(_line(*_ring(BELT_RADIUS + LEFT_RING_EXTRA)[:2], palette.SLOT_COLOURS[palette.SLOT_LEFT], 3, "dot"))
    traces += [_ties(rows, palette.SLOT_OFF, BELT_RADIUS, None),
               _ties(rows, palette.SLOT_LEFT, BELT_RADIUS + LEFT_RING_EXTRA, "dash"),
               _slot_markers(rows), _satellite_markers(rows)]
    axis = {"visible": False, "range": [-8, 8]}
    figure = go.Figure(traces)
    figure.update_layout(
        paper_bgcolor=CLEAR, showlegend=False, margin={"l": 0, "r": 0, "t": 0, "b": 0}, hoverlabel=PLOTLY_HOVER,
        scene={"xaxis": axis, "yaxis": axis, "zaxis": {"visible": False, "range": [-4, 4]},
               "aspectmode": "manual", "aspectratio": {"x": 1, "y": 1, "z": 0.5},
               "bgcolor": CLEAR, "camera": CAMERA})
    if caption:
        figure.add_annotation(text=escape(caption), xref="paper", yref="paper", x=0, y=0, showarrow=False,
                              xanchor="left", yanchor="bottom", font={"color": palette.MUTED, "size": 12})
    return figure


def slot_legend():
    """(colour, words) for each way a satellite can stand, plus an empty slot, for the page's hover legend."""
    return [
        (palette.SLOT_COLOURS[palette.SLOT_IN], f"{palette.SLOT_IN}: sits on its own slot"),
        (palette.SLOT_COLOURS[palette.SLOT_OFF], f"{palette.SLOT_OFF}: a line joins it to its own slot"),
        (palette.SLOT_COLOURS[palette.SLOT_LEFT], f"{palette.SLOT_LEFT}: on the wider dotted ring"),
        (palette.SLOT_COLOURS[palette.SLOT_UNKNOWN], f"{palette.SLOT_UNKNOWN}: no current longitude"),
        (palette.SLOT_EMPTY, "slot with its satellite gone: shown hollow, even if another satellite sits on it"),
    ]
