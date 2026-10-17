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


def band(score):
    """ok from 80, warn from 60, else bad. The one place the score bands are set."""
    return "ok" if score >= 80 else "warn" if score >= 60 else "bad"


def tile(name, orbit="", score=None, status="", slot="", slot_status="idle", weakest=None):
    """One satellite: its name and orbit type, overall score, status word, slot state, weakest part.

    A score of None is a satellite set aside: the tile reads "set aside" and shows only the slot state.
    weakest is (label, score) or None. The score decides the tile's colour; a satellite set aside takes the slot state's.
    """
    _check_status(slot_status)
    edge = slot_status if score is None else band(score)
    kind = f' <span class="muted">{escape(orbit)}</span>' if orbit else ""
    big = ('<div class="s idle">set aside</div>' if score is None
           else f'<div class="s num {edge}">{score:.1f}</div>')
    chips = chip(slot, slot_status) if score is None else chip(status, edge) + chip(slot, slot_status)
    low = f'<div class="small low">Weakest: {escape(weakest[0])} {weakest[1]:.0f}</div>' if weakest else ""
    return f'<div class="tile {edge}"><div class="n">{escape(name)}{kind}</div>{big}<div class="r">{chips}</div>{low}</div>'


def parts_matrix(rows):
    """Score parts side by side: one line per part, one column per satellite. rows: (label, [score or None per satellite]).

    Each score is coloured by its band and carries a bar, so a weak part stands out down its column.
    The columns line up with the tiles of compare_grid.
    """
    lines = ""
    for label, scores in rows:
        cells = "".join(
            '<div class="mc idle">&ndash;</div>' if s is None else
            f'<div class="mc {band(s)}"><span class="num">{s:.0f}</span>'
            f'<i style="width:{max(0.0, min(100.0, s)):g}%"></i></div>' for s in scores)
        lines += f'<div class="mrow"><span class="ml">{escape(label)}</span>{cells}</div>'
    return f'<div class="matrix" style="--n:{len(rows[0][1]) if rows else 0}">{lines}</div>'


def compare_grid(tile_htmls, matrix_html):
    """Tiles in a row with the score-part lines under them, in the same columns."""
    return (f'<div class="tiles cmp" style="--n:{len(tile_htmls)}"><div></div>{"".join(tile_htmls)}</div>'
            + matrix_html)


def group_head(title, line):
    """The heading of one group of satellites: a short name and one plain line after it."""
    return f'<div class="group"><span class="gt">{escape(title)}</span><span class="muted">{escape(line)}</span></div>'


def measure(cell):
    """One table cell from ui.measures: the value now in its status colour, what it should be, an optional note.
    A value with a figure in it is set in the number face."""
    _check_status(cell["status"])
    face = "num " if any(ch.isdigit() for ch in cell["now"]) else ""
    should = f'<span class="sb">{escape(cell["should"])}</span>' if cell["should"] else ""
    note = f'<span class="nt">{escape(cell["note"])}</span>' if cell["note"] else ""
    return f'<b class="{face}{cell["status"]}">{escape(cell["now"])}</b>{should}{note}'


def table(columns, rows):
    """A table in a raised card that scrolls sideways when the page is narrow.

    columns: (heading, one plain line or "") pairs, the first over the names. rows: (name, [cell, ...]),
    each cell a ui.measures cell drawn by measure().
    """
    head = "".join(f"<th>{escape(title)}{f'<small>{escape(line)}</small>' if line else ''}</th>"
                   for title, line in columns)
    body = "".join(f"<tr><th scope=\"row\">{escape(name)}</th>{''.join(f'<td>{measure(c)}</td>' for c in cells)}</tr>"
                   for name, cells in rows)
    return f'<div class="tablewrap"><table class="grid"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


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
