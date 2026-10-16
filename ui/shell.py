"""The frame every page sits in: one top bar, no side panel.

The choices live in st.session_state: `scope` (one constellation), `compare` (on or off),
`compare_constellations` (the constellations Compare draws from; none means all), `compare_picks`
({constellation: [satellite, ...]}, set with ui.picker), `window_days` and `params` (only the
detection thresholds moved off their defaults). Pages read them.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from config.config import DEFAULT_PARAMS
from data import celestrak
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
CONSTELLATIONS = tuple(data.SATELLITES)
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
    st.session_state.setdefault(key, st.session_state.get(f"_{key}_was", options[0]))   # back from a page without it
    st.session_state[f"_{key}_was"] = st.session_state[key]

    def keep():
        if st.session_state[key] is None:
            st.session_state[key] = st.session_state[f"_{key}_was"]

    st.segmented_control(label, options, key=key, format_func=lambda o: labels.get(o, o),
                         label_visibility="collapsed", on_change=keep)
    return st.session_state[key]


def age_words(data_time, now, tz=timezone.utc):
    """('Orbit data 15 Oct 10:42', 'ok') for data from today, ('Orbit data 4 Oct, 10 days old', 'warn') for older.

    Days and times are counted in `tz`, the viewer's time zone. Warn after STALE_DAYS days.
    """
    try:
        taken = datetime.fromisoformat(data_time)
    except (TypeError, ValueError):
        return "Orbit data date not known", "idle"
    taken = (taken if taken.tzinfo else taken.replace(tzinfo=timezone.utc)).astimezone(tz)
    days = (now.astimezone(tz).date() - taken.date()).days
    age = f" {taken:%H:%M}" if days <= 0 else ", 1 day old" if days == 1 else f", {days} days old"
    return f"Orbit data {taken.day} {taken:%b}{age}", "warn" if days > STALE_DAYS else "ok"


def offered():
    """The constellations Compare draws from: those chosen in the top bar, or all when none are."""
    chosen = st.session_state.get("compare_constellations", [])
    return [c for c in CONSTELLATIONS if c in chosen] or list(CONSTELLATIONS)


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


def _viewer_zone():
    """The browser's time zone. st.context loses it after a page switch, so the first one seen is kept."""
    st.session_state["_zone"] = st.context.timezone or st.session_state.get("_zone")
    try:
        return ZoneInfo(st.session_state["_zone"])
    except Exception:   # no browser (tests) or a zone name Python does not know
        return timezone.utc


def _data_chip(names, window_days, params, live, now):
    """The time of the newest orbit data behind the page (the oldest constellation's), and a warning if a refresh failed."""
    try:
        taken = min(data.load(c, window_days, params)["data_time"] for c in names)
    except ValueError:
        return surfaces.chip("No orbit data", "bad")
    if live["fetched"]:
        taken = max(taken, live["fetched"].isoformat())
    text, status = age_words(taken, now, _viewer_zone())
    return surfaces.chip(text, status) + ("" if live["ok"] else surfaces.chip("Refresh failed", "warn"))


def _next(live):
    """'next update 14:20': when the next automatic refresh is, in the viewer's time zone."""
    if not live["tried"]:
        return ""
    return f'<span class="next">next update {(live["tried"] + celestrak.EVERY).astimezone(_viewer_zone()):%H:%M}</span>'


def _ring(live, now):
    """A style rule: the ring round the refresh button holds the share of the wait left before the next automatic
    refresh, and empties over that time. A keyframe name per run restarts it from the right place."""
    left = max(0.0, (live["tried"] + celestrak.EVERY - now).total_seconds()) if live["tried"] else 0.0
    share = f"{100 * left / celestrak.EVERY.total_seconds():.2f}%"
    name = f"ring{now:%H%M%S%f}"
    return (f"<style>@keyframes {name} {{ from {{ --left: {share}; }} to {{ --left: 0%; }} }}"
            f".st-key-refresh_button button::before {{ --left: {share}; animation: {name} {left:.0f}s linear forwards; }}"
            + ("" if live["ok"] else ".st-key-refresh_button button::before { --ring: var(--warn); }") + "</style>")


def _auto_refresh(seconds):
    """Rerun the whole page when the next automatic refresh is due; the top bar then fetches."""
    @st.fragment(run_every=seconds)
    def tick():
        if celestrak.due(datetime.now(timezone.utc)):
            st.rerun()
    tick()


def _refresh(names, window_days, gear_scope):
    """The data chip, the time of the next automatic refresh, the round refresh button with its ring, and the gear
    (on pages without their own filters, `gear_scope` names whose thresholds it shows)."""
    with st.container(key="refresh"):
        chip = st.empty()
        clicked = st.button("Refresh orbit data", key="refresh_button", icon=":material/refresh:",
                            help="Pull the newest orbit data")
        if gear_scope:
            with st.popover("", icon=":material/settings:", help="Detection thresholds"):
                st.session_state["params"] = _thresholds(gear_scope)
        live, now = data.refresh(clicked), datetime.now(timezone.utc)
        chip.html(_data_chip(names, window_days, st.session_state["params"], live, now) + _next(live)
                  + _ring(live, now))
        left = (live["tried"] + celestrak.EVERY - now).total_seconds() if live["tried"] else 0
        _auto_refresh(max(1, int(left) + 1))


def _toggle_compare():
    st.session_state["compare"] = not st.session_state.get("compare", False)


def _keep(plain, widget):
    st.session_state[plain] = st.session_state[widget]


def _scope():
    """Constellation chips: one chosen, or under Compare any number (none means all). Returns the names in view."""
    if not st.session_state.get("compare"):
        return [segment("scope", list(CONSTELLATIONS), label="Constellation")]
    st.session_state["_compare_constellations"] = st.session_state.get("compare_constellations", [])
    st.segmented_control("Constellations", CONSTELLATIONS, selection_mode="multi", key="_compare_constellations",
                         label_visibility="collapsed", on_change=_keep,
                         args=("compare_constellations", "_compare_constellations"))
    names = offered()
    st.session_state["compare_picks"] = {c: picks for c, picks in st.session_state.get("compare_picks", {}).items()
                                         if c in names and picks}
    return names


def top_bar(current):
    """Draw the bar and store the choices. `current` is the st.Page that is running."""
    st.session_state.setdefault("compare", False)
    with st.container(key="topbar"):
        brand, scope_box, compare_box, window_box, refresh_box = st.columns(5, vertical_alignment="center")
        brand.html('<b class="brand">GNSS Health</b>')
        if current.title in OWN_FILTERS:
            names = [st.session_state.get("scope", CONSTELLATIONS[0])]
            window_days = st.session_state.get("window_days", 90)
            st.session_state.setdefault("params", {})
            gear_scope = None
        else:
            with scope_box:
                names = _scope()
            on = st.session_state["compare"]
            compare_box.button("Compare", key="compare_toggle", icon=":material/check:" if on else None,
                               type="primary" if on else "secondary", on_click=_toggle_compare,
                               help="Compare satellites across constellations")
            with window_box:
                window_days = segment("window_days", list(WINDOWS), WINDOWS, label="Window")
            gear_scope = "Compare" if on else names[0]
        with refresh_box:
            _refresh(names, window_days, gear_scope)
    _page_tabs(current)


def _page_tabs(current):
    """The pages sit under the bar, as tabs: there is room for more of them there."""
    with st.container(key="pagetabs"):
        if st.session_state.get("shown_page") != current.title:   # arrived by address or switch: tabs follow the page
            st.session_state["page"] = current.title
        st.session_state["shown_page"] = current.title
        if segment("page", [title for title, _ in PAGES], label="Page") != current.title:
            st.switch_page(next(p for p in pages() if p.title == st.session_state["page"]))
