"""The sky above one place over the next day, drawn on a canvas: overhead in the middle, the horizon at the edge.

One round button beside the timeline plays and pauses: the play sign while paused, the pause sign (and pressed in)
while playing. Between the ten-minute steps the satellites glide, so a day plays in about 15 seconds; dragging the
timeline moves through it by hand. Hover or tap a satellite for its card.

The page is ui/components/sky_view.html (plain JavaScript, no network). Python works out where each satellite is
(ui/geometry_data.py); the page only places and draws. Names reach the page as JSON escaped by embed() and are put
in with textContent, so they are never read as markup.
"""
import math
from pathlib import Path

from ui import geometry_settings as gs
from ui import palette
from ui.components.master_map import embed
from ui.figures import geometry as gf
from ui.theme import root_block
from ui.tooltip import CARD_CSS

PAGE_FILE = Path(__file__).with_name("sky_view.html")
TICK_HOURS = 3   # a time under the timeline every three hours


def _degrees(values):
    return [None if math.isnan(v) else round(v, 2) for v in values]


def sky_payload(frames, paths, types, mask_deg, zone):
    """What the page draws. frames: geometry_data.sky_frames; paths: geometry_data.sky_paths, over the same steps."""
    orbits = sorted({types.get(n, gs.OTHER_ORBIT) for n in paths}, key=lambda o: (o != "GEO", o))
    shape = {o: "circle" if gs.ORBIT_SYMBOLS.get(o) == "circle" else "diamond" for o in orbits}
    return {
        "mask": mask_deg,
        "ms": gs.SKY_FRAME_MS,
        "every": TICK_HOURS * 60 // gs.SKY_STEP_MINUTES,
        "steps": [{"when": gf.clock_words(f["time"], zone), "tick": f"{f['time'].astimezone(zone):%H:%M}",
                   "seen": len(f["satellites"]), "gdop": gf.gdop_words(f["gdop"])} for f in frames],
        "satellites": [{"name": name, "label": gf.short(name), "orbit": gs.ORBIT_WORDS.get(orbit, orbit),
                        "colour": gf._colour(orbit), "shape": shape[orbit], "az": _degrees(az), "el": _degrees(el)}
                       for name, (az, el) in paths.items() for orbit in [types.get(name, gs.OTHER_ORBIT)]],
        "key": [{"shape": shape[o], "colour": gf._colour(o), "words": gs.ORBIT_WORDS.get(o, o)} for o in orbits],
    }


def sky_view_html(frames, paths, types, mask_deg, zone):
    """The finished page: colours and fonts first, the data last so it is never searched for placeholders."""
    page = PAGE_FILE.read_text(encoding="utf-8")
    for placeholder, text in {"__ROOT__": root_block(), "__FONT__": palette.FONT, "__TIP__": CARD_CSS}.items():
        page = page.replace(placeholder, text)
    return page.replace("const DATA = __DATA__;", f"const DATA = {embed(sky_payload(frames, paths, types, mask_deg, zone))};", 1)


def sky_view(frames, paths, types, mask_deg, zone, height=560):
    """Show the view."""
    from streamlit.components.v1 import html

    html(sky_view_html(frames, paths, types, mask_deg, zone), height=height, scrolling=False)
