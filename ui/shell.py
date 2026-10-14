"""The frame every page sits in: one top bar, no side panel.

The choices live in st.session_state: `scope` (a constellation, or Compare), `window_days`
and `params` (only the detection thresholds moved off their defaults). Pages read them.
"""
from datetime import datetime, timezone

import streamlit as st

from config.config import DEFAULT_PARAMS
from ui import data, surfaces

# Pages with their own filters: the bar shows no constellation, window or thresholds there.
OWN_FILTERS = {"Master map"}

# The pages, in one place. Add a page by adding a line: (title, file).
PAGES = [
    ("Overview", "views/overview.py"),
    ("Station-keeping", "views/station_keeping.py"),
    ("Master map", "views/master_map.py"),
    # ("How it works", "views/how_it_works.py"),
]
CONSTELLATIONS = ("NavIC", "QZSS", "BeiDou-3")
SCOPES = (*CONSTELLATIONS, "Compare")
WINDOWS = {90: "90 days", 365: "1 year"}
STALE_DAYS = 7

# (key in params, label, smallest, largest, step, format): the seven detection thresholds app.py offers.
THRESHOLDS = [
    ("z_threshold", "Z-score threshold", 1.0, 10.0, 0.5, "%.1f"),
    ("sma_threshold", "SMA change (km)", 0.1, 5.0, 0.1, "%.1f"),
    ("inc_threshold", "Inclination change (°)", 0.001, 0.1, 0.001, "%.3f"),
    ("persist_window", "Persistence window", 1, 10, 1, "%d"),
    ("inclination_tolerance", "Inclination tolerance (°)", 0.1, 5.0, 0.1, "%.1f"),
    ("drift_tolerance_gso", "GEO drift tolerance (°/day)", 0.01, 0.5, 0.01, "%.2f"),
    ("maneuver_uniformity_threshold", "Manoeuvre uniformity CoV", 0.1, 2.0, 0.1, "%.1f"),
]
QZSS_INCLINATION_TOLERANCE = 4.0   # as app.py: QZSS's IGSO satellites have a wider tolerance


def pages():
    """PAGES as st.Page objects."""
    return [st.Page(path, title=title, default=i == 0) for i, (title, path) in enumerate(PAGES)]


def segment(key, options, labels=None, label="Choose"):
    """A segmented control that always has one item chosen; its value is kept in session_state[key].

    Clicking the chosen item would clear it, so the earlier choice is put back.
    """
    labels = labels or {}
    st.session_state.setdefault(key, options[0])
    st.session_state[f"_{key}_was"] = st.session_state[key]

    def keep():
        if st.session_state[key] is None:
            st.session_state[key] = st.session_state[f"_{key}_was"]

    st.segmented_control(label, options, key=key, format_func=lambda o: labels.get(o, o),
                         label_visibility="collapsed", on_change=keep)
    return st.session_state[key]


def age_words(data_time, now):
    """('Orbit data 4 Oct, 10 days old', 'warn') from an ISO time. Warn after STALE_DAYS days."""
    try:
        taken = datetime.fromisoformat(data_time)
    except (TypeError, ValueError):
        return "Orbit data date not known", "idle"
    days = (now.date() - taken.date()).days
    age = "today" if days <= 0 else "1 day old" if days == 1 else f"{days} days old"
    return f"Orbit data {taken.day} {taken:%b}, {age}", "warn" if days > STALE_DAYS else "ok"


def _thresholds(scope):
    """The gear's inputs, one per threshold. Returns only those moved off their defaults."""
    moved = {}
    for key, label, low, high, step, fmt in THRESHOLDS:
        default = DEFAULT_PARAMS[key]
        if key == "inclination_tolerance" and scope == "QZSS":
            default = QZSS_INCLINATION_TOLERANCE
        value = st.number_input(label, low, high, default, step, format=fmt, key=f"th_{key}_{scope}")
        if value != default:
            moved[key] = value
    return moved


def _data_chip(scope, window_days, params):
    """The age of the orbit data behind the page (the oldest, for Compare)."""
    try:
        times = [data.load(c, window_days, params)["data_time"]
                 for c in (CONSTELLATIONS if scope == "Compare" else (scope,))]
        text, status = age_words(min(times), datetime.now(timezone.utc))
    except ValueError:
        text, status = "No orbit data", "bad"
    return f'<div class="right">{surfaces.chip(text, status)}</div>'


def top_bar(current):
    """Draw the bar and store the choices. `current` is the st.Page that is running."""
    with st.container(key="topbar"):
        brand, scope_box, window_box, chip_box, gear_box = st.columns(
            [1.4, 3.6, 1.8, 2.8, 0.5], vertical_alignment="center")
        brand.html('<b class="brand">GNSS Health</b>')
        if current.title in OWN_FILTERS:
            scope, window_days = st.session_state.get("scope", SCOPES[0]), st.session_state.get("window_days", 90)
            st.session_state.setdefault("params", {})
        else:
            with scope_box:
                scope = segment("scope", list(SCOPES), label="Constellation")
            with window_box:
                window_days = segment("window_days", list(WINDOWS), WINDOWS, label="Window")
            with gear_box, st.popover("", icon=":material/settings:", help="Detection thresholds"):
                st.session_state["params"] = _thresholds(scope)
        chip_box.html(_data_chip(scope, window_days, st.session_state["params"]))
    _page_tabs(current)


def _page_tabs(current):
    """The pages sit under the bar, as tabs: there is room for more of them there."""
    with st.container(key="pagetabs"):
        if st.session_state.get("shown_page") != current.title:   # arrived by address or switch: tabs follow the page
            st.session_state["page"] = current.title
        st.session_state["shown_page"] = current.title
        if segment("page", [title for title, _ in PAGES], label="Page") != current.title:
            st.switch_page(next(p for p in pages() if p.title == st.session_state["page"]))
