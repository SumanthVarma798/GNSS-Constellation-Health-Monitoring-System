"""The dashboard's data: one call per constellation, kept until the hour changes or a setting does."""
from datetime import datetime, timezone

import streamlit as st

from analysis.bundled_run import assess_constellation


@st.cache_data(show_spinner=False)
def _assess(constellation, window_days, params, now):
    return assess_constellation(constellation, now, window_days, params)


def load(constellation, window_days, params=None):
    """assess_constellation's result for the bundled data, with `now` as the current UTC hour.

    params holds only the thresholds moved off their defaults. Raises ValueError as assess_constellation does.
    """
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return _assess(constellation, window_days, params or {}, now)
