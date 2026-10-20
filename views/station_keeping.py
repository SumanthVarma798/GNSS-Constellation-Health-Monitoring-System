"""Station-keeping: how often each satellite's orbit is corrected, and whether the rhythm holds.

The burns in the window first, then each satellite's rhythm and the two charts; then the tables, each in a section
(ui/reveal.py): burns per satellite, open, and every burn in the window, closed.
"""
from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st

from ui import data, measures, reveal, shell, surfaces, time_range, tooltip
from ui.figures.burns import EAST_WEST, burn_cadence, burn_timeline, rhythm

PATTERN_STATUS = {"regular": "ok", "irregular": "warn", "too few": "idle"}
CHART = {"use_container_width": True, "config": {"displayModeBar": False}}


def _chosen():
    """{constellation: [satellite, ...]} for the top bar's choice. Compare reuses the picks (ui.picker)."""
    if not st.session_state["compare"]:
        return {st.session_state["scope"]: None}
    picks = st.session_state.get("compare_picks", {})
    return {name: picks[name] for name in shell.CONSTELLATIONS if picks.get(name)}


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


def _detection(p):
    """How a burn is found, with the thresholds in use, behind a pill."""
    return tooltip.tip("How a burn is found",
                       f"A burn is found where the orbit's size jumps by {p['sma_threshold']:g} km or more "
                       f"(east-west) or its tilt by {p['inc_threshold']:g}° or more (north-south), standing out at a "
                       f"z-score of {p['z_threshold']:g} and holding for {int(p['persist_window'])} element sets.",
                       pill=True)


def _counts(results, chosen, window_days, today):
    """Burns in the window and the score's pattern, one row per satellite shown, and the burns in the window."""
    rows, recent, start = [], [], today - pd.Timedelta(days=window_days)
    for name, result in results.items():
        window = measures.in_window(result["history"], window_days, today)
        burns = result["burns"][pd.to_datetime(result["burns"]["window_end"]) >= start]
        health = {str(h["Satellite"]): h for h in result["health"].to_dict("records")}
        for satellite in chosen[name] or list(dict.fromkeys(result["history"]["satellite"])):
            own = pd.to_datetime(window.loc[window["satellite"] == satellite, "EPOCH"])
            days = (own.max() - own.min()).days if len(own) else None
            rows.append((satellite, measures.burn_row(satellite, burns, days, health.get(satellite))))
            recent.append(burns[burns["satellite"] == satellite])
    return rows, pd.concat(recent, ignore_index=True)


def _events(burns):
    """Every burn in the window, newest first: which satellite, when, which kind, and how much the orbit changed.
    The change that kind of burn makes is drawn in the accent colour."""
    cell, rows = measures.cell, []
    for b in burns.sort_values("window_end", ascending=False).to_dict("records"):
        end, east_west = pd.Timestamp(b["window_end"]), b["kind"] == EAST_WEST
        rows.append((b["satellite"], [cell(f"{end.day} {end:%b %Y %H:%M}"), cell(b["kind"]),
                                      cell(f"{b['d_sma_km']:+.3f} km", status="accent" if east_west else "idle"),
                                      cell(f"{b['d_inc_deg']:+.4f}°", status="idle" if east_west else "accent")]))
    return surfaces.table([("Satellite", ""), ("Found at (UTC)", "End of the window it fell in"), ("Kind", ""),
                           ("Size change", "Semi-major axis"), ("Tilt change", "Inclination")], rows)


chosen = _chosen()
if not chosen:
    surfaces.show('<p class="small">Pick satellites on the Overview to compare.</p>')
    st.stop()
try:
    results = {name: data.load(name, st.session_state["window_days"], st.session_state["params"]) for name in chosen}
except ValueError as error:
    surfaces.show(surfaces.notice(str(error), "warn"))
    st.stop()

for name, result in results.items():   # GPS, GLONASS and Galileo: how much history the burns are looked for in
    if "history_note" in result:
        surfaces.show(surfaces.notice(
            f"{name}. {result['history_note']} Burns show here once weeks of it have built up.", "idle"))
results = {name: result for name, result in results.items()
           if "history_note" not in result or not result["burns"].empty}
if not results:
    st.stop()

satellites, burns, epochs = [], [], []
for name, result in results.items():
    mine = chosen[name] or list(dict.fromkeys(result["history"]["satellite"]))
    satellites += mine
    burns.append(result["burns"][result["burns"]["satellite"].isin(mine)])
    epochs.append(pd.to_datetime(result["history"]["EPOCH"]))
burns = pd.concat(burns, ignore_index=True)
start, end = min(e.min() for e in epochs), max(e.max() for e in epochs)

window_days = st.session_state["window_days"]
counts, recent = _counts(results, chosen, window_days, pd.Timestamp(datetime.now(timezone.utc).date()))

surfaces.show(surfaces.group_head(time_range.words(window_days),
                                  f"{len(recent)} burns: {(recent['kind'] == EAST_WEST).sum()} east-west, "
                                  f"{(recent['kind'] != EAST_WEST).sum()} north-south",
                                  _detection(measures.thresholds(None, st.session_state["params"]))))
surfaces.show(_rhythm(rhythm(burns, satellites, end)))
st.plotly_chart(burn_cadence(burns, satellites), **CHART)
st.plotly_chart(burn_timeline(burns, satellites, start, end), **CHART)
late = sum(any(c["status"] == "warn" for c in cells) for _, cells in counts)
reveal.section("burns_per_satellite", "Burns per satellite",
               f"{reveal.count(len(counts), 'satellite')} · " + (f"{late} overdue" if late else "none overdue"),
               surfaces.table([("Satellite", "")] + measures.BURN_COLUMNS, counts), open=True)
if len(recent):
    newest = pd.Timestamp(recent["window_end"].max())
    reveal.section("every_burn", "Every burn in the window",
                   f"{reveal.count(len(recent), 'burn')} · newest {newest.day} {newest:%b %Y}", _events(recent))
