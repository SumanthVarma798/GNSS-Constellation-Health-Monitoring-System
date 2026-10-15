"""The dashboard's data: one call per constellation, kept until the hour changes, a setting does, or fresh rows arrive."""
from datetime import datetime, timezone

import streamlit as st

from analysis.bundled_run import assess_constellation
from config.config import BEIDOU3_SATS, NAVIK_SATS, QZSS_SATS
from data import celestrak

SATELLITES = {"NavIC": NAVIK_SATS, "QZSS": QZSS_SATS, "BeiDou-3": BEIDOU3_SATS}
TRACKED = {name: [norad for norad in sats.values() if norad is not None] for name, sats in SATELLITES.items()}


@st.cache_data(show_spinner=False)
def _assess(constellation, window_days, params, now, fresh):
    return assess_constellation(constellation, now, window_days, params, fresh)


def refresh(clicked=False):
    """Pull the newest element sets from CelesTrak when one is due (see data.celestrak.refresh). Returns its state."""
    return celestrak.refresh([n for norads in TRACKED.values() for n in norads], datetime.now(timezone.utc), clicked)


def load(constellation, window_days, params=None):
    """assess_constellation's result for the bundled data with the CelesTrak rows held, `now` as the current UTC hour.

    params holds only the thresholds moved off their defaults. Raises ValueError as assess_constellation does.
    """
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    held = celestrak.state["rows"]
    fresh = {norad: list(held[norad]) for norad in TRACKED.get(constellation, []) if norad in held}
    return _assess(constellation, window_days, params or {}, now, fresh)
