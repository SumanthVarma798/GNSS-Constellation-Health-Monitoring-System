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
from ui.components.system_design import system_design_html

HEIGHT = 1000   # the picture, the steps and the longest card on a wide screen; a phone scrolls inside the frame

seen = common.read()
sources = overview()
facts = [(f"{sources['graded'] + sources['candidates']}", f"sources known; {sources['graded']} graded"),
         (str(sum(1 for w, *_ in JOBS if w != TESTS_WORKFLOW)), "scheduled jobs, all on GitHub Actions"),
         ("0", "servers of our own"),
         (str(len(seen["prs"])), "pull requests open"), (str(len(seen["issues"])), "issues open")]

body, actions = common.layout("design", "System design", "How the system works, from the sources it reads to the change a "
                                                         "person approves. Click any part for what it does and the details behind it.")
with body:
    html(system_design_html(console.token_css(st.session_state.get("console_scheme", "auto")), console.FONT, facts),
         height=HEIGHT, scrolling=True)

with actions:
    common.refresh_action()
    st.html('<p class="c-actions-sub">More</p>')
    st.link_button("The design document", f"https://github.com/{REPOSITORY}/blob/main/docs/system-design.md",
                   icon=":material/open_in_new:")
