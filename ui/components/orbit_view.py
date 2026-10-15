"""The 3D orbit view, drawn on a canvas: hover a satellite, its orbit or its chip, and it stands out while the rest dim.

The page is ui/components/orbit_view.html (plain JavaScript, no network). Python works out
the orbits (ui/figures/orbits_3d.py); the page only turns, projects and draws them. Names
reach the page as JSON escaped by embed() and are put in with textContent, so they are
never read as markup. Each satellite also has a real button below the picture, so the
keyboard reaches every one.
"""
from pathlib import Path

from ui import palette, surfaces
from ui.components.master_map import embed
from ui.figures.orbits_3d import latest_elements, orbit_scene
from ui.figures.slot_rows import as_number, slot_words
from ui.orbit_section import CHIP_STATUS
from ui.theme import root_block

PAGE_FILE = Path(__file__).with_name("orbit_view.html")


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


def orbit_view_payload(rows, history, health_df):
    """The scene with each satellite's card facts merged in, one entry per row."""
    scene = orbit_scene(rows, latest_elements(history) if history is not None else {})
    scene["satellites"] = [{**card, **drawn} for card, drawn in zip(hover_cards(rows, health_df), scene["satellites"])]
    return scene


def orbit_view_html(rows, history, health_df):
    """The finished page: colours and fonts first, the data last so it is never searched for placeholders."""
    page = PAGE_FILE.read_text(encoding="utf-8")
    for placeholder, text in {"__ROOT__": root_block(), "__FONT__": palette.FONT,
                              "__FONT_NUMBERS__": palette.FONT_NUMBERS}.items():
        page = page.replace(placeholder, text)
    return page.replace("const DATA = __DATA__;", f"const DATA = {embed(orbit_view_payload(rows, history, health_df))};", 1)


def orbit_view(rows, history, health_df, height=600):
    """Show the view. rows from slot_rows, history and health_df from the constellation's result."""
    from streamlit.components.v1 import html

    html(orbit_view_html(rows, history, health_df), height=height, scrolling=False)
