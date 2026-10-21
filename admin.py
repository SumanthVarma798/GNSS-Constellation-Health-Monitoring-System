"""The administration console: `streamlit run admin.py --server.port 48973`. Signed-in team members only (issue 17).

Google sign-in through Streamlit (st.login), with the allow-list and the GitHub token in .streamlit/secrets.toml under
[admin]. Then the console tree on the left (Streamlit's page list), a title bar and a toolbar (Back and Forward when
there is somewhere to go, the address, Refresh, colours, who is signed in), the page, and a status bar along the bottom.
Its look is its own (ui/console.py, ui/console.css); the dashboard (dashboard.py) keeps its own.
"""
from html import escape

import streamlit as st

from console import common
from evidence import decisions, jobs
from evidence.decision_settings import READ_EVERY_SECONDS
from ui import console, sign_in_fix

st.set_page_config(page_title="GNSS Health Monitor - Administration", layout="wide", initial_sidebar_state="auto")
sign_in_fix.apply()   # before anyone presses Sign in


def _sign_out():
    """Forget everything typed or chosen in this browser before signing out, so nothing carries over to the next person."""
    for key in list(st.session_state):
        del st.session_state[key]
    st.logout()


def _pick_scheme():
    st.session_state["console_scheme"] = st.session_state["console_scheme_pick"] or st.session_state["console_scheme"]


scheme = st.session_state.setdefault("console_scheme", "auto")
st.html(console.theme_css(scheme))

config, sign_in_ready = common.settings()
if not (sign_in_ready and config.get("allowed") and config.get("github_token")):
    st.html(console.title_bar("Not set up") + f'<div class="c-signin"><div class="in">{escape(common.NOT_SET_UP)}</div></div>')
    st.stop()

email = st.user.get("email")
state = decisions.access(st.user.is_logged_in, email, config["allowed"])
if state != "in":
    words = ("Sign in with the Google account on the team's list." if state == "sign in" else
             f"You are signed in as {email}, which is not on the list of people who may use the console. Ask for it to be added.")
    st.html(console.title_bar("Sign in") + f'<div class="c-signin"><div class="in">{escape(words)}</div></div>')
    if state == "sign in":
        st.button("Sign in with Google", key="console_sign_in", on_click=st.login, type="primary")
    else:
        st.button("Sign out", key="console_sign_out", on_click=_sign_out)
    st.stop()

# The console tree: sections (shown as folders) and their pages, each page with its own icon.
SECTIONS = {"Overview": [st.Page("console/summary.py", title="Summary", icon=":material/dashboard:", default=True),
                         st.Page("console/design.py", title="System design", icon=":material/account_tree:",
                                 url_path="design")],
            "Monitoring": [st.Page("console/jobs.py", title="Jobs", icon=":material/schedule:")],
            "Work": [st.Page("console/work.py", title="Issues and pull requests", icon=":material/list_alt:",
                             url_path="work"),
                     st.Page("console/approvals.py", title="Approvals", icon=":material/task_alt:")]}
page = st.navigation(SECTIONS, position="sidebar")
where = {p.url_path: (section, p) for section, pages in SECTIONS.items() for p in pages}
trail = common.follow(st.session_state.setdefault("console_trail", {"back": [], "forward": [], "at": None}), page.url_path)
who = st.user.get("name") or email
st.html(console.title_bar(page.title) + console.current_page_css(page.url_path))
with st.container(key="console_bar"):
    steps = [way for way in ("back", "forward") if trail[way]]   # each shown only when there is a page that way
    *step_cols, crumb, refresh, pick, person, out = st.columns(len(steps) + 5, vertical_alignment="center")
    for col, way in zip(step_cols, steps):
        to = where[trail[way][-1]][1]
        if col.button(way.title(), key=f"console_{way}", icon=f":material/arrow_{way}:", help=f"{way.title()} to {to.title}"):
            st.switch_page(to)
    crumb.html(f'<span class="c-crumb">GNSS Health Monitor › {escape(where[page.url_path][0])} › '
               f'<b>{escape(page.title)}</b></span>')
    if refresh.button("Refresh", key="console_refresh", icon=":material/refresh:", help="Read everything again from GitHub"):
        common.github.clear()
    st.session_state["console_scheme_pick"] = scheme
    pick.segmented_control("Colours", list(console.SCHEMES), format_func=console.SCHEMES.get, key="console_scheme_pick",
                           on_change=_pick_scheme, label_visibility="collapsed", help="Light, dark, or as this computer is set")
    person.html(f'<span class="c-who">Signed in as <b>{escape(who)}</b></span>')
    out.button("Sign out", key="console_sign_out", on_click=_sign_out)

page.run()

seen = common.read()
rows = jobs.job_rows(seen["workflows"], seen["runs"], seen["log"], common.workflow_texts(), common.now())
failing = sum(r["result"][0] == "bad" for r in rows)
off = sum(r["state"] == "Turned off" for r in rows)
waiting = len(decisions.pending(seen["prs"], common.now()))
st.html(console.status_bar(
    [console.status("bad" if failing else "ok", f"{failing} job{'' if failing == 1 else 's'} failing"),
     console.status("warn" if off else "ok", f"{off} turned off"),
     console.status("warn" if waiting else "ok", f"{waiting} waiting for a decision")],
    f"Read from GitHub {seen['read_at']:%H:%M} UTC · read again every {READ_EVERY_SECONDS // 60} minutes"))
