"""Lifecycle timelines: each satellite's steps from build to end of life on one axis of time since launch.
One satellite picked shows the timeline view; two to MAX_COMPARED of one system show the compare view.

The page is ui/components/lifecycle.html (plain JavaScript; the only thing it loads is each event's picture from
Wikimedia Commons). The records come from evidence/lifecycle.py. Text reaches the page as JSON escaped by embed()
and is put in with textContent, so it is never read as markup.
"""
from pathlib import Path

from evidence.library_settings import EVIDENCE_WORDS, WHEN_WORDS
from evidence.lifecycle import timelines
from ui import palette
from ui.components.master_map import embed
from ui.icons import LIFECYCLE_STEP_ICONS, TABLER
from ui.theme import root_block

PAGE_FILE = Path(__file__).with_name("lifecycle.html")
FIRST_SHOWN = ("NVS-01", "NVS-03")   # left, then right: the newest satellite beside the one it most resembles
MAX_COMPARED = 5   # satellites of one system compared at once


def _shared(records):
    """The records with each event's detail and source replaced by its place in one shared list: most of the
    registry's events say the same few things, and the page would otherwise carry each a few hundred times."""
    texts, sources, seen = [], [], {}

    def place(value, into):
        key = (id(into), repr(value))
        if key not in seen:
            seen[key] = len(into)
            into.append(value)
        return seen[key]

    for record in records:
        # Empty fields are left out too: the page reads a missing one as empty.
        record["events"] = [{key: value for key, value in {**e, "detail": place(e["detail"], texts),
                                                           "source": place(e["source"], sources)}.items()
                             if value is not None and value is not False and value != ""} for e in record["events"]]
    return records, texts, sources


def lifecycle_html(rows, today, registry=None):
    """The finished page. today is a timezone-aware datetime; registry holds the tables timelines() reads."""
    page = PAGE_FILE.read_text(encoding="utf-8")
    for placeholder, text in {"__ROOT__": root_block(), "__FONT__": palette.FONT, "__FONT_NUMBERS__": palette.FONT_NUMBERS}.items():
        page = page.replace(placeholder, text)
    satellites, texts, sources = _shared(timelines(rows, today, registry))
    payload = {"satellites": satellites, "texts": texts, "sources": sources, "first": list(FIRST_SHOWN),
               "max_compared": MAX_COMPARED,
               "step_colours": palette.LIFECYCLE_STEP_COLOURS,
               "icons": {step: TABLER[name] for step, name in LIFECYCLE_STEP_ICONS.items()}, "zoom": TABLER["maximize"],
               "today": today.strftime("%Y-%m-%dT%H:%M:%SZ"),   # whole seconds: every browser reads these
               "when_words": WHEN_WORDS, "evidence_words": EVIDENCE_WORDS}
    return page.replace("const DATA = __DATA__;", f"const DATA = {embed(payload)};", 1)


def lifecycle_frame(rows, today, registry=None):
    """Show the timelines; the frame sets its own height."""
    from streamlit.components.v1 import html

    html(lifecycle_html(rows, today, registry), height=900, scrolling=False)
