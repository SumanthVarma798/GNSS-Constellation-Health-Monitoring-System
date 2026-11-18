"""Station-keeping: how often each satellite's orbit is corrected, and whether the rhythm holds.

The burns in the window first, then each satellite's rhythm and the burn timeline; then the tables, each in a section
(ui/reveal.py): burns per satellite, open, and every burn in the window, closed.
"""
from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st

from ui import data, forecast_explainer, measures, next_step, next_step_data, reveal, surfaces, time_range, tooltip
from ui.figures import forecast_marks
from ui.figures.burns import EAST_WEST, burn_timeline, rhythm
from ui.picker import chosen_constellations

PATTERN_STATUS = {"regular": "ok", "irregular": "warn", "too few": "idle"}
CHART = {"use_container_width": True, "config": {"displayModeBar": False}}


def _days(value):
    return f"{abs(value):.0f} d"


def _burn_cell(cell, label):
    """One of the table's two forecast cells: the date, then the size of the change."""
    words, detail, tone = cell
    return f'<span class="due {tone}" data-l="{label}">{words}' + (f'<small class="muted">{detail}</small>' if detail else "") + "</span>"


def _cycle(row):
    """How far the satellite is into its cycle: elapsed fill, the usual window (middle half of intervals) as a band,
    the median as a tick. The fill turns amber once the usual window has passed."""
    if row["due_in_days"] is None:
        return '<span class="cycle"></span>'
    scale = max(row["q3_days"], row["since_days"]) * 1.08
    at = lambda days: f"{100 * days / scale:.1f}%"
    return (f'<span class="cycle{" late" if row["late"] else ""}"><em style="left:{at(row["q1_days"])};width:{at(row["q3_days"] - row["q1_days"])}"></em>'
            f'<i style="width:{at(row["since_days"])}"></i><b style="left:{at(row["median_days"])}"></b></span>')


def _rhythm(rows, cells):
    """One line per satellite, soonest due first: its usual interval, where it is in this cycle, its ideal burn and its
    last chance (ui/next_step.py burn_cells, from today's elements)."""
    lines = ['<div class="rh hd"><span></span><span>East-west, every</span><span>This cycle</span>'
             '<span>Ideal burn</span><span>Last chance</span><span>North-south</span></div>']
    for row in sorted(rows, key=lambda r: (r["due_in_days"] is None, r["due_in_days"] or 0)):
        ideal, last = cells.get(row["satellite"], [("–", "", "idle")] * 2)
        every = ('<span class="muted">&ndash;</span>' if row["median_days"] is None else
                 f'<b class="num">{row["median_days"]:.0f} days</b>')
        north_south = f'<span class="num">{row["ns_count"]}</span>' if row["ns_count"] else '<span class="muted">&ndash;</span>'
        lines.append(f'<div class="rh"><b>{escape(row["satellite"])}</b>'
                     f'<span class="ev">{every}{surfaces.chip(row["pattern"], PATTERN_STATUS[row["pattern"]])}</span>'
                     f'{_cycle(row)}{_burn_cell(ideal, "Ideal burn")}{_burn_cell(last, "Last chance")}{north_south}</div>')
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


# cache_resource, not cache_data: a pickled Plotly figure is checked over again as it is read back, which costs what
# building it did. The figure is never changed after it is made.
@st.cache_resource(show_spinner=False, max_entries=16)
def _timeline(burns, satellites, start, end):
    """The burn timeline, made once per set of burns: on Render's share of a CPU it takes seconds to build."""
    return burn_timeline(burns, satellites, start, end)



def _events(recent, satellites, rhythm_rows):
    """Every burn in the window, one group per satellite in the timeline's order. Each group opens with the satellite's
    name, its burns by kind and its last one, marked late as the timeline marks it; then its burns, newest first: the
    timeline's mark for the kind, when it was found, and how much the orbit's size and tilt changed. The change that
    kind of burn makes is set in bold, the other muted."""
    late = {r["satellite"]: r["late"] for r in rhythm_rows}
    lines = ['<div class="bl-row bl-hd"><span>Kind</span><span>Found at (UTC)<small>End of the window it fell in</small>'
             '</span><span>Size change<small>Semi-major axis</small></span><span>Tilt change<small>Inclination</small>'
             '</span></div>']
    for name in satellites:
        own = recent[recent["satellite"] == name].sort_values("window_end", ascending=False)
        if own.empty:
            continue
        ew, last = int((own["kind"] == EAST_WEST).sum()), pd.Timestamp(own["window_end"].iloc[0])
        lines.append(f'<div class="bl-sat"><b>{escape(name)}</b><span class="muted">{reveal.count(len(own), "burn")}: '
                     f'{ew} east-west, {len(own) - ew} north-south · last {last.day} {last:%b %Y}</span>'
                     f'{surfaces.chip("late", "warn") if late.get(name) else ""}</div>')
        for b in own.to_dict("records"):
            end, east_west = pd.Timestamp(b["window_end"]), b["kind"] == EAST_WEST
            lines.append(f'<div class="bl-row"><span class="kd"><i class="mk {"ew" if east_west else "ns"}"></i>'
                         f'<span>{escape(b["kind"])}</span></span>'
                         f'<span class="num">{end.day} {end:%b %Y} <span class="t">{end:%H:%M}</span></span>'
                         f'<span class="num{" on" if east_west else ""}">{b["d_sma_km"]:+.3f} km</span>'
                         f'<span class="num{"" if east_west else " on"}">{b["d_inc_deg"]:+.4f}°</span></div>')
    return '<div class="bl">' + "".join(lines) + "</div>"


chosen = chosen_constellations()
if not chosen:
    surfaces.show('<p class="small">Pick satellites on the Overview to compare.</p>')
    st.stop()
try:
    results = {name: data.load(name, st.session_state["window_days"], st.session_state["params"]) for name in chosen}
except ValueError as error:
    surfaces.show(surfaces.notice(str(error), "warn", inline=True))
    st.stop()

kept = {name: result for name, result in results.items()
        if "history_note" not in result or not result["burns"].empty}
for name, result in results.items():   # the MEO systems: how much history the burns are looked for in
    if "history_note" in result:   # in the page when nothing else is left to show, else in the inbox
        surfaces.show(surfaces.notice(
            f"{name}. {result['history_note']} Burns show here once weeks of it have built up.", "idle",
            inline=not kept))
results = kept
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
rhythm_rows = rhythm(burns, satellites, end)
try:
    ahead = {name: next_step_data.look_ahead(name, result, st.session_state["params"]) for name, result in results.items()}
except Exception as error:   # the look ahead is extra: the page's own tables and timeline stand without it
    ahead = {}
    surfaces.show(surfaces.notice(f"Next steps could not be worked out: {type(error).__name__}: {error}", "warn"))
forecasts = {n: f for a in ahead.values() for n, f in a.get("forecasts", {}).items()}
fuel = {n: f for a in ahead.values() for n, f in a.get("fuel", {}).items()}
now = next((a["now"] for a in ahead.values()), None)
forecast_cells = {n: next_step.burn_cells(f, now) for n, f in forecasts.items()}
for name, result in results.items():   # what should happen next, once for each constellation shown
    if name in ahead and "forecasts" in ahead[name]:
        text, tone, as_of = next_step.constellation_line(list(ahead[name]["forecasts"].values()), now)
        surfaces.show(next_step.line_html((f"{name}: {text}" if len(results) > 1 else text, tone, as_of)))
surfaces.show(_rhythm(rhythm_rows, forecast_cells))
st.plotly_chart(forecast_marks.add_expected(_timeline(burns, satellites, start, end),
                                            next_step.expected_burns({n: forecasts[n] for n in satellites if n in forecasts}, now)
                                            if now is not None else [], satellites, end), **CHART)
late = sum(any(c["status"] == "warn" for c in cells) for _, cells in counts)
reveal.section("burns_per_satellite", "Burns per satellite",
               f"{reveal.count(len(counts), 'satellite')} · " + (f"{late} overdue" if late else "none overdue"),
               surfaces.table([("Satellite", "")] + measures.BURN_COLUMNS, counts), open=True)
if len(recent):
    newest = pd.Timestamp(recent["window_end"].max())
    reveal.section("every_burn", "Every burn in the window",
                   f"{reveal.count(len(recent), 'burn')} · newest {newest.day} {newest:%b %Y}", _events(recent, satellites, rhythm_rows))

if forecasts:
    lines = "".join(f'<li><b>{escape(n)}</b> {escape(next_step.fuel_line(fuel.get(n)) or "no yearly use worked out: too little history")}'
                    + (f'<br><span class="small">{escape(ns)}</span>' if (ns := next_step.north_south_line(forecasts[n], now)) else "")
                    + "</li>" for n in satellites if n in forecasts)
    reveal.section("fuel_per_satellite", "Fuel and north-south, per satellite",
                   f"{reveal.count(sum(n in forecasts for n in satellites), 'satellite')} · yearly use, and years left typical for the class",
                   f'<ul class="small meanings">{lines}</ul>')
reveal.section("forecast_how", "How these forecasts are made", forecast_explainer.ONE_LINE, forecast_explainer.body())
