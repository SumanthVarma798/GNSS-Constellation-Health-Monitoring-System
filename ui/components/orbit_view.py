"""The 3D orbit view, drawn on a canvas: hover a satellite, its orbit or its chip, and it stands out while the rest dim.

It shows the satellites in service (those CelesTrak's GNSS group lists) or all of the
generation, switched in the page. Satellites the dashboard does not track are drawn from
CelesTrak's elements and are not scored.

The page is ui/components/orbit_view.html (plain JavaScript, no network). Python works out
the orbits (ui/figures/orbits_3d.py); the page only turns, projects and draws them. Names
reach the page as JSON escaped by embed() and are put in with textContent, so they are
never read as markup. Each satellite also has a real button below the picture, so the
keyboard reaches every one.
"""
from pathlib import Path

import pandas as pd

from data import celestrak
from ui import palette, surfaces
from ui.components.master_map import embed
from ui.data import GENERATION
from ui.figures.fleet import OTHER_GROUP, fleet_rows
from ui.figures.orbits_3d import latest_elements, orbit_scene
from ui.figures.slot_rows import as_number, slot_words
from ui.orbit_section import CHIP_STATUS
from ui.pages_data import load_master_map_data
from ui.theme import root_block
from ui.tooltip import CARD_CSS

PAGE_FILE = Path(__file__).with_name("orbit_view.html")
NOT_SCORED = "not scored"
NOT_REACHED = "CelesTrak not reached yet: showing the tracked satellites."


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


def _newest_elements(held, names):
    """{name: elements} from the newest CelesTrak row held for each {norad: name}; names must not repeat."""
    rows = [{**row, "satellite": name} for norad, name in names.items() for row in held.get(norad, [])]
    if not rows:
        return {}
    frame = pd.DataFrame(rows)
    frame["EPOCH"] = pd.to_datetime(frame["EPOCH"])
    return latest_elements(frame)


def _listing_note(listed, norad, tracked):
    """Whether CelesTrak lists it, in words: always for a satellite not tracked, for a tracked one only when it does not."""
    if listed is None or (tracked and norad in listed):
        return ""
    return "listed by CelesTrak" if norad in listed else "not listed by CelesTrak"


def orbit_view_payload(rows, history, health_df, fleet=(), live=None):
    """The scene with each satellite's card facts merged in: one entry per row, then one per other satellite of
    the generation that CelesTrak gave elements for.

    fleet is ui.figures.fleet.fleet_rows() for the constellation; live is data.celestrak.state (rows and listed).
    Each entry says whether it is tracked (scored), in service (listed by CelesTrak; while that is not known,
    the tracked ones), its chip group, and a note on its listing. notes says plainly what each view lacks.
    """
    held, listed = (live or {}).get("rows", {}), (live or {}).get("listed")
    by_name = {entry["name"]: entry for entry in fleet}   # for the tracked rows only: two others can share a name
    extra = [entry for entry in fleet if entry["name"] not in {row["name"] for row in rows} and entry["norad"] in held]
    extra.sort(key=lambda entry: entry["group"] == OTHER_GROUP)   # so the page's plane chips end with Other
    elements = latest_elements(history) if history is not None else {}
    elements |= _newest_elements(held, {entry["norad"]: str(entry["norad"]) for entry in extra})   # by number: names repeat
    unscored = [{"name": e["name"], "orbit": e["orbit"], "slot": NOT_SCORED, "status": "muted", "score": None, "band": None}
                for e in extra]
    scene = orbit_scene([*rows, *({"name": str(e["norad"]), "slot_lon": None, "state": None} for e in extra)], elements)
    satellites = []
    entries = [*(by_name.get(row["name"]) for row in rows), *extra]
    for card, drawn, entry in zip([*hover_cards(rows, health_df), *unscored], scene["satellites"], entries):
        tracked = len(satellites) < len(rows)
        norad = entry["norad"] if entry else None
        satellites.append({**card, **drawn, "tracked": tracked, "group": entry["group"] if entry else OTHER_GROUP,
                           "service": tracked if listed is None else norad in listed,
                           "note": _listing_note(listed, norad, tracked) if entry else ""})
    drawn = sum(s["loop"] is not None for s in satellites)
    scene["satellites"] = satellites
    scene["notes"] = {"service": NOT_REACHED if listed is None else "",
                      "all": f"Orbits known for {drawn} of {len(fleet)}." if drawn < len(fleet) else ""}
    return scene


def orbit_view_html(rows, history, health_df, fleet=(), live=None):
    """The finished page: colours and fonts first, the data last so it is never searched for placeholders."""
    page = PAGE_FILE.read_text(encoding="utf-8")
    for placeholder, text in {"__ROOT__": root_block(), "__FONT__": palette.FONT,
                              "__FONT_NUMBERS__": palette.FONT_NUMBERS, "__TIP__": CARD_CSS}.items():
        page = page.replace(placeholder, text)
    payload = orbit_view_payload(rows, history, health_df, fleet, live)
    return page.replace("const DATA = __DATA__;", f"const DATA = {embed(payload)};", 1)


def orbit_view(rows, history, health_df, constellation, height=600):
    """Show the view. rows from slot_rows, history and health_df from the constellation's result."""
    from streamlit.components.v1 import html

    fleet = fleet_rows(GENERATION[constellation], load_master_map_data())
    html(orbit_view_html(rows, history, health_df, fleet, celestrak.state), height=height, scrolling=False)
