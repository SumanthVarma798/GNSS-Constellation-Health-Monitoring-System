"""What the pages read, loaded once and kept: the registry tables, and the orbit feed names and fetch days.

The files only change with a new commit, and every commit to main redeploys the dashboard (render.yaml), so the
cache is never older than the files. The live orbit feed is not cached here: with_live_feed() lays it over the files.
"""
from datetime import datetime

import streamlit as st

from data.tle_cache import DATA_DIR
from evidence.library_settings import LIBRARY_COUNTS_FILE
from evidence.master_map import orbit_feed_checked, orbit_feed_names
from evidence.registry_tables import read_table
from evidence.registry_settings import (
    REGISTRY_CATALOGUE_FILE,
    REGISTRY_DASHBOARD_SATELLITES_FILE,
    REGISTRY_SATELLITES_FILE,
    REGISTRY_SIGHTINGS_FILE,
    REGISTRY_SIGNAL_IDS_FILE
)


@st.cache_data(show_spinner=False)
def load_master_map_data():
    """The five registry tables as lists of rows, {catalogue number: orbit feed name} and {catalogue number: day that
    feed was fetched} from the bundled weekly orbit files, and the GCAT catalogue's own date for the catalogue rows."""
    return {"satellites": read_table(REGISTRY_SATELLITES_FILE), "sightings": read_table(REGISTRY_SIGHTINGS_FILE),
            "catalogue": read_table(REGISTRY_CATALOGUE_FILE),
            "tracked": read_table(REGISTRY_DASHBOARD_SATELLITES_FILE),
            "signal_ids": read_table(REGISTRY_SIGNAL_IDS_FILE), "feed_names": orbit_feed_names(DATA_DIR),
            "feed_checked": orbit_feed_checked(DATA_DIR),
            "gcat_updated": max((row["gcat_updated"] for row in read_table(LIBRARY_COUNTS_FILE)), default="")}


def live_feed_time(live):
    """When the orbit feed copy in use was taken (aware datetime), or None before one has been read."""
    taken = live.get("copy_at") or live.get("fetched")
    if isinstance(taken, str):
        taken = datetime.fromisoformat(taken)
    return taken


def with_live_feed(data, live):
    """data with the live orbit feed's names laid over the bundled ones. live is data.celestrak.state.

    The bundled files hold only NavIC, QZSS and the high-orbit BeiDou satellites, a week old at most; the live copy
    (read every two hours) holds every tracked satellite of every system, so its names and day win where it has them.
    """
    taken = live_feed_time(live)
    names = {int(norad): rows[-1]["OBJECT_NAME"] for norad, rows in (live.get("rows") or {}).items()
             if rows and rows[-1].get("OBJECT_NAME")}
    if not (taken and names):
        return data
    day = taken.date().isoformat()
    return {**data, "feed_names": {**data["feed_names"], **names},
            "feed_checked": {**data["feed_checked"], **dict.fromkeys(names, day)}}
