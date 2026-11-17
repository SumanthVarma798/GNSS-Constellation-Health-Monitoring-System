"""Master map: what is up there, across every constellation, and how the dashboard knows who each spacecraft is.

The page reads in the order the whole dashboard follows: all the spacecraft (the count), each constellation (the
rows, each leading to its Overview, its News, the Library and its part of the map), every spacecraft under every name
(the map), where each thing comes from and how fresh it is, what the IGS satellite metadata file, GCAT and CelesTrak disagree about, then how to read it.
"""
from datetime import datetime, timezone

import streamlit as st

from data import celestrak
from ui import data, master_map_page as mm, reveal, shell, surfaces, systems
from ui.components.master_map import master_map_canvas, master_map_records
from ui.pages_data import load_master_map_data, with_live_feed
from ui.session_keys import LIBRARY_JUMP

FOCUS = "master_map_focus"   # session_state: the constellation the map is filtered to, or None


def _go(page, scope=None):
    """A button's on_click: open another page, on one constellation's part when `scope` is given."""
    st.session_state.update({"page": page, **({"scope": scope, "compare": False} if scope else {})})


def _lifecycles(name):
    """A button's on_click: open the Library on one constellation's satellite lifecycles (the Library reads
    library_jump: {shelf, constellation as ui/systems.py SYSTEMS names it})."""
    st.session_state.update({LIBRARY_JUMP: {"shelf": "satellites", "constellation": name}, "page": "Library"})


def _focus(name):
    st.session_state[FOCUS] = name


def _links(index, summary):
    """The row's ways onward: its part of the map, each part's Overview, its News, the Library."""
    name, parts = summary["name"], summary["parts"]
    with st.container(key=f"mm_links_{index}"):
        st.button("Show on the map", key=f"mm_map_{index}", icon=":material/my_location:", on_click=_focus,
                  args=(mm.registry_name(name),))
        for part in parts:
            words = systems.part_name(part)
            st.button(f"{name} {words} overview" if words else f"{name} overview", key=f"mm_ov_{part}",
                      on_click=shell.open_system, args=(part,))   # the part's name as ui/systems.py PARTS spells it
        st.button(f"{name} news", key=f"mm_news_{index}", on_click=_go, args=("News", parts[0]))
        st.button(f"{name} lifecycles in the Library", key=f"mm_lib_{index}", on_click=_lifecycles, args=(name,))


def page():
    now = datetime.now(timezone.utc)
    tables = with_live_feed(load_master_map_data(), celestrak.state)
    records = master_map_records(tables)
    rows = mm.constellations(records, systems.SYSTEMS, {part: len(sats) for part, sats in data.SATELLITES.items()})

    surfaces.show(mm.head(rows))
    with st.container(key="mm_rows"):
        for index, summary in enumerate(rows):
            with st.container(key=f"mm_row_{index}"):
                st.html(mm.row(summary))
                _links(index, summary)

    focus = st.session_state.get(FOCUS)
    shown = mm.page_name(focus) if focus else ""
    surfaces.show(surfaces.group_head(
        "Every spacecraft under every name",
        (f"showing {shown}" if focus else "every constellation") + " · drag to move, pinch or Ctrl and scroll to zoom, "
        "tap a card for its signal IDs over time"))
    if focus:
        st.button("Show every constellation", key="mm_all", icon=":material/zoom_out_map:", on_click=_focus, args=(None,))
    master_map_canvas(tables, focus, records)

    surfaces.show(surfaces.group_head("Where this comes from", "and how fresh each part is"))
    surfaces.show(mm.sources(mm.freshness(tables, celestrak.state, now)))

    look = sum(summary["look"] for summary in rows)
    reveal.section("mm_look", "Where the IGS satellite metadata file, GCAT and CelesTrak's orbit feed disagree",
                   f"{mm.spacecraft(look)} marked on the map, each with the two sources and what each says",
                   mm.disagreements(records))
    reveal.section("mm_how", "Need help reading this page?", "what is shown, how, what is left out, what comes next", mm.how())


page()
