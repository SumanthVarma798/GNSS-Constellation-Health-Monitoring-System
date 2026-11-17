"""The Library's citation of the dashboard itself: short and long, its "accessed" time live in UTC, each copied in one
click exactly as shown. The page is ui/components/citation.html (plain JavaScript); it takes the theme's :root."""
from pathlib import Path

from ui import palette
from ui.components.frame import fill
from ui.shelf_settings import CITATION_FORMATS, DASHBOARD_CITATION, OUR_LICENCE
from ui.theme import root_block

PAGE_FILE = Path(__file__).with_name("citation.html")
HEIGHT_PX = 170   # the first height only: the page fits the frame to its content (fitFrame)


def citation_html():
    """The finished page; {year} and {accessed} are filled in the browser at the moment of reading."""
    fields = {**DASHBOARD_CITATION, "year": "{year}", "version": "live dashboard", "licence": OUR_LICENCE[0],
              "accessed": "{accessed}"}
    words = {form: text.format(**fields) for form, text in CITATION_FORMATS.items()}
    return fill(PAGE_FILE.read_text(encoding="utf-8"), words, __ROOT__=root_block(), __FONT__=palette.FONT)


def citation_frame():
    from streamlit.components.v1 import html

    html(citation_html(), height=HEIGHT_PX)
