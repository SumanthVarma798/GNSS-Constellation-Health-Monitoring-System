"""One orbital plane drawn flat: its slots as rings and its satellites as dots, by argument of latitude.

The line is the plane opened out, 0 to 360 degrees along the orbit from the ascending node. Each
satellite is tied to ITS OWN slot (the registry's), never the nearest. Colour is never the only
signal: the dots carry hover text and the picture has a spoken description.
"""
from html import escape

from ui import palette
from ui.figures.slot_belt import _centred_labels, _text

WIDTH, LEFT, RIGHT = 1000, 20, 980
LINE_Y, ROW_PX = 26, 15


def _x(u):
    return LEFT + u / 360 * (RIGHT - LEFT)


def plane_strip(satellites):
    """HTML with one SVG. satellites: [{label, u, slot_at (or None), state (palette.SLOT_*), title}]."""
    out = [f'<line x1="{LEFT}" y1="{LINE_Y}" x2="{RIGHT}" y2="{LINE_Y}" stroke="{palette.TRACK}" stroke-width="2"/>']
    for sat in satellites:
        if sat["slot_at"] is not None:
            out.append(f'<circle cx="{_x(sat["slot_at"]):.1f}" cy="{LINE_Y}" r="9" fill="none" '
                       f'stroke="{palette.ACCENT}" stroke-width="2"/>')
    for sat in satellites:
        colour = palette.SLOT_COLOURS[sat["state"]]
        out.append(f'<circle cx="{_x(sat["u"]):.1f}" cy="{LINE_Y}" r="5.5" fill="{colour}">'
                   f'<title>{escape(sat["title"])}</title></circle>')
    labels, rows = _centred_labels([(_x(sat["u"]), sat["label"]) for sat in satellites])
    out += [_text(x, LINE_Y + 26 + ROW_PX * row, text, palette.MUTED) for x, row, text in labels]
    spoken = escape("Along the plane: " + "; ".join(sat["title"] for sat in satellites), quote=True)
    height = LINE_Y + 20 + ROW_PX * max(rows, 1)
    return (f'<svg viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{spoken}" '
            f'font-family="{escape(palette.FONT, quote=True)}">' + "".join(out) + "</svg>")
