"""Small reusable parts of the look. Each builder returns an HTML string; show() puts one on the page.

Text passed in is escaped, because titles and captions come from outside files.
Only parameters whose names end in _html are trusted to be markup already.
"""
import base64
import re
from html import escape

STATUSES = ("ok", "warn", "bad", "idle", "accent")

# A legend swatch may only be a hex colour or one of the theme variables, nothing that could carry other CSS.
_SWATCH = re.compile(r"#[0-9a-fA-F]{3,8}|var\(--[a-z-]+\)")


def _check_status(status):
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; use one of {', '.join(STATUSES)}")


def _heading(title):
    return f'<div class="part-title">{escape(title)}</div>' if title else ""


def raised(body_html, title=""):
    """A card that stands out of the page."""
    return f'<div class="raised">{_heading(title)}{body_html}</div>'


def well(body_html, title=""):
    """An area pressed into the page."""
    return f'<div class="well">{_heading(title)}{body_html}</div>'


def chip(text, status):
    """A small pill. The words always say the state; colour only backs them up."""
    _check_status(status)
    return f'<span class="chip {status}">{escape(text)}</span>'


def notice(text, status):
    """A short message with a coloured edge."""
    _check_status(status)
    return f'<div class="notice {status}" role="status">{escape(text)}</div>'


def big_number(value, caption):
    """One large figure with a line of words under it."""
    return (
        f'<div class="big-number"><div class="big num">{escape(str(value))}</div>'
        f'<div class="small">{escape(caption)}</div></div>'
    )


def _legend_row(colour, text):
    if not _SWATCH.fullmatch(colour):
        raise ValueError(f"legend colour {colour!r} must be a hex colour or a var(--name)")
    return f'<li><span class="swatch" style="background:{colour}"></span>{escape(text)}</li>'


def hover_legend(entries, label="Legend", opens_left=False):
    """A collapsed control that opens on hover or keyboard focus. entries: (colour, meaning) pairs.

    Set opens_left for a legend near the right edge of the page, so its list is not cut off.
    """
    rows = "".join(_legend_row(colour, text) for colour, text in entries)
    side = " opens-left" if opens_left else ""
    return (
        f'<div class="legend{side}" tabindex="0" role="group" aria-label="{escape(label, quote=True)}">'
        f'<span class="legend-label">{escape(label)}</span><ul>{rows}</ul></div>'
    )


_SVG = re.compile(r"<svg\b([^>]*)>.*?</svg>", re.DOTALL)
_LABEL = re.compile(r'aria-label="([^"]*)"')


def picture(html):
    """Turn each inline <svg> in a figure's HTML into an <img> that carries it as a data URI.

    st.html drops svg elements, so a timeline would show as an empty box. The picture
    keeps its words as the image's alt text; theme variables fall back to palette colours.
    """
    def as_image(found):
        svg = found.group(0)
        if "xmlns=" not in svg:
            svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        label = _LABEL.search(found.group(1))
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return (f'<img alt="{label.group(1) if label else ""}" src="data:image/svg+xml;base64,{encoded}" '
                'style="display:block;width:100%;height:auto">')

    return _SVG.sub(as_image, html)


def show(html):
    """Put an HTML string on the page."""
    import streamlit as st

    st.html(html)
