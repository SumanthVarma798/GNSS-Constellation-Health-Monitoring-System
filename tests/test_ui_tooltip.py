"""The one tooltip (ui/tooltip.py): text is escaped, the trigger takes focus and points at its card, and the canvas
components carry the same card rules as the pages."""
import re
from pathlib import Path

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
    assert html.count('class="tt-item"') == 2 and html.count('class="ic"') == 1   # an icon only where one is named
    assert "<b>Map</b>" in html and "<b>&lt;b&gt;Sky&lt;/b&gt;</b>" in html
    assert "<script>" not in html and html.count("&lt;script&gt;") == 3
    assert not any(tag in html for tag in ("<p>", "<p ", "<div", "<ul"))   # spans only: it may sit inside a <p>


def test_the_sky_and_ground_key_names_only_icons_there_are():
    from ui import geometry_settings as gs, icons

    assert 3 <= len(gs.SKY_GROUND_KEY) <= 5
    assert all(icon in icons.TABLER for icon, _, _ in gs.SKY_GROUND_KEY if icon)


def test_every_glance_icon_the_geometry_page_names_is_on_the_page_as_a_mask():
    # st.html drops inline <svg>, so an icon is a mask, and its variable must be in the root block.
    from ui import geometry_settings, icons
    assert {name for name, _, _ in geometry_settings.SKY_GROUND_KEY if name} <= set(icons.MASKED)


def test_a_plotly_hover_is_the_card_title_in_bold_then_muted_labels_and_escaped():
    card = tooltip.plotly_card("<A>", ("When", "%{x}"), ("Gap", "3 d & more"))

    assert card == (f'<b>&lt;A&gt;</b><br><span style="color:{palette.MUTED}">When</span>  %{{x}}'
                    f'<br><span style="color:{palette.MUTED}">Gap</span>  3 d &amp; more')
    assert tooltip.plotly_template("A").endswith("<extra></extra>")


def test_every_plotly_figure_builder_uses_the_shared_hover():
    """Each module in ui/figures that draws with Plotly sets the shared hoverlabel and writes its hover text with
    tooltip's helpers, never by hand, so every chart's hover card matches the page's tooltip."""
    modules = [p for p in sorted((Path(tooltip.__file__).parent / "figures").glob("*.py")) if "plotly" in p.read_text()]
    assert len(modules) >= 3
    for path in modules:
        text = path.read_text()
        assert "hoverlabel=PLOTLY_HOVER" in text, path.name
        assert re.findall(r"hovertemplate=(?!plotly_)", text) == [], path.name
        assert re.findall(r"hovertext=(?!_|hover\b|\[_|\[plotly_)", text) == [], path.name


def _links(html):
    return re.findall(r'<a class="tt-src" href="([^"]+)" target="_blank" rel="noopener noreferrer">([^<]+)</a>', html)


def test_every_source_named_in_a_card_is_a_link_to_that_source():
    from evidence.settings import SOURCE_LINKS

    words = "; ".join(SOURCE_LINKS)
    for html in (tooltip.tip("Heading", words), tooltip.tip_html("Heading", words),
                 tooltip.tip_html("Heading", tooltip.glance(f"As {next(iter(SOURCE_LINKS))} lists them.", [("", "From", words)], words)),
                 tooltip.legend([("#fff", words)])):
        assert {(url, name) for name, url in SOURCE_LINKS.items()} <= set(_links(html)), html[:200]


def test_a_source_in_the_cards_words_links_each_time_but_never_in_a_tag_or_a_link_or_half_a_word():
    html = tooltip.tip_html("t", '<span title="GCAT">GCAT\'s list, GCAT again, <a href="/x">IGS</a>, Space-Tracking, '
                                 'xCelesTrak, the IGS file</span>')
    card = html.split('role="tooltip"')[1]

    assert [name for _, name in _links(card)] == ["GCAT", "GCAT", "IGS"]                   # two GCAT, and "the IGS file"
    assert 'title="GCAT"' in card and '<a href="/x">IGS</a>' in card                      # attribute and own link untouched
    assert "Space-Tracking" in card and "xCelesTrak" in card and "<a class=\"tt-src\" href=\"https://www.space-track" not in card


def test_text_with_markup_is_still_escaped_before_a_source_is_linked():
    card = tooltip.tip("t", '<img src=x onerror=alert(1)> GCAT').split('role="tooltip"')[1]

    assert "<img" not in card and "&lt;img" in card and _links(card)[0][1] == "GCAT"


def test_an_open_card_takes_the_pointer_so_its_link_can_be_clicked_and_the_canvases_cards_do_not():
    css = tooltip.CARD_CSS

    taking_the_pointer = css.split("pointer-events: auto;")[0].rsplit("}", 1)[-1]   # the selectors of the rule that gives it
    for opened_by in (".tt:hover > .tt-card", ".tt-trigger:focus + .tt-card", ":focus-within", ":hover"):
        assert opened_by in taking_the_pointer, opened_by   # a click or the keyboard opens the card too, not only hover
    assert "a.tt-src" in css and "underline dotted" in css and "text-decoration-style: solid" in css
    assert "z-index: -1" in css                      # the hover bridge sits behind the words, or it blocks the link
    assert "pointer-events: auto" not in css.split(".tt-card.on")[0]   # the base card still ignores the pointer
