"""Burns: when each satellite's orbit was corrected, and how steadily.

burn_timeline    one row per satellite on a shared time axis, each burn a small mark
                 (east-west a dot, north-south an open diamond) whose hover card says
                 when, how much and how long after the one before; at the row's end
                 the days since its last east-west burn, in the warning colour once
                 that has run past the usual window.
cadence_summary  the rhythm of each satellite and kind as numbers and one word.
rhythm           one line per satellite: how often it burns east-west, how far it is
                 into the current cycle, and when the next burn is due.

`burns` is a table with one row per detected manoeuvre: satellite, kind
("east-west" or "north-south"), window_start and window_end (UTC: the element sets
before and at the detected jump, so the burn is somewhere inside), d_sma_km and
d_inc_deg. burns_from_detections builds it from the detector's output.
No Streamlit and no clock: the caller passes the time span.
"""
from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ui.figures import burns_settings
from ui import palette
from ui.burn_groups import COLOURS, CONFIDENCE_WORDS, GROUPS, GROUP_SYMBOL, VERDICT, group_of
from ui.tooltip import PLOTLY_HOVER, plotly_card

EAST_WEST = "east-west"
NORTH_SOUTH = "north-south"
KINDS = (EAST_WEST, NORTH_SOUTH)
COLUMNS = ["satellite", "kind", "window_start", "window_end", "d_sma_km", "d_inc_deg"]
KIND_LABEL = {EAST_WEST: "East-west", NORTH_SOUTH: "North-south"}
# The burn list on the page draws the same two shapes (ui/theme.css, .mk.ew and .mk.ns).
KIND_SYMBOL = {EAST_WEST: "circle", NORTH_SOUTH: "diamond-open"}
PATTERN_REGULAR, PATTERN_IRREGULAR, PATTERN_TOO_FEW = "regular", "irregular", "too few"

# What burn_timeline needs of the classified burns (ui/burn_record.py classified) to colour a mark by what the burn was.
KIND_COLUMNS = ["satellite", "kind", "window_end", "burn_class", "confidence", "counted", "tests", "note"]

MARK_PX = 9                   # one burn's mark
ROW_PX = 34                   # height of one satellite's row
FRAME_PX = 64                 # the key above the rows and the date axis under them
END_PX = 52                   # room after a row for its days since the last burn


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


def _when_after(first, ts):
    """ts, leaving out what it shares with first: '04:10', '4 Mar 04:10' or the whole date."""
    if ts.date() == first.date():
        return f"{ts:%H:%M}"
    return f"{ts.day} {ts:%b %H:%M}" if ts.year == first.year else _when(ts)


def _width_words(delta):
    hours = delta.total_seconds() / 3600
    return f"{hours:.0f} hours" if hours < 48 else f"{hours / 24:.1f} days"


def _days(value):
    return f"{value:.0f} d"


def _with_classes(b, kinds):
    """`b` with what each burn was (the columns of KIND_COLUMNS, matched on satellite, kind and window_end) and the
    picture's group for it; a burn the table does not hold has no group and is drawn as before."""
    if kinds is None or not len(kinds):
        return b.assign(group=None)
    k = kinds.reindex(columns=KIND_COLUMNS).copy()
    k["window_end"] = pd.to_datetime(k["window_end"], utc=True).dt.tz_localize(None)
    b = b.merge(k.drop_duplicates(["satellite", "kind", "window_end"]), on=["satellite", "kind", "window_end"], how="left")
    b["group"] = [group_of(c, bool(n)) if isinstance(c, str) else None for c, n in zip(b["burn_class"], b["counted"])]
    return b


def _mark_hover(row):
    """One burn: when (the window it fell in), how much it changed the orbit, and the gap since the one before."""
    when = (f"{_when(row.window_start)} – {_when_after(row.window_start, row.window_end)} UTC "
            f"({_width_words(row.window_end - row.window_start)})")
    change = f"orbit height {row.d_sma_km:+.2f} km" if row.kind == EAST_WEST else f"tilt {row.d_inc_deg:+.3f}°"
    gap = "first in view" if pd.isna(row.gap_days) else f"{_days(row.gap_days)} after the one before"
    if not pd.isna(row.usual_days):
        gap += f", usually {_days(row.usual_days)}"
    lines = [("When", when), ("Change", change), ("Gap", gap)]
    if isinstance(getattr(row, "burn_class", None), str):   # what it was, how sure, and the tests behind it
        lines.insert(0, ("What", f"{row.burn_class} ({VERDICT.get(row.group, '')})"))
        lines.insert(1, ("Sure", CONFIDENCE_WORDS.get(row.confidence, str(row.confidence))))
        lines += [("Test", test) for test in str(row.tests or "").split("; ") if test]
    return plotly_card(f"{row.satellite} · {row.kind} burn", *lines)


def _since_hover(r):
    """The row's end: days since its last east-west burn, the usual interval, and whether that has run out."""
    if r["since_days"] is None:
        return plotly_card(r["satellite"], ("Last east-west burn", "none in view"))
    lines = [("Last east-west burn", f"{_days(r['since_days'])} ago, {_when(r['last'])} UTC")]
    if r["median_days"] is not None:
        lines.append(("Usually", f"every {_days(r['median_days'])} ({r['q1_days']:.0f} to {_days(r['q3_days'])})"))
    if r["late"]:
        lines.append(("Late", f"past the usual {_days(r['q3_days'])}"))
    return plotly_card(r["satellite"], *lines)


def burn_timeline(burns, satellites, start, end, kinds=None):
    """One row per satellite on a shared time axis over [start, end]: each burn a small mark (east-west a dot,
    north-south an open diamond) and, at the row's end, the days since its last east-west burn. The stretch from
    that burn to the end is drawn as a thicker line, in the warning colour once it has run past the usual window
    (rhythm's late). Every mark and every end value opens a hover card; nothing else is written on the chart.
    With `kinds` (the classified burns, KIND_COLUMNS) each mark is filled by what the burn was (ui/burn_groups.py
    COLOURS); a burn not judged is an empty outline, and its hover card says the kind, how sure, and the tests."""
    start, end = _naive_utc(start), _naive_utc(end)
    satellites = list(satellites)
    b = _with_classes(_with_gaps(_clean(burns)), kinds)
    b["usual_days"] = b.groupby(["satellite", "kind"])["gap_days"].transform("median")
    row_of = {name: -i for i, name in enumerate(satellites)}
    fig = go.Figure()
    for kind in KINDS:
        rows = b[(b["kind"] == kind) & b["satellite"].isin(satellites)]
        marker = {"symbol": KIND_SYMBOL[kind], "size": MARK_PX, "color": palette.INK,
                  "line": {"color": palette.INK, "width": 1.5}}
        if kinds is not None:   # shape and fill both say what the burn was (GROUP_SYMBOL, COLOURS)
            shape = KIND_SYMBOL[kind].replace("-open", "")
            ink = [COLOURS.get(g) or palette.INK for g in rows["group"]]
            marker.update(symbol=[shape + GROUP_SYMBOL.get(g, "-open") for g in rows["group"]], color=ink,
                          line={"color": ink, "width": 1.5})
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=KIND_LABEL[kind], hoverinfo="skip",
                                     marker={"symbol": shape, "size": MARK_PX, "color": palette.INK}, legendgroup=kind))
        fig.add_trace(go.Scatter(
            x=rows["middle"], y=[row_of[s] for s in rows["satellite"]], mode="markers", name=KIND_LABEL[kind],
            cliponaxis=False, hoverinfo="text", hovertext=[_mark_hover(r) for r in rows.itertuples()],
            showlegend=kinds is None, legendgroup=kind, marker=marker))
    if kinds is not None:   # the legend: each group's mark (drawn here as an east-west one) with its word
        for group, words in GROUPS:
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode="markers", name=words, hoverinfo="skip", legendgroup=group,
                marker={"symbol": "circle" + GROUP_SYMBOL[group], "size": MARK_PX, "color": COLOURS.get(group) or palette.INK,
                        "line": {"color": COLOURS.get(group) or palette.INK, "width": 1.5}}))
    for r in rhythm(burns, satellites, end):
        y, late = row_of[r["satellite"]], bool(r["late"])
        fig.add_shape(type="line", x0=start, x1=end, y0=y, y1=y, line={"color": palette.TRACK, "width": 1}, layer="below")
        if r["last"] is not None:
            fig.add_shape(type="line", x0=r["last"], x1=end, y0=y, y1=y, layer="below",
                          line={"color": palette.WARN if late else palette.FILL, "width": 3})
        fig.add_annotation(xref="paper", x=1, xshift=10, xanchor="left", yref="y", y=y, showarrow=False,
                           text="–" if r["since_days"] is None else _days(r["since_days"]),
                           font={"color": palette.WARN if late else palette.MUTED, "family": palette.FONT_NUMBERS,
                                 "size": 13},
                           hovertext=_since_hover(r), hoverlabel={k: v for k, v in PLOTLY_HOVER.items() if k != "align"})
    axis = {"fixedrange": True, "zeroline": False, "automargin": True}
    fig.update_layout(
        height=ROW_PX * max(len(satellites), 1) + FRAME_PX + 24 * (kinds is not None),
        margin={"l": 8, "r": END_PX, "t": 8 + 24 * (kinds is not None), "b": 8},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": palette.INK, "family": palette.FONT},
        dragmode=False, hoverlabel=PLOTLY_HOVER,
        legend={"orientation": "h", "x": 0, "y": 1, "yanchor": "bottom", "itemwidth": 30, "bgcolor": "rgba(0,0,0,0)",
                "font": {"color": palette.MUTED, "size": 12}},
        xaxis={"type": "date", "range": [start, end], "showgrid": False, "linecolor": palette.TRACK,
               "tickcolor": palette.TRACK, "tickfont": {"color": palette.MUTED}, **axis},
        yaxis={"range": [-len(satellites) + 0.5, 0.5], "tickvals": list(row_of.values()),
               "ticktext": [escape(s) for s in satellites], "tickfont": {"color": palette.INK, "size": 13},
               "showgrid": False, "showline": False, "ticks": "", "ticklabelstandoff": 14, **axis})
    return fig


def _with_gaps(b):
    """The burns plus days since the previous burn of the same satellite and kind (blank for the first)."""
    b = b.copy()
    b["gap_days"] = b.groupby(["satellite", "kind"])["middle"].diff().dt.total_seconds() / 86400
    return b


def cadence_summary(burns, satellites):
    """One dict per satellite and kind: count, median_days, q1_days, q3_days, iqr_days, longest_gap_days,
    pattern, and last (the middle of the latest burn's window, or None).

    Intervals are days between the middles of successive windows of the same kind.
    The interval numbers are None when there are fewer than two burns. The pattern is
    "too few" under BURN_MIN_FOR_PATTERN burns, "regular" when the IQR is at most
    BURN_REGULAR_MAX_IQR_SHARE of the median, else "irregular".
    """
    b = _with_gaps(_clean(burns))
    out = []
    for name in satellites:
        for kind in KINDS:
            mine = b[(b["satellite"] == name) & (b["kind"] == kind)]
            gaps = mine["gap_days"].dropna().to_numpy()
            row = {"satellite": name, "kind": kind, "count": len(mine), "median_days": None, "q1_days": None,
                   "q3_days": None, "iqr_days": None, "longest_gap_days": None, "pattern": PATTERN_TOO_FEW,
                   "last": mine["middle"].max() if len(mine) else None}
            if len(gaps):
                q1, med, q3 = np.percentile(gaps, [25, 50, 75])
                row.update(median_days=float(med), q1_days=float(q1), q3_days=float(q3), iqr_days=float(q3 - q1),
                           longest_gap_days=float(gaps.max()))
                if len(mine) >= burns_settings.BURN_MIN_FOR_PATTERN:
                    regular = q3 - q1 <= burns_settings.BURN_REGULAR_MAX_IQR_SHARE * med
                    row["pattern"] = PATTERN_REGULAR if regular else PATTERN_IRREGULAR
            out.append(row)
    return out


def rhythm(burns, satellites, as_of):
    """One dict per satellite, in the order given, for its east-west burns (the ones that keep it in its slot):
    cadence_summary's numbers, plus since_days (days from the latest burn to as_of, the end of the data),
    due_in_days (the median interval less since_days: below zero once the usual time has passed),
    late (True once since_days passes the upper quartile, the end of the usual window) and ns_count.

    Without a median interval since_days may still be known, and due_in_days and late are None.
    """
    as_of = _naive_utc(as_of)
    rows = {(r["satellite"], r["kind"]): r for r in cadence_summary(burns, satellites)}
    out = []
    for name in satellites:
        row = dict(rows[(name, EAST_WEST)], ns_count=rows[(name, NORTH_SOUTH)]["count"])
        since = (as_of - row["last"]).total_seconds() / 86400 if row["last"] is not None else None
        known = row["median_days"] is not None and since is not None
        row.update(since_days=since, due_in_days=row["median_days"] - since if known else None,
                   late=since > row["q3_days"] if known else None)
        out.append(row)
    return out
