"""The satellites picked for Compare: one field of chips, and a list to add from, grouped by constellation.

The picks are kept in st.session_state["compare_picks"] as {constellation: [satellite, ...]}, so every page reads
the same ones. Only the constellations chosen in the top bar are offered (all when none are).
"""
import streamlit as st

from ui import data, shell


def _drop(constellation, satellite):
    picks = st.session_state["compare_picks"]
    picks[constellation] = [s for s in picks[constellation] if s != satellite]


def _take(constellation):
    st.session_state["compare_picks"][constellation] = st.session_state[f"_pick_{constellation}"]


def _toggle_list():
    st.session_state["picker_open"] = not st.session_state.get("picker_open", False)


def picker():
    """Draw the field. Clicking a chip removes it; Add opens the list and Done closes it (it stays open while
    picking). Returns the picks, in constellation order."""
    picks = st.session_state.setdefault("compare_picks", {})
    ordered = {c: picks[c] for c in shell.CONSTELLATIONS if picks.get(c)}
    with st.container(key="picker"):
        for constellation, chosen in ordered.items():
            for satellite in chosen:
                st.button(satellite, key=f"drop_{satellite}", icon=":material/close:", help="Remove",
                          on_click=_drop, args=(constellation, satellite))
        shown = st.session_state.get("picker_open", False)
        st.button("Done" if shown else "Add", key="picker_toggle", icon=":material/check:" if shown else ":material/add:",
                  on_click=_toggle_list)
        if not shown:
            return ordered
        with st.container(key="picker_list"):
            for constellation in shell.offered():
                st.session_state[f"_pick_{constellation}"] = picks.get(constellation, [])
                st.pills(constellation, [s for s, norad in data.SATELLITES[constellation].items() if norad is not None],
                         selection_mode="multi", key=f"_pick_{constellation}", on_change=_take, args=(constellation,))
    return ordered
