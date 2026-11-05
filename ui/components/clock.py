"""The top bar's clock: UTC, or on a double-click the reader's local time in 12-hour form.

The page is ui/components/clock.html (plain JavaScript, no network): it ticks in the browser, so it is never behind
the page's own redraws, and keeps the reader's choice in their browser. It is drawn once per page run; the wait to the
next automatic refresh stays with the server (ui/shell.py).
"""
from pathlib import Path

from ui import palette
from ui.theme import root_block

PAGE_FILE = Path(__file__).with_name("clock.html")
HEIGHT_PX = 18   # one line of the small type


def clock_html():
    """The finished page."""
    page = PAGE_FILE.read_text(encoding="utf-8")
    for placeholder, text in {"__ROOT__": root_block(), "__FONT_NUMBERS__": palette.FONT_NUMBERS}.items():
        page = page.replace(placeholder, text)
    return page


def clock_frame():
    """Show the clock; the frame sets its own width."""
    from streamlit.components.v1 import html

    html(clock_html(), height=HEIGHT_PX)
