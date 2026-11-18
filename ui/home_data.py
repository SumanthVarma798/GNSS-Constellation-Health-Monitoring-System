"""Home's counts: read from the copy the scheduled job publishes, else counted here and kept.

Counting one part means assessing every satellite in it, which takes seconds on the dashboard's small server, and the
server forgets everything it kept each time it sleeps. So the archive job counts every part when the orbit copy changes (and at least every 8 hours) and
publishes the result on branch orbit-data (scripts/home_snapshot.py); Home reads that one file while it is fresh.
When it is missing, too old, or the reader chose another time range, a part is counted here and kept until something
it reads changes: a new UTC hour (the assessment's own clock), a new orbit fetch, or a new broadcast check.
"""
from datetime import datetime, timezone

import requests
import streamlit as st

from data import celestrak
from ui import data, system_summary, systems
from ui.home_settings import SNAPSHOT_MAX_AGE, SNAPSHOT_URL

# What Home reads from each part's summary; a published part missing any of them is counted here instead.
NEEDED = {"name", "sats", "healthy", "total", "settling", "checked", "flagged_healthy", "orbit", "station", "clock",
          "score", "score_parts", "flag_agrees", "burns"}
# What each satellite in it must carry (ui/system_summary.py summary's sats).
SAT_NEEDED = {"name", "group", "score", "state", "ok", "parts", "orbit", "station", "broadcast", "clock", "clock_steady"}
PARTS = {name for names in systems.SYSTEMS.values() for name in names}


def keys(gap):
    """What a kept count depends on, as words: the UTC hour, the last orbit fetch, the broadcast check read."""
    return (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H"), str(celestrak.state.get("fetched")),
            str((gap or {}).get("checked")))


@st.cache_data(show_spinner=False, max_entries=32)   # seven parts at a few time ranges
def part_summary(name, window_days, hour_key, fetched_key, checked_key):
    """ui.system_summary.summary() of one part at the default limits. The three keys are only the cache key (keys())."""
    return system_summary.summary(name, data.load(name, window_days), data.orbit_gap())


@st.cache_data(ttl=600, show_spinner=False)   # the job publishes a new one every few hours
def _snapshot():
    """The published file as it is, or {} when it cannot be read."""
    try:
        payload = requests.get(SNAPSHOT_URL, timeout=8).json()
    except (requests.RequestException, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def published(window_days, now=None):
    """(the time it was counted, {part: summary}) from the published file, or (None, {}) when it cannot stand in for
    counting here: missing, older than SNAPSHOT_MAX_AGE, or counted over another time range. The file comes from
    outside the server, so a part not in the expected shape is left out and counted here."""
    payload = _snapshot()
    try:
        made = datetime.strptime(payload["made"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None, {}
    if payload.get("window_days") != window_days or (now or datetime.now(timezone.utc)) - made > SNAPSHOT_MAX_AGE:
        return None, {}
    parts = payload.get("parts") if isinstance(payload.get("parts"), dict) else {}
    kept = {name: part for name, part in parts.items()
            if name in PARTS and isinstance(part, dict) and NEEDED <= part.keys() and isinstance(part["sats"], list)
            and all(isinstance(sat, dict) and SAT_NEEDED <= sat.keys() for sat in part["sats"])
            # a copy made before the score was weighed by mission has no weights: counted here instead
            and isinstance(part["score_parts"], (list, tuple))
            and all(isinstance(rate, (list, tuple)) and len(rate) == 3 for rate in part["score_parts"])}
    return (made if kept else None), kept
