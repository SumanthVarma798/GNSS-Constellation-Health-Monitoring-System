"""Burns: when each satellite's orbit was corrected, and how steadily.

burn_timeline    one band per satellite on a shared time axis. East-west burns sit in
                 the upper half of a band (solid), north-south in the lower half
                 (hatched). Each bar spans the detected window, so zooming in shows
                 how well the time of a burn is known.
burn_cadence     one small chart per satellite: days since the previous burn of the
                 same kind, at the date of each burn. A steady operator is a flat
                 line of points, an irregular one scatters, a gap is a tall point.
cadence_summary  the same pattern as numbers and one word.

`burns` is a table with one row per detected manoeuvre: satellite, kind
("east-west" or "north-south"), window_start and window_end (UTC: the element sets
before and at the detected jump, so the burn is somewhere inside), d_sma_km and
d_inc_deg. burns_from_detections builds it from the detector's output.
No Streamlit and no clock: the caller passes the time span.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from evidence import settings
from ui import palette

EAST_WEST = "east-west"
NORTH_SOUTH = "north-south"
KINDS = (EAST_WEST, NORTH_SOUTH)
COLUMNS = ["satellite", "kind", "window_start", "window_end", "d_sma_km", "d_inc_deg"]
KIND_COLOUR = {EAST_WEST: palette.ACCENT, NORTH_SOUTH: palette.MUTED}
KIND_LABEL = {EAST_WEST: "E-W", NORTH_SOUTH: "N-S"}
KIND_OFFSET = {EAST_WEST: 0.22, NORTH_SOUTH: -0.22}   # E-W above the middle of a band, N-S below
PATTERN_REGULAR, PATTERN_IRREGULAR, PATTERN_TOO_FEW = "regular", "irregular", "too few"

MIN_WIDTH_SHARE = 1 / 800     # a bar is never narrower than this share of the whole span
BAND_HALF = 0.46              # a band reaches this far either side of its middle, leaving a gap between bands
BAR_HEIGHT = 0.36            # of a band of height 1
ROW_PX = 64                   # height of one band
SLIDER_PX = 110               # axis, range slider and margins under the bands
CADENCE_COLUMNS = 4
CELL_PX = 190


def burns_from_detections(detected_by_satellite):
    """Turn detector output into the burns table.

    detected_by_satellite maps a satellite name to the frame returned by
    analysis.maneuver_detection.detect_navik_maneuvers, run on that satellite's
    element sets sorted by EPOCH. A flagged row's window runs from the previous
    row's EPOCH to its own. A row flagged for both kinds gives two burns.
    """
    rows = []
    for name, df in detected_by_satellite.items():
        epoch = pd.to_datetime(df["EPOCH"]).reset_index(drop=True)
        for flag, kind in (("EW_MANEUVER", EAST_WEST), ("NS_MANEUVER", NORTH_SOUTH)):
            for i in np.flatnonzero(df[flag].to_numpy(bool)):
                if i == 0:
                    continue  # no earlier element set, so no window
                rows.append((name, kind, epoch[i - 1], epoch[i], float(df["dSMA"].iloc[i]), float(df["dINC"].iloc[i])))
    return pd.DataFrame(rows, columns=COLUMNS)


def _naive_utc(ts):
    ts = pd.Timestamp(ts)
    return ts.tz_convert("UTC").tz_localize(None) if ts.tzinfo else ts


def _clean(burns):
    """Burns in time order, timestamps as naive UTC, plus the middle of each window."""
    b = burns.reindex(columns=COLUMNS)
    for c in ("window_start", "window_end"):
        b[c] = pd.to_datetime(b[c], utc=True).dt.tz_localize(None)
    b["middle"] = b["window_start"] + (b["window_end"] - b["window_start"]) / 2
    return b.sort_values("middle").reset_index(drop=True)


def _when(ts):
    return f"{ts.day} {ts:%b %Y %H:%M}"


def _width_words(delta):
    hours = delta.total_seconds() / 3600
    return f"{hours:.0f} hours" if hours < 48 else f"{hours / 24:.1f} days"


def _hover(row):
    if row.kind == EAST_WEST:
        size = f"orbit height changed by {row.d_sma_km:+.2f} km"
    else:
        size = f"tilt changed by {row.d_inc_deg:+.3f} degrees"
    return (f"{row.satellite}: {row.kind} burn<br>sometime between {_when(row.window_start)} "
            f"and {_when(row.window_end)} UTC<br>(window {_width_words(row.window_end - row.window_start)} wide)<br>{size}")


def burn_timeline(burns, satellites, start, end):
    """One band per satellite; opens on the last BURN_TIMELINE_RECENT_DAYS days of [start, end]."""
    start, end = _naive_utc(start), _naive_utc(end)
    satellites = list(satellites)
    b = _clean(burns)
    min_width = (end - start) * MIN_WIDTH_SHARE
    fig = go.Figure()
    for kind in KINDS:
        rows = b[(b["kind"] == kind) & b["satellite"].isin(satellites)]
        width = [max(w, min_width) for w in rows["window_end"] - rows["window_start"]]
        fig.add_trace(go.Bar(
            orientation="h", name=kind, showlegend=False, width=BAR_HEIGHT, hoverinfo="text",
            y=[-satellites.index(s) + KIND_OFFSET[kind] for s in rows["satellite"]],
            x=[w.total_seconds() * 1000 for w in width],               # length in milliseconds...
            base=list(rows["middle"] - pd.to_timedelta(width).values / 2),   # ...from the left edge
            hovertext=[_hover(r) for r in rows.itertuples()],
            marker={"color": KIND_COLOUR[kind], "line": {"color": KIND_COLOUR[kind], "width": 1},
                    **({"pattern": {"shape": "/", "fgcolor": KIND_COLOUR[kind], "bgcolor": palette.PLATFORM, "size": 6}}
                       if kind == NORTH_SOUTH else {})}))
    for i, name in enumerate(satellites):
        fig.add_shape(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=-i - BAND_HALF, y1=-i + BAND_HALF,
                      fillcolor=palette.WELL, line_width=0, layer="below")
        fig.add_annotation(xref="paper", x=0, xshift=-40, xanchor="right", yref="y", y=-i, text=name,
                           showarrow=False, font={"color": palette.INK, "size": 13})
    if satellites:  # name the two halves once, beside the first band
        for kind in KINDS:
            fig.add_annotation(xref="paper", x=0, xshift=-6, xanchor="right", yref="y", y=KIND_OFFSET[kind],
                               text=KIND_LABEL[kind], showarrow=False, font={"color": palette.MUTED, "size": 11})
    first = max(start, end - pd.Timedelta(days=settings.BURN_TIMELINE_RECENT_DAYS))
    fig.update_layout(
        height=ROW_PX * max(len(satellites), 1) + SLIDER_PX, margin={"l": 110, "r": 16, "t": 8, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", barmode="overlay",
        font={"color": palette.INK}, showlegend=False,
        hoverlabel={"bgcolor": palette.PLATFORM, "font": {"color": palette.INK}},
        xaxis={"type": "date", "range": [first, end], "showgrid": False, "linecolor": palette.TRACK,
               "tickcolor": palette.TRACK, "rangeslider": {"visible": True, "range": [start, end], "thickness": 0.1,
                                                           "bgcolor": palette.WELL, "bordercolor": palette.TRACK}},
        yaxis={"range": [-len(satellites) + 0.5, 0.5], "visible": False, "fixedrange": True})
    return fig


def _with_gaps(b):
    """The burns plus days since the previous burn of the same satellite and kind (blank for the first)."""
    b = b.copy()
    b["gap_days"] = b.groupby(["satellite", "kind"])["middle"].diff().dt.total_seconds() / 86400
    return b


def burn_cadence(burns, satellites):
    """Small multiples: days since the previous burn of the same kind, against the date of each burn."""
    b = _with_gaps(_clean(burns))
    satellites = list(satellites)
    cols = min(CADENCE_COLUMNS, max(len(satellites), 1))
    rows = -(-max(len(satellites), 1) // cols)
    fig = make_subplots(rows=rows, cols=cols, shared_xaxes="all", shared_yaxes="all",
                        subplot_titles=satellites, horizontal_spacing=0.03, vertical_spacing=0.14)
    for i, name in enumerate(satellites):
        r, c = i // cols + 1, i % cols + 1
        for kind, symbol in ((EAST_WEST, "circle"), (NORTH_SOUTH, "diamond")):
            pts = b[(b["satellite"] == name) & (b["kind"] == kind)].dropna(subset=["gap_days"])
            fig.add_trace(go.Scatter(
                x=pts["middle"], y=pts["gap_days"], mode="markers", name=KIND_LABEL[kind],
                legendgroup=kind, showlegend=False, hoverinfo="text",
                marker={"symbol": symbol, "size": 8, "color": KIND_COLOUR[kind]},
                hovertext=[f"{name}: {kind} burn, {_when(m)} UTC<br>{g:.0f} days after the previous one"
                           for m, g in zip(pts["middle"], pts["gap_days"])]), row=r, col=c)
            if len(pts):
                fig.add_hline(y=float(pts["gap_days"].median()), row=r, col=c, opacity=0.4,
                              line={"color": KIND_COLOUR[kind], "width": 1, "dash": "dot"})
    for kind, symbol in ((EAST_WEST, "circle"), (NORTH_SOUTH, "diamond")):  # the key, drawn once and never empty
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=KIND_LABEL[kind], legendgroup=kind,
                                 marker={"symbol": symbol, "size": 8, "color": KIND_COLOUR[kind]}, hoverinfo="skip"))
    axis = {"linecolor": palette.TRACK, "tickcolor": palette.TRACK, "zeroline": False}
    fig.update_xaxes(type="date", showgrid=False, **axis)
    fig.update_yaxes(rangemode="tozero", showgrid=True, gridcolor=palette.WELL, **axis)
    fig.update_yaxes(title_text="days since previous burn", row=1, col=1)
    fig.update_annotations(font={"color": palette.INK, "size": 12})
    fig.update_layout(
        height=CELL_PX * rows + 70, margin={"l": 60, "r": 16, "t": 50, "b": 30},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": palette.INK},
        legend={"orientation": "h", "x": 0, "y": 1.12, "bgcolor": "rgba(0,0,0,0)"},
        hoverlabel={"bgcolor": palette.PLATFORM, "font": {"color": palette.INK}})
    return fig


def cadence_summary(burns, satellites):
    """One dict per satellite and kind: count, median_days, iqr_days, longest_gap_days, pattern.

    Intervals are days between the middles of successive windows of the same kind.
    The three numbers are None when there are fewer than two burns. The pattern is
    "too few" under BURN_MIN_FOR_PATTERN burns, "regular" when the IQR is at most
    BURN_REGULAR_MAX_IQR_SHARE of the median, else "irregular".
    """
    b = _with_gaps(_clean(burns))
    out = []
    for name in satellites:
        for kind in KINDS:
            mine = b[(b["satellite"] == name) & (b["kind"] == kind)]
            gaps = mine["gap_days"].dropna().to_numpy()
            row = {"satellite": name, "kind": kind, "count": len(mine),
                   "median_days": None, "iqr_days": None, "longest_gap_days": None, "pattern": PATTERN_TOO_FEW}
            if len(gaps):
                q1, med, q3 = np.percentile(gaps, [25, 50, 75])
                row.update(median_days=float(med), iqr_days=float(q3 - q1), longest_gap_days=float(gaps.max()))
                if len(mine) >= settings.BURN_MIN_FOR_PATTERN:
                    regular = q3 - q1 <= settings.BURN_REGULAR_MAX_IQR_SHARE * med
                    row["pattern"] = PATTERN_REGULAR if regular else PATTERN_IRREGULAR
            out.append(row)
    return out
