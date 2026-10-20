"""The one expandable section: a header that says what is inside, a chevron, and the details under it.

Every page reads top to bottom in the same order: the headline count, then the tiles or the picture, always in
view; then the details, each in one of these sections. Notices (warnings) stay in view. Every table sits in a
section. Tables open closed, except each page's one most important table, which opens by default:
  Overview         the "Measured against limits" table: one per orbit type for NavIC, QZSS and BeiDou-3, one for every
                   satellite for GPS, GLONASS and Galileo, one for the satellites picked under Compare
  Station-keeping  burns per satellite
  Geometry         position quality by place; in "Sky and ground", when each satellite is in view (the question asked)
  Library          the count per system
  Master map       none: the map is the page

The header is a checkbox drawn as a header row: Tab reaches it, Space opens and closes it, and a screen reader
hears "checked" for open. What the reader opened or closed is kept for the session, so a section stays as they
left it on every visit. The body is always on the page and only hidden by height, so it opens and closes in 200 ms
(ui/theme.css), at once for a reader who asks for reduced motion. A click reruns the header alone, as a fragment.
"""
import re

import streamlit as st

MEMORY = "reveal_open"   # session_state: {section key: open}
# Characters Streamlit's markdown would read as formatting, a colour, an icon or a formula.
_MARKDOWN = re.compile(r"([\\`*_{}\[\]()#+\-.!|~<>$:])")


def _markdown_text(text):
    return _MARKDOWN.sub(r"\\\1", text)


def label(title, summary=""):
    """The header's words as Streamlit markdown: the title in bold, then the one-line summary."""
    return f"**{_markdown_text(title)}**" + (f" {_markdown_text(summary)}" if summary else "")


def count(n, word):
    """'1 satellite', '8 satellites': for summaries."""
    return f"{n} {word}{'' if n == 1 else 's'}"


def body(body_html):
    """The details' markup, padded inside the section."""
    return f'<div class="rv-body">{body_html}</div>'


def section(key, title, summary, body_html, open=False):
    """Draw one section. key must be unique on the page; open is the state until the reader changes it."""
    key = re.sub(r"\W", "_", key)
    with st.container(key=f"rv_{key}"):
        _header(key, label(title, summary), open)
        st.html(body(body_html))


@st.fragment
def _header(key, text, default):
    widget = f"rvx_{key}"
    st.session_state[widget] = st.session_state.setdefault(MEMORY, {}).get(key, default)
    st.checkbox(text, key=widget, on_change=_remember, args=(key, widget))


def _remember(key, widget):
    st.session_state[MEMORY][key] = st.session_state[widget]
