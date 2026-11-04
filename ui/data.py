"""The dashboard's data: one call per constellation, kept until the hour changes, a setting does, or fresh rows arrive."""
import os
from datetime import datetime, timezone

import requests
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
# A viewer's own Space-Track login, rows and bookkeeping. These are session_state keys only: the login is
# never written to disk, cached, logged, or put on the page. Streamlit drops session_state when the visit ends.
OWN_LOGIN = "_spacetrack_login"
OWN_ROWS = "_spacetrack_rows"
OWN_TRIED = "_spacetrack_tried"
OWN_NOTE = "_spacetrack_note"
# The public copy the daily RINEX job publishes to the orbit-checks branch.
ORBIT_GAP_URL = ("https://raw.githubusercontent.com/SumanthVarma798/"
                 "GNSS-Constellation-Health-Monitoring-System/orbit-checks/orbit_gap.json")
FITTED_URL = ("https://raw.githubusercontent.com/SumanthVarma798/"
              "GNSS-Constellation-Health-Monitoring-System/orbit-checks/fitted_orbits.json")
# Every registry satellite of the generation each constellation shows, tracked or not (the 3D view's "All").
# A MEO system's is the satellites it tracks: CelesTrak's GNSS group holds them, and asking for each
# retired one by itself would mean dozens of requests every refresh.
GENERATION = {name: generation_satellites(*GENERATIONS[name]) for name in GENERATIONS}
GENERATION |= {name: list(dashboard_registry_rows(name).values()) for name in MEO_SATS}


@st.cache_data(ttl=3600, show_spinner=False)
def orbit_gap():
    """The published orbit-record broadcast-gap JSON, or {} when it cannot be read."""
    try:
        payload = requests.get(ORBIT_GAP_URL, timeout=8).json()
    except (requests.RequestException, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


@st.cache_data(ttl=3600, show_spinner=False)
def fitted_orbits():
    """The published fitted-orbit JSON, or {} when it cannot be read."""
    try:
        payload = requests.get(FITTED_URL, timeout=8).json()
    except (requests.RequestException, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def fitted_by_norad():
    """{norad: (row, fit_km)} for every published fitted record that carries a row."""
    out = {}
    payload = fitted_orbits()
    for row in (payload.get("satellites") if isinstance(payload, dict) else None) or []:
        # a published file is outside data: skip any entry not in the expected shape rather than break the page
        if not isinstance(row, dict) or not isinstance(row.get("row"), dict) or not str(row.get("norad", "")).isdigit():
            continue
        out[int(row["norad"])] = (row["row"], row.get("fit_km"))
    return out


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


def _fitted_rule(fitted_at, other_ats, now):
    """Whether a fitted record may stand in: it must beat every other record, and the newest other
    must already be at least ORBIT_ALERT_DAYS old (or there must be no other record)."""
    if fitted_at is None:
        return False
    if not other_ats:
        return True
    newest = max(other_ats)
    return fitted_at > newest and (now - newest).total_seconds() / 86400 >= ORBIT_ALERT_DAYS


def _merge_rows(*groups):
    merged, seen = [], set()
    for rows in groups:
        for row in rows:
            epoch = row.get("EPOCH")
            if epoch and epoch not in seen:
                merged.append(row)
                seen.add(epoch)
    return merged


def _own_rows():
    """The viewer's Space-Track rows, held only in their session."""
    return st.session_state.get(OWN_ROWS, {})


def _stale_or_missing_tracked(now, celestrak_rows, own_rows=None):
    stale = []
    bundled = _bundled_newest()
    own_rows = {} if own_rows is None else own_rows
    for norad in sorted({norad for norads in TRACKED.values() for norad in norads}):
        held = [{"EPOCH": bundled[norad]}] if norad in bundled else []
        newest_row, newest_at = _newest(_merge_rows(held, celestrak_rows.get(norad, []),
                                                    spacetrack.state["rows"].get(norad, []),
                                                    own_rows.get(norad, [])))
        if newest_row is None or newest_at is None:
            stale.append(norad)
            continue
        age_days = (now - newest_at).total_seconds() / 86400
        if age_days >= ORBIT_ALERT_DAYS:
            stale.append(norad)
    return stale


def refresh(clicked=False):
    """Pull the newest element sets from the archive job's CelesTrak copy when one is due. Returns its state.

    The dashboard never contacts CelesTrak itself (see data.celestrak.refresh, direct=False). Asks for the tracked
    satellites and every other satellite of their generations."""
    now = datetime.now(timezone.utc)
    wanted = {n for norads in TRACKED.values() for n in norads}
    wanted |= {int(row["catalogue_no"]) for rows in GENERATION.values() for row in rows if row["catalogue_no"]}
    live = celestrak.refresh(sorted(wanted), now, clicked, direct=False)
    stale = _stale_or_missing_tracked(now, live["rows"])
    # Always called: with none stale it asks nothing, but reads the saved copy after a restart.
    spacetrack.refresh(stale, now, _server_login())
    # The viewer's own login is asked about the same stale set, recomputed so their rows already held count too.
    own_refresh(_stale_or_missing_tracked(now, live["rows"], _own_rows()), now)
    return live


def own_refresh(stale, now):
    """Fetch stale satellites with the viewer's own Space-Track login, at most once an hour, into session_state.

    The login and rows stay in st.session_state only. A refused login is forgotten immediately; a busy or bad
    reply is left for the next hour and never retried inside this call.
    """
    login = st.session_state.get(OWN_LOGIN)
    if not login or not stale:
        return
    tried = st.session_state.get(OWN_TRIED)
    if tried is not None and now - tried < spacetrack.EVERY:
        return
    st.session_state[OWN_TRIED] = now
    try:
        found = spacetrack.fetch(login[0], login[1], stale)
    except spacetrack.LoginRefused:
        st.session_state[OWN_NOTE] = "login refused"
        st.session_state.pop(OWN_LOGIN, None)
        st.session_state.pop(OWN_ROWS, None)
    except (spacetrack.Busy, spacetrack.SpaceTrackError):
        st.session_state[OWN_NOTE] = "busy"
    else:
        rows = st.session_state.setdefault(OWN_ROWS, {})
        for norad, row in found.items():
            held = rows.setdefault(norad, [])
            if row["EPOCH"] not in {old["EPOCH"] for old in held}:
                held.append(row)
        st.session_state[OWN_NOTE] = "ok"


def load(constellation, window_days, params=None):
    """assess_constellation's result for the bundled data with the CelesTrak rows held, `now` as the current UTC hour.

    params holds only the thresholds moved off their defaults. Raises ValueError as assess_constellation does.
    """
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    held_celestrak, held_spacetrack, held_own = celestrak.state["rows"], spacetrack.state["rows"], _own_rows()
    bundled = _bundled_newest()
    fitted = fitted_by_norad()
    fresh = {}
    for norad in TRACKED.get(constellation, []):
        rows = _merge_rows(held_celestrak.get(norad, []), held_spacetrack.get(norad, []), held_own.get(norad, []))
        other_ats = []
        bundled_at = _epoch(bundled.get(norad)) if norad in bundled else None
        if bundled_at is not None:
            other_ats.append(bundled_at)
        for group in (held_celestrak.get(norad, []), held_spacetrack.get(norad, []), held_own.get(norad, [])):
            _, at = _newest(group)
            if at is not None:
                other_ats.append(at)
        if norad in fitted:
            fitted_row, _ = fitted[norad]
            fitted_at = _epoch(fitted_row.get("EPOCH"))
            if _fitted_rule(fitted_at, other_ats, datetime.now(timezone.utc)):   # the same clock orbit_ages() uses
                rows = _merge_rows(rows, [fitted_row])
        if rows:
            fresh[norad] = rows
    return _assess(constellation, window_days, params or {}, now, fresh)


def orbit_age_rows(tracked, history_rows_by_satellite, celestrak_rows, spacetrack_rows, now, own_rows=None,
                   fitted_rows=None):
    """Orbit ages from plain rows, oldest first. tracked: [(satellite name, norad), ...]."""
    out = []
    own_rows = _own_rows() if own_rows is None else own_rows
    fitted_rows = fitted_rows or {}
    for satellite, norad in tracked:
        candidates = []
        other_ats = []
        for source, rows in (("Space-Track history", history_rows_by_satellite.get(satellite, [])),
                             ("CelesTrak", celestrak_rows.get(norad, [])),
                             ("Space-Track", spacetrack_rows.get(norad, [])),
                             ("Space-Track (your login)", own_rows.get(norad, []))):
            row, at = _newest(rows)
            if row is not None and at is not None:
                # On ties, keep explicit live sources ahead of bundled history.
                candidates.append({"at": at,
                                   "priority": 2 if source == "CelesTrak" else
                                   1 if source in ("Space-Track", "Space-Track (your login)") else 0,
                                   "source": source, "fit_km": None})
                other_ats.append(at)
        if norad in fitted_rows:
            fitted_row, fit_km = fitted_rows[norad]
            fitted_at = _epoch(fitted_row.get("EPOCH"))
            if _fitted_rule(fitted_at, other_ats, now):
                candidates.append({"at": fitted_at, "priority": 3, "source": "fitted to broadcast",
                                   "fit_km": fit_km})
        if candidates:
            chosen = max(candidates, key=lambda item: (item["at"], item["priority"]))
            at, source, fit_km = chosen["at"], chosen["source"], chosen["fit_km"]
            age_days = (now - at).total_seconds() / 86400
            out.append({"satellite": satellite, "epoch": at, "source": source, "age_days": age_days,
                        "status": _status(age_days), "fit_km": fit_km})
        else:
            out.append({"satellite": satellite, "epoch": None, "source": "", "age_days": None, "status": "idle",
                        "fit_km": None})
    return sorted(out, key=lambda row: (row["age_days"] is None, -(row["age_days"] or 0), row["satellite"]))


def own_note():
    """The section's Space-Track note words when the viewer's own login should speak, else None."""
    if st.session_state.get(OWN_LOGIN):
        return "your login"
    if st.session_state.get(OWN_NOTE) == "login refused":
        return "your login was refused"
    return None


def orbit_ages(constellation, result):
    """Orbit age rows for one constellation from its assessed result and the held live rows."""
    tracked = [(satellite, int(norad)) for satellite, norad in SATELLITES[constellation].items() if norad is not None]
    fitted = fitted_by_norad()
    fitted_at = {name: _epoch(fitted[norad][0].get("EPOCH")) for name, norad in tracked if norad in fitted}
    # Only each satellite's newest row: the history is tens of thousands of rows, read on every run. load() put any
    # fitted record in the history too: leave it out here, so it is named as fitted and not as history.
    history = {}
    for satellite, epochs in (result["history"].groupby("satellite")["EPOCH"] if len(result["history"]) else []):
        top = epochs.nlargest(2).tolist()
        if top and fitted_at.get(str(satellite)) is not None and _epoch(top[0]) == fitted_at[str(satellite)]:
            top = top[1:]
        if top:
            history[str(satellite)] = [{"EPOCH": top[0]}]
    return orbit_age_rows(tracked, history, celestrak.state["rows"], spacetrack.state["rows"],
                          datetime.now(timezone.utc), fitted_rows=fitted)
