"""The belt drawn flat: every slot on an "Ideal" line, every satellite on an "Actual" line.

Each satellite is tied to ITS OWN slot, never the nearest one. A slot whose own
satellite is not on it is drawn dashed and in the empty colour, even if some other
satellite happens to sit there. Colour is never the only signal: dots carry hover
text, labels name the state, and the picture has a spoken description.

slot_belt(rows, caption) takes the rows described in ui/figures/slot_rows.py and
returns HTML holding one inline SVG. Names and notes come from outside, so they are
escaped.
"""
import math
from html import escape

from ui import palette
from ui.figures.slot_rows import group_by_position, state_words

WIDTH = 1000
PLOT_LEFT, PLOT_RIGHT = 70, 980   # where the longitude range lands, left to right
RANGE_MARGIN_DEG = 5              # room around the outermost slots
RING_RADIUS = 9
DOT_RADIUS = 7
GAP_PX = 96                       # between the Ideal and Actual lines
ROW_PX = 16                       # height of one row of labels
CHAR_PX = 6.8                     # rough width of one character at the label size
LABEL_SIZE = 12
EDGE_PX = 4


def _lon_text(lon):
    """'25.1° W' for a longitude in degrees east."""
    return f"{abs(round(lon, 2)):g}° {'E' if lon >= 0 else 'W'}"


def _range_and_step(slot_lons):
    """The drawn longitude range, widened to whole tick steps, and the tick step (20 or 40)."""
    low, high = min(slot_lons) - RANGE_MARGIN_DEG, max(slot_lons) + RANGE_MARGIN_DEG
    step = 20 if high - low <= 160 else 40
    return math.floor(low / step) * step, math.ceil(high / step) * step, step


def _stack(boxes):
    """Give each (left, width) box a row number so that none overlap within a row.

    Boxes are placed west to east, each in the first row where it fits.
    """
    row_ends, rows = [], {}
    for index in sorted(range(len(boxes)), key=lambda i: boxes[i][0]):
        left, width = boxes[index]
        row = next((r for r, end in enumerate(row_ends) if left >= end + EDGE_PX), len(row_ends))
        if row == len(row_ends):
            row_ends.append(0)
        row_ends[row] = left + width
        rows[index] = row
    return [rows[i] for i in range(len(boxes))], len(row_ends)


def _centred_labels(items):
    """Stack labels centred on their x. items are (x, text); returns (x, row, text) and the row count."""
    boxes = []
    for x, text in items:
        width = len(text) * CHAR_PX
        left = min(max(x - width / 2, EDGE_PX), WIDTH - EDGE_PX - width)
        boxes.append((left, width))
    rows, count = _stack(boxes)
    return [(box[0] + box[1] / 2, row, text) for box, row, (_, text) in zip(boxes, rows, items)], count


def _text(x, y, content, fill, size=LABEL_SIZE, anchor="middle"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" '
            f'text-anchor="{anchor}">{escape(content)}</text>')


def _slot_groups(rows):
    """One entry per slot longitude: {lon, owners: [(name, empty)]}, west to east."""
    groups = {}
    for row in rows:
        if row["slot_lon"] is not None:
            owners = groups.setdefault(round(row["slot_lon"], 2), [])
            owners.append((row["name"], row["state"] != palette.SLOT_IN))
    return [{"lon": lon, "owners": owners} for lon, owners in sorted(groups.items())]


def _slot_label(group):
    empty = [name for name, is_empty in group["owners"] if is_empty]
    text = f"{group['lon']:g}"
    return f"{text}, empty slot of {' and '.join(empty)}" if empty else text


def _satellite_label(group):
    """One label for satellites sharing a spot: names, with the state in words unless in slot."""
    parts = [row["name"] if row["state"] == palette.SLOT_IN else f"{row['name']} ({row['state']})" for row in group]
    states = {row["state"] for row in group}
    colour = palette.SLOT_COLOURS[states.pop()] if len(states) == 1 else palette.INK
    return ", ".join(parts), (palette.INK if colour == palette.OK else colour)


def _note_for(row, low, high):
    """The note to put beside a satellite's empty slot, or None when the picture already shows it."""
    actual = row["actual_lon"]
    if row["state"] == palette.SLOT_UNKNOWN:
        return f"{row['name']}: position not known"
    if row["state"] == palette.SLOT_LEFT or actual is None:
        return f"{row['name']} gone from this slot"
    if not low <= actual <= high:
        return f"{row['name']} is at {_lon_text(actual)}, off this picture"
    return None


def _ring(cx, cy, radius, empty, group_lon, owner, title):
    colour = palette.SLOT_EMPTY if empty else palette.ACCENT
    dashes = ' stroke-dasharray="4 3"' if empty else ""
    return (f'<circle cx="{cx:.1f}" cy="{cy}" r="{radius}" fill="none" stroke="{colour}" stroke-width="2.5"{dashes} '
            f'data-slot-lon="{group_lon:g}" data-owner="{escape(owner)}" data-empty="{str(empty).lower()}">'
            f'<title>{escape(title)}</title></circle>')


def _aria(rows, low, high):
    parts = [f"Slots along the equator from {_lon_text(low)} to {_lon_text(high)}."]
    for row in rows:
        slot = "no slot" if row["slot_lon"] is None else f"slot {_lon_text(row['slot_lon'])}"
        parts.append(f"{state_words(row)} ({slot}).")
    return " ".join(parts)


def slot_belt(rows, caption=""):
    """HTML with one SVG: slots above, satellites below, each tied to its own slot."""
    if not any(row["slot_lon"] is not None for row in rows):
        return '<p class="sbelt-empty">No slots to draw.</p>'
    groups = _slot_groups(rows)
    low, high, step = _range_and_step([g["lon"] for g in groups])

    def x_of(lon):
        return PLOT_LEFT + (lon - low) / (high - low) * (PLOT_RIGHT - PLOT_LEFT)

    visible = [r for r in rows if r["actual_lon"] is not None and low <= r["actual_lon"] <= high]
    slot_labels, slot_rows_count = _centred_labels([(x_of(g["lon"]), _slot_label(g)) for g in groups])
    sat_groups = group_by_position(visible)
    sat_labels, sat_rows_count = _centred_labels(
        [(sum(x_of(r["actual_lon"]) for r in g) / len(g), _satellite_label(g)[0]) for g in sat_groups])

    ideal_y = 21 + ROW_PX * slot_rows_count
    actual_y = ideal_y + GAP_PX
    axis_y = actual_y + 26 + ROW_PX * (sat_rows_count - 1) + 26
    out = [_axis(low, high, step, x_of, ideal_y, actual_y, axis_y)]

    ring_radius = {}
    for group, (lx, row_no, text) in zip(groups, slot_labels):
        empty = any(is_empty for _, is_empty in group["owners"])
        out.append(_text(lx, ideal_y - 24 - ROW_PX * row_no, text, palette.SLOT_EMPTY if empty else palette.MUTED))
        for k, (owner, is_empty) in enumerate(group["owners"]):
            ring_radius[owner] = RING_RADIUS + 4 * k
            title = f"Slot {_lon_text(group['lon'])}: " + (f"empty, it belongs to {owner}" if is_empty else f"{owner} is on it")
            out.append(_ring(x_of(group["lon"]), ideal_y, ring_radius[owner], is_empty, group["lon"], owner, title))

    out += [_tie(row, x_of, ring_radius, ideal_y, actual_y) for row in visible if row["slot_lon"] is not None]
    out += [_dot(row, x_of(row["actual_lon"]), actual_y) for row in visible]
    for group, (lx, row_no, text) in zip(sat_groups, sat_labels):
        out.append(_text(lx, actual_y + 26 + ROW_PX * row_no, text, _satellite_label(group)[1]))
    out += _notes(rows, low, high, x_of, ideal_y)

    label = escape(_aria(rows, low, high), quote=True)
    font = escape(palette.FONT, quote=True)
    height = axis_y + 10
    svg = (f'<svg viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{label}" font-family="{font}">'
           + "".join(out) + "</svg>")
    figcaption = f'<figcaption class="sbelt-caption">{escape(caption)}</figcaption>' if caption else ""
    return f'<figure class="sbelt" style="margin:0">{svg}{figcaption}</figure>'


def _axis(low, high, step, x_of, ideal_y, actual_y, axis_y):
    out = [_text(10, ideal_y + 4, "Ideal", palette.MUTED, 13, "start"),
           _text(10, actual_y + 4, "Actual", palette.MUTED, 13, "start")]
    for y in (ideal_y, actual_y):
        out.append(f'<line x1="{PLOT_LEFT}" y1="{y}" x2="{PLOT_RIGHT}" y2="{y}" stroke="{palette.TRACK}" stroke-width="2"/>')
    for lon in range(low, high + 1, step):
        x = x_of(lon)
        out.append(f'<line x1="{x:.1f}" y1="{actual_y}" x2="{x:.1f}" y2="{actual_y + 6}" stroke="{palette.TRACK}" stroke-width="2"/>')
        out.append(_text(x, axis_y, _lon_text(lon), palette.MUTED))
    return "".join(out)


def _tie(row, x_of, ring_radius, ideal_y, actual_y):
    """The line from a satellite up to its own slot: straight when in slot, slanted when not."""
    slot_x = x_of(row["slot_lon"])
    in_slot = row["state"] == palette.SLOT_IN
    sat_x = slot_x if in_slot else x_of(row["actual_lon"])
    colour = palette.TRACK if in_slot else palette.SLOT_COLOURS[row["state"]]
    return (f'<line class="sbelt-tie" x1="{slot_x:.1f}" y1="{ideal_y + ring_radius.get(row["name"], RING_RADIUS) + 1}" '
            f'x2="{sat_x:.1f}" y2="{actual_y - DOT_RADIUS - 1}" stroke="{colour}" stroke-width="1.8" '
            f'stroke-dasharray="3 4" data-sat="{escape(row["name"])}" data-slot-lon="{row["slot_lon"]:g}"/>')


def _dot(row, x, actual_y):
    return (f'<circle class="sbelt-sat" cx="{x:.1f}" cy="{actual_y}" r="{DOT_RADIUS}" '
            f'fill="{palette.SLOT_COLOURS[row["state"]]}" data-sat="{escape(row["name"])}" data-state="{escape(row["state"])}">'
            f'<title>{escape(state_words(row))}</title></circle>')


def _notes(rows, low, high, x_of, ideal_y):
    """A note beside each empty slot whose satellite is gone, not known, or off the picture."""
    wanted = [(x_of(r["slot_lon"]), note) for r in rows
              if r["slot_lon"] is not None and (note := _note_for(r, low, high))]
    boxes, anchors = [], []
    for x, note in wanted:
        width = len(note) * CHAR_PX
        # Beside the slot, on the side with more room, so the note stays clear of the lines.
        east = x < (PLOT_LEFT + PLOT_RIGHT) / 2
        boxes.append((x + 12 if east else max(x - 12 - width, EDGE_PX), width))
        anchors.append("start" if east else "end")
    row_numbers, _ = _stack(boxes)
    return [_text(left if anchor == "start" else left + width, ideal_y + 36 + ROW_PX * row_no, note,
                  palette.SLOT_EMPTY, anchor=anchor)
            for (left, width), anchor, row_no, (_, note) in zip(boxes, anchors, row_numbers, wanted)]
