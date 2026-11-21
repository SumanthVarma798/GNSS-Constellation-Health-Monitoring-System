"""Overview: is each satellite healthy and in its slot? One constellation, or satellites picked across constellations.

The count first, then the tiles grouped by orbit type and the slot picture; then the details, each in a section
(ui/reveal.py): per orbit type a table of what each measure is against what it should be, open, then what the checks
found (ui/checks.py) and how each satellite was classed, closed. What is missing or left out goes to the notices
inbox (ui/notices.py), not the page.
"""
import re
from html import escape
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from analysis.commissioning import SETTLING_DAYS
from config.config import TRACKED_NOT_IN_REGISTRY
from evidence.registry_tables import judged_by_plane, left_out_notice, new_on_dashboard
from ui import (burn_ledger, checks, data, limits, measures, meo_overview, official_status, orbit_age, orbit_section,
                marks, next_step_data, palette, reveal, shell, signals_view, surfaces, systems, three_measures, time_range, tooltip)
from ui.data import SATELLITES
from ui.figures.constellation_3d import slot_legend
from ui.figures.slot_rows import as_number, slot_words
from ui.orbit_section import CHIP_STATUS, PARTS
from ui.overview_settings import SLOT_CONFIRM, SLOT_CONFIRM_WHY
from ui.picker import picker
from ui.system_summary import _stage, in_slot_and_healthy, summary, whole
CLASS_COLUMNS = [("Satellite", ""), ("Type", "From the mean inclination: GEO under 10°"),
                 ("Mean inclination", "Over the window"), ("Mean altitude", "Over the window"),
                 ("Longitude drift rate", "Newest, degrees a day")]


def _tile(health, slot, age_html="", name_html="", confirm=False):
    """(tile html, whether it counts as healthy and in its slot) for one health row and its slot row."""
    score = as_number(health.get("Overall Score"))
    scored = [(label, as_number(health.get(column))) for label, column in PARTS]
    scored = [part for part in scored if part[1] is not None]
    state = slot["state"] if slot else palette.SLOT_UNKNOWN
    html = surfaces.tile(
        str(health["Satellite"]), str(health.get("Type", "")), score,
        re.sub(r"^[^A-Za-z]+", "", str(health.get("Health Status", ""))),
        SLOT_CONFIRM if confirm else slot_words(slot), "idle" if confirm else CHIP_STATUS[state],
        min(scored, key=lambda part: part[1]) if scored else None, age_html=age_html, name_html=name_html)
    return html, in_slot_and_healthy(score, state)


def _tiles(result, tags=None, name_marks=None, confirm=()):
    """Everything the page draws from one constellation's result.

    Returns {name: (tile html, counts as healthy, health row or None)} in the order shown, and the slot rows
    (with the satellites set aside) for the picture. Satellites set aside have no health row. name_marks:
    {satellite: a mark after its name} (the clock record's); confirm: the satellites whose slot is to confirm, said so
    on their tile and in the slot picture instead of "off its slot".
    """
    positions_rows = orbit_section.attempt("slot rows", orbit_section.positions_and_rows, result["health"],
                                           result["set_aside"], orbit_section.designated_longitude, result["history"])
    rows = [{**row, "confirm": row["name"] in confirm} for row in (positions_rows[1] if positions_rows else [])]
    slots = {row["name"]: row for row in rows}
    tags, name_marks = tags or {}, name_marks or {}
    tiles = {}
    for health in result["health"].to_dict("records"):
        name = str(health["Satellite"])
        tiles[name] = (*_tile(health, slots.get(name), tags.get(name, ""), name_marks.get(name, ""), name in confirm),
                       health)
    for name in result["set_aside"]:
        html = surfaces.tile(name, slot=palette.SLOT_LEFT, slot_status=CHIP_STATUS[palette.SLOT_LEFT],
                             age_html=tags.get(name, ""), name_html=name_marks.get(name, ""))
        tiles[name] = (html, False, None)
    for name in result.get("moving", {}):
        html = surfaces.tile(name, slot=_stage(result, name), slot_status="accent", unscored="new, not scored yet",
                             age_html=tags.get(name, ""), name_html=name_marks.get(name, ""))
        tiles[name] = (html, False, None)
    return tiles, rows


def _grid(htmls):
    surfaces.show(f'<div class="tiles">{"".join(htmls)}</div>')


def _gaps(constellation, result, today):
    """Notices for what is missing, so that nothing is left out in silence."""
    if new := new_on_dashboard(constellation, today):
        surfaces.show(surfaces.notice(new, "accent"))
    if left := left_out_notice(constellation):
        surfaces.show(surfaces.notice(left, "accent"))
    moving = result.get("moving", {})
    if moving:
        named = ", ".join(f"{name} ({_stage(result, name)}, first orbit record {_day(since)})" for name, since in moving.items())
        surfaces.show(surfaces.notice(
            f"New and not scored yet: {named}. A new satellite is raised "
            "and drifted along the belt for weeks, so its drift and burns are expected. It is left out of the scores until "
            f"it has been parked {SETTLING_DAYS} days.", "accent"))
    shown = set(result["health"]["Satellite"]) | set(result["set_aside"]) | set(moving)
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


def _meta(result, window, window_days, today):
    """A small muted chip for the window ("90 d · 1,381 records"), its dates and the year the scores read in the shared
    tooltip."""
    start = today - pd.Timedelta(days=window_days)
    spans = [str(p).split(" to ") for p in result["health"].get("Pattern Analysis Period", []) if " to " in str(p)]
    shown = window[~window["satellite"].isin([*result["set_aside"], *result.get("moving", {})])]
    items = [("", "Window", f"{_day(start)} to {_day(today)}"), ("", "Orbit records", f"{len(shown):,}")]
    if spans:
        items.append(("", "Scores read", f"{_day(min(a for a, _ in spans))} to {_day(max(b for _, b in spans))}"))
    return tooltip.tip_html(surfaces.chip(f"{window_days} d · {len(shown):,} records", "idle"),
                            tooltip.glance(time_range.words(window_days), items), key="overview_meta")


def _day(value):
    day = pd.Timestamp(value)
    return f"{day.day} {day:%b %Y}"


def _types(names, result, classes):
    """{satellite: orbit type} for `names`: the health row's type, else (set aside) the type its mean tilt gives."""
    of = {str(h["Satellite"]): str(h.get("Type")) for h in result["health"].to_dict("records")}
    by_tilt = {c["satellite"]: c["type"] for c in classes}
    return {n: of.get(n) or by_tilt.get(n, "Unclassified") for n in names}


def _table_rows(chosen, params, window, confirm=None):
    """(name, cells) for each (constellation, result, health row), with the drift spread over the window. confirm:
    {satellite: degrees kept from the slot in our table} for those whose slot is to confirm: their mean longitude says
    so instead of "outside"."""
    spread, confirm = measures.spreads(window), confirm or {}
    out = []
    for c, r, h in chosen:
        name = str(h["Satellite"])
        cells = measures.row(h, c, params, r["history"], spread.get(name))
        if name in confirm:
            lon = cells[2]
            cells[2] = {**lon, "status": "idle", "word": "to confirm",
                        "note": " · ".join(filter(None, [lon["note"], SLOT_CONFIRM_WHY.format(off=confirm[name])]))}
        out.append((name, cells))
    return out


def _measures(key, rows, title="Measured against limits"):
    """The "Measured against limits" table in its section, open (the page's main table), the summary saying how many
    satellites need a look."""
    look = sum(any(c["status"] in ("warn", "bad") for c in cells) for _, cells in rows)
    summary = f"{reveal.count(len(rows), 'satellite')} · " + (f"{look} need{'s' if look == 1 else ''} a look" if look
                                                              else "all within limits")
    reveal.section(key, title, summary, surfaces.table([("Satellite", "")] + measures.COLUMNS, rows, head_tips=True),
                   open=True)


def _classes_table(classes):
    cell = measures.cell
    rows = [(c["satellite"], [cell(c["type"]),
                              cell("–" if c["tilt"] is None else f"{c['tilt']:.3f}°"),
                              cell("–" if c["height"] is None else f"{c['height']:,.1f} km"),
                              cell("–" if c["drift"] is None else f"{c['drift']:+.4f}°")]) for c in classes]
    return surfaces.table(CLASS_COLUMNS, rows, head_tips=True)


def _slot_picture(rows, result, name):
    """The slots against their satellites, flat or in 3D."""
    switch, legend = st.columns([1, 1], vertical_alignment="center")
    with switch:
        view = shell.segment("slot_view", ["Flat", "3D"], label="View")
    if view == "Flat":   # the 3D view carries its own key under the picture
        confirm = [(palette.IDLE, f"{SLOT_CONFIRM}: kept steadily off the slot in our table; drawn with a ?")]
        legend.html(f'<div class="right">{tooltip.legend(slot_legend() + confirm, "Slot legend")}</div>')
    orbit_section.render_belt(rows, view, result["history"], result["health"], name)


def _system_line(name, window_days, params):
    """For one part of a system with several (ui/systems.py): the whole system's count, then each part's, so the part
    below is read as a part. "" for a system that is one part. The other parts are counted at the default limits."""
    system = systems.system_of(name)
    if len(systems.SYSTEMS[system]) == 1:
        return ""
    read = []
    for part in systems.SYSTEMS[system]:
        try:
            read.append(summary(part, data.load(part, window_days, params if part == name else None), data.orbit_gap()))
        except Exception:   # that part's own page says why it cannot be read
            pass
    both = whole(system, read)
    chips = "".join(surfaces.chip(f"{label} {count} of {of}", "accent" if label == systems.part_name(name) else "idle")
                    for label, count, of in both["parts"])
    score = (surfaces.chip(f"{system} score {both['score']} of 100", surfaces.band(both["score"]))
             if both["score"] is not None else "")   # the same number as Home's card
    return (f'<div class="sysline"><b>{marks.mark(system)}{escape(system)}</b>{score}<span class="num">{both["healthy"]} of {both["total"]}</span>'
            f'<span class="muted">healthy and in place, across its parts</span>{chips}</div>'
            + three_measures.part_scores(both, systems.part_name(name)))


def _next_step(name, result, params):
    """Show the constellation's "what should happen next" line; return ({satellite: tile line} for the tiles,
    {satellite: degrees kept from its table slot} for those whose slot is to confirm). The look ahead is extra: when it
    fails the page stands without it and the inbox says so."""
    try:
        surfaces.show(next_step_data.outlook_html(name, result, params))
        forecasts = next_step_data.look_ahead(name, result, params).get("forecasts", {})
        confirm = {n: abs((f["station_lon"] - f["slot"] + 180) % 360 - 180)
                   for n, f in forecasts.items() if f.get("confirm")}
        return next_step_data.tile_tags(name, result, params), confirm
    except Exception as error:
        surfaces.notice(f"Next steps could not be worked out: {type(error).__name__}: {error}", "warn")
        return {}, {}


def constellation(name, window_days, params):
    """One constellation: one header (the score, the count, the scores' bar, the burn record), the tiles per orbit
    type, the slot picture, then the details: each orbit type's table, what the checks found, how each satellite was
    classed."""
    result = data.load(name, window_days, params)
    surfaces.show(_system_line(name, window_days, params))
    ahead, confirm = _next_step(name, result, params)   # what should happen next, under the system line
    measured = summary(name, result, data.orbit_gap())
    if judged_by_plane(name):   # judged by orbital plane, not longitude slot
        meo_overview.page(name, result, measured)
        three_measures.section(measured)
        return
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    window = measures.in_window(result["history"], window_days, today)
    classes = measures.classified(window, name)
    tags = orbit_age.tags(name, result)
    for satellite, html in ahead.items():   # a short line on the tile of each satellite with something due soon
        tags[satellite] = tags.get(satellite, "") + html
    tiles, rows = _tiles(result, tags, three_measures.clock_marks(name), confirm)
    healthy = sum(healthy for _, healthy, _ in tiles.values())
    surfaces.show(three_measures.header(measured, healthy, len(tiles) - len(result.get("moving", {})),
                                        "healthy and in their slot", _meta(result, window, window_days, today),
                                        official_status.line(name))
                  + three_measures.states(result["health"]) + burn_ledger.bar(measured.get("burn_record")))
    orbit_age.show(name, result)
    signals_view.show(name)
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
            _measures(f"overview_measures_{kind}", _table_rows(scored, params, window, confirm),
                      f"Measured against limits: {kind}")
    grouped = checks.by_outcome(result["health"])
    reveal.section("overview_checks", "What the checks found", checks.summary(grouped, len(result["health"])),
                   checks.body(grouped))
    kinds = measures.grouped({c["satellite"]: c["type"] for c in classes})
    reveal.section("overview_classes", "How each satellite was classed",
                   " · ".join(f"{len(n)} {kind}" for kind, n in kinds.items()), _classes_table(classes))
    three_measures.section(measured)


def compare(window_days, params):
    """Satellites picked across constellations: their tiles side by side, then their score parts in step."""
    chosen, measured = [], []
    picks = picker()
    for name, picked in picks.items():
        result = data.load(name, window_days, params)
        tags = orbit_age.tags(name, result)
        tiles = meo_overview.tiles(result, tags) if judged_by_plane(name) else _tiles(result, tags)[0]
        chosen += [(s, *tiles[s]) for s in picked if s in tiles]
        if not judged_by_plane(name):   # the limits table is for slot-keeping satellites
            measured += [(name, result, tiles[s][2]) for s in picked if s in tiles and tiles[s][2] is not None]
    if not chosen:
        surfaces.show('<p class="small">Add satellites to compare.</p>')
        return
    parts = PARTS + (meo_overview.PARTS if any(judged_by_plane(name) for name in picks) else [])
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
    surfaces.show(surfaces.notice(str(error), "warn", inline=True))
