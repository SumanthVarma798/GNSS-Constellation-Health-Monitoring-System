"""surfaces.picture: st.html drops svg, so a figure's svg travels as an image."""
import base64
import re

from ui import surfaces

FIGURE = ('<p>A caption.</p><svg viewBox="0 0 10 10" role="img" aria-label="Timeline. C59, then C04">'
          '<text x="1" y="5">C04, since 21 Apr 2026</text></svg>')


def test_a_figures_svg_becomes_an_image_with_the_same_words():
    html = surfaces.picture(FIGURE)
    assert "<svg" not in html
    assert 'alt="Timeline. C59, then C04"' in html
    assert "A caption." in html  # what sits beside the svg is kept


def test_the_image_holds_the_whole_svg_and_declares_its_namespace():
    svg = base64.b64decode(re.search(r"base64,([A-Za-z0-9+/=]+)", surfaces.picture(FIGURE)).group(1)).decode("utf-8")
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"') and svg.endswith("</svg>")
    assert "C04, since 21 Apr 2026" in svg


def test_html_without_an_svg_is_left_alone():
    assert surfaces.picture("<p>nothing to draw</p>") == "<p>nothing to draw</p>"
