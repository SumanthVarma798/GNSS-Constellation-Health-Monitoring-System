"""The Geometry page's pictures and grids: position quality (DOP), the sky, ground tracks, orbit trends and
orbit plane spacing.

Figure builders return Plotly figures; grid builders return HTML strings for ui.surfaces.show. Names come from
outside files, so they are escaped. No Streamlit and no clock: the numbers come from ui/geometry_data.py.
"""
import json
import math
from functools import cache
from html import escape

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.dop_calculations import assess_dop_quality
from ui import geometry_settings as gs
from ui import palette, surfaces
from ui.figures.orbits_3d import LAND_FILE
from ui.tooltip import PLOTLY_HOVER

CLEAR = "rgba(0,0,0,0)"
AXIS = {"linecolor": palette.TRACK, "tickcolor": palette.TRACK, "gridcolor": palette.WELL, "zeroline": False}
DOP_LINES = {"GDOP": (palette.ACCENT, "solid", 3), "PDOP": (palette.INK, "solid", 1.5),
             "HDOP": (palette.MUTED, "solid", 1.5), "VDOP": (palette.MUTED, "dot", 1.5)}
BAND_LINES = [("Excellent", palette.OK), ("Good", palette.WARN), ("Moderate", palette.BAD)]
TREND_ROW_PX = 120      # each measure's strip in a satellite's trends
TREND_FORMAT = {"altitude_km": ",.1f"}   # hover numbers: km to a tenth, the rest to three places
MAP_PAD_DEG = 12
MAP_MIN_WIDE = 1.6     # the map is at least this many times as wide as it is tall
MAP_PX = 500


def _layout(fig, height, **extra):
    fig.update_layout(height=height, paper_bgcolor=CLEAR, plot_bgcolor=CLEAR, font={"color": palette.INK},
                      hoverlabel=PLOTLY_HOVER, **extra)
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
    return (f'<p>{escape(gs.DOP_INTRO)}</p><ul class="geo-key">{lines}</ul>'
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


def _after(when, now):
    minutes = round((when - now).total_seconds() / 60)
    hours, minutes = divmod(minutes, 60)
    return f"in {hours} h {minutes} min" if hours else f"in {minutes} min"


def next_words(row, orbit, now, zone, hours=gs.NEXT_HOURS):
    """(now: 'in view' or 'not in view', status, when: until when, or when next, in plain words) for one row of
    geometry_data.next_visible. A geostationary satellite stays at one point in the sky, so it says so."""
    state, status = ("in view", "ok") if row["in_view"] else ("not in view", "idle")
    if row["change"] is not None:
        verb = "until" if row["in_view"] else "next in view"
        return state, status, f"{verb} {clock_words(row['change'], zone)}, {_after(row['change'], now)}"
    if orbit == "GEO":
        return state, status, ("always in view: geostationary, it stays at one point in the sky" if row["in_view"] else
                               "never in view from here: geostationary, it stays below the elevation mask")
    return state, status, (f"in view for all of the next {hours} hours" if row["in_view"] else
                           f"not in the next {hours} hours")


def next_order(rows):
    """In view first (leaving soonest first), then the rest by when they come into view; never last."""
    far = max((r["change"] for r in rows if r["change"] is not None), default=None)
    return sorted(rows, key=lambda r: (not r["in_view"], r["change"] is None, r["change"] or far))


def next_table(rows, types, now, zone):
    """One line per satellite: in view now or not, and until when or when next."""
    lines = ['<div class="nr hd"><span>Satellite</span><span>Now</span><span>Until, or next in view</span></div>']
    for row in next_order(rows):
        orbit = types.get(row["satellite"], gs.OTHER_ORBIT)
        state, status, when = next_words(row, orbit, now, zone)
        lines.append(f'<div class="nr"><b>{escape(row["satellite"])}<small>{escape(gs.ORBIT_WORDS.get(orbit, orbit))}</small></b>'
                     f'<span>{surfaces.chip(state, status)}</span><span>{escape(when)}</span></div>')
    return f'<div class="geo-next">{"".join(lines)}</div>'


def next_summary(rows, now, zone):
    """The section's one line: how many are in view now and the next to come into view."""
    seen = sum(r["in_view"] for r in rows)
    rising = [r for r in next_order(rows) if not r["in_view"] and r["change"] is not None]
    soonest = (f" · next: {short(rising[0]['satellite'])} {clock_words(rising[0]['change'], zone)}" if rising else "")
    return f"{seen} of {len(rows)} in view now{soonest}"


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


def ground_map(tracks, here, types, places, chosen=None):
    """Each satellite's ground track, where it is now, the key places, and the chosen place (name, lat, lon).

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
                                 line={"color": _colour(orbit), "width": 2}, marker={"size": 16, "opacity": 0},
                                 selected=hidden, unselected=hidden, name=orbit, legendgroup=orbit,
                                 showlegend=orbit not in shown,
                                 hovertemplate=(f"<b>{escape(name)}</b><br>%{{customdata[0]}}<br>"
                                                "over %{customdata[1]}<br>height %{customdata[2]:,.0f} km<extra></extra>")))
        shown.add(orbit)
    now = [(n, *here[n]) for n in tracks if n in here]
    keep = {"marker": {"opacity": 1}}
    fig.add_trace(go.Scatter(
        x=[lon for _, _, lon in now], y=[lat for _, lat, _ in now], text=[escape(short(n)) for n, _, _ in now],
        customdata=[[escape(n), latlon_words(lat, lon, 1)] for n, lat, lon in now],
        mode="markers+text", textposition="top center", textfont={"color": palette.INK, "size": 11}, showlegend=False,
        marker={"size": 10, "color": [_colour(types.get(n, gs.OTHER_ORBIT)) for n, _, _ in now],
                "symbol": [_symbol(types.get(n, gs.OTHER_ORBIT)) for n, _, _ in now], "line": {"color": palette.PLATFORM, "width": 1}},
        selected=keep, unselected=keep, hovertemplate="<b>%{customdata[0]}</b> now<br>over %{customdata[1]}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[lon for lat, lon in places.values()], y=[lat for lat, lon in places.values()],
                             text=[escape(p) for p in places], mode="markers", name="key places", selected=keep, unselected=keep,
                             marker={"symbol": "x-thin", "size": 10, "color": palette.MUTED, "line": {"color": palette.MUTED, "width": 2}},
                             hovertemplate="%{text}<br>click to see its sky<extra></extra>"))
    picked = [chosen[1:]] if chosen else []
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
    """What the measure should be, as a shaded band (a dashed line when it is one value). Drawn as a trace, so the
    axis always takes it in; its words are in the measure's own hover."""
    if low == high:
        fig.add_trace(go.Scatter(x=[x0, x1], y=[low, low], mode="lines", line={"color": palette.OK, "dash": "dash", "width": 1},
                                 hoverinfo="skip", showlegend=False, yaxis=yaxis))
        return
    fig.add_trace(go.Scatter(x=[x0, x1, x1, x0, x0], y=[low, low, high, high, low], mode="lines", fill="toself",
                             fillcolor=palette.OK, line={"width": 0}, opacity=0.16, showlegend=False, hoverinfo="skip",
                             yaxis=yaxis))


def _should(band):
    if band is None:
        return ""
    low, high = band
    return f" (should be {low:g})" if low == high else f" (should be {low:g} to {high:g})"


def satellite_trends(series, name, orbit, bands, start, end):
    """One satellite's measures (TRENDS), one strip each, over one shared time axis: hovering any strip reads all of
    them at that time, with a line down through every strip.

    series: {history column: table with satellite, EPOCH and that column}. bands: {column: (low, high)}."""
    fig = go.Figure()
    count, gap = len(gs.TRENDS), 0.07
    tall = (1 - gap * (count - 1)) / count
    for i, (column, label, unit, _) in enumerate(gs.TRENDS):
        yaxis = "y" if i == 0 else f"y{i + 1}"
        top = 1 - i * (tall + gap)
        fig.update_layout({f"yaxis{'' if i == 0 else i + 1}": {
            "domain": [top - tall, top], "title": {"text": f"{label}<br>{unit}", "font": {"size": 12, "color": palette.MUTED},
                                                   "standoff": 6},
            "showgrid": True, "nticks": 4, "tickfont": {"size": 12, "color": palette.MUTED},
            "tickformat": ",.0f" if column == "altitude_km" else None, **AXIS}})
        if column in bands:
            _band(fig, start, end, *bands[column], yaxis)
        table = series.get(column)
        own = table[table["satellite"] == name] if table is not None else None
        if own is not None and not own.empty:
            fig.add_trace(go.Scatter(x=own["EPOCH"], y=own[column], name=label, yaxis=yaxis,
                                     mode="lines+markers" if len(own) < 30 else "lines",
                                     line={"color": _colour(orbit), "width": 1.8}, marker={"size": 5}, showlegend=False,
                                     hovertemplate=(f"{label} %{{y:{TREND_FORMAT.get(column, '.3f')}}} {unit}"
                                                    f"{_should(bands.get(column))}<extra></extra>")))
    fig.update_xaxes(type="date", range=[start, end], anchor=f"y{count}", showgrid=False, tickfont={"size": 12, "color": palette.MUTED},
                     hoverformat="%d %b %Y %H:%M UTC", showspikes=True, spikemode="across", spikesnap="cursor",
                     spikecolor=palette.MUTED, spikethickness=1, spikedash="solid",
                     linecolor=palette.TRACK, tickcolor=palette.TRACK)
    return _layout(fig, TREND_ROW_PX * count + 70, hovermode="x unified", hoversubplots="axis", spikedistance=-1,
                   margin={"l": 74, "r": 16, "t": 40, "b": 30},
                   title={"text": f"<b>{escape(name)}</b>  <span style='color:{palette.MUTED}'>{escape(gs.ORBIT_WORDS.get(orbit, orbit))}</span>",
                          "font": {"size": 14, "color": palette.INK}, "x": 0.01, "y": 0.98})


def trends_key():
    """What each trend column means."""
    lines = "".join(f'<li><b>{escape(name)}</b> <span>{escape(meaning)}.</span></li>' for _, name, _, meaning in gs.TRENDS)
    return f'<ul class="geo-key">{lines}</ul><p class="muted">Green band: what it should be, where a target is set.</p>'


# ---- orbit plane spacing ----

def spacing_card(group):
    """One group of satellites sharing a ground track: what the spacing should be and how far it is off."""
    status = gs.SPACING_STATUS.get(group["status"], "idle")
    facts = (f'<div class="geo-facts"><span><small>Should be</small><b class="num">{group["ideal_spacing_deg"]:g}° apart</b></span>'
             f'<span><small>Largest miss</small><b class="num">{group["max_deviation_deg"]:.2f}°</b></span>'
             f'<span><small>Typical miss</small><b class="num">{group["rms_deviation_deg"]:.2f}°</b></span>'
             f'<span><small>Verdict</small>{surfaces.chip(group["status"].lower(), status)}</span></div>')
    return surfaces.raised(facts, spacing_title(group))


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
