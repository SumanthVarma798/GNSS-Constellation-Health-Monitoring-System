"""System design: the whole system in one picture, explained in simple terms with the technical details that matter.

The picture and its words are ui/components/system_design.{html,py}, a summary of docs/system-design.md.
"""
import streamlit as st
from streamlit.components.v1 import html

from console import common
from evidence.console_settings import JOBS, TESTS_WORKFLOW
from evidence.decision_settings import REPOSITORY
from evidence.source_overview import overview
from ui import console
from ui.components.hosting import hosting_html
from ui.components.system_design import facts_strip_html, system_design_html

# Each frame's height until its page fits the frame to itself (fitFrame in the page); none scrolls inside.
HEIGHT = 960
HOST_HEIGHT = 620
FACTS_HEIGHT = 88

body, actions = common.layout("design", "System design", "How the system works, from the sources it reads to the change a "
                                                         "person approves. Click any part for what it does and the details behind it.")
tokens = console.token_css(st.session_state.get("console_scheme", "auto"))
font = console.FONT


def live_facts(seen):
    sources = overview()
    return [(f"{sources['graded'] + sources['candidates']}", f"sources known; {sources['graded']} graded"),
            (str(sum(1 for w, *_ in JOBS if w != TESTS_WORKFLOW)), "scheduled jobs, all on GitHub Actions"),
            ("0", "servers of our own"),
            (str(len(seen["prs"])), "pull requests open"), (str(len(seen["issues"])), "issues open")]


with body:
    html(system_design_html(tokens, font), height=HEIGHT)   # the frame then fits itself to the picture


@st.fragment
def live_figures_from_github():
    seen = common.read()
    html(facts_strip_html(tokens, font, live_facts(seen)), height=FACTS_HEIGHT)   # fits itself; on a phone the figures wrap into rows
    st.caption(f"Live figures, read from GitHub at {seen['read_at']:%H:%M} UTC.")


with body:   # both pictures first: neither needs GitHub, so neither waits for it
    st.subheader("How it is hosted")
    st.caption("Where each public name points, and what redeploys when main changes. Click any box for details.")
    html(hosting_html(tokens, font), height=HOST_HEIGHT)
    live_figures_from_github()


with body:   # the assistant has a page of its own
    st.page_link("console/ask.py", label="Questions about the system: ask them on the Ask page",
                 icon=":material/forum:")

with actions:
    common.refresh_action()
    st.html('<p class="c-actions-sub">More</p>')
    st.link_button("The design document", f"https://github.com/{REPOSITORY}/blob/main/docs/system-design.md",
                   icon=":material/open_in_new:")
