"""The belt drawn flat: every slot on an "Ideal" line, every satellite on an "Actual" line.

Each satellite is tied to ITS OWN slot, never the nearest one. A slot whose own
satellite is not on it is drawn dashed and in the empty colour, even if some other
satellite happens to sit there. A satellite off its slot also has a faint ring on the
Actual line where its slot is and an arrow from it to the satellite, so the offset reads
at a glance. A row marked "confirm" (its slot in our table is in doubt,
ui/overview_settings.py) is drawn in the idle colour with a "?" and never called empty.
Colour is never the only signal: shape (dashed, hollow, arrow, "?") says the state.

The labels are short (a slot's longitude, a satellite's name) and stacked so none
overlap; the details (owner, state, offset in degrees) open in the shared tooltip
(ui/tooltip.py) from a spot laid over each ring and dot, so the picture stays an image.

slot_belt(rows, caption) takes the rows described in ui/figures/slot_rows.py and
returns HTML holding one inline SVG and its spots. Names and notes come from outside,
so they are escaped.
"""
import math
from html import escape

from ui import palette, tooltip
from ui.figures.slot_rows import deviation_of, group_by_position, state_words
from ui.overview_settings import SLOT_CONFIRM

WIDTH = 1000
PLOT_LEFT, PLOT_RIGHT = 70, 980   # where the longitude range lands, left to right
RANGE_MARGIN_DEG = 5              # room around the outermost slots
RING_RADIUS = 7
DOT_RADIUS = 6
GAP_PX = 96                       # between the Ideal and Actual lines
ROW_PX = 16                       # height of one row of labels
CHAR_PX = 7.4                     # width of one character at the label size, on the wide side so labels never touch
LABEL_SIZE = 12
EDGE_PX = 4
EMPTY_STATES = (palette.SLOT_OFF, palette.SLOT_LEFT)   # the satellite is known not to be on its slot
COLOURS = {**palette.SLOT_COLOURS, SLOT_CONFIRM: palette.IDLE}


def _state(row):
    """The state the picture draws: the row's, or SLOT_CONFIRM for a satellite whose slot is to confirm."""
    return SLOT_CONFIRM if row.get("confirm") and row["state"] == palette.SLOT_OFF else row["state"]


def _east(lon):
    """A longitude of any number of turns as degrees east, -180 to 180: the belt draws 185 for 175° W (see _unwrapped)."""
    lon = (lon + 180) % 360 - 180 or 0.0
    return 180.0 if lon == -180 else lon


def _lon_text(lon):
    """'25.1° W' for a longitude in degrees east."""
    lon = _east(lon)
    return f"{abs(round(lon, 2)):g}° {'E' if lon >= 0 else 'W'}"


def _unwrapped(rows):
    """The rows with every longitude moved by whole turns to within 180 degrees of the slots' circular mean, so slots
    either side of the date line are drawn as one stretch: QZS-7's slot at 175° W lies 37 degrees east of QZS-1R's at
    148° E, not 323 degrees west of it."""
    slots = [math.radians(row["slot_lon"]) for row in rows if row["slot_lon"] is not None]
    middle = math.degrees(math.atan2(sum(map(math.sin, slots)), sum(map(math.cos, slots))))

    def near(lon):
        return None if lon is None else middle + (lon - middle + 180) % 360 - 180

    return [{**row, "slot_lon": near(row["slot_lon"]), "actual_lon": near(row["actual_lon"])} for row in rows]


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


def centred_labels(items):
    """Stack labels centred on their x. items are (x, text); returns (x, row, text) and the row count."""
    boxes = []
    for x, text in items:
        width = len(text) * CHAR_PX
        left = min(max(x - width / 2, EDGE_PX), WIDTH - EDGE_PX - width)
        boxes.append((left, width))
    rows, count = _stack(boxes)
    return [(box[0] + box[1] / 2, row, text) for box, row, (_, text) in zip(boxes, rows, items)], count


def text(x, y, content, fill, size=LABEL_SIZE, anchor="middle"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" '
            f'text-anchor="{anchor}">{escape(content)}</text>')


def _slot_groups(rows):
    """One entry per slot longitude: {lon, owners: [(name, state)]}, west to east."""
    groups = {}
    for row in rows:
        if row["slot_lon"] is not None:
            owners = groups.setdefault(round(row["slot_lon"], 2), [])
            owners.append((row["name"], _state(row)))
    return [{"lon": lon, "owners": owners} for lon, owners in sorted(groups.items())]


def _owners_in(group, states):
    return [name for name, state in group["owners"] if state in states]


def _slot_label(group):
    """The slot's longitude alone; who it belongs to and its state open from its ring."""
    return f"{_east(group['lon']):g}"


def _satellite_label(group):
    """One label for satellites sharing a spot: their names; the state is in the mark's shape and its tooltip."""
    states = {_state(row) for row in group}
    colour = COLOURS[states.pop()] if len(states) == 1 else palette.INK
    return ", ".join(row["name"] for row in group), (palette.INK if colour == palette.OK else colour)


def _ring_title(lon, owner, state):
    if state == SLOT_CONFIRM:
        return f"Slot {_lon_text(lon)}: belongs to {owner} in our table; {SLOT_CONFIRM}"
    if state == palette.SLOT_UNKNOWN:
        return f"Slot {_lon_text(lon)}: belongs to {owner}, whose position is not known"
    if state in EMPTY_STATES:
        return f"Slot {_lon_text(lon)}: empty, it belongs to {owner}"
    return f"Slot {_lon_text(lon)}: {owner} is on it"


def _ring(cx, cy, radius, state, group_lon, owner, title):
    """A hollow ring for a slot: dashed and in the empty colour, in the idle colour if its owner is not known, else blue."""
    empty, unknown = state in EMPTY_STATES, state in (palette.SLOT_UNKNOWN, SLOT_CONFIRM)
    colour = palette.SLOT_EMPTY if empty else COLOURS[state] if unknown else palette.ACCENT
    dashes = ' stroke-dasharray="4 3"' if empty or state == SLOT_CONFIRM else ""
    return (f'<circle cx="{cx:.1f}" cy="{cy}" r="{radius}" fill="none" stroke="{colour}" stroke-width="2.5"{dashes} '
            f'data-slot-lon="{_east(group_lon):g}" data-owner="{escape(owner)}" data-empty="{str(empty).lower()}" '
            f'data-unknown="{str(unknown).lower()}"><title>{escape(title)}</title></circle>')


def _group_colour(group):
    states = {state for _, state in group["owners"]}
    if states & set(EMPTY_STATES):
        return palette.SLOT_EMPTY
    return palette.IDLE if states & {palette.SLOT_UNKNOWN, SLOT_CONFIRM} else palette.MUTED


def _aria(rows, low, high):
    parts = [f"Slots along the equator from {_lon_text(low)} to {_lon_text(high)}."]
    for row in rows:
        slot = "no slot" if row["slot_lon"] is None else f"slot {_lon_text(row['slot_lon'])}"
        words = state_words(row).replace(row["state"], SLOT_CONFIRM, 1) if _state(row) == SLOT_CONFIRM else state_words(row)
        parts.append(f"{words} ({slot}).")
    return " ".join(parts)


def slot_belt(rows, caption=""):
    """HTML with one SVG: slots above, satellites below, each tied to its own slot; a tooltip spot over each mark."""
    if not any(row["slot_lon"] is not None for row in rows):
        return '<p class="sbelt-empty">No slots to draw.</p>'
    rows = _unwrapped(rows)
    groups = _slot_groups(rows)
    low, high, step = _range_and_step([g["lon"] for g in groups])

    def x_of(lon):
        return PLOT_LEFT + (lon - low) / (high - low) * (PLOT_RIGHT - PLOT_LEFT)

    visible = [r for r in rows if r["actual_lon"] is not None and low <= r["actual_lon"] <= high]
    slot_labels, slot_rows_count = centred_labels([(x_of(g["lon"]), _slot_label(g)) for g in groups])
    sat_groups = group_by_position(visible)
    sat_labels, sat_rows_count = centred_labels(
        [(sum(x_of(r["actual_lon"]) for r in g) / len(g), _satellite_label(g)[0]) for g in sat_groups])

    ideal_y = 21 + ROW_PX * slot_rows_count
    actual_y = ideal_y + GAP_PX
    axis_y = actual_y + 26 + ROW_PX * (sat_rows_count - 1) + 26
    out = [_axis(low, high, step, x_of, ideal_y, actual_y, axis_y)]
    spots = []

    ring_radius = {}
    for group, (lx, row_no, label) in zip(groups, slot_labels):
        out.append(text(lx, ideal_y - 14 - ROW_PX * row_no, label, _group_colour(group)))
        for k, (owner, state) in enumerate(group["owners"]):
            ring_radius[owner] = RING_RADIUS + 4 * k
            out.append(_ring(x_of(group["lon"]), ideal_y, ring_radius[owner], state, group["lon"], owner,
                             _ring_title(group["lon"], owner, state)))
        spots.append((x_of(group["lon"]), ideal_y, _slot_card(group, rows, low, high)))

    out += [_tie(row, x_of, ring_radius, ideal_y, actual_y) for row in visible if row["slot_lon"] is not None]
    out += [_offset(row, x_of, actual_y) for row in visible if _state(row) == palette.SLOT_OFF and row["slot_lon"] is not None]
    out += [_dot(row, x_of(row["actual_lon"]), actual_y) for row in visible]
    spots += [(sum(x_of(r["actual_lon"]) for r in g) / len(g), actual_y, "".join(map(_satellite_card, g)))
              for g in sat_groups]   # one spot for satellites at the same spot, their cards one after the other
    for group, (lx, row_no, label) in zip(sat_groups, sat_labels):
        out.append(text(lx, actual_y + 26 + ROW_PX * row_no, label, _satellite_label(group)[1]))

    label = escape(_aria(rows, low, high), quote=True)
    font = escape(palette.FONT, quote=True)
    height = axis_y + 10
    svg = (f'<svg viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{label}" font-family="{font}">'
           + "".join(out) + "</svg>")
    marks = "".join(f'<span class="sbelt-spot" style="left:{100 * x / WIDTH:.2f}%;top:{100 * y / height:.2f}%">'
                    f'{tooltip.tip_html("<i></i>", body, key=f"belt{k}")}</span>' for k, (x, y, body) in enumerate(spots))
    figcaption = f'<figcaption class="sbelt-caption">{escape(caption)}</figcaption>' if caption else ""
    # on a phone the belt keeps a readable width and scrolls sideways (ui/theme.css .sbelt-scroll)
    return f'<div class="sbelt-scroll"><figure class="sbelt" style="margin:0">{svg}{marks}{figcaption}</figure></div>'


def _owner_words(row, state, low, high):
    """Where a slot's owner is, in a few words."""
    actual = row["actual_lon"]
    if state in (palette.SLOT_IN, SLOT_CONFIRM, palette.SLOT_UNKNOWN):
        return "on it" if state == palette.SLOT_IN else state
    if state == palette.SLOT_LEFT or actual is None:
        return "gone from this slot"
    return f"at {_lon_text(actual)}" + ("" if low <= actual <= high else ", off this picture")


def _slot_card(group, rows, low, high):
    """The tooltip for one slot: its longitude, then each owner and where it is."""
    of = {row["name"]: row for row in rows}
    return tooltip.glance(f"Slot {_lon_text(group['lon'])}",
                          [("", owner, _owner_words(of[owner], state, low, high)) for owner, state in group["owners"]])


def _satellite_card(row):
    """The tooltip for one satellite: where it is, its state, and how far and which way from its own slot."""
    off = deviation_of(row)
    items = [("", "Mean longitude", _lon_text(row["actual_lon"])), ("", "State", _state(row))]
    if row["slot_lon"] is not None:
        way = "east" if _east(row["actual_lon"] - row["slot_lon"]) > 0 else "west"
        items.append(("", "Slot", _lon_text(row["slot_lon"]) + (f", {off:.2f}° {way} of it" if off else "")))
    return tooltip.glance(row["name"], items, note=row["note"])


def _axis(low, high, step, x_of, ideal_y, actual_y, axis_y):
    out = [text(10, ideal_y + 4, "Ideal", palette.MUTED, 13, "start"),
           text(10, actual_y + 4, "Actual", palette.MUTED, 13, "start")]
    for y in (ideal_y, actual_y):
        out.append(f'<line x1="{PLOT_LEFT}" y1="{y}" x2="{PLOT_RIGHT}" y2="{y}" stroke="{palette.TRACK}" stroke-width="2"/>')
    for lon in range(low, high + 1, step):
        x = x_of(lon)
        out.append(f'<line x1="{x:.1f}" y1="{actual_y}" x2="{x:.1f}" y2="{actual_y + 6}" stroke="{palette.TRACK}" stroke-width="2"/>')
        out.append(text(x, axis_y, _lon_text(lon), palette.MUTED))
    return "".join(out)


def _tie(row, x_of, ring_radius, ideal_y, actual_y):
    """The line from a satellite up to its own slot: straight when in slot, slanted when not."""
    slot_x = x_of(row["slot_lon"])
    in_slot = row["state"] == palette.SLOT_IN
    sat_x = slot_x if in_slot else x_of(row["actual_lon"])
    colour = palette.TRACK if in_slot else COLOURS[_state(row)]
    return (f'<line class="sbelt-tie" x1="{slot_x:.1f}" y1="{ideal_y + ring_radius.get(row["name"], RING_RADIUS) + 1}" '
            f'x2="{sat_x:.1f}" y2="{actual_y - DOT_RADIUS - 1}" stroke="{colour}" stroke-width="1.8" '
            f'stroke-dasharray="3 4" data-sat="{escape(row["name"])}" data-slot-lon="{_east(row["slot_lon"]):g}"/>')


def _offset(row, x_of, actual_y):
    """For a satellite off its slot: a faint ring on the Actual line where its slot is, and an arrow from it to the
    satellite, so how far and which way read at a glance."""
    slot_x, sat_x = x_of(row["slot_lon"]), x_of(row["actual_lon"])
    ring = (f'<circle cx="{slot_x:.1f}" cy="{actual_y}" r="{RING_RADIUS}" fill="none" stroke="{palette.WARN}" '
            f'stroke-width="1.5" stroke-dasharray="2 2" data-ideal="{escape(row["name"])}"/>')
    gap = sat_x - slot_x
    if abs(gap) < RING_RADIUS + DOT_RADIUS + 6:   # too close for an arrow: the ring beside the dot says it
        return ring
    way = 1 if gap > 0 else -1
    start, tip = slot_x + way * (RING_RADIUS + 2), sat_x - way * (DOT_RADIUS + 2)
    head = f"{tip:.1f},{actual_y} {tip - way * 6:.1f},{actual_y - 4} {tip - way * 6:.1f},{actual_y + 4}"
    return (ring + f'<line x1="{start:.1f}" y1="{actual_y}" x2="{tip - way * 5:.1f}" y2="{actual_y}" stroke="{palette.WARN}" '
            f'stroke-width="2"/><polygon points="{head}" fill="{palette.WARN}" data-arrow="{escape(row["name"])}"/>')


def _dot(row, x, actual_y):
    state = _state(row)
    mark = (f'<text x="{x:.1f}" y="{actual_y + 3.5:.1f}" fill="{palette.PLATFORM}" font-size="10" font-weight="700" '
            'text-anchor="middle">?</text>') if state == SLOT_CONFIRM else ""
    return (f'<circle class="sbelt-sat" cx="{x:.1f}" cy="{actual_y}" r="{DOT_RADIUS}" '
            f'fill="{COLOURS[state]}" data-sat="{escape(row["name"])}" data-state="{escape(state)}">'
            f'<title>{escape(state_words(row))}</title></circle>{mark}')
