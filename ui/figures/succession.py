"""Succession lanes: who held a signal ID over time, or which signal IDs a spacecraft sent.

One horizontal time axis with year ticks and one rounded bar per period,
placed by date and alternating between two rows so neighbours do not collide.
The current period is drawn in the accent colour, a period shorter than
SHORT_DAYS in the warn colour, any other in a neutral fill.
"""

from datetime import date
from html import escape

from ui import palette
from ui.figures._themed import themed

WIDTH = 520
AXIS_LEFT = 20
AXIS_RIGHT = 500
ROW_TOPS = (44, 92)          # the two rows of bars; the gap above each holds an outside label
BAR_HEIGHT = 26
AXIS_Y = 140
TICK_LABEL_Y = 160
HEIGHT = 170
MIN_BAR_WIDTH = 5
SHORT_DAYS = 60
TICK_STEPS = (1, 2, 5, 10, 20, 50, 100)
MAX_TICKS = 9
FONT_PX = 13
CHAR_PX = 7.4                # rough width of one character at FONT_PX
LABEL_PAD = 13               # space inside a bar before its label
LABEL_GAP = 8                # space between an outside label and the bar below it
CAPTION_STYLE = f"margin:6px 0 0;font-size:14px;color:{themed('muted')}"


def date_to_x(day, first, last, left=AXIS_LEFT, right=AXIS_RIGHT):
    """Map a date to an x position: first lands on left, last on right, linearly in between."""
    return left + (day - first).days / (last - first).days * (right - left)


def _day(text):
    return date.fromisoformat(text)


def _words(day):
    """A date as words, for example 1 Nov 2018."""
    return f"{day.day} {day.strftime('%b')} {day.year}"


def _axis_range(starts, ends):
    """Whole calendar years that contain every period, so ticks sit on real 1 January dates."""
    latest = max(ends)
    round_up = latest > date(latest.year, 1, 1)
    return date(min(starts).year, 1, 1), date(latest.year + round_up, 1, 1)


def year_ticks(first, last):
    """Years to label: the smallest step from TICK_STEPS that gives at most MAX_TICKS ticks."""
    years = range(first.year, last.year + 1)
    for step in TICK_STEPS:
        ticks = [y for y in years if y % step == 0]
        if len(ticks) <= MAX_TICKS:
            return ticks
    return ticks


def _resolve(period, today):
    """Return (start, end) as dates; an empty end means until today."""
    return _day(period["start"]), _day(period["end"]) if period.get("end") else today


def _look(period, days):
    """Return (bar colour, text colour on that bar, outside label colour, extra words) for a period."""
    if period.get("current"):
        return palette.ACCENT, palette.PLATFORM, palette.ACCENT, f"since {_words(_day(period['start']))}"
    if days < SHORT_DAYS:
        return palette.WARN, palette.PLATFORM, palette.WARN, f"{days} days"
    return palette.FILL, palette.INK, palette.INK, ""


def _description(period, start, end):
    """One period in words, for the aria-label and the hover text."""
    if period.get("current"):
        return f"{period['label']}, from {_words(start)}, current"
    return f"{period['label']}, from {_words(start)} to {_words(end)}"


def _bar(index, period, start, end, axis):
    """Draw one bar with its label inside, or above it when the bar is too narrow."""
    first, last = axis
    x0 = date_to_x(start, first, last)
    x1 = date_to_x(end, first, last)
    width = max(MIN_BAR_WIDTH, x1 - x0)
    top = ROW_TOPS[index % len(ROW_TOPS)]
    fill, on_bar, outside, extra = _look(period, (end - start).days)
    text = f"{period['label']}, {extra}" if extra else period["label"]
    needed = len(text) * CHAR_PX + 2 * LABEL_PAD
    hover = escape(_description(period, start, end))
    parts = [
        f'<g><title>{hover}</title>'
        f'<rect x="{x0:.1f}" y="{top}" width="{width:.1f}" height="{BAR_HEIGHT}" '
        f'rx="{min(BAR_HEIGHT / 2, width / 2):.1f}" fill="{fill}"/>'
    ]
    if width >= needed:
        parts.append(
            f'<text x="{x0 + LABEL_PAD:.1f}" y="{top + BAR_HEIGHT / 2 + 4.5}" fill="{on_bar}" '
            f'font-size="{FONT_PX}">{escape(text)}</text>'
        )
    else:
        # Right-aligned to the bar's end, but never starting left of the axis.
        anchor = max(x0 + width, AXIS_LEFT + len(text) * CHAR_PX)
        parts.append(
            f'<text x="{anchor:.1f}" y="{top - LABEL_GAP}" fill="{outside}" font-size="{FONT_PX}" '
            f'text-anchor="end">{escape(text)}</text>'
        )
    parts.append("</g>")
    return "".join(parts)


def _axis(axis):
    """The axis line with a tick and a year label for each chosen year."""
    first, last = axis
    parts = [
        f'<line x1="{AXIS_LEFT}" y1="{AXIS_Y}" x2="{AXIS_RIGHT}" y2="{AXIS_Y}" '
        f'stroke="{palette.TRACK}" stroke-width="2"/>'
    ]
    for year in year_ticks(first, last):
        x = date_to_x(date(year, 1, 1), first, last)
        parts.append(
            f'<line x1="{x:.1f}" y1="{AXIS_Y}" x2="{x:.1f}" y2="{AXIS_Y + 6}" stroke="{palette.TRACK}" stroke-width="2"/>'
            f'<text x="{x:.1f}" y="{TICK_LABEL_Y}" fill="{palette.MUTED}" font-size="12" '
            f'text-anchor="middle">{year}</text>'
        )
    return "".join(parts)


def succession_lanes(periods, today, caption=""):
    """Return HTML holding one inline SVG timeline of the periods, oldest first.

    today is YYYY-MM-DD and is where an open-ended period stops.
    """
    if not periods:
        return f'<p style="color:{themed("muted")}">No periods to show.</p>'
    now = _day(today)
    spans = [_resolve(p, now) for p in periods]
    axis = _axis_range([s for s, _ in spans], [e for _, e in spans])
    summary = "Timeline. " + ". ".join(_description(p, s, e) for p, (s, e) in zip(periods, spans)) + "."
    bars = "".join(_bar(i, p, s, e, axis) for i, (p, (s, e)) in enumerate(zip(periods, spans)))
    figure = (
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{escape(summary)}" '
        f'style="max-width:100%;height:auto;display:block;font-family:{escape(palette.FONT)}">'
        f"{bars}{_axis(axis)}</svg>"
    )
    note = f'<p style="{CAPTION_STYLE}">{escape(caption)}</p>' if caption else ""
    return figure + note
