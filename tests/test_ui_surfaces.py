"""The look's building blocks: text is escaped, status is always in words, and the theme comes from the palette."""
import re

import pytest

from ui import palette, surfaces
from ui.theme import theme_css

ATTACK = "<script>alert(1)</script> & more"
VARIABLES = [
    "platform", "lift", "sink", "well", "track", "fill", "ink", "muted", "accent",
    "ok", "warn", "bad", "idle", "edge", "raised", "raised-sm", "pressed", "r",
]


def assert_escaped(html):
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp; more" in html


def test_titles_and_captions_are_escaped():
    assert_escaped(surfaces.raised("<p>body</p>", title=ATTACK))
    assert_escaped(surfaces.well("<p>body</p>", title=ATTACK))
    assert_escaped(surfaces.big_number(ATTACK, ATTACK))
    assert_escaped(surfaces.hover_legend([(palette.OK, ATTACK)], label=ATTACK))


def test_body_html_is_passed_through():
    assert "<p>body</p>" in surfaces.raised("<p>body</p>")


@pytest.mark.parametrize("status", surfaces.STATUSES)
def test_chip_and_notice_keep_their_words(status):
    assert f"words for {status}" in surfaces.chip(f"words for {status}", status)
    assert f"words for {status}" in surfaces.notice(f"words for {status}", status)
    assert f'class="chip {status}"' in surfaces.chip("x", status)


def test_chip_and_notice_escape_text():
    assert_escaped(surfaces.chip(ATTACK, "ok"))
    assert_escaped(surfaces.notice(ATTACK, "bad"))


def test_unknown_status_is_a_clear_error():
    for build in (surfaces.chip, surfaces.notice):
        with pytest.raises(ValueError, match="unknown status 'fine'.*ok, warn, bad, idle, accent"):
            build("text", "fine")


def test_hover_legend_lists_every_entry_and_can_take_focus():
    entries = [(palette.OK, "in slot"), (palette.WARN, "off its slot"), ("var(--bad)", "left its slot")]
    html = surfaces.hover_legend(entries)
    for colour, text in entries:
        assert colour in html and text in html
    assert 'tabindex="0"' in html


def test_legend_colour_cannot_carry_other_css():
    with pytest.raises(ValueError):
        surfaces.hover_legend([("red;background:url(x)", "bad")])


def test_theme_defines_every_variable():
    css = theme_css()
    for name in VARIABLES:
        assert f"--{name}:" in css, name


def test_theme_takes_its_colours_from_the_palette():
    css = theme_css()
    for colour in (palette.PLATFORM, palette.LIFT, palette.SINK, palette.WELL, palette.TRACK, palette.FILL,
                   palette.INK, palette.MUTED, palette.ACCENT, palette.OK, palette.WARN, palette.BAD, palette.IDLE):
        assert colour in css


def test_stylesheet_rules_use_variables_not_colours():
    rules = theme_css().split("}", 1)[1]  # everything after the :root block
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", rules)



def test_theme_keeps_icons_and_words_centred_in_controls():
    # Measured in the browser (issue 57): Streamlit's icon margin pushed icon-only buttons 4px sideways, the gear's
    # hidden arrow pushed it 1.5px, and Avenir rode 1.4px high in chips. These rules are the fix; keep them.
    css = theme_css()
    assert 'button span:has(> [data-testid="stIconMaterial"]), button [data-testid="stIconMaterial"] { margin: 0; }' in css
    assert '[data-testid="stPopover"] button > :not(:first-child) { display: none; }' in css
    assert "text-box: trim-both cap alphabetic" in css
    assert 'button [data-testid="stMarkdownContainer"] { font-size: inherit; }' in css


def test_the_framework_theme_file_matches_the_palette():
    # .streamlit/config.toml cannot import Python, so its colours are typed again there.
    # This keeps the two from drifting apart.
    import tomllib
    from pathlib import Path

    from ui import palette

    typed = tomllib.loads((Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml").read_text())["theme"]

    assert typed == {"base": "dark", "primaryColor": palette.ACCENT, "backgroundColor": palette.PLATFORM,
                     "secondaryBackgroundColor": palette.WELL, "textColor": palette.INK}


def test_a_legend_near_the_right_edge_can_open_leftwards():
    from ui.surfaces import hover_legend

    assert 'class="legend opens-left"' in hover_legend([("#74d6a0", "in slot")], opens_left=True)
    assert 'class="legend"' in hover_legend([("#74d6a0", "in slot")])


@pytest.mark.parametrize("score, band", [(100, "ok"), (80, "ok"), (79.9, "warn"), (60, "warn"), (59.9, "bad"), (0, "bad")])
def test_score_bands(score, band):
    assert surfaces.band(score) == band
    assert f'class="tile {band}"' in surfaces.tile("A", score=score, status="x", slot="y", slot_status="ok")


def test_tile_says_everything_in_words():
    html = surfaces.tile("IRNSS-1B", "IGSO", 88.94, "Healthy", "in slot", "ok", ("Inclination", 73.2))

    for words in ("IRNSS-1B", "IGSO", "88.9", "Healthy", "in slot", "Weakest: Inclination 73"):
        assert words in html
    assert 'class="chip ok">Healthy' in html and 'class="chip ok">in slot' in html


def test_tile_set_aside_reads_so_and_has_no_score():
    html = surfaces.tile("IRNSS-1D", slot="left its slot", slot_status="bad")

    assert "set aside" in html and "left its slot" in html
    assert 'class="tile bad"' in html
    assert "Weakest" not in html and 'class="chip bad">left its slot' in html


def test_tile_escapes_text_and_rejects_an_unknown_status():
    html = surfaces.tile(ATTACK, ATTACK, 70, ATTACK, ATTACK, "warn", (ATTACK, 1))

    assert "<script>" not in html and "&lt;script&gt;" in html
    with pytest.raises(ValueError):
        surfaces.tile("A", slot_status="shiny")


def test_parts_matrix_colours_each_score_and_dashes_the_missing():
    html = surfaces.parts_matrix([("Inclination", [90, None]), ("Upkeep", [55, 70])])

    assert html.count('class="mrow"') == 2 and 'style="--n:2"' in html
    assert 'class="mc ok"' in html and 'class="mc bad"' in html and 'class="mc warn"' in html
    assert html.count('class="mc idle"') == 1
    assert 'width:90%' in html


def test_compare_grid_puts_tiles_and_matrix_in_the_same_columns():
    html = surfaces.compare_grid(["<i>a</i>", "<i>b</i>"], surfaces.parts_matrix([("Drift", [1, 2])]))

    assert html.count('style="--n:2"') == 2 and html.index("<i>a</i>") < html.index('class="matrix"')
