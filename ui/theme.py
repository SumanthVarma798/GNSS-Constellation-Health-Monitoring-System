"""Puts the dashboard's look on a page.

Every colour comes from ui/palette.py. The rules that use them are in ui/theme.css.
"""
from pathlib import Path

from ui import palette
from ui.tooltip import CARD_CSS

CSS_FILE = Path(__file__).with_name("theme.css")

# The faint light edge on raised things. Not a palette colour: it is white at low strength.
EDGE = "rgba(255,255,255,.06)"

# CSS variable name -> value. The shadows are written in terms of the colour variables.
VARIABLES = {
    "platform": palette.PLATFORM,
    "lift": palette.LIFT,
    "sink": palette.SINK,
    "well": palette.WELL,
    "track": palette.TRACK,
    "fill": palette.FILL,
    "ink": palette.INK,
    "muted": palette.MUTED,
    "accent": palette.ACCENT,
    "ok": palette.OK,
    "warn": palette.WARN,
    "bad": palette.BAD,
    "idle": palette.IDLE,
    "edge": EDGE,
    "raised": "-6px -6px 14px var(--lift), 7px 7px 16px var(--sink)",
    "raised-sm": "-3px -3px 8px var(--lift), 4px 4px 10px var(--sink)",
    "pressed": "inset -3px -3px 7px var(--lift), inset 4px 4px 9px var(--sink)",
    "r": f"{palette.RADIUS_PX}px",
}


def root_block():
    """The :root rule that defines every variable."""
    lines = "".join(f"  --{name}: {value};\n" for name, value in VARIABLES.items())
    return ":root {\n" + lines + "}\n"


def font_rules():
    """Typefaces, taken from the palette so no font is named twice."""
    return (
        f'.stApp, [data-testid="stSidebar"], button, input, textarea {{ font-family: {palette.FONT}; }}\n'
        f'.num, .big, [data-testid="stMetricValue"] {{ font-family: {palette.FONT_NUMBERS}; }}\n'
    )


def theme_css():
    """The full stylesheet text: variables, typefaces, the tooltip's card (shared with the canvas components), the rules."""
    return root_block() + font_rules() + CARD_CSS + CSS_FILE.read_text(encoding="utf-8")


def apply_theme():
    """Put the stylesheet on the current page. Call once, near the top of the page."""
    import streamlit as st

    st.html(f"<style>{theme_css()}</style>")
