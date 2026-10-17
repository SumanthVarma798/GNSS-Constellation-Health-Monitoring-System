"""The dashboard's data: one call per constellation, kept until the hour changes, a setting does, or fresh rows arrive."""
from datetime import datetime, timezone

import streamlit as st

from analysis.bundled_run import assess_constellation
from analysis.meo_run import assess_meo
from config.config import BEIDOU3_SATS, GENERATIONS, MEO_SATS, NAVIK_SATS, QZSS_SATS
from data import celestrak
from evidence.registry_tables import dashboard_registry_rows, generation_satellites

SATELLITES = {"NavIC": NAVIK_SATS, "QZSS": QZSS_SATS, "BeiDou-3": BEIDOU3_SATS, **MEO_SATS}
TRACKED = {name: [norad for norad in sats.values() if norad is not None] for name, sats in SATELLITES.items()}
# Every registry satellite of the generation each constellation shows, tracked or not (the 3D view's "All").
# A MEO system's is the satellites it tracks: CelesTrak's GNSS group holds them, and asking for each
# retired one by itself would mean dozens of requests every refresh.
GENERATION = {name: generation_satellites(*GENERATIONS[name]) for name in GENERATIONS}
GENERATION |= {name: list(dashboard_registry_rows(name).values()) for name in MEO_SATS}


@st.cache_data(show_spinner=False)
def _assess(constellation, window_days, params, now, fresh):
    assess_any = assess_meo if constellation in MEO_SATS else assess_constellation
    return assess_any(constellation, now, window_days, params, fresh)


def refresh(clicked=False):
    """Pull the newest element sets from CelesTrak when one is due (see data.celestrak.refresh). Returns its state.

    Asks for the tracked satellites and every other satellite of their generations."""
    wanted = {n for norads in TRACKED.values() for n in norads}
    wanted |= {int(row["catalogue_no"]) for rows in GENERATION.values() for row in rows if row["catalogue_no"]}
    return celestrak.refresh(sorted(wanted), datetime.now(timezone.utc), clicked)


def load(constellation, window_days, params=None):
    """assess_constellation's result for the bundled data with the CelesTrak rows held, `now` as the current UTC hour.

    params holds only the thresholds moved off their defaults. Raises ValueError as assess_constellation does.
    """
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    held = celestrak.state["rows"]
    fresh = {norad: list(held[norad]) for norad in TRACKED.get(constellation, []) if norad in held}
    return _assess(constellation, window_days, params or {}, now, fresh)
