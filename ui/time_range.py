"""The time range every constellation page shows: quick presets, or a date of the reader's own to now.

The range is kept as st.session_state["window_days"]: that many days up to today (UTC), as every page and
data.load read it. A range ending in the past is not offered: the scores, the slot picture, the sky and the
satellites set aside are all judged as of now, so a range closing before today would mix two moments.

Bounds, worked out from the data held each time the bar is drawn:
  earliest  the oldest orbit record held for the constellations in view. NavIC, QZSS and BeiDou-3 carry a
            bundled year (data/*_gp_history.json); GPS, GLONASS and Galileo hold only what CelesTrak has
            given since the server first ran (data/celestrak.py), so theirs is days or weeks.
  latest    now: there are no records from the future, so the range always ends today.
  shortest  MIN_DAYS, below.
  longest   everything held, from the earliest record.
A preset longer than what is held is greyed, and its tip says how much is held.
"""
from datetime import datetime, timedelta, timezone
from html import escape

import pandas as pd
import streamlit as st

from ui import data

# Quick choices, in days up to today, with their words.
PRESETS = {30: "30 days", 90: "90 days", 182: "6 months", 365: "1 year"}
DEFAULT_DAYS = 90
# Two weeks at least: the bundled history has one to four element sets a satellite a day, so 14 days give each
# satellite some 17 to 55. A burn is placed from a 3-set median and must hold for 2 sets either side
# (DEFAULT_PARAMS persist_window), and the drift trend compares the first and last 7 sets
# (analysis/drift_analysis.py); fewer days than this leave too few sets for either to say anything.
MIN_DAYS = 14
# The overall scores read this many days up to now whatever the range (analysis/bundled_run.py's pattern
# analysis); the range sets what the pages show around them.
SCORES_READ_DAYS = 365
SCORES_WORDS = (f"The health scores always read the last {SCORES_READ_DAYS} days, whatever the range: "
                "the range sets the records, burns and trends the pages show.")


def words(days):
    """'90 days', '1 year', '47 days': a range in words."""
    return PRESETS.get(days, f"{days} day{'' if days == 1 else 's'}")


def firsts(names, window_days, params):
    """{name: date of its oldest orbit record held, or None when it has none yet}."""
    found = {}
    for name in names:
        try:
            found[name] = pd.to_datetime(data.load(name, window_days, params)["history"]["EPOCH"]).min().date()
        except ValueError:   # no orbit data for it yet
            found[name] = None
    return found


def oldest(names, window_days, params):
    """The first day every one of `names` has records for: the latest of their oldest records (under Compare a
    range must fit the constellation with the least history). None when none has any."""
    held = [first for first in firsts(names, window_days, params).values() if first]
    return max(held) if held else None


def held_days(first, today):
    """Whole days from the oldest record held to today; 0 when nothing is held."""
    return (today - first).days if first else 0


def too_long(days, held, names):
    """Why a preset is greyed (more days than are held), or None when it can be chosen."""
    if days <= held:
        return None
    held_words = f"Only {words(held)} of orbit records are" if held else "No orbit records are yet"
    return f"{held_words} held for {', '.join(names)}."


def from_bounds(first, today):
    """(earliest, latest) start date a custom range may take, or None when less than MIN_DAYS is held."""
    latest = today - timedelta(days=MIN_DAYS)
    return (first, latest) if first and first <= latest else None


def _day(value):
    return f"{value.day} {value:%b %Y}"


def _choose(days):
    st.session_state["window_days"] = days


def _from_date(today):
    st.session_state["window_days"] = (today - st.session_state["_window_from"]).days


def control(names, params):
    """The range button and its panel, for the constellations `names` in view."""
    today = datetime.now(timezone.utc).date()
    window_days = st.session_state.setdefault("window_days", DEFAULT_DAYS)
    first_of = firsts(names, window_days, params)
    first = max((f for f in first_of.values() if f), default=None)   # the span they all share
    held = held_days(first, today)
    if held >= MIN_DAYS and window_days > held:   # less is held here than was chosen: the range shrinks to fit
        window_days = st.session_state["window_days"] = held
    with st.container(key="range"):
        label = f"Last {words(window_days)}" if held >= MIN_DAYS else ("Only " + words(held) if held else "No records yet")
        with st.popover(label, icon=":material/date_range:"):
            st.html('<p class="range-title">Time range, ending now</p>')
            with st.container(key="range_presets"):
                for days, label in PRESETS.items():
                    short = [n for n, f in first_of.items() if held_days(f, today) < days]   # who lacks it
                    reason = too_long(days, held, short or names)
                    st.button(label, key=f"window_{days}", disabled=reason is not None, help=reason,
                              type="primary" if days == window_days else "secondary", on_click=_choose, args=(days,))
            bounds = from_bounds(first, today)
            if bounds:
                earliest, latest = bounds
                st.session_state["_window_from"] = min(max(today - timedelta(days=window_days), earliest), latest)
                with st.container(key="range_custom"):
                    st.date_input("Custom: from", min_value=earliest, max_value=latest, key="_window_from",
                                  format="YYYY-MM-DD", on_change=_from_date, args=(today,))
                    st.html('<span class="range-to">to now</span>')
            held_words = (f"Orbit records held from {_day(first)}, {words(held)}." if first
                          else "No orbit records are held yet.")
            st.html(f'<p class="range-note">{escape(held_words)} Shortest range {MIN_DAYS} days, '
                    f'so a burn has enough element sets around it to be found.</p>'
                    f'<p class="range-note">{escape(SCORES_WORDS)}</p>')
