"""Station-keeping: how often each satellite's orbit is corrected, and whether the rhythm holds."""
import pandas as pd
import streamlit as st

from ui import data, shell, surfaces
from ui.figures.burns import burn_cadence, burn_timeline, cadence_summary

PATTERN_STATUS = {"regular": "ok", "irregular": "warn", "too few": "idle"}
SHORT = {"east-west": "E-W", "north-south": "N-S"}
CHART = {"use_container_width": True, "config": {"displayModeBar": False}}


def _chosen():
    """{constellation: [satellite, ...]} for the top bar's choice. Compare reuses the picks (ui.picker)."""
    if not st.session_state["compare"]:
        return {st.session_state["scope"]: None}
    picks = st.session_state.get("compare_picks", {})
    return {name: picks[name] for name in shell.CONSTELLATIONS if picks.get(name)}


def _rhythm(summary):
    """One raised card per satellite: its east-west rhythm in words, and north-south only when there is one."""
    cards = []
    for name in dict.fromkeys(row["satellite"] for row in summary):
        lines = []
        for row in (r for r in summary if r["satellite"] == name):
            if row["count"] == 0 and row["kind"] == "north-south":
                continue
            every = f"every {row['median_days']:.0f} days" if row["median_days"] else f"{row['count']} burn"
            lines.append(f'<div class="r">{surfaces.chip(SHORT[row["kind"]] + ", " + every, "accent")}'
                         f'{surfaces.chip(row["pattern"], PATTERN_STATUS[row["pattern"]])}</div>')
        cards.append(surfaces.raised("".join(lines), title=name))
    return '<div class="tiles">' + "".join(cards) + "</div>"


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

surfaces.show(_rhythm(cadence_summary(burns, satellites)))
st.plotly_chart(burn_cadence(burns, satellites), **CHART)
st.plotly_chart(burn_timeline(burns, satellites, start, end), **CHART)
