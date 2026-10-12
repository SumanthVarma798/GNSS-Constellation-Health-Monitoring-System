"""The master map page: which spacecraft is which, under every identifier.

Run it alone with: streamlit run views/master_map.py
It only composes parts: the theme, ui.surfaces, the figures and Streamlit widgets.
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.master_map import (agreement, display_name, holders_of, identifiers, signal_ids_of, summary)
from evidence.settings import (IDENTITY_DIFFER, SCHEME_COSPAR, SCHEME_NORAD, SCHEME_SIGNAL_ID, SERVICE_DISAGREE)
from ui import surfaces
from ui.figures.agreement_strip import agreement_legend, agreement_strip
from ui.figures.identity_dial import identity_dial
from ui.figures.succession import succession_lanes
from ui.pages_data import load_master_map_data
from ui.theme import apply_theme

ALL = "All"
DEFAULT_SVN = "C217"


def _disagrees(line):
    return line["identity"] == IDENTITY_DIFFER or line["service"] == SERVICE_DISAGREE


def _table_row(line, satellite, entry, names):
    svn = line["svn"]
    # The two readings come early: they are what the page is about, and must not be cut off.
    return {"Master ID": svn, "Name": names[svn], "Constellation": line["constellation"],
            "Identity reading": line["identity"], "Service reading": line["service"],
            SCHEME_SIGNAL_ID: satellite["signal_id_now"], "Orbital slot": satellite["slot"],
            "Owner": entry.get("owner", ""), SCHEME_NORAD: satellite["catalogue_no"],
            SCHEME_COSPAR: satellite["cospar_id"]}


def _show_spacecraft(svn, names, data, today):
    """The dial and the two timelines for one spacecraft."""
    satellite = next(row for row in data["satellites"] if row["svn"] == svn)
    surfaces.show(surfaces.raised(
        identity_dial(svn, names[svn], identifiers(svn, data["satellites"], data["catalogue"], data["tracked"],
                                                   data["signal_ids"], data["feed_names"])),
        title="Every name this spacecraft goes by"))
    periods = signal_ids_of(svn, data["signal_ids"])
    signal_id, caption = satellite["signal_id_now"], ""
    if not signal_id and periods:
        signal_id = periods[-1]["label"]
        caption = f"{svn} has no current signal ID, so this shows the most recent one."
    left, right = st.columns(2)
    with left:
        surfaces.show(surfaces.raised(surfaces.picture(succession_lanes(periods, today)),
                                      title="This spacecraft's signal IDs over time"))
    with right:
        if signal_id:
            holders = holders_of(signal_id, data["signal_ids"], data["satellites"], data["catalogue"], data["tracked"])
            surfaces.show(surfaces.raised(surfaces.picture(succession_lanes(holders, today, caption)),
                                          title=f"Who has held signal ID {signal_id}"))
        else:
            surfaces.show(surfaces.notice(f"{svn} has never had a signal ID, so there is no holder history to show.",
                                          "idle"))


def render():
    apply_theme()
    data = load_master_map_data()
    satellites, catalogue = data["satellites"], data["catalogue"]
    today = date.today().isoformat()

    st.title("Master map")
    st.write("Every navigation spacecraft under each name agencies use for it, resolved to one master ID "
             "(its space vehicle number, SVN), and who held each signal ID (pseudorandom noise number, PRN) when.")

    totals = summary(satellites, catalogue, data["signal_ids"])
    for column, (value, words) in zip(st.columns(3), [
            (totals["spacecraft"], f"spacecraft, {totals['systems']} systems"),
            (totals["confirmed"], "identity confirmed by a second source"),
            (f"{totals['signal_ids_reused']} of {totals['signal_ids']}",
             "signal IDs held by more than one spacecraft")]):
        with column:
            surfaces.show(surfaces.raised(surfaces.big_number(value, words)))

    names = {row["svn"]: display_name(row["svn"], satellites, catalogue, data["tracked"]) for row in satellites}
    lines = agreement(satellites, catalogue)
    systems = list(dict.fromkeys(row["constellation"] for row in satellites))
    chosen = st.pills("Constellation", [ALL, *systems], selection_mode="single", default=ALL,
                      key="constellation") or ALL
    only_disagree, only_tracked = st.columns(2)
    differing = only_disagree.toggle("Only where the sources disagree", key="only_disagree")
    watched = only_tracked.toggle("Only the ones the dashboard tracks", key="only_tracked")

    tracked = {row["svn"] for row in data["tracked"]}
    shown = [line for line in lines
             if chosen in (ALL, line["constellation"]) and (not differing or _disagrees(line))
             and (not watched or line["svn"] in tracked)]
    if not shown:
        surfaces.show(surfaces.notice("No spacecraft match these filters. Turn one off to see more.", "warn"))
        return

    svns = [line["svn"] for line in shown]
    st.selectbox("Spacecraft", svns, index=svns.index(DEFAULT_SVN) if DEFAULT_SVN in svns else 0,
                 format_func=lambda svn: f"{svn}, {names[svn]}", key="spacecraft")
    _show_spacecraft(st.session_state["spacecraft"], names, data, today)

    title, legend = st.columns([3, 7], vertical_alignment="center")
    title.subheader("Do the sources agree?")
    with legend:
        surfaces.show(surfaces.hover_legend(agreement_legend()))
    surfaces.show(surfaces.raised(agreement_strip(shown)))
    st.write(f"{sum(_disagrees(line) for line in shown)} of the {len(shown)} spacecraft shown have sources "
             "that disagree about who they are or whether they are in service.")

    by_svn, entries = {row["svn"]: row for row in satellites}, {row["svn"]: row for row in catalogue}
    st.dataframe(pd.DataFrame([_table_row(line, by_svn[line["svn"]], entries.get(line["svn"], {}), names)
                               for line in shown]), hide_index=True, use_container_width=True,
                 column_config={name: st.column_config.Column(width="small")
                                for name in ("Master ID", "Orbital slot", "Owner")})
    st.caption("NORAD is the North American Aerospace Defense Command, COSPAR the Committee on Space Research, "
               "GCAT the General Catalogue of Artificial Space Objects, and IGS the International Global Navigation Satellite System Service.")


if __name__ == "__main__":
    st.set_page_config(page_title="Master map", layout="wide")
    render()
