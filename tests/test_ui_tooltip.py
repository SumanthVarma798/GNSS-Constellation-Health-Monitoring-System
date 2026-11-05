"""The one tooltip (ui/tooltip.py): text is escaped, the trigger takes focus and points at its card, and the canvas
components carry the same card rules as the pages."""
import pytest

from ui import palette, tooltip
from ui.components.master_map import master_map_html
from ui.components.orbit_view import orbit_view_html
from ui.pages_data import load_master_map_data
from ui.theme import theme_css

ATTACK = '<script>alert("1")</script> & \'more\''


def test_text_is_escaped_in_the_trigger_and_the_card():
    html = tooltip.tip(ATTACK, ATTACK)

    assert "<script>" not in html
    assert html.count("&lt;script&gt;alert(&quot;1&quot;)&lt;/script&gt; &amp; &#x27;more&#x27;") == 2


def test_the_trigger_takes_focus_and_is_described_by_its_card():
    html = tooltip.tip("Upkeep", "Burns over the year scored")
    card = html.split('role="tooltip" id="')[1].split('"')[0]

    assert 'tabindex="0"' in html and f'aria-describedby="{card}"' in html
    assert html.index("tt-trigger") < html.index("tt-card")   # the card follows its trigger, as the CSS expects
    assert tooltip.tip("Upkeep", "Burns over the year scored") == html   # the same markup on every run


def test_a_pill_is_marked_as_one():
    assert 'class="tt-trigger pill"' in tooltip.tip("Key", "words", pill=True)
    assert 'class="tt-trigger"' in tooltip.tip("Key", "words")


def test_a_legend_lists_every_entry_and_escapes_its_words():
    entries = [(palette.OK, "in slot"), (palette.WARN, "off its slot"), ("var(--bad)", "<b>left</b>")]
    html = tooltip.legend(entries, label="Slot <legend>")

    for colour, _ in entries:
        assert f"background:{colour}" in html
    assert "&lt;b&gt;left&lt;/b&gt;" in html and "Slot &lt;legend&gt;" in html and "<b>" not in html


def test_a_legend_colour_cannot_carry_other_css():
    with pytest.raises(ValueError):
        tooltip.legend([("red;background:url(x)", "bad")])


def test_pages_and_both_canvases_share_the_card_rules():
    assert tooltip.CARD_CSS in theme_css()
    assert tooltip.CARD_CSS in master_map_html(load_master_map_data())
    assert tooltip.CARD_CSS in orbit_view_html([], None, None)


def test_the_same_tip_twice_gets_two_ids_when_keyed():
    from ui import tooltip
    a, b = tooltip.tip("Node", "How far the plane sits", key="A"), tooltip.tip("Node", "How far the plane sits", key="B")
    assert a != b and tooltip.tip("Node", "x") == tooltip.tip("Node", "x")


def test_a_glance_card_leads_in_bold_highlights_each_key_term_and_escapes_its_words():
    html = tooltip.glance(ATTACK, [("map", "Map", ATTACK), ("", "<b>Sky</b>", "words")], note=ATTACK)

    assert '<span class="tt-lead">' in html and '<span class="tt-note">' in html
    assert html.count('class="tt-item"') == 2 and html.count("<svg") == 1   # an icon only where one is named
    assert "<b>Map</b>" in html and "<b>&lt;b&gt;Sky&lt;/b&gt;</b>" in html
    assert "<script>" not in html and html.count("&lt;script&gt;") == 3
    assert not any(tag in html for tag in ("<p>", "<p ", "<div", "<ul"))   # spans only: it may sit inside a <p>


def test_the_sky_and_ground_key_names_only_icons_there_are():
    from ui import geometry_settings as gs, icons

    assert 3 <= len(gs.SKY_GROUND_KEY) <= 5
    assert all(icon in icons.TABLER for icon, _, _ in gs.SKY_GROUND_KEY if icon)
