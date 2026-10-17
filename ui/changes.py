"""Major changes readers should know about, shown in a strip under the top bar on every page.

To announce a change, add an entry to CHANGES (newest first is not required; show() sorts). Each says in plain
language what happened and what it means for the reader, and where it came from.
"""
from dataclasses import dataclass
from datetime import datetime
from html import escape

import streamlit as st

from ui import surfaces

STATUS = "accent"   # the notice colour (ui/palette.py ACCENT): news, not a fault


@dataclass(frozen=True)
class Change:
    id: str
    date: str                  # "2026-04-21", or "2026-04" when only the month is known
    constellations: tuple      # names as the top bar spells them
    headline: str              # one plain sentence
    meaning: str               # what it means for the reader
    source: str                # who said so
    link: str = ""             # where to read it, when there is a public address


CHANGES = [
    Change(
        id="beidou3-slot-swap",
        date="2026-04",
        constellations=("BeiDou-3",),
        headline="BeiDou-3 satellites G1 and G4 swapped orbital slots: G1 is now at 160°E and G4 at 140°E.",
        meaning="G1 and G4 are judged against their new slots, so their longitude scores follow the new places. "
                "G4 (PRN 1) left 160°E first, so 140°E, the main slot, was never empty; G1 (PRN 4) then moved to "
                "160°E, the constellation's spare slot. The IGS satellite file still lists G1 at 140°E (checked "
                "16 Oct 2026).",
        source="The team's dashboard note, citing the China Satellite Navigation Office (CSNO) April 2026 "
               "re-designation; the CSNO notice itself not yet seen",
    ),
    Change(
        id="beidou3-signal-ids",
        date="2026-04-21",
        constellations=("BeiDou-3",),
        headline="The signal IDs C01 to C04 moved from four BeiDou-2 satellites to the four BeiDou-3 geostationary satellites.",
        meaning="Older files and charts that use C01 to C04 may mean a BeiDou-2 satellite. G1 was C59, then C62, and "
                "has been C04 since 21 Apr 2026. All 7 BeiDou-3 geostationary and inclined geosynchronous satellites "
                "we track changed ID in March and April 2026; the swap itself took place between 17 and 21 Apr 2026.",
        source="IGS satellite metadata file, checked 16 Oct 2026",
    ),
]


def for_constellations(names):
    """The changes that apply to any of `names`, newest first."""
    return sorted((c for c in CHANGES if set(c.constellations) & set(names)), key=lambda c: c.date, reverse=True)


def _when(date):
    return (datetime.strptime(date, "%Y-%m-%d").strftime("%-d %b %Y") if len(date) > 7
            else datetime.strptime(date, "%Y-%m").strftime("%b %Y"))


def _html(change):
    """The strip entry: one line to read at a glance; a click opens what it means and where it came from."""
    source = escape(change.source)
    if change.link:
        source = f'<a href="{escape(change.link, quote=True)}" target="_blank" rel="noopener">{source}</a>'
    return (
        f'<details class="notice {STATUS} change"><summary>'
        f'<span class="when">{_when(change.date)}</span>{surfaces.chip(" · ".join(change.constellations), STATUS)}'
        f'<span class="headline">{escape(change.headline)}</span><span class="more">What it means</span></summary>'
        f'<p><b>What this means for you.</b> {escape(change.meaning)}</p><p class="small">Source: {source}</p></details>'
    )


def _dismiss(change_id):
    st.session_state["dismissed_changes"].add(change_id)


def show(names):
    """Draw the strip for the constellations in view: nothing when none apply or all have been dismissed."""
    dismissed = st.session_state.setdefault("dismissed_changes", set())
    shown = [c for c in for_constellations(names) if c.id not in dismissed]
    if not shown:
        return
    with st.container(key="changes"):
        for change in shown:
            with st.container(key=f"change_{change.id}"):
                note, close = st.columns([1, 0.001], vertical_alignment="top")
                note.html(_html(change))
                close.button("Dismiss", key=f"dismiss_{change.id}", on_click=_dismiss, args=(change.id,),
                             help="Hide this note until you reload the page")
