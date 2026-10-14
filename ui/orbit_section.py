"""The orbit pictures on the Health Overview tab: where each satellite is, against its OWN slot.

app.py makes one call, render_slot_pictures. Everything drawn here comes from the figure
modules and ui/surfaces.py; this file holds no colours, sizes or CSS. A picture that
cannot be drawn becomes a short notice, so the rest of the page carries on.
"""
import re

import pandas as pd
import streamlit as st

from config.config import (
    BEIDOU3_SERVICE_REQUIREMENTS, GEO_NOMINAL_ALTITUDE, NAVIK_SERVICE_REQUIREMENTS,
    QZSS_SERVICE_REQUIREMENTS,
)
from ui import palette, surfaces
from ui.figures.constellation_3d import constellation_3d, slot_legend
from ui.figures.score_parts import score_parts
from ui.figures.slot_belt import slot_belt
from ui.figures.slot_rows import as_number, deviation_of, last_known_position, slot_rows

HEADING = "Where each satellite is, against its own slot"
SENTENCE = ("Each satellite is judged against its own slot only, so one that drifts onto "
            "another satellite's slot still shows as away from its own.")
SET_ASIDE_NOTE = "set aside, graveyard orbit"
CHIP_STATUS = {palette.SLOT_IN: "ok", palette.SLOT_OFF: "warn",
               palette.SLOT_LEFT: "bad", palette.SLOT_UNKNOWN: "idle"}
# The score parts in the order they are drawn: (label, column of the health table).
PARTS = [("Inclination", "_inc_score"), ("Upkeep", "_maintenance_score"),
         ("Regularity", "_uniformity_score"), ("Drift", "_drift_score"),
         ("Longitude", "Lon Deviation Score")]


def designated_longitude(name):
    """The longitude of a satellite's own slot in degrees east, or None if the config has none."""
    if name in NAVIK_SERVICE_REQUIREMENTS:
        return NAVIK_SERVICE_REQUIREMENTS[name]["longitude"]
    for requirements in (QZSS_SERVICE_REQUIREMENTS, BEIDOU3_SERVICE_REQUIREMENTS):
        if name in requirements:
            return requirements[name]["central_longitude_deg"]
    return None


def _lon_words(lon):
    """'25.1 degrees W' for a longitude in degrees east."""
    return f"{abs(lon):.2f} degrees {'E' if lon >= 0 else 'W'}"


def _last_known(name, history):
    """Where a satellite last was, from its newest record in the history table, or None."""
    if history is None or "satellite" not in history.columns:
        return None
    own = history[history["satellite"] == name]
    if own.empty:
        return None
    newest = own.loc[own["EPOCH"].idxmax()]
    record = {"EPOCH": pd.Timestamp(newest["EPOCH"]).isoformat(), "MEAN_MOTION": newest["MEAN_MOTION"],
              "TLE_LINE1": newest["TLE_LINE1"], "TLE_LINE2": newest["TLE_LINE2"]}
    return last_known_position([record])


def set_aside_positions(set_aside_names, history=None):
    """{name: last known position or None} for each set-aside satellite."""
    return {name: _last_known(name, history) for name in set_aside_names}


def set_aside_rows(positions, slot_of):
    """Items for slot_rows, one per set-aside satellite that has a slot, in name order.

    positions comes from set_aside_positions. Where it is None the position is not
    known: actual_lon is None, and the satellite still counts as having left its slot.
    """
    items = []
    for name, seen in sorted(positions.items()):
        slot = slot_of(name)
        if slot is not None:
            items.append({"name": name, "slot_lon": slot, "note": SET_ASIDE_NOTE,
                          "actual_lon": None if seen is None else seen["lon"]})
    return items


def _drift_words(per_day):
    return f"{abs(per_day):.1f} degrees a day {'west' if per_day > 0 else 'east'}"


def _left_words(seen):
    """Where a satellite that left the belt was last seen, in words."""
    height = seen["altitude_km"] - GEO_NOMINAL_ALTITUDE
    return (f"Last known on {seen['date']}: over {_lon_words(seen['lon'])}, "
            f"{abs(height):.0f} km {'above' if height >= 0 else 'below'} the belt, "
            f"drifting {_drift_words(seen['drift_deg_per_day'])}.")


def _caption(row, seen):
    """The line under the big figure on a card: the slot, then where the satellite is."""
    slot = f"Its own slot is {_lon_words(row['slot_lon'])}."
    if row["state"] == palette.SLOT_LEFT:
        return f"{slot} {_left_words(seen)}" if seen else f"{slot} Position not known: no orbit records."
    if row["state"] == palette.SLOT_UNKNOWN:
        return f"{slot} There is no current orbit record, so its position against the slot could not be worked out."
    return f"{slot} It is at {_lon_words(row['actual_lon'])}."


def _card(row, seen):
    """A raised card for one satellite that is not on its slot."""
    deviation = deviation_of(row)
    headline = "no position" if deviation is None else f"{deviation:.2f}° away"
    body = surfaces.big_number(headline, _caption(row, seen)) + surfaces.chip(row["state"], CHIP_STATUS[row["state"]])
    return surfaces.raised(body, title=f"{row['name']}: {row['state']}")


def _status_cards(rows, positions):
    """Cards for every satellite not in its slot, or one line saying all are."""
    away = [row for row in rows if row["state"] != palette.SLOT_IN]
    if not away:
        st.html(surfaces.notice("Every satellite is in its own slot.", "ok"))
    for row in away:
        st.html(_card(row, positions.get(row["name"])))


def _score_card(row):
    parts = [(label, as_number(row.get(column))) for label, column in PARTS]
    status = re.sub(r"^[^A-Za-z]+", "", str(row.get("Health Status", "")))
    return surfaces.raised(score_parts(str(row["Satellite"]), as_number(row.get("Overall Score")), status, parts))


def _score_grid(health_df):
    """One score card per scored satellite, two to a row."""
    scored = [row for row in health_df.to_dict("records") if as_number(row.get("Overall Score")) is not None]
    for start in range(0, len(scored), 2):
        for column, row in zip(st.columns(2), scored[start:start + 2]):
            column.html(_score_card(row))


def attempt(picture, draw, *args):
    """Run draw(*args). If it raises, show one notice saying why and return None."""
    try:
        return draw(*args)
    except Exception as error:
        st.html(surfaces.notice(f"The {picture} could not be drawn: {type(error).__name__}: {error}", "warn"))
        return None


def positions_and_rows(health_df, set_aside_names, slot_of, history):
    positions = set_aside_positions(set_aside_names, history)
    return positions, slot_rows(health_df.to_dict("records"), set_aside_rows(positions, slot_of))


def render_belt(rows, view="Flat"):
    """The slot picture on its own: the flat belt, or with view="3D" the belt seen from above the pole."""
    if view == "3D":
        attempt("3D view", lambda: st.plotly_chart(constellation_3d(rows), use_container_width=True,
                                                      config={"displayModeBar": False}))
    else:
        attempt("flat belt", lambda: surfaces.show(surfaces.raised(surfaces.picture(slot_belt(rows)))))


def _top(rows, positions):
    """The 3D view on the left, the cards for satellites away from their slot on the right."""
    view, cards = st.columns([3, 2])
    with view:
        st.plotly_chart(constellation_3d(rows), use_container_width=True, config={"displayModeBar": False})
    with cards:
        _status_cards(rows, positions)


def render_slot_pictures(health_df, set_aside_names, slot_of, history=None, constellation=""):
    """Draw the slot pictures: 3D view with status cards, the flat belt, then the score parts.

    health_df is the dashboard's health table, set_aside_names the satellites it set aside
    for a graveyard orbit, slot_of maps a name to its slot longitude or None, and history
    is the full bundled history table or None.
    """
    title, legend = st.columns([3, 2])   # the legend opens to the right, over the cards and clear of the 3D view
    title.subheader(HEADING)
    title.write(SENTENCE)
    legend.html(surfaces.hover_legend(slot_legend(), opens_left=True))

    positions, rows = attempt("slot rows", positions_and_rows, health_df, set_aside_names, slot_of, history) or ({}, None)
    if rows is None:
        return
    if not rows:
        st.html(surfaces.notice(f"No {constellation or 'tracked'} satellite has a slot to compare against.", "idle"))
        return
    attempt("3D view and status cards", _top, rows, positions)
    render_belt(rows)
    attempt("score parts", _score_grid, health_df)
