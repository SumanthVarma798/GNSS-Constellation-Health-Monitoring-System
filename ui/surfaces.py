"""Small reusable parts of the look. Each builder returns an HTML string; show() puts one on the page.

Text passed in is escaped, because titles and captions come from outside files.
Only parameters whose names end in _html are trusted to be markup already.
"""
import base64
import re
from html import escape

from analysis.score_rules import status_word

STATUSES = ("ok", "warn", "bad", "idle", "accent")


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


def notice(text, status, inline=False):
    """A short message for the reader.

    By default it goes to the notices inbox (ui/notices.py), out of the page's way, and "" is returned, which show()
    skips. inline=True returns it as a box with a coloured edge, for the page itself: for a message that stands in
    for what the page could not draw (an error, an empty choice, a system the page does not cover).
    """
    _check_status(status)
    if not inline:
        from ui import notices

        notices.post(text, status)
        return ""
    return f'<div class="notice {status}" role="status">{escape(text)}</div>'


def big_number(value, caption):
    """One large figure with a line of words under it."""
    return (
        f'<div class="big-number"><div class="big num">{escape(str(value))}</div>'
        f'<div class="small">{escape(caption)}</div></div>'
    )


def band(score):
    """ok from 80, warn from 60, else bad. The one place the score bands are set."""
    return {"Healthy": "ok", "Fair": "warn", "Degraded": "bad", "Critical": "bad"}[status_word(score)]


def share_tone(fraction):
    """The tone of a count-of-total share bar: the same thresholds the score bands use today."""
    return "ok" if fraction >= 80 else "warn" if fraction >= 60 else "bad"


def tile(name, orbit="", score=None, status="", slot="", slot_status="idle", weakest=None, age_html="",
         unscored="set aside", name_html=""):
    """One satellite: its name and orbit type, overall score, status word, slot state, weakest part.

    A score of None is a satellite set aside, or one with nothing to score it against: the tile reads `unscored`
    and shows only the slot state.
    weakest is (label, score) or None, drawn as a small chip naming the part by its technical term
    (ui/overview_settings.py PART_TERMS), its score in the shared tooltip. The score decides the tile's colour; a
    satellite set aside takes the slot state's. age_html, when given, is one more tag drawn in the tile's tag row after
    the state words. name_html, when given, is drawn after the name (a mark such as the clock record's).
    """
    _check_status(slot_status)
    edge = slot_status if score is None else band(score)
    kind = f' <span class="muted">{escape(orbit)}</span>' if orbit else ""
    big = (f'<div class="s idle">{escape(unscored)}</div>' if score is None
           else f'<div class="s num {edge}">{score:.1f}</div>')
    chips = chip(slot, slot_status) if score is None else chip(status, edge) + chip(slot, slot_status)
    low = _weakest(name, *weakest) if weakest and weakest[1] < 100 else ""
    return (f'<div class="tile {edge}"><div class="n">{escape(name)}{kind}{name_html}</div>{big}'
            f'<div class="r">{chips}{age_html}</div>{low}</div>')


def _weakest(name, label, score):
    """The weakest part as a chip: a down arrow and its technical term, its score out of 100 in the shared tooltip."""
    from ui import tooltip
    from ui.overview_settings import PART_TERMS

    term = PART_TERMS.get(label, label.lower())
    words = f"Weakest part of {name}'s score: {term}, {score:.0f} of 100."
    return f'<div class="low">{tooltip.tip_html(chip("weakest: " + term, band(score)), escape(words), key=name)}</div>'


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


def group_head(title, line, extra_html=""):
    """The heading of one group of satellites: a short name, one plain line after it, and optionally a tip."""
    return (f'<div class="group"><span class="gt">{escape(title)}</span><span class="muted">{escape(line)}</span>'
            f'{extra_html}</div>')


def gauge(value, low, high, status, floor=False, tick=None, strict=False):
    """(markup, outside) for a small bar: the allowed range shaded in the middle half of its scale (the scale runs half
    a range past each end; from `low` itself when the quantity cannot go under it, `floor`), the value a dot in its
    status colour. low None: no lower limit, the scale mirrored about `tick` (a nominal value, drawn as a line).
    A value past the scale sits at its end as an arrow pointing out, so "outside" is said by shape as well as colour."""
    _check_status(status)
    start = 2 * tick - high if low is None else low
    span = (high - start) or abs(high) or 1.0
    lo, hi = (start, high + span / 2) if floor or low is None else (start - span / 2, high + span / 2)

    def at(v):
        return 100 * (v - lo) / (hi - lo)

    where = at(value)
    side = " hi" if where > 100 else " lo" if where < 0 else ""
    outside = not (low is None or low <= value) or (value >= high if strict else value > high)   # strict: the limit itself is out
    band_left = 0.0 if low is None else at(low)
    line = f'<b style="left:{at(tick):.1f}%"></b>' if tick is not None else ""
    return (f'<span class="gg {status}{" out" if outside else ""}" aria-hidden="true">'
            f'<em style="left:{band_left:.1f}%;width:{at(high) - band_left:.1f}%"></em>{line}'
            f'<i class="{side.strip()}" style="left:{max(0.0, min(100.0, where)):.1f}%"></i></span>'), outside


def measure(cell, lead=""):
    """One table cell from ui.measures: the value now in its status colour, what it should be, an optional note.
    A value with a figure in it is set in the number face. A cell with a "gauge" ({value, low, high, floor, tick})
    draws the value over its gauge and says what it should be and the note in the shared tooltip, led by `lead`; its
    "word", when given, stands beside the value in place of "outside"."""
    _check_status(cell["status"])
    face = "num " if any(ch.isdigit() for ch in cell["now"]) else ""
    now = f'<b class="{face}{cell["status"]}">{escape(cell["now"])}</b>'
    if cell.get("gauge"):
        from ui import tooltip

        bar, outside = gauge(status=cell["status"], **cell["gauge"])
        should = cell["should"].replace(" · outside", "")
        items = [("", "Allowed", should)] * bool(should) + [("", "", part) for part in cell["note"].split(" · ") if part]
        word = cell.get("word") or ("outside" if outside else "")   # "outside" said in words, or what stands for it
        trigger = f'<span class="gc">{now}{f"<small>{escape(word)}</small>" if word else ""}</span>{bar}'
        return tooltip.tip_html(trigger, tooltip.glance(lead or cell["now"], items), key=lead)
    should = f'<span class="sb">{escape(cell["should"])}</span>' if cell["should"] else ""
    note = f'<span class="nt">{escape(cell["note"])}</span>' if cell["note"] else ""
    return f'{now}{should}{note}'


def table(columns, rows, head_tips=False):
    """A table in a raised card that scrolls sideways when the page is narrow.

    columns: (heading, one plain line or "") pairs, the first over the names. rows: (name, [cell, ...]),
    each cell a ui.measures cell drawn by measure(). head_tips: each heading's line opens from it in the shared
    tooltip instead of standing under it.
    """
    from ui import tooltip

    head = "".join(f"<th>{tooltip.tip(title, line) if head_tips and line else escape(title)}"
                   f"{f'<small>{escape(line)}</small>' if line and not head_tips else ''}</th>" for title, line in columns)
    titles = [title for title, _ in columns[1:]]
    body = "".join(f"<tr><th scope=\"row\">{escape(name)}</th>"
                   + "".join(f'<td>{measure(c, " · ".join([name, *titles[i:i + 1]]))}</td>' for i, c in enumerate(cells))
                   + "</tr>" for name, cells in rows)
    return f'<div class="tablewrap"><table class="grid"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


_SVG = re.compile(r"<svg\b([^>]*)>.*?</svg>", re.DOTALL)
_LABEL = re.compile(r'aria-label="([^"]*)"')


_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def picture(html):
    """Turn each inline <svg> in a figure's HTML into an <img> that carries it as a data URI.

    st.html drops svg elements, so a timeline would show as an empty box. The picture
    keeps its words as the image's alt text. An image cannot read the page's colour variables, so each picture is made
    twice, in the dark palette and with each of its colours swapped for the light theme's, and the page shows the one
    for its theme (--pic-dark and --pic-light, ui/theme.py; the rule in ui/theme.css).
    """
    from ui import palette

    to_light = {dark.lower(): palette.THEMED_LIGHT[name] for name, dark in palette.THEMED_DARK.items()}

    def image(svg, alt, look):
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return (f'<img class="pic-{look}" alt="{alt}" src="data:image/svg+xml;base64,{encoded}" '
                'style="width:100%;height:auto">')

    def as_image(found):
        svg = found.group(0)
        if "xmlns=" not in svg:
            svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        label = _LABEL.search(found.group(1))
        alt = label.group(1) if label else ""
        light = _HEX.sub(lambda hit: to_light.get(hit.group(0).lower(), hit.group(0)), svg)
        return image(svg, alt, "dark") + image(light, "", "light")   # the light copy is silent: one picture is read

    return _SVG.sub(as_image, html)


def show(html):
    """Put an HTML string on the page. An empty one (a notice sent to the inbox) draws nothing."""
    import streamlit as st

    if html:
        st.html(html)
