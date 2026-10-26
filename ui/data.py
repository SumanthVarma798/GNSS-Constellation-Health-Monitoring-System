"""The dashboard's data: one call per constellation, kept until the hour changes, a setting does, or fresh rows arrive."""
import os
from datetime import datetime, timezone

import streamlit as st

from analysis.bundled_run import assess_constellation
from analysis.meo_run import assess_meo
from config.config import BEIDOU3_SATS, GENERATIONS, MEO_SATS, NAVIK_SATS, QZSS_SATS
from data import celestrak, spacetrack
from data.tle_cache import load_bundled_gp_history
from evidence.settings import ORBIT_ALERT_DAYS, ORBIT_STALE_DAYS
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


@st.cache_data(show_spinner=False)
def _bundled_newest():
    """{norad: the newest bundled EPOCH} for every tracked satellite: only the newest, as the files are tens of MB
    and Streamlit copies a cached result on every run."""
    newest = {}
    for constellation, satellites in SATELLITES.items():
        bundled = (load_bundled_gp_history(constellation.lower().replace("-", "")) or {}).get("satellites") or {}
        for name, norad in satellites.items():
            if norad is not None and bundled.get(name):
                newest[int(norad)] = max(row["EPOCH"] for row in bundled[name] if row.get("EPOCH"))
    return newest


def _server_login():
    """(username, password) from the server's env or secrets, else None."""
    username, password = os.environ.get("SPACETRACK_USERNAME"), os.environ.get("SPACETRACK_PASSWORD")
    if username and password:
        return username, password
    try:
        creds = st.secrets["spacetrack"]
        username, password = creds["username"], creds["password"]
        return (username, password) if username and password else None
    except Exception:
        return None


def _epoch(value):
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _newest(rows):
    dated = [(row, _epoch(row.get("EPOCH"))) for row in rows]
    dated = [(row, at) for row, at in dated if at is not None]
    return max(dated, key=lambda item: item[1]) if dated else (None, None)


def _status(age_days):
    if age_days is None:
        return "idle"
    if age_days >= ORBIT_STALE_DAYS:
        return "bad"
    if age_days >= ORBIT_ALERT_DAYS:
        return "warn"
    return "ok"


def _merge_rows(*groups):
    merged, seen = [], set()
    for rows in groups:
        for row in rows:
            epoch = row.get("EPOCH")
            if epoch and epoch not in seen:
                merged.append(row)
                seen.add(epoch)
    return merged


def _stale_or_missing_tracked(now, celestrak_rows):
    stale = []
    bundled = _bundled_newest()
    for norad in sorted({norad for norads in TRACKED.values() for norad in norads}):
        held = [{"EPOCH": bundled[norad]}] if norad in bundled else []
        newest_row, newest_at = _newest(_merge_rows(held, celestrak_rows.get(norad, []),
                                                    spacetrack.state["rows"].get(norad, [])))
        if newest_row is None or newest_at is None:
            stale.append(norad)
            continue
        age_days = (now - newest_at).total_seconds() / 86400
        if age_days >= ORBIT_ALERT_DAYS:
            stale.append(norad)
    return stale


def refresh(clicked=False):
    """Pull the newest element sets from CelesTrak when one is due (see data.celestrak.refresh). Returns its state.

    Asks for the tracked satellites and every other satellite of their generations."""
    now = datetime.now(timezone.utc)
    wanted = {n for norads in TRACKED.values() for n in norads}
    wanted |= {int(row["catalogue_no"]) for rows in GENERATION.values() for row in rows if row["catalogue_no"]}
    live = celestrak.refresh(sorted(wanted), now, clicked)
    stale = _stale_or_missing_tracked(now, live["rows"])
    # Always called: with none stale it asks nothing, but reads the saved copy after a restart.
    spacetrack.refresh(stale, now, _server_login())
    return live


def load(constellation, window_days, params=None):
    """assess_constellation's result for the bundled data with the CelesTrak rows held, `now` as the current UTC hour.

    params holds only the thresholds moved off their defaults. Raises ValueError as assess_constellation does.
    """
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    held_celestrak, held_spacetrack = celestrak.state["rows"], spacetrack.state["rows"]
    fresh = {}
    for norad in TRACKED.get(constellation, []):
        rows = _merge_rows(held_celestrak.get(norad, []), held_spacetrack.get(norad, []))
        if rows:
            fresh[norad] = rows
    return _assess(constellation, window_days, params or {}, now, fresh)


def orbit_age_rows(tracked, history_rows_by_satellite, celestrak_rows, spacetrack_rows, now):
    """Orbit ages from plain rows, oldest first. tracked: [(satellite name, norad), ...]."""
    out = []
    for satellite, norad in tracked:
        newest = []
        for source, rows in (("Space-Track history", history_rows_by_satellite.get(satellite, [])),
                             ("CelesTrak", celestrak_rows.get(norad, [])),
                             ("Space-Track", spacetrack_rows.get(norad, []))):
            row, at = _newest(rows)
            if row is not None and at is not None:
                # On ties, keep explicit live sources ahead of bundled history.
                newest.append((at, 2 if source == "CelesTrak" else 1 if source == "Space-Track" else 0, source))
        if newest:
            at, _, source = max(newest, key=lambda item: (item[0], item[1]))
            age_days = (now - at).total_seconds() / 86400
            out.append({"satellite": satellite, "epoch": at, "source": source, "age_days": age_days,
                        "status": _status(age_days)})
        else:
            out.append({"satellite": satellite, "epoch": None, "source": "", "age_days": None, "status": "idle"})
    return sorted(out, key=lambda row: (row["age_days"] is None, -(row["age_days"] or 0), row["satellite"]))


def orbit_ages(constellation, result):
    """Orbit age rows for one constellation from its assessed result and the held live rows."""
    tracked = [(satellite, int(norad)) for satellite, norad in SATELLITES[constellation].items() if norad is not None]
    # Only each satellite's newest row: the history is tens of thousands of rows, read on every run.
    newest = result["history"].groupby("satellite")["EPOCH"].max() if len(result["history"]) else {}
    history = {str(satellite): [{"EPOCH": epoch}] for satellite, epoch in dict(newest).items()}
    return orbit_age_rows(tracked, history, celestrak.state["rows"], spacetrack.state["rows"], datetime.now(timezone.utc))
