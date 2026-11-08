"""A plane drawn flat keeps each satellite beside its slot, wherever the two sit around the orbit."""
import re

from ui import palette
from ui.figures.plane_strip import LEFT, RIGHT, opening, plane_strip


def _positions(svg):
    """(ring x positions, dot x positions) in drawing order."""
    rings = [float(x) for x in re.findall(r'<circle cx="([\d.]+)" cy="\d+" r="9"', svg)]
    dots = [float(x) for x in re.findall(r'<circle cx="([\d.]+)" cy="\d+" r="5.5"', svg)]
    return rings, dots


def test_a_satellite_just_past_the_node_is_drawn_beside_its_slot_just_before_it():
    # C30 in BeiDou-3 MEO plane A on 8 Nov 2026: 2 degrees past the node, its slot 1 degree before it.
    sats = [{"label": "C30", "u": 2.0, "slot_at": 359.0, "state": palette.SLOT_IN, "title": "C30"},
            {"label": "C27", "u": 46.0, "slot_at": 44.0, "state": palette.SLOT_IN, "title": "C27"},
            {"label": "C35", "u": 271.0, "slot_at": 269.0, "state": palette.SLOT_IN, "title": "C35"}]
    rings, dots = _positions(plane_strip(sats))
    span = RIGHT - LEFT

    assert abs(rings[0] - dots[0]) < span * 10 / 360   # 3 degrees apart in orbit: drawn side by side
    assert all(LEFT <= x <= RIGHT for x in rings + dots)
    assert abs(rings[1] - dots[1]) < span * 10 / 360


def test_the_line_opens_in_the_widest_empty_stretch():
    assert opening([10, 20, 200]) == 110.0     # 20 to 200 is the widest stretch: its middle
    assert opening([350, 5, 100]) == 225.0     # the stretch that crosses the node counts too
    assert opening([90]) == 270.0 and opening([]) == 0.0
