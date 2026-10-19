"""The Geometry page's pictures and grids: position quality (DOP), the sky, ground tracks, orbit trends and
orbit plane spacing.

Figure builders return Plotly figures; grid builders return HTML strings for ui.surfaces.show. Names come from
outside files, so they are escaped. No Streamlit and no clock: the numbers come from ui/geometry_data.py.
"""
import json
from functools import cache
from html import escape

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.dop_calculations import assess_dop_quality
from ui import geometry_settings as gs
from ui import palette, surfaces
from ui.figures.orbits_3d import LAND_FILE

CLEAR = "rgba(0,0,0,0)"
HOVER = {"bgcolor": palette.PLATFORM, "font": {"color": palette.INK}}
AXIS = {"linecolor": palette.TRACK, "tickcolor": palette.TRACK, "gridcolor": palette.WELL, "zeroline": False}
DOP_LINES = {"GDOP": (palette.ACCENT, "solid", 3), "PDOP": (palette.INK, "solid", 1.5),
             "HDOP": (palette.MUTED, "solid", 1.5), "VDOP": (palette.MUTED, "dot", 1.5)}
BAND_LINES = [("Excellent", palette.OK), ("Good", palette.WARN), ("Moderate", palette.BAD)]
TREND_ROW_PX = 112
MAP_PAD_DEG = 12
MAP_MIN_WIDE = 1.6     # the map is at least this many times as wide as it is tall
SKY_PX = 560
SKY_LABEL_EVERY = 3     # a time under every third step of the slider


def _layout(fig, height, **extra):
    fig.update_layout(height=height, paper_bgcolor=CLEAR, plot_bgcolor=CLEAR, font={"color": palette.INK},
                      hoverlabel=HOVER, **extra)
    return fig


def _colour(orbit):
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
    return (f'<p class="small">{escape(gs.DOP_INTRO)}</p><ul class="geo-key">{lines}</ul>'
            f'<p class="small">{escape(gs.SEEN_WORDS)} {escape(gs.DOP_SOURCE)}</p>')


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
                                 hovertemplate=f"{key} %{{y:.2f}}<extra></extra>"), row=1, col=1)
    for band, colour in BAND_LINES:
        edge = gs.DOP_BANDS["GDOP"][band][1]
        fig.add_hline(y=edge, row=1, col=1, line={"color": colour, "width": 1, "dash": "dot"}, opacity=0.7,
                      annotation_text=f"{band.lower()} below {edge:g}", annotation_position="top right",
                      annotation_font={"color": colour, "size": 11})
    fig.add_trace(go.Bar(x=series["time"], y=series["seen"], name="In view", marker={"color": palette.FILL},
                         hovertemplate="%{y} in view<extra></extra>", showlegend=False), row=2, col=1)
    fig.update_xaxes(type="date", showgrid=False, **{k: v for k, v in AXIS.items() if k != "gridcolor"})
    fig.update_yaxes(rangemode="tozero", showgrid=True, **AXIS)
    fig.update_yaxes(title_text=f"DOP at {place}", row=1, col=1)
    fig.update_yaxes(title_text="in view", row=2, col=1, dtick=2)
    fig.update_xaxes(title_text="UTC", row=2, col=1)
    return _layout(fig, 460, margin={"l": 60, "r": 16, "t": 40, "b": 30}, hovermode="x unified",
                   legend={"orientation": "h", "x": 0, "y": 1.1, "bgcolor": CLEAR})


# ---- sky view ----

def _sky_traces(frame, types, groups):
    """One trace per orbit type in `groups`, in that order, so every frame has the same traces."""
    traces = []
    for orbit in groups:
        here = [s for s in frame["satellites"] if types.get(s[0], gs.OTHER_ORBIT) == orbit]
        traces.append(go.Scatterpolar(
            r=[90 - el for _, _, el in here], theta=[az for _, az, _ in here], text=[escape(short(n)) for n, _, _ in here],
            mode="markers+text", textposition="top center", name=orbit,
            textfont={"color": palette.INK, "size": 11},
            marker={"size": 12, "color": _colour(orbit), "symbol": _symbol(orbit), "line": {"color": palette.PLATFORM, "width": 1}},
            hovertemplate="%{customdata[0]}<br>azimuth %{theta:.0f}°<br>elevation %{customdata[1]:.0f}°<extra></extra>",
            customdata=[[escape(n), el] for n, _, el in here]))
    return traces


def _sky_title(frame):
    gdop = "no position" if frame["gdop"] is None else f"GDOP {frame['gdop']:.2f}, {quality('GDOP', frame['gdop'])[0]}"
    return f"{frame['time']:%d %b %H:%M} UTC · {len(frame['satellites'])} in view · {gdop}"


def sky_view(frames, types, mask_deg):
    """Where the satellites sit in the sky at one place: overhead in the middle, the horizon at the edge.

    A slider moves through the frames (the first is now)."""
    groups = sorted({types.get(n, gs.OTHER_ORBIT) for f in frames for n, _, _ in f["satellites"]} or {"GEO"})
    mask = go.Scatterpolar(r=[90 - mask_deg] * 73, theta=list(range(0, 365, 5)), mode="lines", hoverinfo="skip",
                           line={"color": palette.TRACK, "dash": "dot", "width": 1}, showlegend=False)
    fig = go.Figure([mask, *_sky_traces(frames[0], types, groups)])
    fig.frames = [go.Frame(data=_sky_traces(f, types, groups), traces=list(range(1, 1 + len(groups))), name=str(i),
                           layout={"title": {"text": _sky_title(f)}}) for i, f in enumerate(frames)]
    steps = [{"method": "animate", "label": f"{f['time']:%H:%M}" if i % SKY_LABEL_EVERY == 0 else "",
              "args": [[str(i)], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}}]}
             for i, f in enumerate(frames)]
    return _layout(
        fig, SKY_PX, margin={"l": 40, "r": 40, "t": 50, "b": 90},
        title={"text": _sky_title(frames[0]), "font": {"size": 14, "color": palette.INK}, "x": 0.02},
        legend={"orientation": "h", "x": 1, "xanchor": "right", "y": 1.08, "bgcolor": CLEAR},
        polar={"bgcolor": palette.WELL,
               "radialaxis": {"range": [0, 90], "tickvals": [0, 30, 60, 90], "ticktext": ["overhead", "60°", "30°", "horizon"],
                              "gridcolor": palette.TRACK, "linecolor": palette.TRACK, "tickfont": {"color": palette.MUTED, "size": 10}},
               "angularaxis": {"direction": "clockwise", "rotation": 90, "tickvals": [0, 90, 180, 270],
                               "ticktext": ["N", "E", "S", "W"], "gridcolor": palette.TRACK, "linecolor": palette.TRACK}},
        sliders=[{"steps": steps, "x": 0.12, "len": 0.88, "y": -0.06, "pad": {"t": 10}, "bgcolor": palette.WELL,
                  "bordercolor": palette.TRACK, "font": {"color": palette.MUTED, "size": 10},
                  "currentvalue": {"visible": False}}],
        updatemenus=[{"type": "buttons", "x": 0, "y": -0.06, "xanchor": "left", "yanchor": "top", "showactive": False,
                      "bgcolor": palette.PLATFORM, "bordercolor": palette.TRACK, "font": {"color": palette.INK},
                      "buttons": [{"label": "Play", "method": "animate",
                                   "args": [None, {"frame": {"duration": 400, "redraw": True}, "fromcurrent": True}]}]}])


# ---- ground tracks ----

@cache
def _land():
    """Land outlines as one x, y pair of lists, rings parted by None."""
    xs, ys = [], []
    for flat in json.loads(LAND_FILE.read_text())["rings"]:
        xs += flat[0::2] + [None]
        ys += flat[1::2] + [None]
    return xs, ys


def _unwrapped(lats, lons):
    """The track with a break wherever it crosses the 180° line, so no line runs across the whole map."""
    xs, ys = [], []
    for i, (lat, lon) in enumerate(zip(lats, lons)):
        if i and abs(lon - lons[i - 1]) > 180:
            xs.append(None)
            ys.append(None)
        xs.append(lon)
        ys.append(lat)
    return xs, ys


def ground_map(tracks, here, types, places):
    """Each satellite's ground track, where it is now, and the places position quality is worked out for."""
    land_x, land_y = _land()
    fig = go.Figure(go.Scatter(x=land_x, y=land_y, mode="lines", fill="toself", fillcolor=palette.FILL,
                               line={"color": palette.TRACK, "width": 0.5}, hoverinfo="skip", showlegend=False, opacity=0.5))
    shown = set()
    for name, (lats, lons) in tracks.items():
        orbit = types.get(name, gs.OTHER_ORBIT)
        xs, ys = _unwrapped(lats, lons)
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line={"color": _colour(orbit), "width": 2}, opacity=0.8,
                                 name=orbit, legendgroup=orbit, showlegend=orbit not in shown,
                                 hovertemplate=f"{escape(name)}<br>%{{y:.1f}}°, %{{x:.1f}}°<extra></extra>"))
        shown.add(orbit)
    now = [(n, *here[n]) for n in tracks if n in here]
    fig.add_trace(go.Scatter(
        x=[lon for _, _, lon in now], y=[lat for _, lat, _ in now], text=[escape(short(n)) for n, _, _ in now],
        customdata=[escape(n) for n, _, _ in now],
        mode="markers+text", textposition="top center", textfont={"color": palette.INK, "size": 11}, showlegend=False,
        marker={"size": 10, "color": [_colour(types.get(n, gs.OTHER_ORBIT)) for n, _, _ in now],
                "symbol": [_symbol(types.get(n, gs.OTHER_ORBIT)) for n, _, _ in now], "line": {"color": palette.PLATFORM, "width": 1}},
        hovertemplate="%{customdata} now<extra></extra>"))
    fig.add_trace(go.Scatter(x=[lon for lat, lon in places.values()], y=[lat for lat, lon in places.values()],
                             text=[escape(p) for p in places], mode="markers", name="places",
                             marker={"symbol": "x-thin", "size": 10, "color": palette.MUTED, "line": {"color": palette.MUTED, "width": 2}},
                             hovertemplate="%{text}<extra></extra>"))
    lons = [x for lats, lons in tracks.values() for x in lons] + [lon for _, lon in places.values()]
    lats = [y for lats, lons in tracks.values() for y in lats] + [lat for lat, _ in places.values()]
    y_range = [max(-90, min(lats) - MAP_PAD_DEG), min(90, max(lats) + MAP_PAD_DEG)] if lats else [-90, 90]
    half = max((max(lons) - min(lons)) / 2 + MAP_PAD_DEG, (y_range[1] - y_range[0]) * MAP_MIN_WIDE / 2) if lons else 180
    middle = (max(lons) + min(lons)) / 2 if lons else 0
    x_range = [max(-180, middle - half), min(180, middle + half)]
    fig.update_xaxes(range=x_range, ticksuffix="°", showgrid=True, constrain="domain", **AXIS)
    fig.update_yaxes(range=y_range, ticksuffix="°", showgrid=True, scaleanchor="x", constrain="domain", **AXIS)
    return _layout(fig, 560, margin={"l": 50, "r": 16, "t": 10, "b": 40},
                   legend={"orientation": "h", "x": 0, "y": 1.06, "bgcolor": CLEAR})


# ---- orbit trends ----

def _band(fig, x0, x1, low, high, row, col):
    """What the measure should be, as a shaded band (a dashed line when it is one value). Drawn as a trace, so the
    axis always takes it in."""
    if low == high:
        fig.add_trace(go.Scatter(x=[x0, x1], y=[low, low], mode="lines", line={"color": palette.OK, "dash": "dash", "width": 1},
                                 hovertemplate=f"should be {low:g}<extra></extra>", showlegend=False), row=row, col=col)
        return
    fig.add_trace(go.Scatter(x=[x0, x1, x1, x0, x0], y=[low, low, high, high, low], mode="lines", fill="toself",
                             fillcolor=palette.OK, line={"width": 0}, opacity=0.16, showlegend=False,
                             hovertemplate=f"should be {low:g} to {high:g}<extra></extra>"), row=row, col=col)


def orbit_trends(series, satellites, types, bands, start, end):
    """One row per satellite (grouped by orbit type), one column per measure in TRENDS: the measure over the window
    and, where a target is set, the band it should sit in.

    series: {history column: table with satellite, EPOCH and that column}. bands: {name: {column: (low, high)}}."""
    order = [n for _, names in by_orbit(satellites, types) for n in names]
    titles = [f"{name} ({unit})" for _, name, unit, _ in gs.TRENDS]
    fig = make_subplots(rows=max(len(order), 1), cols=len(gs.TRENDS), shared_xaxes=True, column_titles=titles,
                        horizontal_spacing=0.07, vertical_spacing=0.25 / max(len(order), 1))
    for r, name in enumerate(order, start=1):
        orbit = types.get(name, gs.OTHER_ORBIT)
        for c, (column, label, unit, _) in enumerate(gs.TRENDS, start=1):
            if column in bands.get(name, {}):
                _band(fig, start, end, *bands[name][column], r, c)
            table = series.get(column)
            own = table[table["satellite"] == name] if table is not None else None
            if own is not None and not own.empty:
                fig.add_trace(go.Scatter(x=own["EPOCH"], y=own[column], mode="lines+markers" if len(own) < 30 else "lines",
                                         line={"color": _colour(orbit), "width": 1.6}, marker={"size": 4}, showlegend=False,
                                         hovertemplate=f"{escape(name)}<br>{label} %{{y:.3f}} {unit}<br>%{{x|%d %b %Y}}<extra></extra>"),
                              row=r, col=c)
        fig.add_annotation(text=f"<b>{escape(name)}</b> <span style='color:{palette.MUTED}'>{orbit}</span>", xref="paper",
                           yref=f"y{'' if r == 1 else (r - 1) * len(gs.TRENDS) + 1} domain", x=0, y=1.0, xanchor="left",
                           yanchor="bottom", showarrow=False, font={"size": 12, "color": palette.INK})
    fig.update_xaxes(type="date", showgrid=False, range=[start, end], linecolor=palette.TRACK, tickcolor=palette.TRACK)
    fig.update_yaxes(showgrid=True, nticks=4, **AXIS)
    fig.update_yaxes(tickformat=",.0f", col=1 + [t[0] for t in gs.TRENDS].index("altitude_km"))   # km in full
    for title in titles:   # the column titles sit above the first satellite's name
        fig.update_annotations(selector={"text": title}, yshift=20, font={"color": palette.MUTED, "size": 12})
    return _layout(fig, TREND_ROW_PX * max(len(order), 1) + 80, margin={"l": 50, "r": 16, "t": 60, "b": 30})


def trends_key():
    """What each trend column means."""
    lines = "".join(f'<li><b>{escape(name)}</b> <span>{escape(meaning)}.</span></li>' for _, name, _, meaning in gs.TRENDS)
    return f'<ul class="geo-key">{lines}</ul><p class="small">Green band: what it should be, where a target is set.</p>'


# ---- orbit plane spacing ----

def spacing_card(group):
    """One group of satellites sharing a ground track: should be, is, and each satellite's node and gap."""
    status = gs.SPACING_STATUS.get(group["status"], "idle")
    rows = "".join(
        f'<div class="sr"><b>{escape(s["name"])}</b><span class="num">{s["raan_deg"]:.2f}°</span>'
        f'<span>{escape(s["next_neighbor"])}</span><span class="num">{s["gap_to_next_deg"]:.2f}°</span>'
        f'<span class="num">{s["deviation_from_ideal_deg"]:+.2f}°</span></div>' for s in group["satellites"])
    head = ('<div class="sr hd"><span>Satellite</span><span>Node at</span><span>Next along</span>'
            '<span>Gap to next</span><span>Off even</span></div>')
    facts = (f'<div class="geo-facts"><span><small>Should be</small><b class="num">{group["ideal_spacing_deg"]:g}° apart</b></span>'
             f'<span><small>Largest miss</small><b class="num">{group["max_deviation_deg"]:.2f}°</b></span>'
             f'<span><small>Typical miss</small><b class="num">{group["rms_deviation_deg"]:.2f}°</b></span>'
             f'<span><small>Verdict</small>{surfaces.chip(group["status"].lower(), status)}</span></div>')
    title = f'{group["satellite_count"]} satellites around {group["central_longitude_deg"]:.1f}° east'
    return surfaces.raised(facts + f'<div class="spacing">{head}{rows}</div>', title)


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
                                  hovertemplate="even spacing %{theta:.1f}°<extra></extra>"))
    fig.add_trace(go.Scatterpolar(r=[1] * len(sats), theta=[s["raan_deg"] for s in sats], mode="markers+text",
                                  text=[escape(short(s["name"])) for s in sats], textposition="top center", name="node",
                                  textfont={"color": palette.INK, "size": 11}, marker={"size": 10, "color": palette.ACCENT},
                                  hovertemplate="%{text}<br>node %{theta:.2f}°<extra></extra>"))
    return _layout(fig, 340, margin={"l": 40, "r": 40, "t": 30, "b": 30},
                   legend={"orientation": "h", "x": 0, "y": -0.05, "bgcolor": CLEAR},
                   polar={"bgcolor": palette.WELL, "radialaxis": {"visible": False, "range": [0, 1.15]},
                          "angularaxis": {"direction": "counterclockwise", "rotation": 0, "ticksuffix": "°",
                                          "gridcolor": palette.TRACK, "linecolor": palette.TRACK,
                                          "tickfont": {"color": palette.MUTED, "size": 10}}})
