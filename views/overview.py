"""Overview: is each satellite healthy and in its slot? One constellation, or satellites picked across constellations."""
import re

import streamlit as st

from config.config import BEIDOU3_SATS, NAVIK_SATS, QZSS_SATS, TRACKED_NOT_IN_REGISTRY
from ui import data, orbit_section, palette, shell, surfaces
from ui.figures.constellation_3d import slot_legend
from ui.figures.slot_rows import as_number, deviation_of
from ui.orbit_section import CHIP_STATUS, PARTS

SATELLITES = {"NavIC": NAVIK_SATS, "QZSS": QZSS_SATS, "BeiDou-3": BEIDOU3_SATS}
HEALTHY_FROM = 80


def _slot_words(row):
    """'in slot', 'off its slot, 2.08°', 'left its slot' or 'position not known'."""
    if row is None:
        return palette.SLOT_UNKNOWN
    deviation = deviation_of(row)
    return f"{row['state']}, {deviation:.2f}°" if row["state"] == palette.SLOT_OFF and deviation is not None else row["state"]


def _tile(health, slot):
    """(tile html, whether it counts as healthy and in its slot) for one health row and its slot row."""
    score = as_number(health.get("Overall Score"))
    scored = [(label, as_number(health.get(column))) for label, column in PARTS]
    scored = [part for part in scored if part[1] is not None]
    state = slot["state"] if slot else palette.SLOT_UNKNOWN
    html = surfaces.tile(
        str(health["Satellite"]), str(health.get("Type", "")), score,
        re.sub(r"^[^A-Za-z]+", "", str(health.get("Health Status", ""))),
        _slot_words(slot), CHIP_STATUS[state], min(scored, key=lambda part: part[1]) if scored else None)
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


def _gaps(constellation, result):
    """Notices for what is missing, so that nothing is left out in silence."""
    shown = set(result["health"]["Satellite"]) | set(result["set_aside"])
    no_data = [name for name, norad in SATELLITES[constellation].items() if norad is not None and name not in shown]
    unlisted = TRACKED_NOT_IN_REGISTRY[constellation]
    for text in (*result["warnings"],
                 *([f"No orbit data: {', '.join(no_data)}"] if no_data else []),
                 *([f"Awaiting a registry update: {', '.join(unlisted)}"] if unlisted else [])):
        surfaces.show(surfaces.notice(text, "warn"))


def _slot_picture(rows):
    """The slots against their satellites, flat or in 3D."""
    switch, legend = st.columns([1, 1], vertical_alignment="center")
    with switch:
        view = shell.segment("slot_view", ["Flat", "3D"], label="View")
    legend.html(f'<div class="right">{surfaces.hover_legend(slot_legend(), opens_left=True)}</div>')
    orbit_section.render_belt(rows, view)


def constellation(name, window_days, params):
    """One constellation: the count, a tile per satellite, the slot picture."""
    result = data.load(name, window_days, params)
    tiles, rows = _tiles(result)
    healthy = sum(healthy for _, healthy, _ in tiles.values())
    surfaces.show(f'<div class="head"><span class="big num">{healthy} of {len(tiles)}</span>'
                  '<span class="muted">healthy and in their slot</span></div>')
    _gaps(name, result)
    _grid(html for html, _, _ in tiles.values())
    if rows:
        _slot_picture(rows)


def compare(window_days, params):
    """Satellites picked across constellations: their tiles side by side, then their score parts in step."""
    picks = {name: column.multiselect(name, [s for s, norad in SATELLITES[name].items() if norad is not None],
                                      key=f"pick_{name}", placeholder="Add")
             for name, column in zip(shell.CONSTELLATIONS, st.columns(3))}
    chosen = []
    for name, picked in picks.items():
        if picked:
            tiles, _ = _tiles(data.load(name, window_days, params))
            chosen += [(s, *tiles[s]) for s in picked if s in tiles]
    if not chosen:
        surfaces.show('<p class="small">Pick satellites to compare.</p>')
        return
    scores = [[as_number(health.get(column)) if health else None for _, column in PARTS] for *_, health in chosen]
    rows = [(label, [column[i] for column in scores]) for i, (label, _) in enumerate(PARTS)]
    surfaces.show(surfaces.compare_grid([html for _, html, _, _ in chosen], surfaces.parts_matrix(rows)))


scope = st.session_state["scope"]
try:
    if scope == "Compare":
        compare(st.session_state["window_days"], st.session_state["params"])
    else:
        constellation(scope, st.session_state["window_days"], st.session_state["params"])
except ValueError as error:
    surfaces.show(surfaces.notice(str(error), "warn"))
