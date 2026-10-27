"""The orbit pictures judge every satellite against its OWN slot, never the nearest one."""
import json
import math
import re
import xml.etree.ElementTree as ET

import pytest

from data.tle_cache import DATA_DIR
from ui import palette
from ui.figures.constellation_3d import BELT_RADIUS, LEFT_RING_EXTRA, constellation_3d, slot_legend
from ui.figures.score_parts import score_parts
from ui.figures.slot_belt import slot_belt
from ui.figures.slot_rows import empty_slots, last_known_position, slot_rows, unknown_slots

NAN = float("nan")
HISTORY = DATA_DIR / "navic_gp_history.json"


def health(name, slot, actual, deviation, score):
    return {"Satellite": name, "Designated Lon (°)": slot, "Current Mean Lon (°)": actual,
            "Lon Slot Deviation (°)": deviation, "Lon Deviation Score": score}


NAVIC_HEALTH = [
    health("IRNSS-1F", 32.5, "N/A", "N/A", "N/A"),
    health("IRNSS-1B", 55, 55.2, 0.2, 100),
    health("IRNSS-1I", 55, 55.05, 0.05, 100),
    health("IRNSS-1C", 83, 82.84, 0.16, 100),
    health("IRNSS-1E", 111.75, 111.58, 0.17, 100),
    health("IRNSS-1G", 129.5, 129.53, 0.03, 100),
    health("NVS-01", 131.5, 129.42, -2.08, 38.3),
    health("Unslotted", "N/A", 10.0, "N/A", "N/A"),
]
IRNSS_1D = {"name": "IRNSS-1D", "slot_lon": 111.75, "actual_lon": -25.1, "note": "set aside, graveyard orbit"}


@pytest.fixture
def navic():
    return slot_rows(NAVIC_HEALTH, set_aside=[IRNSS_1D])


def by_name(rows):
    return {row["name"]: row for row in rows}


def svg_of(html_text):
    return ET.fromstring(re.search(r"<svg.*</svg>", html_text, re.S).group(0))


def find(svg, tag, **attributes):
    """Elements of the SVG with the given data attributes, e.g. find(svg, 'line', **{'data-sat': 'A'})."""
    return [e for e in svg.iter(tag) if all(e.get(k) == v for k, v in attributes.items())]


def drawn(rows):
    return svg_of(slot_belt(rows))


# --- rows -------------------------------------------------------------------

def test_rows_take_their_state_from_the_longitude_score(navic):
    rows = by_name(navic)
    assert rows["IRNSS-1B"]["state"] == palette.SLOT_IN
    assert rows["NVS-01"]["state"] == palette.SLOT_OFF
    assert rows["NVS-01"]["deviation_deg"] == pytest.approx(2.08)
    assert rows["IRNSS-1F"]["state"] == palette.SLOT_UNKNOWN
    assert rows["IRNSS-1F"]["actual_lon"] is None
    assert rows["IRNSS-1D"]["state"] == palette.SLOT_LEFT


def test_rows_without_a_slot_are_left_out(navic):
    assert "Unslotted" not in by_name(navic)


def test_set_aside_deviation_is_the_shortest_way_round(navic):
    assert by_name(navic)["IRNSS-1D"]["deviation_deg"] == pytest.approx(136.85)


@pytest.mark.parametrize("score", [None, NAN, "N/A"])
def test_a_missing_score_is_never_called_in_slot(score):
    rows = slot_rows([health("A", 100, 100.0, 0.0, score)])
    assert rows[0]["state"] == palette.SLOT_UNKNOWN


def test_empty_slots_name_their_owner(navic):
    empties = {(e["owner"], e["slot_lon"]) for e in empty_slots(navic)}
    assert empties == {("NVS-01", 131.5), ("IRNSS-1D", 111.75)}


def test_a_slot_whose_satellite_has_no_position_is_unknown_not_empty(navic):
    assert "IRNSS-1F" not in {e["owner"] for e in empty_slots(navic)}
    assert [(e["owner"], e["slot_lon"]) for e in unknown_slots(navic)] == [("IRNSS-1F", 32.5)]


def test_belt_draws_that_slot_as_an_idle_hollow_ring_labelled_unknown_never_empty(navic):
    svg = drawn(navic)
    ring = find(svg, "circle", **{"data-owner": "IRNSS-1F"})[0]
    assert (ring.get("data-empty"), ring.get("data-unknown")) == ("false", "true")
    assert ring.get("stroke") == palette.SLOT_COLOURS[palette.SLOT_UNKNOWN] and ring.get("fill") == "none"
    assert "whose position is not known" in ring.find("{*}title").text
    texts = {t.text: t.get("fill") for t in svg.iter("text")}
    idle = palette.SLOT_COLOURS[palette.SLOT_UNKNOWN]
    assert texts["32.5, slot of IRNSS-1F, position not known"] == idle
    assert texts["IRNSS-1F: position not known"] == idle
    assert not any("empty slot of IRNSS-1F" in text for text in texts)


def test_last_known_position_of_irnss_1d():
    records = json.loads(HISTORY.read_text())["satellites"]["IRNSS-1D"]
    seen = last_known_position(records)
    assert seen["date"] == "2026-10-01"
    assert seen["lon"] == pytest.approx(-25.1, abs=0.1)
    assert seen["altitude_km"] == pytest.approx(36406, abs=5)
    assert seen["drift_deg_per_day"] == pytest.approx(8.3, abs=0.05)


def test_last_known_position_without_records_is_none():
    assert last_known_position([]) is None


# --- the two cases that are the point ----------------------------------------

def test_navic_nvs_01_is_warn_tied_to_131_5_and_that_slot_is_empty(navic):
    svg = drawn(navic)
    dot = find(svg, "circle", **{"data-sat": "NVS-01"})[0]
    assert dot.get("fill") == palette.WARN
    tie = find(svg, "line", **{"data-sat": "NVS-01"})[0]
    assert tie.get("data-slot-lon") == "131.5" and tie.get("stroke") == palette.WARN
    ring = find(svg, "circle", **{"data-slot-lon": "131.5"})[0]
    assert ring.get("data-owner") == "NVS-01" and ring.get("data-empty") == "true"
    assert ring.get("stroke") == palette.SLOT_EMPTY
    assert float(tie.get("x1")) == pytest.approx(float(ring.get("cx")))
    # IRNSS-1G sits almost on the 129.5 slot and that slot is its own, so it is not empty.
    assert find(svg, "circle", **{"data-slot-lon": "129.5"})[0].get("data-empty") == "false"
    assert {e["owner"] for e in empty_slots(navic) if e["slot_lon"] == 131.5} == {"NVS-01"}


MADE_UP = [
    health("A", 100, 120.0, 20.0, 40),    # sits exactly on B's slot
    health("B", 120, 120.05, 0.05, 100),
]


def test_a_satellite_on_anothers_slot_is_not_fine():
    rows = by_name(slot_rows(MADE_UP))
    assert rows["A"]["state"] == palette.SLOT_OFF and rows["B"]["state"] == palette.SLOT_IN
    svg = drawn(list(rows.values()))
    assert find(svg, "circle", **{"data-sat": "A"})[0].get("fill") == palette.SLOT_COLOURS[palette.SLOT_OFF]
    assert find(svg, "circle", **{"data-sat": "B"})[0].get("fill") == palette.SLOT_COLOURS[palette.SLOT_IN]
    assert find(svg, "line", **{"data-sat": "A"})[0].get("data-slot-lon") == "100"
    assert find(svg, "circle", **{"data-slot-lon": "100"})[0].get("data-empty") == "true"
    assert find(svg, "circle", **{"data-slot-lon": "120"})[0].get("data-empty") == "false"
    assert [e["slot_lon"] for e in empty_slots(list(rows.values()))] == [100]


# --- the belt ----------------------------------------------------------------

def test_belt_has_one_svg_with_a_spoken_description(navic):
    html_text = slot_belt(navic, "NavIC on 1 Oct 2026")
    assert html_text.count("<svg") == 1 and "NavIC on 1 Oct 2026" in html_text
    svg = svg_of(html_text)
    label = svg.get("aria-label")
    assert svg.get("role") == "img"
    for words in ("NVS-01: off its slot", "IRNSS-1F: position not known", "IRNSS-1D: left its slot",
                  "IRNSS-1B: in slot"):
        assert words in label


def test_belt_notes_the_satellite_that_left_beside_its_empty_slot(navic):
    svg = drawn(navic)
    assert "IRNSS-1D gone from this slot" in "".join(t.text for t in svg.iter("text"))
    assert not find(svg, "circle", **{"data-sat": "IRNSS-1D"})   # -25.1 is outside the drawn range
    assert find(svg, "circle", **{"data-slot-lon": "111.75", "data-owner": "IRNSS-1D"})[0].get("data-empty") == "true"


def test_belt_says_when_a_position_is_not_known(navic):
    svg = drawn(navic)
    assert not find(svg, "circle", **{"data-sat": "IRNSS-1F"})
    assert "IRNSS-1F: position not known" in "".join(t.text for t in svg.iter("text"))


def test_belt_merges_labels_of_satellites_at_the_same_spot(navic):
    texts = [t.text for t in drawn(navic).iter("text")]
    assert "IRNSS-1I, IRNSS-1B" in texts
    assert "NVS-01 (off its slot), IRNSS-1G" in texts


def test_belt_range_comes_from_the_slots():
    svg = drawn(slot_rows(NAVIC_HEALTH))
    ticks = [t.text for t in svg.iter("text") if t.text and t.text.endswith("° E")]
    assert ticks == ["20° E", "40° E", "60° E", "80° E", "100° E", "120° E", "140° E"]


def test_belt_without_slots_says_so():
    assert "No slots" in slot_belt([])


# --- the 3D figure -----------------------------------------------------------

def traces_by_mode(figure):
    return [t for t in figure.data if t.type == "scatter3d"]


def test_3d_has_no_legend_and_no_axes(navic):
    figure = constellation_3d(navic)
    assert figure.layout.showlegend is False
    assert figure.layout.scene.xaxis.visible is False
    assert figure.layout.paper_bgcolor == "rgba(0,0,0,0)"


def test_3d_colours_satellites_by_state(navic):
    markers = [t for t in traces_by_mode(constellation_3d(navic)) if t.mode == "markers+text"][0]
    by_hover = dict(zip(markers.hovertext, markers.marker.color))
    nvs = next(v for k, v in by_hover.items() if k.startswith("NVS-01"))
    assert nvs == palette.WARN
    assert next(v for k, v in by_hover.items() if k.startswith("IRNSS-1D")) == palette.BAD


def test_3d_hover_says_every_state_in_words(navic):
    figure = constellation_3d(navic)
    hover = " ".join(" ".join(t.hovertext) for t in traces_by_mode(figure) if t.hovertext is not None)
    assert "NVS-01: off its slot, 2.08 degrees from its own slot" in hover
    assert "IRNSS-1B: in slot" in hover
    assert "IRNSS-1D: left its slot, 136.85 degrees from its own slot" in hover
    unknown = constellation_3d(slot_rows(NAVIC_HEALTH[:1]))   # no position, so only its slot is drawn
    slots = next(t for t in traces_by_mode(unknown) if t.marker.symbol == "circle-open")
    assert dict(zip(slots.hovertext, slots.marker.color)) == {
        "Slot 32.5 degrees east: belongs to IRNSS-1F, whose position is not known": palette.SLOT_COLOURS[palette.SLOT_UNKNOWN]}


def test_3d_slot_of_nvs_01_is_hollow_and_empty(navic):
    slots = next(t for t in traces_by_mode(constellation_3d(navic)) if t.marker.symbol == "circle-open")
    hover = dict(zip(slots.hovertext, slots.marker.color))
    assert hover["Slot 131.5 degrees east: empty, it belongs to NVS-01 (off its slot)"] == palette.SLOT_EMPTY
    assert hover["Slot 129.5 degrees east: IRNSS-1G is on it"] == palette.ACCENT


def test_3d_left_satellite_rides_the_wider_ring_with_a_dashed_line_back(navic):
    figure = constellation_3d(navic)
    wide = BELT_RADIUS + LEFT_RING_EXTRA
    dotted = next(t for t in traces_by_mode(figure) if t.line.dash == "dot")
    assert max(dotted.x) == pytest.approx(wide)
    markers = [t for t in traces_by_mode(figure) if t.mode == "markers+text"][0]
    index = next(i for i, h in enumerate(markers.hovertext) if h.startswith("IRNSS-1D"))
    assert (markers.x[index] ** 2 + markers.y[index] ** 2) ** 0.5 == pytest.approx(wide)
    dashed = next(t for t in traces_by_mode(figure) if t.line.dash == "dash")
    assert any(v == pytest.approx(BELT_RADIUS * math.cos(math.radians(111.75))) for v in dashed.x if v is not None)


def test_3d_off_slot_tie_line_ends_at_its_own_slot(navic):
    tie = next(t for t in traces_by_mode(constellation_3d(navic)) if t.line.color == palette.WARN)
    assert tie.x[1] == pytest.approx(BELT_RADIUS * math.cos(math.radians(131.5)))


def test_3d_has_no_ring_when_nobody_left():
    figure = constellation_3d(slot_rows(NAVIC_HEALTH))
    assert not [t for t in traces_by_mode(figure) if t.line.dash == "dot"]


def test_legend_covers_the_four_states_and_the_empty_slot():
    legend = slot_legend()
    assert {colour for colour, _ in legend} == set(palette.SLOT_COLOURS.values()) | {palette.SLOT_EMPTY}
    text = " ".join(words for _, words in legend)
    for state in palette.SLOT_COLOURS:
        assert state in text
    assert "satellite gone" in text


# --- score parts --------------------------------------------------------------

PARTS = [("Inclination", 36), ("Upkeep", 82), ("Regularity", 100), ("Drift", 70), ("Longitude", None)]


def test_score_parts_fills_each_segment_and_names_the_missing_part():
    html_text = score_parts("IRNSS-1F", 65.2, "fair, on four parts", PARTS)
    assert "IRNSS-1F" in html_text and "65.2" in html_text and "fair, on four parts" in html_text
    assert html_text.count("sparts-fill") == 4 + 1   # four fills plus the class rule in the CSS
    assert 'style="width:36%"' in html_text and 'style="width:100%"' in html_text
    assert html_text.count("sparts-missing") == 2    # the CSS rule and the one hatched segment
    assert "Not scored: Longitude." in html_text
    assert "Longitude: not scored" in html_text


def test_score_parts_with_every_part_has_nothing_missing():
    html_text = score_parts("IRNSS-1B", 88.9, "healthy", [("Inclination", 73), ("Upkeep", 88)])
    assert "Not scored" not in html_text and "2 parts." in html_text
    assert 'class="sparts-seg sparts-missing"' not in html_text


# --- untrusted text and colours -------------------------------------------------

HOSTILE = '<img src=x onerror="alert(1)">'


def test_names_and_notes_are_escaped_everywhere():
    rows = slot_rows([health(HOSTILE, 50, 52.0, 2.0, 40)],
                     set_aside=[{"name": HOSTILE + "2", "slot_lon": 80, "actual_lon": -30, "note": HOSTILE}])
    belt = slot_belt(rows, caption=HOSTILE)
    ET.fromstring(re.search(r"<svg.*</svg>", belt, re.S).group(0))    # still well-formed
    assert "<img" not in belt
    figure = constellation_3d(rows, caption=HOSTILE)
    assert "<img" not in figure.to_json()
    card = score_parts(HOSTILE, 1.0, HOSTILE, [(HOSTILE, 5), (HOSTILE, None)])
    assert "<img" not in card


def test_every_colour_comes_from_the_palette(navic):
    allowed = {value.lower() for name, value in vars(palette).items() if isinstance(value, str) and value.startswith("#")}
    for html_text in (slot_belt(navic), score_parts("A", 1.0, "ok", PARTS)):
        assert {c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b", html_text)} <= allowed
    figure_text = json.dumps([t.to_plotly_json() for t in constellation_3d(navic).data], default=str)
    assert {c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b", figure_text)} <= allowed
