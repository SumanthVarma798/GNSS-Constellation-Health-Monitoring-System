"""The Geometry page's pictures and grids: position quality (DOP), the sky, ground tracks, orbit trends and
orbit plane spacing.

Figure builders return Plotly figures; grid builders return HTML strings for ui.surfaces.show. Names come from
outside files, so they are escaped. No Streamlit and no clock: the numbers come from ui/geometry_data.py.
"""
import json
import math
from datetime import timedelta, timezone
from functools import cache
from html import escape

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.dop_calculations import assess_dop_quality
from ui import geometry_data as gd
from ui import geometry_settings as gs
from ui import palette, surfaces, type_scale
from ui.figures.orbits_3d import LAND_FILE
from ui.tooltip import PLOTLY_HOVER, tip_html, plotly_label_backing, plotly_line, plotly_template

CLEAR = "rgba(0,0,0,0)"
AXIS = {"linecolor": palette.TRACK, "tickcolor": palette.TRACK, "gridcolor": palette.WELL, "zeroline": False}
DOP_LINES = {"GDOP": (palette.ACCENT, "solid", 3), "PDOP": (palette.INK, "solid", 1.5),
             "HDOP": (palette.MUTED, "solid", 1.5), "VDOP": (palette.MUTED, "dot", 1.5)}
BAND_LINES = [("Excellent", palette.OK), ("Good", palette.WARN), ("Moderate", palette.BAD)]
TREND_ROW_PX = 150      # each measure's strip in a satellite's trends
TREND_PAD_PX = 110       # a trend picture's height beyond its strips: the line's room, the time axis, the margins
TREND_FORMAT = {"altitude_km": ",.1f"}   # hover numbers: km to a tenth, the rest to three places
MAP_PAD_DEG = 12
MAP_MIN_WIDE = 1.6     # the map is at least this many times as wide as it is tall
MAP_ASPECT = 2.0       # the city map's width over its height: the whole world fits it exactly (360 by 180 degrees)
MAP_PX = 500
LANE_PX = 30            # each satellite's lane in the timeline: tall enough to read and to touch on a phone


def _layout(fig, height, **extra):
    fig.update_layout(**({"height": height} if height else {}), paper_bgcolor=CLEAR, plot_bgcolor=CLEAR, font={"color": palette.INK},
                      hoverlabel=PLOTLY_HOVER, **extra)
    return fig


def colour(orbit):
    return gs.ORBIT_COLOURS.get(orbit, gs.ORBIT_COLOURS[gs.OTHER_ORBIT])


def _symbol(orbit):
    return gs.ORBIT_SYMBOLS.get(orbit, gs.ORBIT_SYMBOLS[gs.OTHER_ORBIT])


def short(name):
    """'QZS-2' for 'QZS-2 (Michibiki-2)': the label drawn beside a mark; the hover keeps the full name."""
    return name.split(" (")[0]


def by_orbit(names, types):
    """The names grouped by orbit type, GEO first, each group in the order given: [(type, [name, ...]), ...]."""
    groups = {}
    for name in names:
        groups.setdefault(types.get(name, gs.OTHER_ORBIT), []).append(name)
    return sorted(groups.items(), key=lambda item: (item[0] != "GEO", item[0]))


# ---- position quality ----

def quality(key, value, seen=0):
    """(band word, status) for one DOP value. Without a value: 'no fix' with fewer than 4 satellites in view,
    'unusable' with 4 or more (the layout is too poor to work a position out). A measure without bands: ('', 'idle')."""
    if value is None:
        return ("no fix" if seen < 4 else "unusable"), "bad"
    if key not in gs.DOP_BANDS:
        return "", "idle"
    word = assess_dop_quality(key, value)
    return word.lower(), gs.QUALITY_STATUS[word]


def should_be(key):
    """'below 5 (2 excellent)' from the configured bands, or '' for a measure without bands of its own."""
    bands = gs.DOP_BANDS.get(key)
    if not bands:
        return ""
    return f"below {bands['Good'][1]:g}, {bands['Excellent'][1]:g} excellent"


def dop_key():
    """What each DOP measure means and what it should be, one line each."""
    lines = "".join(
        f'<li><b>{key}</b> <span>{escape(name)}: {escape(meaning)}.</span>'
        f'<span class="muted">{"Should be " + should_be(key) + "." if should_be(key) else "No set target."}</span></li>'
        for key, name, meaning in gs.DOP_MEASURES)
    return (f'<p>{escape(gs.DOP_LINE)}</p><ul class="geo-key">{lines}</ul>'
            f'<p class="muted">{escape(gs.SEEN_WORDS)} {escape(gs.DOP_SOURCE)}</p>')


def _cell(key, value, seen):
    word, status = quality(key, value, seen)
    number = "&ndash;" if value is None else f"{value:.2f}"
    return f'<span class="gc {status}"><b class="num">{number}</b><small>{escape(word) or "&nbsp;"}</small></span>'


def dop_grid(rows):
    """One line per place: satellites in view, then each DOP value with its band word."""
    head = "".join(f'<span>{key}<small>{escape(should_be(key)) or "&nbsp;"}</small></span>'
                   for key, _, _ in gs.DOP_MEASURES)
    lines = [f'<div class="gr hd"><span>Place</span><span>In view<small>4 or more</small></span>{head}</div>']
    for row in rows:
        seen = "ok" if row["seen"] >= 4 else "bad"
        lines.append(f'<div class="gr"><span class="gp">{escape(row["place"])}</span>'
                     f'<span class="gc {seen}"><b class="num">{row["seen"]}</b></span>'
                     + "".join(_cell(key, row[key], row["seen"]) for key, _, _ in gs.DOP_MEASURES) + "</div>")
    return surfaces.raised(f'<div class="geo-grid" style="--n:{len(gs.DOP_MEASURES) + 1}">{"".join(lines)}</div>')


def metres_words(metres):
    """'12 m', '6.5 m' (a tenth below 10 m), or 'no position' without one."""
    if metres is None:
        return "no position"
    return f"{metres:.1f} m" if metres < 10 else f"{metres:,.0f} m"


def band_rows():
    """[(band word, its PDOP range, its position error in metres, what that is like)] from the configured PDOP bands,
    each edge times gs.UERE_M. The metres are to the band's upper edge; the last has none."""
    rows = []
    for band, (low, high) in gs.DOP_BANDS["PDOP"].items():
        dop = f"{low:g} to {high:g}" if high != float("inf") else f"over {low:g}"
        metres = (f"{low * gs.UERE_M:g} to {high * gs.UERE_M:g} m" if high != float("inf") else f"over {low * gs.UERE_M:g} m")
        rows.append((band, dop, metres, gs.BAND_LIKE[band]))
    return rows


def band_table():
    """The quality bands in metres: band, DOP, metres, and what that length is like."""
    lines = "".join(f'<div class="br"><b>{escape(band)}</b><span class="num">{dop}</span><span class="num">{metres}</span>'
                    f'<span>{escape(like)}</span></div>' for band, dop, metres, like in band_rows())
    head = '<div class="br hd"><span>Band</span><span>PDOP</span><span>Error</span><span>About as long as</span></div>'
    return f'<div class="geo-bands">{head}{lines}</div>'


def dop_steps_html():
    """First principles, one step at a time, then the four DOPs in a line each and the bands in metres."""
    steps = "".join(f"<li>{escape(step)}</li>" for step in gs.DOP_STEPS)
    plain = "".join(f"<li><b>{key}</b> {escape(words)}</li>" for key, words in gs.PLAIN_DOP)
    return (f'<ol class="geo-steps">{steps}</ol><ul class="geo-key">{plain}</ul>'
            f'<p class="small">{escape(gs.UERE_WORDS)}</p>{band_table()}<p class="small">{escape(gs.DOP_SOURCE)}</p>')


def _error_class(row):
    return quality("PDOP", row["PDOP"], row["seen"])


def place_card(label, row):
    """One place's card: its name and where it is, the satellites in view, and the position error in metres."""
    word, status = _error_class(row)
    metres = metres_words(row["metres"])
    fix = "no position: fewer than 4 in view" if row["PDOP"] is None and row["seen"] < 4 else (
        "no position: layout too poor" if row["PDOP"] is None else f"{word}")
    return (f'<div class="geo-place {status}"><small>{escape(label)}</small><b class="gp">{escape(row["place"])}</b>'
            f'<small>{latlon_words(row["lat"], row["lon"])}</small>'
            f'<span class="geo-metres num {status}">{"&asymp; " if row["metres"] is not None else ""}{escape(metres)}</span>'
            f'<small>expected position error</small>'
            f'<span>{row["seen"]} satellite{"" if row["seen"] == 1 else "s"} in view {surfaces.chip(fix, status)}</span></div>')


def compare_words(you, other):
    """One line: how the two places' position error compare, in plain words."""
    a, b = you["metres"], other["metres"]
    if a is None or b is None:
        return "At least one of the two places has no position now, so they cannot be compared."
    if round(a) == round(b):
        return f"{you['place']} and {other['place']} are about equally well pinned down."
    better, worse = (you, other) if a < b else (other, you)
    return (f"{better['place']} is pinned down about {worse['metres'] / better['metres']:.1f} times more tightly "
            f"than {worse['place']}.")


def place_cards(you, other):
    """The two places side by side (one under the other on a phone), and the line that compares them."""
    cards = place_card(gs.YOU_LABEL, you) + place_card(gs.COMPARE_LABEL, other)
    return f'<div class="geo-places">{cards}</div><p class="geo-say">{escape(compare_words(you, other))}</p>'


def quality_legend():
    """[(status, symbol, words)]: what each dot's colour and shape say, from the PDOP bands in metres."""
    bands = gs.DOP_BANDS["PDOP"]
    ok, warn = bands["Good"][1] * gs.UERE_M, bands["Moderate"][1] * gs.UERE_M
    return [("ok", "circle", f"under {ok:g} m"), ("warn", "diamond", f"{ok:g} to {warn:g} m"),
            ("bad", "square", f"over {warn:g} m, or no position")]


def quality_map(rows, you, other, ranges):
    """The land, each city a dot coloured (and shaped) by its position error now, and the two chosen places ringed and
    named beside the ring on a backing, towards the nearer edge so they stay off the dots. rows: gd.dop_rows for the
    cities shown. ranges: (x_range, y_range) from map_ranges, in the card's shape (MAP_ASPECT), so land fills the plot."""
    land_x, land_y = _land()
    fig = go.Figure(go.Scatter(x=land_x, y=land_y, mode="lines", fill="toself", fillcolor=palette.FILL, opacity=0.6,
                               line={"color": palette.TRACK, "width": 0.5}, hoverinfo="skip", showlegend=False))
    for status, symbol, words in quality_legend():
        mine = [r for r in rows if _error_class(r)[1] == status]
        fig.add_trace(go.Scatter(
            x=[r["lon"] for r in mine], y=[r["lat"] for r in mine], mode="markers", name=words, showlegend=False,
            marker={"symbol": symbol, "size": 11, "color": {"ok": palette.OK, "warn": palette.WARN, "bad": palette.BAD}[status],
                    "line": {"color": palette.PLATFORM, "width": 1}},
            customdata=[[escape(r["place"]), r["seen"], metres_words(r["metres"]), _error_class(r)[0]] for r in mine],
            hovertemplate=plotly_template("%{customdata[0]}", ("In view", "%{customdata[1]} satellites"),
                                          ("Expected error", "%{customdata[2]}"), ("Quality", "%{customdata[3]}"))))
    middle = [(ranges[0][0] + ranges[0][1]) / 2, (ranges[1][0] + ranges[1][1]) / 2]
    for label, row, line in ((gs.YOU_LABEL, you, palette.ACCENT), (gs.COMPARE_LABEL, other, palette.INK)):
        fig.add_trace(go.Scatter(x=[row["lon"]], y=[row["lat"]], mode="markers", name=label, hoverinfo="skip",
                                 showlegend=False, marker={"symbol": "circle-open", "size": 22, "color": line, "line": {"width": 3}}))
        left, up = row["lon"] < middle[0], row["lat"] >= middle[1]   # the label goes outwards, away from the middle
        fig.add_annotation(x=row["lon"], y=row["lat"], text=f"<b>{escape(gs.city_short(row['place']))}</b>", showarrow=False,
                           xanchor="right" if left else "left", yanchor="bottom" if up else "top",
                           xshift=-16 if left else 16, yshift=10 if up else -10,
                           font={"color": line, "size": type_scale.LEVELS["small"][1]}, **plotly_label_backing())
    fig.update_xaxes(range=ranges[0], ticksuffix="°", showgrid=True, **AXIS)
    fig.update_yaxes(range=ranges[1], ticksuffix="°", showgrid=True, scaleanchor="x", constrain="domain", **AXIS)
    return _layout(fig, None, margin={"l": 40, "r": 4, "t": 4, "b": 24}, hovermode="closest", dragmode=False, showlegend=False)


def quality_legend_html():
    """What the map's marks mean, in a row above it that wraps on a phone: each mark as the map draws it, with its words."""
    marks = [(palette.css({"ok": palette.OK, "warn": palette.WARN, "bad": palette.BAD}[status]), words, symbol)
             for status, symbol, words in quality_legend()]
    marks += [(palette.css(palette.ACCENT), gs.YOU_LABEL, "ring"), (palette.css(palette.INK), gs.COMPARE_LABEL, "ring")]
    shape = {"circle": "swatch", "diamond": "swatch diamond", "square": "swatch square", "ring": "swatch ring"}
    items = "".join(f'<li><span class="{shape[mark]}" style="--c:{colour};background:{colour}"></span>{escape(words)}</li>'
                    for colour, words, mark in marks)
    return f'<ul class="geo-legend" aria-label="Map key">{items}</ul>'


def map_ranges(key_points, picks):
    """(x_range, y_range) for the map: wide enough for the key places and the picks with a margin, and exactly
    MAP_ASPECT times as wide as tall, so with equal degrees on both axes the land fills the plot to its edges. The
    whole world when the places spread over more than half of it. Kept inside -180 to 180 and -90 to 90."""
    lats = [lat for lat, _ in [*key_points, *picks]]
    lons = [lon for _, lon in [*key_points, *picks]]
    pad = gs.MAP_REGION_PAD_DEG
    width = max(max(lons) - min(lons) + 2 * pad, (max(lats) - min(lats) + 2 * pad) * MAP_ASPECT, gs.MAP_MIN_SPAN_DEG)
    if width >= 360 * 0.6:
        return [-180, 180], [-90, 90]
    height = width / MAP_ASPECT
    def fit(low, high, span, limit):
        start = (low + high) / 2 - span / 2
        start = max(-limit, min(limit - span, start))
        return [start, start + span]
    return fit(min(lons), max(lons), width, 180), fit(min(lats), max(lats), height, 90)


def quality_map_deeper():
    """What the map's colours stand for, in metres, and where the cities are drawn."""
    ok, warn = (gs.DOP_BANDS["PDOP"][band][1] * gs.UERE_M for band in ("Good", "Moderate"))
    return (f'<p>Colour and shape are always together, so neither is the only signal: a circle is under {ok:g} m, a diamond '
            f'{ok:g} to {warn:g} m, a square over {warn:g} m or no position. The error is the position quality (PDOP) of '
            f'the satellites above the elevation mask now, times {gs.UERE_M:g} m. The two rings are your places. The map '
            f'shows the cities that fall in the constellation\'s area; a constellation with satellites all round the '
            f'world shows them everywhere.</p>')


def _satellite(angle, size):
    return size * math.cos(math.radians(angle)), size * math.sin(math.radians(angle))


def _crossing(first, second, r1, r2):
    """The point nearer the origin where the circle of radius r1 about `first` meets the one of radius r2 about `second`."""
    (x1, y1), (x2, y2) = first, second
    d = math.hypot(x2 - x1, y2 - y1)
    a = (r1 ** 2 - r2 ** 2 + d ** 2) / (2 * d)
    h = math.sqrt(max(r1 ** 2 - a ** 2, 0))
    mid_x, mid_y = x1 + a * (x2 - x1) / d, y1 + a * (y2 - y1) / d
    points = [(mid_x + h * (y2 - y1) / d, mid_y - h * (x2 - x1) / d), (mid_x - h * (y2 - y1) / d, mid_y + h * (x2 - x1) / d)]
    return min(points, key=lambda p: math.hypot(*p))


def where_you_could_be(angles, size=2.0, spread_m=0.16):
    """The patch where the receiver could be: the four corners where the edges of two satellites' distance rings
    (each `spread_m` either side of its distance, `size`) cross, in order round the patch."""
    first, second = (_satellite(angle, size) for angle in angles)
    return [_crossing(first, second, size + one, size + other) for one, other in
            ((spread_m, spread_m), (spread_m, -spread_m), (-spread_m, -spread_m), (-spread_m, spread_m))]


def overlap_area(angles):
    """The patch's area, by the shoelace formula: smaller is a tighter position."""
    corners = where_you_could_be(angles)
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(corners, corners[1:] + corners[:1]))) / 2


def _ring(angle, size, spread_m, steps=60):
    """One satellite's ring of distance as a polygon: the arc of radius size - spread_m to size + spread_m about it,
    for 60 degrees either side of the direction to the receiver."""
    cx, cy = _satellite(angle, size)
    turns = [math.radians(angle + 180 + 60 * (2 * i / steps - 1)) for i in range(steps + 1)]
    outer = [(cx + (size + spread_m) * math.cos(t), cy + (size + spread_m) * math.sin(t)) for t in turns]
    inner = [(cx + (size - spread_m) * math.cos(t), cy + (size - spread_m) * math.sin(t)) for t in reversed(turns)]
    return outer + inner + outer[:1]


def spread_sketch(angles, size=2.0, spread_m=0.16):
    """Two satellites at these angles above the horizon, each with its ring of distance (the measurement's error as
    the ring's width), the receiver on the ground at the middle, and the patch where the rings cross lit up: where the
    receiver could be. Drawn as filled shapes, so the browser's theme reaches them."""
    fig = go.Figure()
    for angle in angles:
        ring = _ring(angle, size, spread_m)
        fig.add_trace(go.Scatter(x=[x for x, _ in ring], y=[y for _, y in ring], mode="lines", fill="toself",
                                 fillcolor=palette.TRACK, line={"width": 0}, opacity=0.8, hoverinfo="skip", showlegend=False))
    corners = where_you_could_be(angles, size, spread_m)
    fig.add_trace(go.Scatter(x=[x for x, _ in corners + corners[:1]], y=[y for _, y in corners + corners[:1]], mode="lines",
                             fill="toself", fillcolor=palette.WARN, line={"color": palette.WARN, "width": 2},
                             hoverinfo="skip", showlegend=False))
    fig.add_shape(type="line", x0=-size * 1.2, x1=size * 1.2, y0=0, y1=0, line={"color": palette.MUTED, "width": 1})
    for n, angle in enumerate(angles, 1):
        x, y = _satellite(angle, size)
        fig.add_shape(type="line", x0=0, y0=0, x1=x, y1=y, line={"color": palette.MUTED, "width": 1, "dash": "dot"})
        fig.add_trace(go.Scatter(x=[x], y=[y], mode="markers+text", text=[f"satellite {n}"],
                                 textposition="top right" if x >= 0 else "top left", showlegend=False, hoverinfo="skip",
                                 textfont={"color": palette.INK, "size": 11},
                                 marker={"symbol": "diamond", "size": 12, "color": palette.ACCENT}))
    fig.add_trace(go.Scatter(x=[0], y=[0], mode="markers+text", text=["receiver"], textposition="bottom center",
                             showlegend=False, hoverinfo="skip", textfont={"color": palette.INK, "size": 11},
                             marker={"symbol": "circle", "size": 9, "color": palette.INK}))
    fig.update_xaxes(visible=False, range=[-size * 1.2, size * 1.2], constrain="domain", fixedrange=True)
    fig.update_yaxes(visible=False, range=[-size * 0.4, size * 1.2], scaleanchor="x", fixedrange=True)
    return _layout(fig, 250, margin={"l": 4, "r": 4, "t": 4, "b": 4}, dragmode=False, showlegend=False)


def spread_words():
    """The sketches' one line, with the sizes of their patches worked out: how many times bigger the patch is bunched."""
    times = overlap_area(gs.BUNCHED_ANGLES) / overlap_area(gs.SPREAD_ANGLES)
    return f"{gs.SPREAD_LINE} Here the patch is about {times:.0f} times bigger when they are bunched."


def too_few_line(constellation, names, choice, more=False):
    """When the satellites counted number fewer than the 4 a position needs, one line saying so for the whole
    constellation, the count's names in a tooltip. '' with 4 or more. choice: gs.SATELLITE_CHOICES' word; more: satellites are set aside that All would add."""
    if len(names) >= gs.MIN_FOR_FIX:
        return ""
    count = f"{len(names)} satellite{'' if len(names) == 1 else 's'}"
    kind = "in service" if choice == gs.SATELLITE_CHOICES[0] else "counted"
    listed = tip_html(escape(count), "<br>".join(escape(n) for n in names) or "none", key=constellation)
    hint = f" {gs.CHOOSE_ALL}" if more and choice == gs.SATELLITE_CHOICES[0] else ""
    return (f'<p class="geo-say">{escape(constellation)} has {listed} {kind} now, and a position needs {gs.MIN_FOR_FIX}, '
            f'so no place gets a position from {escape(constellation)} alone today.{escape(hint)}</p>')


def place_line(row):
    """One place's state in a line: satellites in view, the error in metres and its band."""
    word, _ = _error_class(row)
    if row["PDOP"] is None:
        return f"{row['place']}: {row['seen']} in view now, " + ("fewer than the 4 a position needs." if row["seen"] < 4
                                                                  else "but spread too poorly for a position.")
    return f"{row['place']}: {row['seen']} in view now, position error about {metres_words(row['metres'])} ({word})."


def gdop_summary(series):
    """Best, worst and average GDOP over the series, with their band words, as tiles; '' when there is none."""
    values = series["GDOP"].dropna()
    if values.empty:
        return ""
    tiles = []
    for label, value in (("Best", values.min()), ("Worst", values.max()), ("Average", values.mean())):
        word, status = quality("GDOP", value)
        tiles.append(f'<div class="tile {status}"><div class="n">{label} GDOP</div>'
                     f'<div class="s num {status}">{value:.2f}</div>{surfaces.chip(word, status)}</div>')
    return f'<div class="tiles geo-three">{"".join(tiles)}</div>'


def dop_trend(series, place):
    """GDOP, PDOP, HDOP and VDOP at one place over time, the band edges marked, and satellites in view under it."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.06)
    for key, (colour, dash, width) in DOP_LINES.items():
        fig.add_trace(go.Scatter(x=series["time"], y=series[key], name=key, mode="lines",
                                 line={"color": colour, "dash": dash, "width": width},
                                 hovertemplate=plotly_line(key, "%{y:.2f}") + "<extra></extra>"), row=1, col=1)
    for band, colour in BAND_LINES:
        edge = gs.DOP_BANDS["GDOP"][band][1]
        fig.add_hline(y=edge, row=1, col=1, line={"color": colour, "width": 1, "dash": "dot"}, opacity=0.7,
                      layer="above", annotation_text=f"{band.lower()} below {edge:g}",
                      annotation_position="top right", annotation_font={"color": colour, "size": 11},
                      **plotly_label_backing("annotation_"))
    fig.add_trace(go.Bar(x=series["time"], y=series["seen"], name="In view", marker={"color": palette.FILL},
                         hovertemplate=plotly_line("In view", "%{y}") + "<extra></extra>", showlegend=False), row=2, col=1)
    fig.update_xaxes(type="date", showgrid=False, hoverformat="<b>%d %b %Y %H:%M UTC</b>",
                     **{k: v for k, v in AXIS.items() if k != "gridcolor"})
    fig.update_yaxes(rangemode="tozero", showgrid=True, **AXIS)
    fig.update_yaxes(title_text=f"DOP at {place}", row=1, col=1)
    fig.update_yaxes(title_text="in view", row=2, col=1, dtick=2)
    fig.update_xaxes(title_text="UTC", row=2, col=1)
    return _layout(fig, 460, margin={"l": 60, "r": 16, "t": 40, "b": 30}, hovermode="x unified",
                   legend={"orientation": "h", "x": 0, "y": 1.1, "bgcolor": CLEAR})


# ---- sky view (drawn by ui/components/sky_view.py) ----

def gdop_words(gdop):
    """'GDOP 2.10, excellent', or 'no position' without one."""
    return "no position" if gdop is None else f"GDOP {gdop:.2f}, {quality('GDOP', gdop)[0]}"


# ---- when each satellite is next in view ----

def latlon_words(lat, lon, places=2):
    """'28.61° N, 77.21° E': a place in words, for headings and hovers."""
    lat, lon = round(lat, places) + 0.0, round(lon, places) + 0.0   # + 0.0: no "0.0° S" for a hair south
    return f"{abs(lat):.{places}f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.{places}f}° {'E' if lon >= 0 else 'W'}"


def clock_words(when, zone):
    """'20 Oct 14:20 IST · 08:50 UTC': the viewer's time and UTC (UTC alone for a viewer on UTC)."""
    local = when.astimezone(zone)
    if not local.utcoffset():
        return f"{when.day} {when:%b %H:%M} UTC"
    utc = f"{when:%H:%M} UTC" if local.date() == when.date() else f"{when.day} {when:%b %H:%M} UTC"
    return f"{local.day} {local:%b %H:%M} {local.tzname()} · {utc}"


def next_summary(rows, now, zone):
    """The timeline's one line: how many are in view now and the next to come into view."""
    seen = sum(r["in_view"] for r in rows)
    rising = sorted(((gd.next_rise(r), r) for r in rows if not r["in_view"] and r["windows"]), key=lambda pair: pair[0])
    soonest = f" · next: {short(rising[0][1]['satellite'])} {clock_words(rising[0][0], zone)}" if rising else ""
    return f"{seen} of {len(rows)} in view now{soonest}"


def _wall(when, zone):
    """The clock time in the viewer's zone as a plain datetime: Plotly's axis shows its numbers as written."""
    return when.astimezone(zone).replace(tzinfo=None)


def _utc(when):
    """A moment on the timeline's axis: UTC without a zone, so every bar's start and length agree across a clock change
    in the reader's zone (only the axis labels are written in that zone)."""
    return when.astimezone(timezone.utc).replace(tzinfo=None)


def _lane_names(rows):
    names = [short(r["satellite"]) for r in rows]
    return [r["satellite"] if names.count(n) > 1 else n for r, n in zip(rows, names)]


def view_timeline(rows, types, now, zone, hours=gs.NEXT_HOURS):
    """One lane per satellite, a bar for each stretch above the elevation mask over the next `hours`, the rise time
    written at the start of each bar, a line for now. Lanes in gd.timeline_order: in view now first, then the next rise.
    Each lane is LANE_PX tall, so the picture grows with the number of satellites and the page scrolls."""
    rows = gd.timeline_order(rows)
    # each lane names its orbit too, so colour is never the only sign of it
    lanes = [f"{lane} · {types.get(row['satellite'], gs.OTHER_ORBIT)}" for row, lane in zip(rows, _lane_names(rows))]
    start, end = _utc(now), _utc(now + timedelta(hours=hours))
    bars = {"y": [], "base": [], "x": [], "text": [], "colour": [], "hover": []}
    for row, lane in zip(rows, lanes):
        orbit = types.get(row["satellite"], gs.OTHER_ORBIT)
        for rise, set_ in row["windows"]:
            a, b = _wall(rise, zone), _wall(set_, zone)
            now_up = rise == now
            bars["y"].append(lane)
            bars["base"].append(_utc(rise))   # placed in UTC; the words on it are the reader's clock (a)
            # elapsed time (right across a clock change), never under one step, so a pass seen once still shows
            bars["x"].append(max((set_ - rise).total_seconds(), gs.NEXT_STEP_MINUTES * 60) * 1000)
            bars["text"].append("in view" if now_up else f"{a:%H:%M}")
            bars["colour"].append(colour(orbit))
            bars["hover"].append([escape(row["satellite"]), gs.ORBIT_WORDS.get(orbit, orbit),
                                  "now" if now_up else f"{a:%d %b %H:%M}",
                                  f"{b:%d %b %H:%M}" + (" or later" if set_ >= now + timedelta(hours=hours) else "")])
    fig = go.Figure(go.Bar(
        orientation="h", y=bars["y"], base=bars["base"], x=bars["x"], text=bars["text"], customdata=bars["hover"],
        marker={"color": bars["colour"], "line": {"width": 0}}, textposition="inside", insidetextanchor="start",
        constraintext="none", textfont={"color": palette.PLATFORM, "size": type_scale.LEVELS["small"][1]},
        showlegend=False,
        hovertemplate=plotly_template("%{customdata[0]}", ("Kind", "%{customdata[1]}"), ("Rises", "%{customdata[2]}"),
                                      ("Sets", "%{customdata[3]}"))))
    empty = [lane for row, lane in zip(rows, lanes) if not row["windows"]]
    if empty:   # a lane without a bar says so, instead of looking forgotten
        fig.add_trace(go.Scatter(x=[start + (end - start) / 2] * len(empty), y=empty, mode="text", hoverinfo="skip",
                                 text=["below the mask all day"] * len(empty), showlegend=False,
                                 textfont={"color": palette.MUTED, "size": type_scale.LEVELS["small"][1]}))
    fig.add_shape(type="line", x0=start, x1=start, y0=0, y1=1, yref="paper",
                  line={"color": palette.ACCENT, "width": 2})
    fig.add_annotation(text="now", x=start, y=1, yref="paper", xanchor="left", yanchor="bottom", showarrow=False,
                       font={"color": palette.ACCENT, "size": type_scale.LEVELS["small"][1]})
    ticks = [start + timedelta(hours=h) for h in range(0, hours + 1, 6)]
    # one step past the end, so a pass first seen at the last step still draws inside the axis
    fig.update_xaxes(type="date", range=[start, end + timedelta(minutes=gs.NEXT_STEP_MINUTES)], side="top", tickvals=ticks,
                     ticktext=[f"{_wall(t.replace(tzinfo=timezone.utc), zone):%H:%M<br>%d %b}" for t in ticks],
                     fixedrange=True, showgrid=True, **AXIS)
    fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=lanes, fixedrange=True, showgrid=False,
                     tickfont={"size": type_scale.LEVELS["small"][1]}, **{k: v for k, v in AXIS.items() if k != "gridcolor"})
    return _layout(fig, LANE_PX * len(rows) + 70, bargap=0.25, dragmode=False, hovermode="closest",
                   margin={"l": 8, "r": 12, "t": 46, "b": 8, "autoexpand": True})


# ---- ground tracks ----

@cache
def _land():
    """Land outlines as one x, y pair of lists, rings parted by None."""
    xs, ys = [], []
    for flat in json.loads(LAND_FILE.read_text())["rings"]:
        xs += flat[0::2] + [None]
        ys += flat[1::2] + [None]
    return xs, ys


def _unwrapped(*columns, lon_at=1):
    """The track's columns with a break (None) wherever it crosses the 180° line, so no line runs across the map.
    lon_at: which column is the longitude."""
    lons = columns[lon_at]
    out = [[] for _ in columns]
    for i in range(len(lons)):
        if i and abs(lons[i] - lons[i - 1]) > 180:
            for column in out:
                column.append(None)
        for column, values in zip(out, columns):
            column.append(values[i])
    return out


def _ranges(lats, lons):
    y_range = [max(-90, min(lats) - MAP_PAD_DEG), min(90, max(lats) + MAP_PAD_DEG)] if lats else [-90, 90]
    half = max((max(lons) - min(lons)) / 2 + MAP_PAD_DEG, (y_range[1] - y_range[0]) * MAP_MIN_WIDE / 2) if lons else 180
    middle = (max(lons) + min(lons)) / 2 if lons else 0
    return [max(-180, middle - half), min(180, middle + half)], y_range


def click_cells(x_range, y_range, step=gs.CLICK_GRID_DEG):
    """Squares `step` degrees a side covering the map: [(west edge, south edge), ...]."""
    wests = range(math.floor(x_range[0] / step) * step, math.ceil(x_range[1]), step)
    souths = range(math.floor(y_range[0] / step) * step, math.ceil(y_range[1]), step)
    return [(w, s) for w in wests for s in souths]


def ground_map(tracks, here, types, places, chosen=None, marked=()):
    """Each satellite's ground track, where it is now, the key places, and the chosen place (name, lat, lon).

    marked: [(label, lat, lon)], other places the reader chose, ringed and named on the map.

    Hovering a track says which satellite, when, the point on the ground under it and its height. A click anywhere
    on the map picks that point, to the nearest square of CLICK_GRID_DEG (Plotly reports clicks on drawn things only)."""
    land_x, land_y = _land()
    fig = go.Figure(go.Scatter(x=land_x, y=land_y, mode="lines", fill="toself", fillcolor=palette.FILL,
                               line={"color": palette.TRACK, "width": 0.5}, hoverinfo="skip", showlegend=False, opacity=0.5))
    hidden = {"marker": {"opacity": 0}}
    shown = set()
    for name, track in tracks.items():
        orbit = types.get(name, gs.OTHER_ORBIT)
        words = [[f"{t:%d %b %H:%M} UTC", latlon_words(lat, lon, 1), h]
                 for t, lat, lon, h in zip(track["time"], track["lat"], track["lon"], track["height"])]
        lats, lons, info = _unwrapped(track["lat"], track["lon"], words)
        # big invisible markers: a hover near the line finds the track before the click grid under it
        fig.add_trace(go.Scatter(x=lons, y=lats, customdata=info, mode="lines+markers", opacity=0.8,
                                 line={"color": colour(orbit), "width": 2}, marker={"size": 16, "opacity": 0},
                                 selected=hidden, unselected=hidden, name=orbit, legendgroup=orbit,
                                 showlegend=orbit not in shown,
                                 hovertemplate=plotly_template(name, ("When", "%{customdata[0]}"), ("Over", "%{customdata[1]}"),
                                                               ("Altitude", "%{customdata[2]:,.0f} km"))))
        shown.add(orbit)
    now = [(n, *here[n]) for n in tracks if n in here]
    keep = {"marker": {"opacity": 1}}
    fig.add_trace(go.Scatter(
        x=[lon for _, _, lon in now], y=[lat for _, lat, _ in now], text=[escape(short(n)) for n, _, _ in now],
        customdata=[[escape(n), latlon_words(lat, lon, 1)] for n, lat, lon in now],
        mode="markers+text", textposition="top center", textfont={"color": palette.INK, "size": 11}, showlegend=False,
        marker={"size": 10, "color": [colour(types.get(n, gs.OTHER_ORBIT)) for n, _, _ in now],
                "symbol": [_symbol(types.get(n, gs.OTHER_ORBIT)) for n, _, _ in now], "line": {"color": palette.PLATFORM, "width": 1}},
        selected=keep, unselected=keep, hovertemplate=plotly_template("%{customdata[0]}", ("Now over", "%{customdata[1]}"))))
    fig.add_trace(go.Scatter(x=[lon for lat, lon in places.values()], y=[lat for lat, lon in places.values()],
                             text=[escape(p) for p in places], mode="markers", name="key places", selected=keep, unselected=keep,
                             marker={"symbol": "x-thin", "size": 10, "color": palette.MUTED, "line": {"color": palette.MUTED, "width": 2}},
                             hovertemplate=plotly_template("%{text}", ("Click", "to see its sky"))))
    picked = ([chosen[1:]] if chosen else []) + [(lat, lon) for _, lat, lon in marked]
    lons = [x for t in tracks.values() for x in t["lon"]] + [lon for _, lon in [*places.values(), *picked]]
    lats = [y for t in tracks.values() for y in t["lat"]] + [lat for lat, _ in [*places.values(), *picked]]
    x_range, y_range = _ranges(lats, lons)
    # Invisible squares under everything: a click on one picks its middle. Plotly ranks the inside of a bar behind
    # any point within the hover distance, so a track's hover still wins near the track.
    cells, half = click_cells(x_range, y_range), gs.CLICK_GRID_DEG / 2
    fig.add_trace(go.Bar(x=[w + half for w, _ in cells], y=[gs.CLICK_GRID_DEG] * len(cells), base=[s for _, s in cells],
                         width=gs.CLICK_GRID_DEG, customdata=[[s + half, w + half] for w, s in cells], name="click",
                         marker={"opacity": 0, "line": {"width": 0}}, selected=hidden, unselected=hidden,
                         hoverinfo="none", showlegend=False))
    if marked:
        fig.add_trace(go.Scatter(x=[lon for _, _, lon in marked], y=[lat for _, lat, _ in marked], mode="markers+text",
                                 name="your places", hoverinfo="skip", text=[escape(label) for label, _, _ in marked],
                                 textposition="bottom center", textfont={"color": palette.INK, "size": 11},
                                 marker={"symbol": "circle-open", "size": 16, "color": palette.INK, "line": {"width": 2}},
                                 selected=keep, unselected=keep, showlegend=False))
    if chosen:
        fig.add_trace(go.Scatter(x=[chosen[2]], y=[chosen[1]], mode="markers", name="chosen place", hoverinfo="skip",
                                 marker={"symbol": "circle-open", "size": 18, "color": palette.ACCENT, "line": {"width": 3}},
                                 selected=keep, unselected=keep))
    fig.update_xaxes(range=x_range, ticksuffix="°", showgrid=True, constrain="domain", **AXIS)
    fig.update_yaxes(range=y_range, ticksuffix="°", showgrid=True, scaleanchor="x", constrain="domain", **AXIS)
    return _layout(fig, MAP_PX, margin={"l": 50, "r": 16, "t": 10, "b": 40}, hovermode="closest", hoverdistance=16,
                   legend={"orientation": "h", "x": 0, "y": 1.06, "bgcolor": CLEAR})


# ---- orbit trends ----

def _band(fig, x0, x1, low, high, yaxis):
    """What the measure should be, drawn quietly: a pressed-in band (a dashed line when it is one value). Drawn as a
    trace, so the axis always takes it in; its words are in the measure's own hover."""
    if low == high:
        fig.add_trace(go.Scatter(x=[x0, x1], y=[low, low], mode="lines", line={"color": palette.TRACK, "dash": "dash", "width": 1},
                                 hoverinfo="skip", showlegend=False, yaxis=yaxis))
        return
    fig.add_trace(go.Scatter(x=[x0, x1, x1, x0, x0], y=[low, low, high, high, low], mode="lines", fill="toself",
                             fillcolor=palette.WELL, line={"width": 0}, showlegend=False, hoverinfo="skip", yaxis=yaxis))


def _should(band):
    if band is None:
        return ""
    low, high = band
    return f" (should be {low:g})" if low == high else f" (should be {low:g} to {high:g})"


def outside(values, band):
    """True for each value outside its band. A band of one value has no tolerance set, so nothing is outside it."""
    if band is None or band[0] == band[1]:
        return values != values   # all False (NaN aside)
    return (values < band[0]) | (values > band[1])


def satellite_trends(series, name, bands, start, end, measures=gs.TRENDS):
    """One satellite's measures (TRENDS), one strip each over one shared time axis, to be read at a glance: the line
    in ink, what it should be as a quiet pressed-in band, readings outside the band marked in the bad colour, and the
    latest reading written at the right of its name (in the bad colour, and named above the strips, when outside). Each
    strip's name and unit sit above it. Hovering any strip reads all of them at that time, with a line down through
    every strip. Fixed side margins keep every satellite's strips on the same time scale, one under another.

    series: {history column: table with satellite, EPOCH and that column}. bands: {column: (low, high)}. measures: the
    strips drawn (gs.MEO_TRENDS for a MEO system)."""
    fig = go.Figure()
    count, gap = len(measures), 0.1
    tall = (1 - gap * (count - 1)) / count
    small = {"size": type_scale.LEVELS["small"][1], "color": palette.MUTED}
    now_outside = []
    for i, (column, label, unit, _) in enumerate(measures):
        yaxis = "y" if i == 0 else f"y{i + 1}"
        top = 1 - i * (tall + gap)
        fig.update_layout({f"yaxis{'' if i == 0 else i + 1}": {
            "domain": [max(0, top - tall), top], "showgrid": False, "nticks": 3, "tickfont": small,
            "tickformat": ",.0f" if column == "altitude_km" else None, **AXIS}})
        fig.add_annotation(text=f"{escape(label)}  <span style='color:{palette.MUTED}'>{escape(unit)}</span>",
                           xref="paper", yref="paper", x=0, y=top, xanchor="left", yanchor="bottom", showarrow=False,
                           font={**small, "color": palette.INK})
        band = bands.get(column)
        if band is not None:
            _band(fig, start, end, *band, yaxis)
        table = series.get(column)
        own = table[table["satellite"] == name] if table is not None else None
        if own is None or own.empty:
            continue
        number = TREND_FORMAT.get(column, ".3f")
        fig.add_trace(go.Scatter(x=own["EPOCH"], y=own[column], name=label, yaxis=yaxis,
                                 mode="lines+markers" if len(own) < 30 else "lines",
                                 line={"color": palette.INK, "width": 1.5}, marker={"size": 4}, showlegend=False,
                                 hovertemplate=plotly_line(label, f"%{{y:{number}}}{_should(band)}") + "<extra></extra>"))
        off = own[outside(own[column], band)]
        if not off.empty:
            fig.add_trace(go.Scatter(x=off["EPOCH"], y=off[column], name=f"{label} outside", yaxis=yaxis, mode="markers",
                                     marker={"size": 6, "color": palette.BAD}, hoverinfo="skip", showlegend=False))
        last = own.sort_values("EPOCH").iloc[-1]
        late_out = bool(outside(last[column], band))
        if late_out:
            now_outside.append(label)
        fig.add_annotation(text=f"now {last[column]:{number}}", xref="paper", x=1, yref="paper", y=top, xanchor="right",
                           yanchor="bottom", showarrow=False,
                           font={"family": palette.FONT_NUMBERS, "size": small["size"],
                                 "color": palette.BAD if late_out else palette.INK})
    fig.update_xaxes(type="date", range=[start, end], anchor=f"y{count}", showgrid=False, tickfont=small, nticks=4,
                     hoverformat="<b>%d %b %Y %H:%M UTC</b>", showspikes=True, spikemode="across", spikesnap="cursor",
                     spikecolor=palette.MUTED, spikethickness=1, spikedash="solid",
                     linecolor=palette.TRACK, tickcolor=palette.TRACK)
    if now_outside:   # a line of its own, right under the card's own line
        fig.add_annotation(text=f"now outside: {escape(', '.join(now_outside))}", xref="paper", yref="paper", x=0, y=1,
                           xanchor="left", yanchor="bottom", yshift=26, showarrow=False, font={**small, "color": palette.BAD})
    # the card's height is the same for every satellite of a constellation (room for the line is always kept), the
    # strips take the rest, and the side margins are slim so a phone gives the lines nearly its whole width
    return _layout(fig, TREND_ROW_PX * count + TREND_PAD_PX, hovermode="x unified", hoversubplots="axis", spikedistance=-1,
                   margin={"l": 56, "r": 12, "t": 56, "b": 30, "autoexpand": False})


def _clause(column, own, band):
    """One measure in words: steady within its span, or rising or falling by so much over the readings' days; 'now outside its
    range' when the latest reading is. '' with no readings."""
    word, unit, steady, decimals = gs.TREND_WORDS[column]
    own = own.sort_values("EPOCH")
    values = own[column].dropna()
    if values.empty:
        return ""
    span = values.max() - values.min()
    if len(values) < 2:
        text = f"{word} {values.iloc[-1]:.{decimals}f}{unit}"
    elif span <= steady:
        text = f"{word} steady within {span:.{decimals}f}{unit}"
    else:
        epochs = own.loc[values.index, "EPOCH"]
        days_apart = (epochs - epochs.iloc[0]).dt.total_seconds() / 86400
        days = max(round(days_apart.iloc[-1]), 1)
        change = np.polyfit(days_apart, values, 1)[0] * days_apart.iloc[-1]   # the fitted line's own rise or fall
        if abs(change) < steady:
            text = f"{word} steady within {span:.{decimals}f}{unit}"
        else:
            text = f"{word} {'rising' if change > 0 else 'falling'} {abs(change):.{decimals}f}{unit} over {days} days"
    return text + (", now outside its range" if outside(values.iloc[-1], band) else "")


def trend_line(series, name, bands, days, measures=gs.TRENDS):
    """What a satellite's trends say right now, in one line: 'Over the last 90 days: height steady within 1.2 km; tilt
    falling 0.12° over 90 days.' series and bands as for satellite_trends. '' when there are no readings."""
    clauses = []
    for column, *_ in measures:
        table = series.get(column)
        if table is not None:
            clause = _clause(column, table[table["satellite"] == name], bands.get(column))
            if clause:
                clauses.append(clause)
    return f"Over the last {days} days: " + "; ".join(clauses) + "." if clauses else ""


def trends_key():
    """What each trend column means, and how the picture marks a reading out of bounds."""
    lines = "".join(f'<li><b>{escape(name)}</b> <span>{escape(meaning)}.</span></li>' for _, name, _, meaning in gs.TRENDS)
    return (f'<ul class="geo-key">{lines}</ul><p class="muted">Each line is one measure over the window, one reading '
            "per element set. The pressed-in band is what it should be, where a target is set; a reading outside it is "
            "marked red. The number at the right of a name is the latest reading. Hover to read every strip at one time.</p>"
            '<p class="muted">Medium-orbit constellations show inclination and altitude only: drift and centre are measured against one turn '
            "a day over one longitude, and a medium-orbit satellite circles the globe.</p>")


# ---- orbit plane spacing ----

def spacing_card(group):
    """One group of satellites sharing a ground track: what the spacing should be and how far it is off."""
    status = gs.SPACING_STATUS.get(group["status"], "idle")
    facts = (f'<div class="geo-facts"><span><small>Should be</small><b class="num">{group["ideal_spacing_deg"]:g}° apart</b></span>'
             f'<span><small>Largest miss</small><b class="num">{group["max_deviation_deg"]:.2f}°</b></span>'
             f'<span><small>Typical miss</small><b class="num">{group["rms_deviation_deg"]:.2f}°</b></span>'
             f'<span><small>Verdict</small>{surfaces.chip(group["status"].lower(), status)}</span></div>')
    return surfaces.raised(facts, spacing_title(group))


def plane_card(row):
    """One plane of a medium-orbit system: how far its node is from the pattern of planes `spacing_deg` apart."""
    # the worse of its two misses decides: the node off the pattern, and the widest gap between neighbours along it
    misses = [abs(row["offset"]) / row["offset_limit"]]
    gap_limit = row.get("gap_limit") or None   # none set, or zero: the miss is shown without a verdict of its own
    if row["gap"] is not None and gap_limit:
        misses.append(abs(row["gap"]) / gap_limit)
    worst = max(misses)
    status = "ok" if worst <= 1 else "warn" if worst <= 3 else "bad"
    gap = ("–" if row["gap"] is None else f'{row["gap"]:.2f}°' + (f' (allowed ±{gap_limit:g}°)' if gap_limit else ""))
    facts = (f'<div class="geo-facts"><span><small>Planes should be</small><b class="num">{row["spacing_deg"]:g}° apart</b></span>'
             f'<span><small>Node off the pattern</small><b class="num">{row["offset"]:+.2f}°</b></span>'
             f'<span><small>Allowed</small><b class="num">±{row["offset_limit"]:g}°</b></span>'
             f'<span><small>Worst spacing miss in it</small><b class="num">{gap}</b></span>'
             f'<span><small>Verdict</small>{surfaces.chip("within limit" if status == "ok" else "past limit", status)}</span></div>')
    return surfaces.raised(facts, f'Plane {escape(str(row["plane"]))} · {row["count"]} satellites')


def spacing_title(group):
    return f'{group["satellite_count"]} satellites around {group["central_longitude_deg"]:.1f}° east'


def spacing_table(group):
    """Each satellite of the group: where its node is, the next one along, the gap to it and how far that is off even."""
    rows = "".join(
        f'<div class="sr"><b>{escape(s["name"])}</b><span class="num">{s["raan_deg"]:.2f}°</span>'
        f'<span>{escape(s["next_neighbor"])}</span><span class="num">{s["gap_to_next_deg"]:.2f}°</span>'
        f'<span class="num">{s["deviation_from_ideal_deg"]:+.2f}°</span></div>' for s in group["satellites"])
    head = ('<div class="sr hd"><span>Satellite</span><span>Node at</span><span>Next along</span>'
            '<span>Gap to next</span><span>Off even</span></div>')
    return f'<div class="spacing">{head}{rows}</div>'


def spacing_wheel(group):
    """The group's nodes on a circle (looking down on the equator from the north), and hollow rings where even
    spacing would put them, starting from the first."""
    sats = group["satellites"]
    even = [(sats[0]["raan_deg"] + k * group["ideal_spacing_deg"]) % 360 for k in range(len(sats))]
    fig = go.Figure()
    for s in sats:
        fig.add_trace(go.Scatterpolar(r=[0, 1], theta=[s["raan_deg"]] * 2, mode="lines", hoverinfo="skip",
                                      line={"color": palette.TRACK, "width": 1}, showlegend=False))
    fig.add_trace(go.Scatterpolar(r=[1] * len(even), theta=even, mode="markers", name="even spacing",
                                  marker={"size": 16, "color": CLEAR, "line": {"color": palette.MUTED, "width": 2}},
                                  hovertemplate=plotly_template("Even spacing", ("Node at", "%{theta:.1f}°"))))
    fig.add_trace(go.Scatterpolar(r=[1] * len(sats), theta=[s["raan_deg"] for s in sats], mode="markers+text",
                                  text=[escape(short(s["name"])) for s in sats], textposition="top center", name="node",
                                  textfont={"color": palette.INK, "size": 11}, marker={"size": 10, "color": palette.ACCENT},
                                  hovertemplate=plotly_template("%{text}", ("Node at", "%{theta:.2f}°"))))
    return _layout(fig, 340, margin={"l": 40, "r": 40, "t": 30, "b": 30},
                   legend={"orientation": "h", "x": 0, "y": -0.05, "bgcolor": CLEAR},
                   polar={"bgcolor": palette.WELL, "radialaxis": {"visible": False, "range": [0, 1.15]},
                          "angularaxis": {"direction": "counterclockwise", "rotation": 0, "ticksuffix": "°",
                                          "gridcolor": palette.TRACK, "linecolor": palette.TRACK,
                                          "tickfont": {"color": palette.MUTED, "size": 10}}})
