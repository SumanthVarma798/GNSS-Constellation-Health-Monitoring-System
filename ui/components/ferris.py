"""The ferris-wheel picker: one choice from a list, for every single-choice picker on the dashboard.

The page is ui/components/ferris/index.html (plain JavaScript, a two-way component: no build step). It shows the
current option; hover, or press and hold on a touch screen, opens the wheel at it with its neighbours above and below;
the mouse wheel, a swipe or the arrow keys turn it; a click, a tap or Enter picks.

It behaves as st.selectbox does for its callers: the value lives in st.session_state[key] (so a caller may set it, and
it holds across reruns), `on_change(*args)` runs before the page is drawn again, and the first option (or None, with a
placeholder) stands until something is picked. The frame's own value, {"i": index, "n": time of the pick}, is kept
under f"{key}__wheel" and read only when it changes, so a value a caller set afterwards is never undone by an old pick.
"""
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import declare_component

from ui import palette
from ui.theme import root_block

_wheel = declare_component("ferris", path=str(Path(__file__).with_name("ferris")))


def chosen(options, value, placeholder=None, disabled=()):
    """What the picker stands at: `value` when it can be chosen, else None under a placeholder, else the first option
    that can be chosen (None when there is none)."""
    if value in options and value not in disabled:
        return value
    return None if placeholder else next((o for o in options if o not in disabled), None)


def take(state, key, options, event, disabled=()):
    """Put a pick from the frame into state[key]. True when it did; an event naming no choosable option is ignored."""
    if not event or not 0 <= event.get("i", -1) < len(options) or options[event["i"]] in disabled:
        return False
    state[key] = options[event["i"]]
    return True


def ferris(label, options, key, *, format_func=str, disabled=(), placeholder=None, on_change=None, args=()):
    """Draw the picker; returns the value it stands at. `disabled` options are shown struck through and skipped."""
    options = list(options)
    value = st.session_state[key] = chosen(options, st.session_state.get(key), placeholder, disabled)

    def picked():
        if take(st.session_state, key, options, st.session_state.get(f"{key}__wheel"), disabled) and on_change:
            on_change(*args)

    _wheel(label=label, labels=[format_func(o) for o in options], disabled=[o in disabled for o in options],
           index=options.index(value) if value in options else -1, placeholder=placeholder or "",
           css=root_block(), font=palette.FONT, key=f"{key}__wheel", default=None, on_change=picked,
           tab_index=0)   # tabbable, so a panel that focuses its first control on opening (the range) focuses this
    return value
