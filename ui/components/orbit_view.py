"""The 3D orbit view with its own hover: one satellite, its orbit and its slot stand out, the rest dim.

The page is ui/components/orbit_view.html. Plotly's script is put in from the installed
package, so nothing is fetched from the network. Hover cards are built with textContent,
so names are never read as markup. Inside WebGL there is no keyboard focus per satellite.
"""
import json
from functools import cache
from pathlib import Path

from plotly.offline import get_plotlyjs

from ui import palette, surfaces
from ui.components.master_map import embed
from ui.figures.orbits_3d import latest_elements, orbits_3d
from ui.figures.slot_rows import as_number, slot_words
from ui.orbit_section import CHIP_STATUS
from ui.theme import root_block

PAGE_FILE = Path(__file__).with_name("orbit_view.html")


@cache
def _plotly_js():
    return get_plotlyjs()


def hover_cards(rows, health_df):
    """One card's facts per row, in row order: name, orbit type, slot state in words, overall score and its band."""
    health = {str(h["Satellite"]): h for h in health_df.to_dict("records")} if health_df is not None else {}
    cards = []
    for row in rows:
        found = health.get(row["name"], {})
        score = as_number(found.get("Overall Score"))
        cards.append({"name": row["name"], "orbit": str(found.get("Type") or row["note"]), "slot": slot_words(row),
                      "status": CHIP_STATUS[row["state"]], "score": score,
                      "band": None if score is None else surfaces.band(score)})
    return cards


def orbit_view_html(rows, history, health_df):
    """The finished page. Plotly's script goes in before the data, so the data is never searched for placeholders."""
    figure = orbits_3d(rows, latest_elements(history) if history is not None else {})
    page = PAGE_FILE.read_text(encoding="utf-8")
    for placeholder, text in {"__ROOT__": root_block(), "__FONT__": palette.FONT,
                              "__FONT_NUMBERS__": palette.FONT_NUMBERS}.items():
        page = page.replace(placeholder, text)
    page = page.replace("__PLOTLY__", _plotly_js(), 1)
    payload = {"figure": json.loads(figure.to_json()), "satellites": hover_cards(rows, health_df)}
    return page.replace("const DATA = __DATA__;", f"const DATA = {embed(payload)};", 1)


def orbit_view(rows, history, health_df, height=600):
    """Show the view. rows from slot_rows, history and health_df from the constellation's result."""
    from streamlit.components.v1 import html

    html(orbit_view_html(rows, history, health_df), height=height, scrolling=False)
