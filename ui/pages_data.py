"""What the pages read, loaded once and kept: the registry tables, and the orbit feed names and fetch days."""

import streamlit as st

from data.tle_cache import DATA_DIR
from evidence.master_map import orbit_feed_checked, orbit_feed_names
from evidence.registry_tables import read_table
from evidence.settings import (REGISTRY_CATALOGUE_FILE, REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_SATELLITES_FILE,
                               REGISTRY_SIGNAL_IDS_FILE)


@st.cache_data(show_spinner=False)
def load_master_map_data():
    """The four registry tables as lists of rows, {catalogue number: orbit feed name}, and
    {catalogue number: day that feed was fetched}."""
    return {"satellites": read_table(REGISTRY_SATELLITES_FILE), "catalogue": read_table(REGISTRY_CATALOGUE_FILE),
            "tracked": read_table(REGISTRY_DASHBOARD_SATELLITES_FILE),
            "signal_ids": read_table(REGISTRY_SIGNAL_IDS_FILE), "feed_names": orbit_feed_names(DATA_DIR),
            "feed_checked": orbit_feed_checked(DATA_DIR)}
