"""A small mark for each constellation: its orbital signature, drawn beside its name wherever the name appears, so
a reader can tell at a glance which constellation a row, a story or a card is about.

Each mark is true to the constellation it stands for:
  NavIC    an even figure of eight: the daily ground track of its inclined geosynchronous satellites
  QZSS     a lopsided eight, small loop on top: its quasi-zenith orbit dwells longest over Japan
  BeiDou   an eight inside an orbit: geosynchronous satellites and a medium-orbit shell in one constellation
  GPS      six crossing orbits: its six orbital planes
  GLONASS  three steep orbits: three planes tilted 64.8 degrees, the steepest of the global constellations
  Galileo  three orbits with a satellite on each: its three orbital planes

The artwork was generated with Higgsfield (GPT Image 2.6, SVG output) on 15 Nov 2026 as one set of six, then cut into
one mark each, with the strokes thickened so they read at text size. It is this project's own artwork (LICENSE-DATA).

st.html drops inline <svg>, so a mark is drawn as a CSS mask, the way ui/icons.py draws icons: ui/theme.py puts each
on the page as a variable, --mk-<key>, and mark() is the span that shows one in the constellation's colour.
"""
import base64
from html import escape

from ui import palette

STROKE = 20   # in the 320-unit box each mark is drawn in: about 1.4px at text size
DOT = 17

# key (as ui.palette.CONSTELLATION_COLOURS names it): (the mark's box in the generated sheet, its shapes).
_EIGHT = ("M171 176 C144 155 106 132 106 94 C106 60 135 36 171 36 C207 36 236 60 236 94 C236 132 198 155 171 176 "
          "C144 197 106 220 106 258 C106 292 135 316 171 316 C207 316 236 292 236 258 C236 220 198 197 171 176 Z")
SHAPES = {
    "NavIC": ("11 16 320 320", f'<path d="{_EIGHT}"/>'),
    "QZSS": ("352 16 320 320",
             '<path d="M512 135 C490 119 467 100 467 77 C467 53 487 35 512 35 C537 35 557 53 557 77 C557 100 534 119 '
             '512 135 C478 159 423 197 423 242 C423 287 461 317 512 317 C563 317 601 287 601 242 C601 197 546 159 512 135 Z"/>'),
    "BeiDou": ("693 16 320 320",
               '<ellipse cx="853" cy="176" rx="91" ry="151" transform="rotate(44 853 176)"/>'
               '<path d="M853 176 C835 163 813 148 813 128 C813 109 831 95 853 95 C875 95 893 109 893 128 C893 148 871 '
               '163 853 176 C835 189 813 204 813 224 C813 243 831 257 853 257 C875 257 893 243 893 224 C893 204 871 189 '
               f'853 176 Z"/><circle cx="947" cy="58" r="{DOT}" fill="#000" stroke="none"/>'),
    "GPS": ("11 356 320 320", "".join(
        f'<ellipse cx="171" cy="516" rx="27" ry="133" transform="rotate({turn} 171 516)"/>' for turn in range(0, 180, 30))),
    "GLONASS": ("352 356 320 320", "".join(
        f'<ellipse cx="512" cy="516" rx="28" ry="138" transform="rotate({turn} 512 516)"/>' for turn in (0, -42, 42))),
    "Galileo": ("693 356 320 320",
                "".join(f'<ellipse cx="853" cy="516" rx="140" ry="42" transform="rotate({turn} 853 516)"/>'
                        for turn in (0, 60, 120))
                + "".join(f'<circle cx="{x}" cy="{y}" r="{DOT}" fill="#000" stroke="none"/>'
                          for x, y in ((961, 543), (775, 414), (931, 414)))),
}


def svg(key):
    """One mark as a standalone SVG, black on clear, for a mask or a file."""
    box, shapes = SHAPES[key]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}" fill="none" stroke="#000" '
            f'stroke-width="{STROKE}" stroke-linecap="round" stroke-linejoin="round">{shapes}</svg>')


def mask_url(key):
    """The mark as a CSS url() of an SVG data URI. Base64, so the style block holds no angle bracket."""
    return f'url("data:image/svg+xml;base64,{base64.b64encode(svg(key).encode()).decode("ascii")}")'


def key(name):
    """The mark for a name as any page spells it: 'BeiDou-3 MEO' and 'BeiDou' are both BeiDou's. None if it has none."""
    return next((known for known in SHAPES if str(name).startswith(known)), None)


def mark(name):
    """The constellation's mark as a span in its colour, or "" for a name with none. Hidden from screen readers:
    the name beside it says which constellation it is."""
    known = key(name)
    if known is None:
        return ""
    return (f'<span class="mk" style="--mk: var(--mk-{known.lower()}); color: {palette.CONSTELLATION_COLOURS[known]}" '
            'aria-hidden="true"></span>')


def named(name):
    """The mark, then the name: for anywhere a constellation is named in a line of text."""
    return f'<span class="mk-name">{mark(name)}{escape(str(name))}</span>'
