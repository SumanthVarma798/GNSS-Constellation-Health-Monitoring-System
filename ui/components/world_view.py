"""The World map: every tracked satellite of all six systems on one canvas, coloured by broadcast health.

The page is ui/components/world_view.html (plain JavaScript, no network). Python works out where each satellite
is and its next-day ground track (ui/world_data.py), then sends one record per satellite. Names reach the page as
JSON escaped by embed() and are put in with textContent, so they are never read as markup.
"""
import json
import math
from datetime import datetime
from pathlib import Path

from ui import orbit_age, palette, world_settings
from ui.components.master_map import embed
from ui.theme import root_block
from ui.tooltip import CARD_CSS

PAGE_FILE = Path(__file__).with_name("world_view.html")
LAND_FILE = Path(__file__).resolve().parents[1] / "figures" / "land.json"


def _day_words(day):
    """'25 Oct' for a YYYY-MM-DD day, or None when it cannot be read."""
    if not isinstance(day, str):
        return None
    try:
        at = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError:
        return None
    return f"{at.day} {at:%b}"


def _rows_by_satellite(gap):
    """{satellite: the orbit-gap row} for every row in the published payload."""
    if not isinstance(gap, dict):
        return {}
    out = {}
    for row in gap.get("satellites", []):
        if isinstance(row, dict) and row.get("satellite") is not None:
            out[str(row["satellite"])] = row
    return out


def _row_for(sat):
    """The orbit-gap row for one satellite record, whether it was given as status or as plain fields."""
    if sat.get("status"):
        return sat["status"]
    if "health" in sat or "note" in sat or "accuracy_m" in sat:
        return {"health": sat.get("health"), "signal_id": sat.get("signal_id"),
                "accuracy_m": sat.get("accuracy_m"), "note": sat.get("note")}
    return {}


def _health_for(sat):
    """(words, status) for one satellite's broadcast health."""
    return orbit_age.health_words(_row_for(sat))


def _accuracy_words(row, sat):
    accuracy = row.get("accuracy_m")
    if isinstance(accuracy, (int, float)) and not isinstance(accuracy, bool):
        return f"{accuracy:.1f} m"
    return "-"


def _age_words(sat):
    age = sat.get("age")
    if isinstance(age, dict):
        days = age.get("age_days")
    else:
        days = sat.get("age_days", age if isinstance(age, (int, float)) else None)
    if isinstance(days, (int, float)) and not isinstance(days, bool):
        return f"{days:.1f} days"
    return "no orbit record"


def _position_words(lat, lon):
    if lat is None or lon is None:
        return "-"
    return f"{abs(lat):.2f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.2f}° {'E' if lon >= 0 else 'W'}"


def _short(name):
    return str(name).split(" (")[0]


def split_track(track):
    """A ground track broken into segments where the longitude jumps over the antimeridian.

    Each returned segment is a {"lat", "lon", "height"} dict of the same length. The page draws each segment
    separately, so no line runs across the whole map.
    """
    lats = track.get("lat", [])
    lons = track.get("lon", [])
    heights = track.get("height", [len(lats) * [None]][0] if lats else [])
    segments, current = [], {"lat": [], "lon": [], "height": []}
    for i, lon in enumerate(lons):
        if current["lon"] and abs(lon - current["lon"][-1]) > 180:
            segments.append(current)
            current = {"lat": [], "lon": [], "height": []}
        current["lat"].append(lats[i] if i < len(lats) else None)
        current["lon"].append(lon)
        current["height"].append(heights[i] if i < len(heights) else None)
    if current["lon"]:
        segments.append(current)
    return segments


def _satellite_record(system, sat, tracks):
    """One satellite's record for the page."""
    name = str(sat["name"])
    row = _row_for(sat)
    words, status = _health_for(sat)
    track = tracks.get(name) or sat.get("track") or {"lat": [], "lon": [], "height": []}
    return {
        "name": name,
        "label": _short(name),
        "system": system,
        "signal_id": row.get("signal_id") or "",
        "health_words": words,
        "health_status": status,
        "accuracy_words": _accuracy_words(row, sat),
        "age_words": _age_words(sat),
        "lat": sat.get("lat"),
        "lon": sat.get("lon"),
        "height": sat.get("height"),
        "position_words": _position_words(sat.get("lat"), sat.get("lon")),
        "track_segments": split_track(track),
    }


def payload(systems, gap=None, now=None):
    """What the page draws. systems: one {"name", "satellites", "tracks"} entry per constellation, or a dict keyed
    by constellation name. gap: ui.data.orbit_gap() rows. now: a datetime, or HH:MM words already worked out."""
    entries = list(systems.items()) if isinstance(systems, dict) else list(systems)
    rows_by_satellite = _rows_by_satellite(gap)
    as_of = now.strftime("%H:%M") if isinstance(now, datetime) else (now or "")
    day = _day_words((gap or {}).get("day"))
    shown_systems = []
    for entry in entries:
        system = entry.get("name") or entry.get("system")
        satellites = entry.get("satellites", {})
        if isinstance(satellites, dict):
            satellites = [{"name": name, **sat} if isinstance(sat, dict) else {"name": name}
                          for name, sat in satellites.items()]
        tracks = entry.get("tracks", {})
        here = entry.get("here", {})
        ages = entry.get("ages", {})
        records = []
        for sat in satellites:
            if isinstance(sat, str):
                sat = {"name": sat}
            name = str(sat.get("name"))
            sat = {"name": name, "status": rows_by_satellite.get(name, {}), **sat}
            sat.setdefault("age", ages.get(name, sat.get("age")))
            if sat.get("lat") is None and name in here:
                sat["lat"], sat["lon"] = here[name]
            if not tracks.get(name) and "track" not in sat:
                sat["track"] = {"lat": [], "lon": [], "height": []}
            records.append(_satellite_record(system, sat, tracks))
        shown_systems.append({"name": system, "colour": world_settings.SYSTEM_COLOURS.get(system, palette.FILL),
                              "satellites": records})
    navic_area = {**world_settings.NAVIC_AREA, "label": world_settings.NAVIC_AREA_LABEL}
    return {
        "home": {"lat": world_settings.HOME_LAT, "lon": world_settings.HOME_LON},
        "area": navic_area,
        "navic_area": navic_area,
        "as_of": as_of,
        "day": day or "no IGS file",
        "health_key": [
            {"words": "healthy", "status": "ok", "colour": world_settings.HEALTH_COLOURS["ok"]},
            {"words": "unhealthy", "status": "bad", "colour": world_settings.HEALTH_COLOURS["bad"]},
            {"words": "flags set", "status": "warn", "colour": world_settings.HEALTH_COLOURS["warn"]},
            {"words": "not in the day's file or unknown", "status": "idle", "colour": world_settings.HEALTH_COLOURS["idle"]},
        ],
        "system_key": [{"name": system, "colour": world_settings.SYSTEM_COLOURS.get(system, palette.FILL)}
                       for system in world_settings.SYSTEM_COLOURS],
        "systems": shown_systems,
    }


# The page's name follows the existing picture pattern; keep both names for callers.
world_payload = payload
build_payload = payload


def world_view_html(systems, gap=None, now=None):
    """The finished page: colours and fonts first, the land and data last so they are never searched for placeholders."""
    page = PAGE_FILE.read_text(encoding="utf-8")
    fills = {"__ROOT__": root_block(), "__FONT__": palette.FONT, "__TIP__": CARD_CSS}
    for placeholder, text in fills.items():
        page = page.replace(placeholder, text)
    land = json.loads(LAND_FILE.read_text(encoding="utf-8"))["rings"]
    page = page.replace("const LAND = __LAND__;", f"const LAND = {embed(land)};", 1)
    return page.replace("const DATA = __DATA__;", f"const DATA = {embed(payload(systems, gap, now))};", 1)


def world_view(systems, gap=None, now=None, height=760):
    """Show the view."""
    from streamlit.components.v1 import html

    html(world_view_html(systems, gap, now), height=height, scrolling=False)
