"""The administration console: `streamlit run admin.py --server.port 48973`. Signed-in team members only (issue 17).

Google sign-in through Streamlit (st.login), with the allow-list and the GitHub token in .streamlit/secrets.toml under
[admin]. Then the console tree on the left (Streamlit's page list), a title bar and a toolbar (Back and Forward when
there is somewhere to go, the address, Refresh, colours, who is signed in), the page, and a status bar along the bottom.
Its look is its own (ui/console.py, ui/console.css); the dashboard (dashboard.py) keeps its own.
"""
from html import escape

import streamlit as st

from console import common, pages
from evidence import decisions
from evidence.decision_settings import READ_EVERY_SECONDS
from ui import console, sign_in_fix

st.set_page_config(page_title="GNSS Health Monitor - Administration", layout="wide", initial_sidebar_state="auto")
sign_in_fix.apply()   # before anyone presses Sign in


def _sign_out():
    """Forget everything typed or chosen in this browser, then sign out, so nothing carries over to the next person.
    Called from the script, not as a button's on_click: Streamlit ignores the rerun st.logout() asks for in a callback,
    which left the page signed in."""
    for key in list(st.session_state):
        del st.session_state[key]
    st.logout()


def _pick_scheme():
    st.session_state[common.CONSOLE_SCHEME_KEY] = (st.session_state[common.CONSOLE_SCHEME_PICK_KEY]
                                                    or st.session_state[common.CONSOLE_SCHEME_KEY])


scheme = st.session_state.setdefault(common.CONSOLE_SCHEME_KEY, common.CONSOLE_SCHEME_DEFAULT)
st.html(console.theme_css(scheme))

config = common.settings()
if missing := common.missing():
    words = f"{common.NOT_SET_UP} Missing or empty: {', '.join(missing)}."
    st.html(console.title_bar("Not set up") + f'<div class="c-signin c-signin-plain"><div class="in">{escape(words)}</div></div>')
    st.stop()

email = st.user.get("email")
state = decisions.access(st.user.is_logged_in, email, config["allowed"])
if state != "in":
    words = ("Sign in with the Google account on the team's list." if state == "sign in" else
             f"You are signed in as {email}, which is not on the list of people who may use the console. Ask for it to be added.")
    st.html(console.title_bar("Sign in"))
    with st.container(key="console_signin"):
        st.html(console.signin_card(escape(words)))
        if state == "sign in":
            st.button("Sign in with Google", key="console_sign_in", on_click=st.login, type="primary")
        elif st.button("Sign out", key="console_sign_out"):
            _sign_out()
    st.stop()

SECTIONS = pages.navigation_sections()
page = st.navigation(SECTIONS, position="sidebar")
where = {p.url_path: (section, p) for section, section_pages in SECTIONS.items() for p in section_pages}
trail = common.follow(st.session_state.setdefault("console_trail", {"back": [], "forward": [], "at": None}), page.url_path)
who = st.user.get("name") or email
st.html(console.title_bar(page.title) + console.current_page_css(page.url_path))
with st.sidebar, st.container(key="console_scheme"):   # placed in the tree's header, left of its close button
    st.session_state[common.CONSOLE_SCHEME_PICK_KEY] = scheme
    st.segmented_control("Colours", list(console.SCHEMES), format_func=console.SCHEME_ICONS.get,
                         key=common.CONSOLE_SCHEME_PICK_KEY,
                         on_change=_pick_scheme, label_visibility="collapsed",
                         help="Colours: as this computer is set, light, or dark")
with st.container(key="console_bar"):
    # each shown only when there is a page that way, and that page still exists (one may be removed mid-session)
    steps = [way for way in ("back", "forward") if trail[way] and trail[way][-1] in where]
    *step_cols, crumb, refresh, person, out = st.columns(len(steps) + 4, vertical_alignment="center")
    for col, way in zip(step_cols, steps):
        to = where[trail[way][-1]][1]
        if col.button(way.title(), key=f"console_{way}", icon=f":material/arrow_{way}:", help=f"{way.title()} to {to.title}"):
            st.switch_page(to)
    crumb.html(f'<span class="c-crumb">GNSS Health Monitor › {escape(where[page.url_path][0])} › '
               f'<b>{escape(page.title)}</b></span>')
    if refresh.button("Refresh", key="console_refresh", icon=":material/refresh:", help="Read everything again from GitHub"):
        common.request_refresh()
    person.html(f'<span class="c-who">Signed in as <b>{escape(who)}</b></span>')
    if out.button("Sign out", key="console_sign_out"):
        _sign_out()

page.run()

seen = common.read_status()
if st.session_state.pop(common.REFRESH_PENDING, False):
    st.toast(f"Read again from GitHub at {seen['read_at']:%H:%M} UTC")
failing = seen["status"]["failing"]
off = seen["status"]["off"]
waiting = seen["status"]["waiting"]
st.html(console.status_bar(
    [console.status("bad" if failing else "ok", f"{failing} job{'' if failing == 1 else 's'} failing"),
     console.status("warn" if off else "ok", f"{off} turned off"),
     console.status("warn" if waiting else "ok", f"{waiting} waiting for a decision")],
    f"Read from GitHub {seen['read_at']:%H:%M} UTC · read again every {READ_EVERY_SECONDS // 60} minutes"))
