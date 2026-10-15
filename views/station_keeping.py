"""Station-keeping: how often each satellite's orbit is corrected, and whether the rhythm holds."""
from html import escape

import pandas as pd
import streamlit as st

from ui import data, shell, surfaces
from ui.figures.burns import burn_cadence, burn_timeline, rhythm

PATTERN_STATUS = {"regular": "ok", "irregular": "warn", "too few": "idle"}
CHART = {"use_container_width": True, "config": {"displayModeBar": False}}


def _chosen():
    """{constellation: [satellite, ...]} for the scope in the top bar. Compare reuses the Overview's picks."""
    scope = st.session_state["scope"]
    if scope != "Compare":
        return {scope: None}
    return {name: st.session_state.get(f"pick_{name}") for name in shell.CONSTELLATIONS
            if st.session_state.get(f"pick_{name}")}


def _days(value):
    return f"{abs(value):.0f} d"


def _next(row):
    """(words, status) for when the next east-west burn is due."""
    if row["due_in_days"] is None:
        return ("last " + _days(row["since_days"]) + " ago", "idle") if row["since_days"] is not None else ("no burns", "idle")
    guess = "~" if row["pattern"] != "regular" else ""
    if row["late"]:
        return f"{_days(row['due_in_days'])} late", "warn"
    if round(row["due_in_days"]) <= 0:
        return "due now", "accent"
    return f"in {guess}{_days(row['due_in_days'])}", "ok" if guess == "" else "idle"


def _cycle(row):
    """How far the satellite is into its cycle: elapsed fill, the usual window (middle half of intervals) as a band,
    the median as a tick. The fill turns amber once the usual window has passed."""
    if row["due_in_days"] is None:
        return '<span class="cycle"></span>'
    scale = max(row["q3_days"], row["since_days"]) * 1.08
    at = lambda days: f"{100 * days / scale:.1f}%"
    return (f'<span class="cycle{" late" if row["late"] else ""}"><em style="left:{at(row["q1_days"])};width:{at(row["q3_days"] - row["q1_days"])}"></em>'
            f'<i style="width:{at(row["since_days"])}"></i><b style="left:{at(row["median_days"])}"></b></span>')


def _rhythm(rows):
    """One line per satellite, soonest due first: its usual interval, where it is in this cycle, when the next is due."""
    lines = ['<div class="rh hd"><span></span><span>East-west, every</span><span>This cycle</span>'
             '<span>Next</span><span>North-south</span></div>']
    for row in sorted(rows, key=lambda r: (r["due_in_days"] is None, r["due_in_days"] or 0)):
        words, status = _next(row)
        every = ('<span class="muted">&ndash;</span>' if row["median_days"] is None else
                 f'<b class="num">{row["median_days"]:.0f} days</b>')
        north_south = f'<span class="num">{row["ns_count"]}</span>' if row["ns_count"] else '<span class="muted">&ndash;</span>'
        lines.append(f'<div class="rh"><b>{escape(row["satellite"])}</b>'
                     f'<span class="ev">{every}{surfaces.chip(row["pattern"], PATTERN_STATUS[row["pattern"]])}</span>'
                     f'{_cycle(row)}<span class="due {status}">{words}</span>{north_south}</div>')
    return surfaces.raised('<div class="rhythm">' + "".join(lines) + "</div>")


chosen = _chosen()
if not chosen:
    surfaces.show('<p class="small">Pick satellites on the Overview to compare.</p>')
    st.stop()
try:
    results = {name: data.load(name, st.session_state["window_days"], st.session_state["params"]) for name in chosen}
except ValueError as error:
    surfaces.show(surfaces.notice(str(error), "warn"))
    st.stop()

satellites, burns, epochs = [], [], []
for name, result in results.items():
    mine = chosen[name] or list(dict.fromkeys(result["history"]["satellite"]))
    satellites += mine
    burns.append(result["burns"][result["burns"]["satellite"].isin(mine)])
    epochs.append(pd.to_datetime(result["history"]["EPOCH"]))
burns = pd.concat(burns, ignore_index=True)
start, end = min(e.min() for e in epochs), max(e.max() for e in epochs)

surfaces.show(_rhythm(rhythm(burns, satellites, end)))
st.plotly_chart(burn_cadence(burns, satellites), **CHART)
st.plotly_chart(burn_timeline(burns, satellites, start, end), **CHART)
