"""The notices inbox: a round bell floating at the top right of every page, with a count on it while anything is unread.

Pages say what is missing, late or left out with surfaces.notice(); those notices gather here instead of sitting in
the page, and the bell shows how many are unread, in the colour of the worst. With nothing unread the bell is quiet:
no count. The bell is a Streamlit popover: Tab reaches it, Enter or Space opens the list, Escape closes it. Each
notice has a round tick that marks it read, for the session, and pressed in marks it unread again. A read notice
stays where it was in the list, quieter, so the tick keeps the keyboard focus.

dashboard.py calls clear() before the page runs and inbox() after it. Words are in ui/notice_settings.py, the
look in ui/theme.css ("notices inbox").
"""
import hashlib
from html import escape

import streamlit as st

from ui import icons
from ui import notice_settings as words

PAGE = "notices_page"   # session_state: {key: (text, status)}, what the page said in its latest run, in order
READ = "notices_read"   # session_state: keys of the notices marked read this session


def key(text, status):
    """The same notice always gets the same key, so it stays read on every visit."""
    return hashlib.sha1(f"{status}\0{text}".encode("utf-8")).hexdigest()[:12]


def clear():
    """Forget the last run's notices. Call before the page runs."""
    st.session_state[PAGE] = {}


def post(text, status):
    """Add one notice to the inbox. Said twice in a run, it is listed once."""
    st.session_state.setdefault(PAGE, {})[key(text, status)] = (text, status)


def unread(page, read):
    """The keys of `page`'s notices not in `read`, in the order they were said."""
    return [k for k in page if k not in read]


def _toggle_read(k):
    st.session_state.setdefault(READ, set()).symmetric_difference_update({k})


def _row(text, status, read=False):
    return (f'<div class="nt-row{" read" if read else ""}">{icons.tag(status)}<span>'
            f'<span class="nt-sr">{words.STATUS_WORDS[status]}: </span>{escape(text)}</span></div>')


@st.fragment
def inbox():
    """The bell and its list. A fragment, so marking a notice read redraws the inbox alone, not the page."""
    page = st.session_state.get(PAGE, {})
    read = st.session_state.setdefault(READ, set())
    fresh = unread(page, read)
    with st.container(key="notices"):
        with st.popover(words.button_words(len(fresh)), help=words.TITLE):
            st.html(f'<div class="nt-head"><b>{words.TITLE}</b><span class="muted">'
                    f'{words.summary_words(len(fresh), len(page))}</span></div>')
            if not page:
                st.html(f'<p class="small">{words.EMPTY}</p>')
            for k, (text, status) in page.items():
                with st.container(key=f"ntrow_{k}"):
                    note, tick = st.columns([1, 0.001], vertical_alignment="center")
                    note.html(_row(text, status, read=k in read))
                    tick.button(words.MARK_UNREAD if k in read else words.MARK_READ, key=f"ntread_{k}",
                                on_click=_toggle_read, args=(k,))
        if fresh:
            worst = next(s for s in words.WORST_FIRST if any(page[k][1] == s for k in fresh))
            st.html(f'<span class="nt-count num {worst}" aria-hidden="true">{len(fresh)}</span>')
