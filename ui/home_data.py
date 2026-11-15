"""Home's counts, kept so a visit does not count again what has not changed.

Counting one part means assessing every satellite in it, which takes seconds on the dashboard's small server. A
count is kept until something it reads changes: a new UTC hour (the assessment's own clock), a new orbit fetch, or a
new broadcast check.
"""
from datetime import datetime, timezone

import streamlit as st

from data import celestrak
from ui import data, system_summary


def keys(gap):
    """What a kept count depends on, as words: the UTC hour, the last orbit fetch, the broadcast check read."""
    return (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H"), str(celestrak.state.get("fetched")),
            str((gap or {}).get("checked")))


@st.cache_data(show_spinner=False, max_entries=32)   # seven parts at a few time ranges
def part_summary(name, window_days, hour_key, fetched_key, checked_key):
    """ui.system_summary.summary() of one part at the default limits. The three keys are only the cache key (keys())."""
    return system_summary.summary(name, data.load(name, window_days), data.orbit_gap())
