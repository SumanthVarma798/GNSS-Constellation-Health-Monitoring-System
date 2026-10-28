"""World map: every tracked satellite of all six systems on one map, coloured by broadcast health (work in progress)."""
from datetime import datetime, timezone

import streamlit as st

from data import celestrak
from ui import surfaces, time_range
from ui.components.world_view import world_view
from ui.world_data import load

st.session_state.setdefault("window_days", time_range.DEFAULT_DAYS)
st.session_state.setdefault("params", {})
window_days = st.session_state["window_days"]
params = tuple(sorted(st.session_state["params"].items()))
hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
entries, notices, gap, now = load(hour_key, str(celestrak.state.get("fetched")), window_days, params)

surfaces.show(surfaces.notice("Work in progress", "idle"))
for notice in notices:
    surfaces.show(surfaces.notice(notice, "idle"))
world_view(entries, gap, now)
