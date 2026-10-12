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
