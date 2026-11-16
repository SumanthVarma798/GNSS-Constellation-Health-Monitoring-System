"""The frame every page sits in: one top bar, no side panel.

The choices live in st.session_state: `scope` (one constellation: a system, or one part of it, ui/systems.py),
`page` (the page wanted), `compare` (on or off),
`compare_constellations` (the constellations Compare draws from; none means all), `compare_picks`
({constellation: [satellite, ...]}, set with ui.picker), `window_days` (the time range, ui/time_range.py) and
`params` (only the detection thresholds moved off their defaults). Pages read them.

The bar: the product name and its buttons (refresh, the gear, the key; the bell keeps its room beside them), and the
data's state (the UTC clock, when the next update is, the data chip). Under it, the navigation in two steps (_nav): the pages across every system and the systems, then,
once a system is chosen, that system's pages with what filters them. On a phone the systems are a menu.
"""
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

import base64
from pathlib import Path

import streamlit as st

from config.config import DEFAULT_PARAMS
from data import celestrak
from evidence import jobs
from evidence.console_settings import WORKFLOWS_DIR
from evidence.registry_tables import judged_by_plane
from ui import changes, data, marks, palette, surfaces, systems, threshold_settings, time_range, tooltip
from ui.age_rule import orbit_age_status
from ui.components.clock import clock_frame

# Pages with their own filters: the bar shows no constellation, window or thresholds there.
HOME = "Home"   # every system side by side: where a first-time reader starts
OWN_FILTERS = {HOME, "Master map", "World map", "Library"}
# Pages that use only the constellation choice in the bar.
SCOPE_ONLY = {"News"}

# The pages, in one place. Add a page by adding a line: (title, file).
PAGES = [
    (HOME, "views/home.py"),
    ("Overview", "views/overview.py"),
    ("Station-keeping", "views/station_keeping.py"),
    ("Geometry", "views/geometry.py"),
    ("News", "views/news.py"),
    ("Master map", "views/master_map.py"),
    ("World map", "views/world_map.py"),
    ("Library", "views/library.py"),
]
CONSTELLATIONS = tuple(data.SATELLITES)
DEFAULT_PAGE = HOME   # the page the dashboard opens on
# The OpenGNSS mark (ui/opengnss_logo.svg), inline: st.html drops <svg>, but keeps a data address. It is drawn as a
# mask (ui/theme.css .brand-mark), so it takes the theme's colour whatever colour the file is drawn in.
LOGO = "data:image/svg+xml;base64," + base64.b64encode(
    (Path(__file__).with_name("opengnss_logo.svg")).read_bytes()).decode()
# The clock and "next update" are redrawn this often, alone: never a page redraw, at most this far behind.
CLOCK_TICK_SECONDS = 15

# Under every page: the licences (LICENSE, LICENSE-DATA) and whose data the pages draw on, as NOTICE lists them.
FOOTER_HTML = (
    '<div class="footer small">'
    'Code <a href="https://www.apache.org/licenses/LICENSE-2.0">Apache-2.0</a> · '
    'Our data <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> · '
    'Orbits from CelesTrak and Space-Track · Navigation messages from the IGS, via BKG · '
    'Catalogue from GCAT (J. McDowell, planet4589.org/space/gcat) · Land from Natural Earth'
    '</div>'
)


def footer():
    """The licence and credits line, after the page."""
    st.html(FOOTER_HTML)


def pages():
    """PAGES as st.Page objects."""
    return [st.Page(path, title=title, default=title == DEFAULT_PAGE) for title, path in PAGES]


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
    status = orbit_age_status(elapsed)
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
    """'Orbits from CelesTrak, fetched 05:06 · next fetch about 08:15' for a copy in use: in words a reader of the
    dashboard knows (the archive job that fetches them is ours, not theirs).

    The copy's time and the archive job's next orbital run are shown in `tz`, with the day in front when not today.
    No next time is shown when the workflow file cannot be read or has no orbital schedule.
    """
    words = f"Orbits from CelesTrak, fetched {_day_time(copy_at, now, tz)}"
    try:
        crons = jobs.schedules((WORKFLOWS_DIR / "archive.yml").read_text(encoding="utf-8")).get("orbital", [])
        next_at = jobs.next_run(crons, now) if crons else None
    except (OSError, ValueError, TypeError, IndexError):
        next_at = None
    return words + (f" · next fetch about {_day_time(next_at, now, tz)}" if next_at else "")


def offered():
    """The constellations Compare draws from: those chosen in the top bar, or all when none are."""
    chosen = st.session_state.get("compare_constellations", [])
    return [c for c in CONSTELLATIONS if c in chosen] or list(CONSTELLATIONS)


def _default(setting, scope):
    return threshold_settings.DEFAULTS_BY_SYSTEM.get(scope, {}).get(setting["key"], DEFAULT_PARAMS[setting["key"]])


def _reset(scope, shown):
    """Reset's on_click: every setting shown goes back to its default."""
    for setting in shown:
        st.session_state[f"th_{setting['key']}_{scope}"] = _default(setting, scope)


def _setting_help(setting, default):
    """What to know before moving one setting. What it does is always in view; what raising and lowering it does,
    and when to change it, open one step deeper."""
    rows = "".join(f"<div><dt>{escape(term)}</dt><dd>{escape(setting[field])}</dd></div>" for term, field in (
        ("Raise it", "raise"), ("Lower it", "lower"), ("Change it when", "when")))
    return (f'<p class="th-what">{escape(setting["what"])}</p>'
            f'<details class="th-more"><summary>Raising it, lowering it, and when to change it</summary>'
            f'<dl class="th-help">{rows}</dl></details>'
            f'<p class="th-also small">Default {setting["format"] % default} · also called {escape(setting["also"])}</p>')


def _thresholds(scope):
    """The gear's panel: each setting with what to know before moving it, in its group, and a way back to the
    defaults. Returns only the settings moved off their defaults. A system judged by orbital plane shows the
    settings that find burns; its scoring limits are not moved here."""
    by_plane = judged_by_plane(scope)
    shown = [s for s in threshold_settings.SETTINGS if not (by_plane and s["group"] == threshold_settings.SCORING)]
    st.html(f'<div class="th-head"><b>Settings for {escape(scope)}</b><span class="small">They apply on this '
            "constellation's pages for this visit. The Home page always uses the defaults.</span></div>")
    moved = {}
    for group, words in threshold_settings.GROUPS.items():
        if by_plane and group == threshold_settings.SCORING:
            st.html(f'<div class="th-group"><b>{escape(group)}</b><span class="small">'
                    f'{escape(threshold_settings.BY_PLANE.format(name=scope))}</span></div>')
            continue
        st.html(f'<div class="th-group"><b>{escape(group)}</b><span class="small">{escape(words)}</span></div>')
        for setting in (s for s in shown if s["group"] == group):
            default = _default(setting, scope)
            with st.container(key=f"thset_{setting['key']}"):
                value = st.number_input(setting["label"], setting["low"], setting["high"], default, setting["step"],
                                        format=setting["format"], key=f"th_{setting['key']}_{scope}")
                st.html(_setting_help(setting, default))
            if value != default:
                moved[setting["key"]] = value
    st.button("Back to the defaults", key=f"th_reset_{scope}", on_click=_reset, args=(scope, shown),
              disabled=not moved, help="Every setting above returns to its default")
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
    # say ok False beside it, and is not failing). Where it came from and when the next comes is in the chip's tip,
    # so the bar keeps one short chip; a failing fetch stays in view as its own chip.
    if live.get("copy_at"):
        return tooltip.tip_html(surfaces.chip(text, status), tooltip.glance(text, [
            ("", "Source", copy_words(live["copy_at"], now, viewer_zone())),
            ("", "Refresh", "the round button loads the newest copy we have")]), key="data_chip")
    if live["ok"]:
        return surfaces.chip(text, status)
    # A copy saved before failing_since was kept has none: its last try stands in.
    return surfaces.chip(text, status) + surfaces.chip(
        failing_words(live["failing_since"] or live["tried"], now, viewer_zone(), what="Orbit fetch"), "warn")


def next_words(left):
    """'Next update in 1 h 42 m' for `left` seconds to go; minutes are rounded up, so it never says 0 m too soon."""
    if left <= 0:
        return "Next update due now"
    hours, minutes = divmod(-(-int(left) // 60), 60)
    parts = ([f"{hours} h"] if hours else []) + ([f"{minutes} m"] if minutes or not hours else [])
    return "Next update in " + " ".join(parts)


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
    """The wait to the next automatic refresh, redrawn alone every CLOCK_TICK_SECONDS (the clock above it ticks in the
    browser: ui/components/clock.py); when the refresh is due the whole page reruns and the top bar fetches."""
    now = datetime.now(timezone.utc)
    if celestrak.state["tried"] and celestrak.due(now):
        st.rerun()
    upcoming = next_words(_left(celestrak.state["tried"], now)) if celestrak.state["tried"] else ""
    st.html(f'<span class="next">{upcoming}</span>')


def _refresh(names, window_days, gear_scope):
    """The bar's groups, each with its own place on its grid (ui/theme.css, "the bar"): the UTC clock and the wait to
    the next automatic refresh in the middle; on the right the data chip, then the buttons (the round refresh button
    with its ring, the gear, and the key). The gear is always there, so the bar does not change from page to page: on
    a constellation's pages it opens that constellation's settings (`gear_scope` names whose), elsewhere it is greyed
    and says where they are."""
    with st.container(key="bar_clock"):
        clock = st.container(key="clock")
    with st.container(key="bar_right"):
        with st.container(key="bar_chip"):
            chip = st.empty()
        with st.container(key="bar_buttons"):
            clicked = st.button("Refresh orbit data", key="refresh_button", icon=":material/refresh:",
                                help="Load the newest orbit data we have fetched")
            if gear_scope:
                with st.popover("", icon=":material/settings:", help="Settings: what counts as a burn, and how strictly satellites are scored"):
                    st.session_state["params"] = _thresholds(gear_scope)
            else:
                st.button("Settings", key="gear_off", icon=":material/settings:", disabled=True,
                          help="Settings belong to one constellation: choose one to change its limits. This page "
                               "uses the defaults.")
            _own_login()
    live, now = data.refresh(clicked), datetime.now(timezone.utc)
    chip.html(_data_chip(names, window_days, st.session_state["params"], live, now) + _ring(live, now))
    with clock:   # after the refresh, so it reads the try just made
        clock_frame()
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


def offered_parts():
    """The constellations in view under Compare, with the picks of those no longer offered dropped."""
    names = offered()
    st.session_state["compare_picks"] = {c: picks for c, picks in st.session_state.get("compare_picks", {}).items()
                                         if c in names and picks}
    return names


def _pick_system(widget):
    """A system chosen in the bar or in the phone's menu: its pages open, on the page last read for a system.
    Clicking the chosen system again keeps it."""
    system = st.session_state[widget]
    if system is None:
        return
    if st.session_state["scope"] not in systems.SYSTEMS[system]:
        st.session_state["scope"] = systems.SYSTEMS[system][0]
    if st.session_state["page"] in OWN_FILTERS:
        st.session_state["page"] = st.session_state.get("system_page", SYSTEM_PAGES[0])


def _pick_part(widget):
    """A part of the system chosen; clicking the chosen part again keeps it."""
    if st.session_state[widget] is not None:
        st.session_state["scope"] = st.session_state[widget]


def _pick_page(key):
    """A page chosen in either row; clicking the chosen page again keeps it chosen."""
    if st.session_state[key] is not None:
        st.session_state["page"] = st.session_state[key]


def _go_home():
    """The brand's on_click: back to Home from any page, keeping the reader's choices (no page reload)."""
    st.session_state.update({"compare": False, "page": HOME})


def open_system(name):
    """A button's on_click: go to the Overview of `name`, a system's part as ui.data.SATELLITES names it."""
    st.session_state.update({"scope": name, "compare": False, "page": "Overview"})


def top_bar(current):
    """Draw the bar and the navigation under it, and store the choices. `current` is the st.Page that is running."""
    st.session_state.setdefault("compare", False)
    st.session_state.setdefault("params", {})
    st.session_state.setdefault("scope", CONSTELLATIONS[0])
    window_days = st.session_state.setdefault("window_days", time_range.DEFAULT_DAYS)
    on_system = current.title not in OWN_FILTERS
    filtered = on_system and current.title not in SCOPE_ONLY   # the page takes Compare, the range and the thresholds
    comparing = filtered and st.session_state["compare"]
    names = offered_parts() if comparing else [st.session_state["scope"]]
    with st.container(key="topbar"), st.container(key="bar_grid"):
        with st.container(key="brand"):   # the OpenGNSS mark and the name; a click on either opens Home
            st.html(f'<span class="brand"><span class="brand-mark" role="img" aria-label="OpenGNSS" '
                    f'style="--logo: url({LOGO})"></span>'
                    '<span>GNSS Health Monitor</span></span>')
            st.button("Home", key="brand_home", on_click=_go_home, help="Back to Home")
        _refresh(names, window_days, ("Compare" if comparing else names[0]) if filtered else None)
    _nav(current, names, on_system, filtered, comparing)
    changes.post(CONSTELLATIONS if current.title in OWN_FILTERS else names)   # the pages across all systems show every one


# The pages across every system, and the pages of one system, each in the order of PAGES.
ALL_PAGES = [title for title, _ in PAGES if title in OWN_FILTERS]
SYSTEM_PAGES = [title for title, _ in PAGES if title not in OWN_FILTERS]


def _chip_marks():
    """A style rule that puts each constellation's mark (ui/marks.py) before its name on its chip, in the row and in
    the phone's menu. The chips are a Streamlit control whose labels take no markup, so the marks are drawn by
    position: the chips are in the order of ui.systems.SYSTEMS."""
    rules = "".join(
        f":is(.st-key-nav_system, .st-key-nav_system_menu) button:nth-of-type({place})::before "
        f"{{ --mk: var(--mk-{marks.key(name).lower()}); color: {palette.CONSTELLATION_COLOURS[marks.key(name)]}; }}"
        for place, name in enumerate(systems.SYSTEMS, 1) if marks.key(name))
    return f"<style>{rules}</style>"


def _nav(current, names, on_system, filtered, comparing):
    """The navigation under the bar, in two steps. First row, always there: the pages across every system, then the
    systems. Choosing a system opens the second row: that system's pages, its parts when it has several, and what
    filters them (Compare, the time range). On a page across every system the second row is closed. One page is
    chosen across both rows. The second row stays on the page, closed to no height, so it opens and closes with a
    motion (ui/theme.css, "navigation")."""
    if st.session_state.get("shown_page") != current.title:   # arrived by address or switch: the rows follow the page
        st.session_state["page"] = current.title
    st.session_state["shown_page"] = current.title
    system = systems.system_of(st.session_state["scope"])
    if on_system:
        st.session_state["system_page"] = current.title
    with st.container(key="nav"):
        st.session_state["nav_all"] = None if on_system else current.title
        st.segmented_control("Across all constellations", ALL_PAGES, key="nav_all", label_visibility="collapsed",
                             on_change=_pick_page, args=("nav_all",))
        st.html(_chip_marks() + '<span class="nav-label">Constellations</span>')
        st.session_state["nav_system"] = st.session_state["nav_system_menu"] = system if on_system else None
        st.segmented_control("Choose a constellation", list(systems.SYSTEMS), key="nav_system", label_visibility="collapsed",
                             on_change=_pick_system, args=("nav_system",))
        with st.container(key="system_menu"), st.popover(system if on_system else "Choose a constellation",
                                                         help="Choose the constellation"):   # the phone's menu
            st.segmented_control("Constellation menu", list(systems.SYSTEMS), key="nav_system_menu",
                                 label_visibility="collapsed", on_change=_pick_system, args=("nav_system_menu",))
    with st.container(key="subnav"), st.container(key="subnav_in"):
        st.session_state["nav_page"] = current.title if on_system else None
        st.segmented_control(f"{system} pages", SYSTEM_PAGES, key="nav_page", label_visibility="collapsed",
                             on_change=_pick_page, args=("nav_page",))
        parts = systems.SYSTEMS[system]
        if on_system and len(parts) > 1 and not comparing:
            st.session_state["nav_part"] = st.session_state["scope"]
            st.segmented_control(f"Part of {system}", parts, key="nav_part", format_func=systems.part_name,
                                 label_visibility="collapsed", on_change=_pick_part, args=("nav_part",))
        if filtered:
            st.button("Compare", key="compare_toggle", icon=":material/check:" if comparing else None,
                      type="primary" if comparing else "secondary", on_click=_toggle_compare,
                      help="Compare satellites across constellations")
            if comparing:
                st.session_state["_compare_constellations"] = st.session_state.get("compare_constellations", [])
                st.segmented_control("Constellations", CONSTELLATIONS, selection_mode="multi",
                                     key="_compare_constellations", label_visibility="collapsed", on_change=_keep,
                                     args=("compare_constellations", "_compare_constellations"))
            time_range.control(names, st.session_state["params"])   # after the gear: its bounds read this run's thresholds
    if st.session_state["page"] != current.title:
        st.switch_page(next(p for p in pages() if p.title == st.session_state["page"]))
