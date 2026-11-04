"""The frame every page sits in: one top bar, no side panel.

The choices live in st.session_state: `scope` (one constellation), `compare` (on or off),
`compare_constellations` (the constellations Compare draws from; none means all), `compare_picks`
({constellation: [satellite, ...]}, set with ui.picker), `window_days` (the time range, ui/time_range.py) and
`params` (only the detection thresholds moved off their defaults). Pages read them.

The bar: the product name, then the filters as their own group (constellations, Compare, time range), then the
data's state (the UTC clock, when the next update is, the data chip, refresh and the gear). Two arrangements in
ui/theme.css: from 640px the filters as a strip of their own under the rest, and on a phone the constellations as
a menu.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from config.config import DEFAULT_PARAMS
from data import celestrak
from evidence import jobs
from evidence.console_settings import WORKFLOWS_DIR
from evidence.settings import ORBIT_ALERT_DAYS, ORBIT_STALE_DAYS
from ui import changes, data, surfaces, time_range

# Pages with their own filters: the bar shows no constellation, window or thresholds there.
OWN_FILTERS = {"Master map", "World map", "Library"}
# Pages that use only the constellation choice in the bar.
SCOPE_ONLY = {"News"}

# The pages, in one place. Add a page by adding a line: (title, file).
PAGES = [
    ("Overview", "views/overview.py"),
    ("Station-keeping", "views/station_keeping.py"),
    ("Geometry", "views/geometry.py"),
    ("News", "views/news.py"),
    ("Master map", "views/master_map.py"),
    ("World map", "views/world_map.py"),
    ("Library", "views/library.py"),
    # ("How it works", "views/how_it_works.py"),
]
CONSTELLATIONS = tuple(data.SATELLITES)
# The clock and "next update" are redrawn this often, alone: never a page redraw, at most this far behind.
CLOCK_TICK_SECONDS = 15

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

    Days and times are counted in `tz`, the viewer's time zone.
    """
    try:
        taken = datetime.fromisoformat(data_time)
    except (TypeError, ValueError):
        return "Orbit data date not known", "idle"
    taken = (taken if taken.tzinfo else taken.replace(tzinfo=timezone.utc)).astimezone(tz)
    days = (now.astimezone(tz).date() - taken.date()).days
    age = f" {taken:%H:%M}" if days <= 0 else ", 1 day old" if days == 1 else f", {days} days old"
    elapsed = (now - taken).total_seconds() / 86400   # coloured by time passed, as the orbit-age strip is
    status = "bad" if elapsed >= ORBIT_STALE_DAYS else "warn" if elapsed >= ORBIT_ALERT_DAYS else "ok"
    return f"Orbit data {taken.day} {taken:%b}{age}", status


def _day_time(moment, now, tz):
    """'14:02' for a moment today in `tz`, '18 Oct 14:02' for another day."""
    moment = moment.astimezone(tz)
    return f"{moment:%H:%M}" if moment.date() == now.astimezone(tz).date() else f"{moment.day} {moment:%b %H:%M}"


def failing_words(since, now, tz=timezone.utc, what="CelesTrak"):
    """'CelesTrak failing since 14:02' when the failures began today, 'CelesTrak failing since 18 Oct 14:02' before.

    `what` names the failing source. Days and times are counted in `tz`, the viewer's time zone.
    """
    return f"{what} failing since {_day_time(since, now, tz)}"


def copy_words(copy_at, now, tz=timezone.utc):
    """'CelesTrak via the archive job · copy 05:06 · next about 08:15' for a copy in use.

    The copy's time and the archive job's next orbital run are shown in `tz`, with the day in front when not today.
    No next time is shown when the workflow file cannot be read or has no orbital schedule.
    """
    words = f"CelesTrak via the archive job · copy {_day_time(copy_at, now, tz)}"
    try:
        crons = jobs.schedules((WORKFLOWS_DIR / "archive.yml").read_text(encoding="utf-8")).get("orbital", [])
        next_at = jobs.next_run(crons, now) if crons else None
    except (OSError, ValueError, TypeError, IndexError):
        next_at = None
    return words + (f" · next about {_day_time(next_at, now, tz)}" if next_at else "")


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


def viewer_zone():
    """The browser's time zone. st.context loses it after a page switch, so the first one seen is kept."""
    st.session_state["_zone"] = st.context.timezone or st.session_state.get("_zone")
    try:
        return ZoneInfo(st.session_state["_zone"])
    except Exception:   # no browser (tests) or a zone name Python does not know
        return timezone.utc


def _data_chip(names, window_days, params, live, now):
    """The time of the newest orbit data behind the page (the oldest constellation's), and since when its live source
    has been failing, if it is. Every saved copy stays in use meanwhile (issue 39: parts out of step say so); while
    the archive job's copy is in use, the second chip says so, and the age chip keeps its colour."""
    try:
        taken = min(data.load(c, window_days, params)["data_time"] for c in names)
    except ValueError:
        return surfaces.chip("No orbit data", "bad")
    if live["fetched"]:
        taken = max(taken, live["fetched"].isoformat())
    text, status = age_words(taken, now, viewer_zone())
    # A copy in use means the last read worked: a failed read clears copy_at (a state saved by older code may still
    # say ok False beside it, and is not failing).
    if live.get("copy_at"):
        return surfaces.chip(text, status) + surfaces.chip(copy_words(live["copy_at"], now, viewer_zone()), "idle")
    if live["ok"]:
        return surfaces.chip(text, status)
    # A copy saved before failing_since was kept has none: its last try stands in.
    return surfaces.chip(text, status) + surfaces.chip(
        failing_words(live["failing_since"] or live["tried"], now, viewer_zone(), what="Archive copy"), "warn")


def next_words(left):
    """'Next update in 1 h 42 m' for `left` seconds to go; minutes are rounded up, so it never says 0 m too soon."""
    if left <= 0:
        return "Next update due now"
    hours, minutes = divmod(-(-int(left) // 60), 60)
    parts = ([f"{hours} h"] if hours else []) + ([f"{minutes} m"] if minutes or not hours else [])
    return "Next update in " + " ".join(parts)


def clock_words(now):
    """'14:05 UTC'."""
    return f"{now.astimezone(timezone.utc):%H:%M} UTC"


def _left(tried, now):
    """Seconds to the next automatic refresh; 0 before the first try."""
    return max(0.0, (tried + celestrak.EVERY - now).total_seconds()) if tried else 0.0


def _ring(live, now):
    """A style rule: the ring round the refresh button holds the share of the wait left before the next automatic
    refresh, and empties over that time. A keyframe name per run restarts it from the right place."""
    left = _left(live["tried"], now)
    share = f"{100 * left / celestrak.EVERY.total_seconds():.2f}%"
    name = f"ring{now:%H%M%S%f}"
    return (f"<style>@keyframes {name} {{ from {{ --left: {share}; }} to {{ --left: 0%; }} }}"
            f".st-key-refresh_button button::before {{ --left: {share}; animation: {name} {left:.0f}s linear forwards; }}"
            + ("" if live["ok"] or live.get("copy_at") else ".st-key-refresh_button button::before { --ring: var(--warn); }")
            + "</style>")


@st.fragment(run_every=CLOCK_TICK_SECONDS)
def _clock():
    """The UTC clock and the wait to the next automatic refresh, redrawn alone every CLOCK_TICK_SECONDS; when the
    refresh is due the whole page reruns and the top bar fetches."""
    now = datetime.now(timezone.utc)
    if celestrak.state["tried"] and celestrak.due(now):
        st.rerun()
    upcoming = next_words(_left(celestrak.state["tried"], now)) if celestrak.state["tried"] else ""
    st.html(f'<span class="clock num">{clock_words(now)}</span><span class="next">{upcoming}</span>')


def _refresh(names, window_days, gear_scope):
    """The UTC clock and the wait to the next automatic refresh, the data chip, the round refresh button with its
    ring, and the gear (on pages without their own filters, `gear_scope` names whose thresholds it shows)."""
    with st.container(key="refresh"):
        clock, chip = st.container(key="clock"), st.empty()
        clicked = st.button("Refresh orbit data", key="refresh_button", icon=":material/refresh:",
                            help="Re-read the archive job's newest copy of the orbit data")
        if gear_scope:
            with st.popover("", icon=":material/settings:", help="Detection thresholds"):
                st.session_state["params"] = _thresholds(gear_scope)
        _own_login()
        live, now = data.refresh(clicked), datetime.now(timezone.utc)
        chip.html(_data_chip(names, window_days, st.session_state["params"], live, now) + _ring(live, now))
        with clock:   # after the refresh, so it reads the try just made
            _clock()


_OWN_NOTE_WORDS = {"busy": "busy, will try again in an hour", "login refused": "login refused"}


def _own_login():
    """The key popover next to the gear: the viewer's own Space-Track login, kept only for this visit."""
    with st.popover("", icon=":material/key:", help="Your Space-Track login (this session only)"):
        login = st.session_state.get(data.OWN_LOGIN)
        if login:
            st.write("Using your Space-Track login for this visit")
            note = st.session_state.get(data.OWN_NOTE)
            if note and note != "ok":
                st.write(_OWN_NOTE_WORDS.get(note, note))
            if st.button("Forget my login", key="forget_login"):
                # The last try's time stays, so a new login still waits out the hour.
                for key in (data.OWN_LOGIN, data.OWN_ROWS, data.OWN_NOTE):
                    st.session_state.pop(key, None)
                st.rerun()
            return
        if st.session_state.get(data.OWN_NOTE) == "login refused":
            st.write("Space-Track refused that login, so it was forgotten. Check it on space-track.org and try again.")
        st.write("Space-Track fills in satellites CelesTrak has not updated for 2 days. "
                 "Your login is kept only for this visit, on the server, and never saved.")
        with st.form("own_login_form", clear_on_submit=True):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            use = st.form_submit_button("Use my login for this visit")
        if use and not (username and password):
            st.write("Enter both the username and the password.")
        elif use:
            st.session_state[data.OWN_LOGIN] = (username, password)
            st.session_state[data.OWN_NOTE] = "ok"
            st.rerun()


def _toggle_compare():
    st.session_state["compare"] = not st.session_state.get("compare", False)


def _keep(plain, widget):
    st.session_state[plain] = st.session_state[widget]


def _from_menu(plain, widget):
    """A choice in the phone's menu; clicking the chosen constellation again keeps it."""
    if st.session_state[widget] is not None:
        st.session_state[plain] = st.session_state[widget]


def _menu(plain, multi):
    """On a phone the chips are a menu: a button naming the choice that opens the same chips as a list. The same
    choice as the chips, under its own key; ui/theme.css shows one or the other by screen width."""
    chosen = st.session_state.get(plain, [] if multi else CONSTELLATIONS[0])
    title = (chosen if not multi else "All constellations" if not chosen else
             chosen[0] if len(chosen) == 1 else f"{len(chosen)} constellations")
    st.session_state[f"_{plain}_menu"] = chosen
    with st.container(key="scope_menu"), st.popover(title, help="Choose the constellation"):
        st.segmented_control("Constellations menu" if multi else "Constellation menu", CONSTELLATIONS,
                             selection_mode="multi" if multi else "single", key=f"_{plain}_menu",
                             label_visibility="collapsed", on_change=_from_menu, args=(plain, f"_{plain}_menu"))


def _scope(force_single=False):
    """Constellation chips: one chosen, or under Compare any number (none means all). Returns the names in view."""
    if force_single or not st.session_state.get("compare"):
        name = segment("scope", list(CONSTELLATIONS), label="Constellation")
        _menu("scope", multi=False)
        return [name]
    st.session_state["_compare_constellations"] = st.session_state.get("compare_constellations", [])
    st.segmented_control("Constellations", CONSTELLATIONS, selection_mode="multi", key="_compare_constellations",
                         label_visibility="collapsed", on_change=_keep,
                         args=("compare_constellations", "_compare_constellations"))
    _menu("compare_constellations", multi=True)
    names = offered()
    st.session_state["compare_picks"] = {c: picks for c, picks in st.session_state.get("compare_picks", {}).items()
                                         if c in names and picks}
    return names


def top_bar(current):
    """Draw the bar and store the choices. `current` is the st.Page that is running."""
    st.session_state.setdefault("compare", False)
    with st.container(key="topbar"):
        brand, filters, refresh_box = st.columns(3, vertical_alignment="center")
        brand.html('<span class="brand">GNSS Health Monitor</span>')
        st.session_state.setdefault("params", {})
        window_days = st.session_state.setdefault("window_days", time_range.DEFAULT_DAYS)
        if current.title in OWN_FILTERS:
            names = [st.session_state.get("scope", CONSTELLATIONS[0])]
            gear_scope = None
        elif current.title in SCOPE_ONLY:
            with filters:
                with st.container(key="filters"):
                    names = _scope(force_single=True)
            gear_scope = None
        else:
            with filters:
                filter_box = st.container(key="filters")
            with filter_box:
                names = _scope()
                on = st.session_state["compare"]
                st.button("Compare", key="compare_toggle", icon=":material/check:" if on else None,
                          type="primary" if on else "secondary", on_click=_toggle_compare,
                          help="Compare satellites across constellations")
            gear_scope = "Compare" if on else names[0]
        with refresh_box:
            _refresh(names, window_days, gear_scope)
        if current.title not in OWN_FILTERS | SCOPE_ONLY:   # after the gear, so the range's bounds read this run's thresholds
            with filter_box:
                time_range.control(names, st.session_state["params"])
    _page_tabs(current)
    changes.show(CONSTELLATIONS if current.title in OWN_FILTERS else names)   # the master map shows every constellation


def _page_tabs(current):
    """The pages under the bar, in two groups: those that look at one constellation at a time, and those that look
    across every system (OWN_FILTERS). One page is chosen across both groups."""
    with st.container(key="pagetabs"):
        if st.session_state.get("shown_page") != current.title:   # arrived by address or switch: tabs follow the page
            st.session_state["page"] = current.title
        st.session_state["shown_page"] = current.title
        page = st.session_state["page"]
        for key, label, titles in (("page_one", "Page", [t for t, _ in PAGES if t not in OWN_FILTERS]),
                                   ("page_all", "Across all systems", [t for t, _ in PAGES if t in OWN_FILTERS])):
            st.session_state[key] = page if page in titles else None
            with st.container(key=f"{key}_group"):
                st.segmented_control(label, titles, key=key, label_visibility="collapsed", on_change=_pick_page, args=(key,))
        if st.session_state["page"] != current.title:
            st.switch_page(next(p for p in pages() if p.title == st.session_state["page"]))


def _pick_page(key):
    """A tab in either group chooses the page; clicking the chosen tab again keeps it chosen."""
    if st.session_state[key] is not None:
        st.session_state["page"] = st.session_state[key]
