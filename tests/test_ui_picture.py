"""surfaces.picture: st.html drops svg, so a figure's svg travels as an image."""
import base64
import re

from ui import surfaces
from ui.figures.succession import succession_lanes

PERIODS = [{"label": "C59", "start": "2018-11-01", "end": "2026-03-31", "current": False},
           {"label": "C04", "start": "2026-04-21", "end": "", "current": True}]


def test_a_figures_svg_becomes_an_image_with_the_same_words():
    html = surfaces.picture(succession_lanes(PERIODS, "2026-10-12", caption="A caption."))
    assert "<svg" not in html
    assert 'alt="Timeline. C59, from 1 Nov 2018 to 31 Mar 2026' in html
    assert "A caption." in html  # what sits beside the svg is kept


def test_the_image_holds_the_whole_svg_and_declares_its_namespace():
    html = surfaces.picture(succession_lanes(PERIODS, "2026-10-12"))
    svg = base64.b64decode(re.search(r"base64,([A-Za-z0-9+/=]+)", html).group(1)).decode("utf-8")
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"') and svg.endswith("</svg>")
    assert "C04, since 21 Apr 2026" in svg


def test_html_without_an_svg_is_left_alone():
    assert surfaces.picture("<p>nothing to draw</p>") == "<p>nothing to draw</p>"
