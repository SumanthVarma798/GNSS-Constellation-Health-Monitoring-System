"""Lifecycle timelines: each satellite's steps from build to end of life on one axis of time since launch, side by side.

The page is ui/components/lifecycle.html (plain JavaScript; the only thing it loads is each event's picture from
Wikimedia Commons). The records come from evidence/lifecycle.py. Text reaches the page as JSON escaped by embed()
and is put in with textContent, so it is never read as markup.
"""
from pathlib import Path

from evidence.library_settings import EVIDENCE_WORDS, WHEN_WORDS
from evidence.lifecycle import timelines
from ui import palette
from ui.components.master_map import embed
from ui.theme import root_block

PAGE_FILE = Path(__file__).with_name("lifecycle.html")
FIRST_SHOWN = ("NVS-01", "NVS-03")   # left, then right: the newest satellite beside the one it most resembles
COLOURS = [palette.ACCENT, palette.WARN, palette.OK]


def lifecycle_html(rows, today):
    """The finished page. today is a timezone-aware datetime."""
    page = PAGE_FILE.read_text(encoding="utf-8")
    for placeholder, text in {"__ROOT__": root_block(), "__FONT__": palette.FONT, "__FONT_NUMBERS__": palette.FONT_NUMBERS}.items():
        page = page.replace(placeholder, text)
    payload = {"satellites": timelines(rows, today), "first": list(FIRST_SHOWN), "colours": COLOURS,
               "today": today.strftime("%Y-%m-%dT%H:%M:%SZ"),   # whole seconds: every browser reads these
               "when_words": WHEN_WORDS, "evidence_words": EVIDENCE_WORDS}
    return page.replace("const DATA = __DATA__;", f"const DATA = {embed(payload)};", 1)


def lifecycle_frame(rows, today):
    """Show the timelines; the frame sets its own height."""
    from streamlit.components.v1 import html

    html(lifecycle_html(rows, today), height=900, scrolling=False)
