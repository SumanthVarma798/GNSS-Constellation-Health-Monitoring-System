"""The World map's numbers, worked out once an hour: where every tracked satellite is now and its next-day track.

Nothing here draws. The page (ui/components/world_view.py) turns these records into its payload; the canvas page
only places and draws.
"""
from datetime import datetime, timezone

import streamlit as st

from ui import data, geometry_data as gd, geometry_settings as gs


@st.cache_data(show_spinner=False)
def load(hour_key, fetched_key, window_days, params):
    """One entry per constellation that has orbit data, plus any notices for the others.

    hour_key and fetched_key are only the cache key: the same UTC hour gets the same payload without recomputing the
    tracks, and a new orbit fetch (fetched_key, CelesTrak's last fetch) recomputes it, so a load made before any
    orbit data arrived is not kept for the hour.
    """
    gap = data.orbit_gap()
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    entries, notices = [], []
    for constellation in data.SATELLITES:
        try:
            result = data.load(constellation, window_days, dict(params))
        except ValueError as error:
            notices.append(f"{constellation}: {error}")
            continue
        tracked = [name for name, norad in data.SATELLITES[constellation].items() if norad is not None]
        satellites = gd.satellites_from_history(result["history"], tracked)
        if not satellites:
            notices.append(f"No orbit data for {constellation}.")
            continue
        tracks, here = gd.ground_tracks(satellites, now, gs.TRACK_WINDOWS[0])
        ages = {row["satellite"]: row for row in data.orbit_ages(constellation, result)}
        records = []
        for name in tracked:
            if name not in satellites:
                continue
            lat, lon = here.get(name, (None, None))
            track = tracks.get(name, {})
            height = track["height"][0] if track.get("height") else None
            records.append({"name": name, "lat": lat, "lon": lon, "height": height, "age": ages.get(name, {})})
        if records:
            entries.append({"name": constellation, "satellites": records, "tracks": tracks})
    return entries, notices, gap, now
