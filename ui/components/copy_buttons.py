"""Copy-only citation controls: labels on buttons, values copied to clipboard inside a fitted frame."""
from pathlib import Path

from ui import palette
from ui.components.frame import fill
from ui.theme import root_block

PAGE_FILE = Path(__file__).with_name("copy_buttons.html")
HEIGHT_PX = 72   # first height only; the page fits the frame to its content (fitFrame)


def copy_buttons_html(labels_to_text):
    """The finished page with copy buttons and values, with {accessed} kept for the browser to fill on click."""
    return fill(PAGE_FILE.read_text(encoding="utf-8"), labels_to_text, __ROOT__=root_block(), __FONT__=palette.FONT)


def copy_buttons_frame(labels_to_text):
    from streamlit.components.v1 import html

    html(copy_buttons_html(labels_to_text), height=HEIGHT_PX)
