"""Each constellation's mark: one per constellation, found for any spelling of its name, drawn in its colour."""
from ui import marks, palette, systems, theme


def test_every_constellation_has_a_mark_and_a_colour_and_its_parts_share_it():
    assert set(marks.SHAPES) == set(palette.CONSTELLATION_COLOURS)
    for system, parts in systems.SYSTEMS.items():
        assert marks.key(system) is not None, system
        assert {marks.key(part) for part in parts} == {marks.key(system)}   # BeiDou-3 and BeiDou-3 MEO: one mark
    assert marks.key("BeiDou") == marks.key("BeiDou-3 MEO") == "BeiDou" and marks.key("Starlink") is None


def test_a_mark_is_a_mask_in_the_constellations_colour_and_the_name_says_which_it_is():
    drawn = marks.named("QZSS")

    # the constellation's colour, as the variable that follows the theme
    assert "color: var(--sys-qzss)" in drawn and "var(--mk-qzss)" in drawn
    assert 'aria-hidden="true"' in drawn and drawn.endswith("QZSS</span>")
    assert marks.mark("Starlink") == "" and marks.named("<b>") == '<span class="mk-name">&lt;b&gt;</span>'
    assert all(f"--mk-{key.lower()}:" in theme.root_block() for key in marks.SHAPES)   # each is on the page to mask with


def test_a_mark_is_a_whole_small_svg_with_nothing_outside_its_box():
    for key in marks.SHAPES:
        drawn = marks.svg(key)
        assert drawn.startswith("<svg ") and drawn.endswith("</svg>") and len(drawn) < 1500 and "<script" not in drawn
