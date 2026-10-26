"""Overview: is each satellite healthy and in its slot? One constellation, or satellites picked across constellations.

The count first, then the tiles grouped by orbit type and the slot picture; then the details, each in a section
(ui/reveal.py): per orbit type a table of what each measure is against what it should be, open, then what the checks
found and how each satellite was classed, closed.
"""
import re
from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st

from config.config import MEO_SATS, TRACKED_NOT_IN_REGISTRY
from evidence.registry_tables import new_on_dashboard
from ui import data, limits, measures, meo_overview, orbit_age, orbit_section, palette, reveal, shell, surfaces, time_range, tooltip
from ui.data import SATELLITES
from ui.figures.constellation_3d import slot_legend
from ui.figures.slot_rows import as_number, slot_words
from ui.orbit_section import CHIP_STATUS, PARTS
from ui.picker import picker
HEALTHY_FROM = 80
STATUS_CHIP = {"Healthy": "ok", "Fair": "warn", "Degraded": "bad", "Critical": "bad"}
EMOJI = re.compile(r"[\u2100-\u23FF\u2460-\u27BF\U0001F000-\U0001FAFF\uFE0F]\s?")   # the remarks' status signs; the words stay
CLASS_COLUMNS = [("Satellite", ""), ("Type", "From the mean tilt"), ("Mean inclination", "In the window"),
                 ("Mean height", "In the window"), ("Drift now", "Per day")]


def _tile(health, slot):
    """(tile html, whether it counts as healthy and in its slot) for one health row and its slot row."""
    score = as_number(health.get("Overall Score"))
    scored = [(label, as_number(health.get(column))) for label, column in PARTS]
    scored = [part for part in scored if part[1] is not None]
    state = slot["state"] if slot else palette.SLOT_UNKNOWN
    html = surfaces.tile(
        str(health["Satellite"]), str(health.get("Type", "")), score,
        re.sub(r"^[^A-Za-z]+", "", str(health.get("Health Status", ""))),
        slot_words(slot), CHIP_STATUS[state], min(scored, key=lambda part: part[1]) if scored else None)
    return html, score is not None and score >= HEALTHY_FROM and state == palette.SLOT_IN


def _tiles(result):
    """Everything the page draws from one constellation's result.

    Returns {name: (tile html, counts as healthy, health row or None)} in the order shown, and the slot rows
    (with the satellites set aside) for the picture. Satellites set aside have no health row.
    """
    positions_rows = orbit_section.attempt("slot rows", orbit_section.positions_and_rows, result["health"],
                                           result["set_aside"], orbit_section.designated_longitude, result["history"])
    rows = positions_rows[1] if positions_rows else []
    slots = {row["name"]: row for row in rows}
    tiles = {}
    for health in result["health"].to_dict("records"):
        html, healthy = _tile(health, slots.get(str(health["Satellite"])))
        tiles[str(health["Satellite"])] = (html, healthy, health)
    for name in result["set_aside"]:
        html = surfaces.tile(name, slot=palette.SLOT_LEFT, slot_status=CHIP_STATUS[palette.SLOT_LEFT])
        tiles[name] = (html, False, None)
    return tiles, rows


def _grid(htmls):
    surfaces.show(f'<div class="tiles">{"".join(htmls)}</div>')


def _gaps(constellation, result, today):
    """Notices for what is missing, so that nothing is left out in silence."""
    if new := new_on_dashboard(constellation, today):
        surfaces.show(surfaces.notice(new, "accent"))
    shown = set(result["health"]["Satellite"]) | set(result["set_aside"])
    no_data = [name for name, norad in SATELLITES[constellation].items() if norad is not None and name not in shown]
    unlisted = TRACKED_NOT_IN_REGISTRY[constellation]
    for text in (*result["warnings"],
                 *([f"No orbit data: {', '.join(no_data)}"] if no_data else []),
                 *([f"Awaiting a registry update: {', '.join(unlisted)}"] if unlisted else []),
                 *([f"Scored on four parts, no current position against the slot: {', '.join(unplaced)}"]
                   if (unplaced := _unplaced(result["health"])) else [])):
        surfaces.show(surfaces.notice(text, "warn"))


def _unplaced(health):
    """Satellites with a slot but no longitude score: their overall score uses the other four parts."""
    return [str(h["Satellite"]) for h in health.to_dict("records")
            if as_number(h.get("Designated Lon (°)")) is not None and as_number(h.get("Lon Deviation Score")) is None]


def _period(result, window, window_days, today):
    """Status counts, the window and its records, the year the scores read, and how the score is made."""
    chips = "".join(surfaces.chip(f"{n} {word.lower()}", STATUS_CHIP[word])
                    for word, n in measures.status_counts(result["health"]))
    start = today - pd.Timedelta(days=window_days)
    spans = [str(p).split(" to ") for p in result["health"].get("Pattern Analysis Period", []) if " to " in str(p)]
    year = (f'<span>scores read {_day(min(a for a, _ in spans))} to {_day(max(b for _, b in spans))}</span>'
            if spans else "")
    shown = window[~window["satellite"].isin(result["set_aside"])]
    legend = tooltip.legend(
        [("var(--fill)", f"{label} {weight}%") for label, weight in limits.SCORE_WEIGHTS]
        + [(f"var(--{STATUS_CHIP[word]})", f"{word} from {low}" if low else f"{word} under {limits.STATUS_FROM[i - 1][1]}")
           for i, (word, low) in enumerate(limits.STATUS_FROM)], label="How the score is made")
    surfaces.show(f'<div class="facts">{chips}<span>{time_range.words(window_days)}: {_day(start)} to {_day(today)}</span>'
                  f'<span>{len(shown):,} orbit records</span>{year}{legend}</div>')


def _day(value):
    day = pd.Timestamp(value)
    return f"{day.day} {day:%b %Y}"


def _types(names, result, classes):
    """{satellite: orbit type} for `names`: the health row's type, else (set aside) the type its mean tilt gives."""
    of = {str(h["Satellite"]): str(h.get("Type")) for h in result["health"].to_dict("records")}
    by_tilt = {c["satellite"]: c["type"] for c in classes}
    return {n: of.get(n) or by_tilt.get(n, "Unclassified") for n in names}


def _table_rows(chosen, params, window):
    """(name, cells) for each (constellation, result, health row), with the drift spread over the window."""
    spread = measures.spreads(window)
    return [(str(h["Satellite"]), measures.row(h, c, params, r["history"], spread.get(str(h["Satellite"]))))
            for c, r, h in chosen]


def _measures(key, rows, title="Measured against limits"):
    """The "Measured against limits" table in its section, open (the page's main table), the summary saying how many
    satellites need a look."""
    look = sum(any(c["status"] in ("warn", "bad") for c in cells) for _, cells in rows)
    summary = f"{reveal.count(len(rows), 'satellite')} · " + (f"{look} need{'s' if look == 1 else ''} a look" if look
                                                              else "all within limits")
    reveal.section(key, title, summary, surfaces.table([("Satellite", "")] + measures.COLUMNS, rows), open=True)


def _findings(health_row):
    """One satellite's findings, one line each, as the health assessment wrote them, without the status signs."""
    lines = [EMOJI.sub("", part).strip() for part in str(health_row.get("Remarks", "")).split(" | ")]
    return [line for line in lines if line]


def _remarks(health):
    """Each satellite's findings, one line each."""
    items = ""
    for h in health.to_dict("records"):
        items += (f"<li><b>{escape(str(h['Satellite']))}</b>"
                  + "".join(f"<span>{escape(line)}</span>" for line in _findings(h)) + "</li>")
    return f'<ul class="remarks">{items}</ul>'


def _classes_table(classes):
    cell = measures.cell
    rows = [(c["satellite"], [cell(c["type"]),
                              cell("–" if c["tilt"] is None else f"{c['tilt']:.3f}°"),
                              cell("–" if c["height"] is None else f"{c['height']:,.1f} km"),
                              cell("–" if c["drift"] is None else f"{c['drift']:+.4f}°")]) for c in classes]
    return surfaces.table(CLASS_COLUMNS, rows)


def _slot_picture(rows, result, name):
    """The slots against their satellites, flat or in 3D."""
    switch, legend = st.columns([1, 1], vertical_alignment="center")
    with switch:
        view = shell.segment("slot_view", ["Flat", "3D"], label="View")
    if view == "Flat":   # the 3D view carries its own key under the picture
        legend.html(f'<div class="right">{tooltip.legend(slot_legend(), "Slot legend")}</div>')
    orbit_section.render_belt(rows, view, result["history"], result["health"], name)


def constellation(name, window_days, params):
    """One constellation: the count, the tiles per orbit type, the slot picture, then the details: each orbit type's
    table, what the checks found, how each satellite was classed."""
    result = data.load(name, window_days, params)
    if name in MEO_SATS:   # judged by orbital plane, not longitude slot
        meo_overview.page(name, result)
        return
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    window = measures.in_window(result["history"], window_days, today)
    classes = measures.classified(window, name)
    tiles, rows = _tiles(result)
    healthy = sum(healthy for _, healthy, _ in tiles.values())
    surfaces.show(f'<div class="head"><span class="big num">{healthy} of {len(tiles)}</span>'
                  '<span class="muted">healthy and in their slot</span></div>')
    _period(result, window, window_days, today)
    orbit_age.show(name, result)
    _gaps(name, result, today.date())
    groups = measures.grouped(_types(tiles, result, classes))
    for kind, names in groups.items():
        count = f"{len(names)} satellite{'s' if len(names) > 1 else ''}"
        surfaces.show(surfaces.group_head(kind, " · ".join(filter(None, [count, limits.ORBIT_TYPES.get(kind)]))))
        _grid(tiles[n][0] for n in names)
    if rows:
        _slot_picture(rows, result, name)
    for kind, names in groups.items():
        scored = [(name, result, tiles[n][2]) for n in names if tiles[n][2] is not None]
        if scored:
            _measures(f"overview_measures_{kind}", _table_rows(scored, params, window), f"Measured against limits: {kind}")
    found = sum(len(_findings(h)) for h in result["health"].to_dict("records"))
    reveal.section("overview_checks", "What the checks found",
                   f"{reveal.count(len(result['health']), 'satellite')} · {reveal.count(found, 'finding')}",
                   _remarks(result["health"]))
    kinds = measures.grouped({c["satellite"]: c["type"] for c in classes})
    reveal.section("overview_classes", "How each satellite was classed",
                   " · ".join(f"{len(n)} {kind}" for kind, n in kinds.items()), _classes_table(classes))


def compare(window_days, params):
    """Satellites picked across constellations: their tiles side by side, then their score parts in step."""
    chosen, measured = [], []
    picks = picker()
    for name, picked in picks.items():
        result = data.load(name, window_days, params)
        tiles = meo_overview.tiles(result) if name in MEO_SATS else _tiles(result)[0]
        chosen += [(s, *tiles[s]) for s in picked if s in tiles]
        if name not in MEO_SATS:   # the limits table is for slot-keeping satellites
            measured += [(name, result, tiles[s][2]) for s in picked if s in tiles and tiles[s][2] is not None]
    if not chosen:
        surfaces.show('<p class="small">Add satellites to compare.</p>')
        return
    parts = PARTS + (meo_overview.PARTS if set(picks) & set(MEO_SATS) else [])
    scores = [[as_number(health.get(column)) if health else None for _, column in parts] for *_, health in chosen]
    rows = [(label, [column[i] for column in scores]) for i, (label, _) in enumerate(parts)]
    surfaces.show(surfaces.compare_grid([html for _, html, _, _ in chosen], surfaces.parts_matrix(rows)))
    if measured:
        today = pd.Timestamp(datetime.now(timezone.utc).date())
        window = pd.concat([measures.in_window(r["history"], window_days, today) for _, r, _ in measured])
        _measures("compare_measures", _table_rows(measured, params, window))


try:
    if st.session_state["compare"]:
        compare(st.session_state["window_days"], st.session_state["params"])
    else:
        constellation(st.session_state["scope"], st.session_state["window_days"], st.session_state["params"])
except ValueError as error:
    surfaces.show(surfaces.notice(str(error), "warn"))
