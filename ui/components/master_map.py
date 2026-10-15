"""The master map as one interactive canvas: an identity card per spacecraft on an endless, pannable plane.

The page itself is ui/components/master_map.html (plain JavaScript, no network). This
module turns the registry tables into one record per spacecraft, puts them and the
dashboard's colours into the page, and shows it with Streamlit.
"""
import json
import re
from pathlib import Path

from evidence.master_map import agreement, display_name, identifiers, signal_ids_of
from evidence.settings import COUNTRY_NAMES, COUNTRY_NOT_GIVEN, IDENTITY_DIFFER, SCHEME_SIGNAL_ID, SERVICE_DISAGREE
from ui import palette
from ui.theme import root_block

PAGE_FILE = Path(__file__).with_name("master_map.html")

# Characters that could end a <script> block early or start markup, written as JSON escapes.
SCRIPT_UNSAFE = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026"}
PLACEHOLDER = re.compile(r"__[A-Z_]+__")


def _disagreement(line):
    """Why the two sources disagree about one spacecraft, or "" when they do not."""
    return line["remark"] if line["identity"] == IDENTITY_DIFFER or line["service"] == SERVICE_DISAGREE else ""


def master_map_records(data):
    """One record per spacecraft, in registry order, from load_master_map_data()'s dict."""
    satellites, catalogue, tracked = data["satellites"], data["catalogue"], data["tracked"]
    signal_ids, feed_names, feed_checked = data["signal_ids"], data["feed_names"], data["feed_checked"]
    states = {row["svn"]: row["state"] for row in catalogue}
    records = []
    for line in agreement(satellites, catalogue):
        svn = line["svn"]
        found = identifiers(svn, satellites, catalogue, tracked, signal_ids, feed_names, feed_checked)
        records.append({
            "svn": svn,
            "name": display_name(svn, satellites, catalogue, tracked),
            "constellation": line["constellation"],
            "country": COUNTRY_NAMES.get(states.get(svn, ""), COUNTRY_NOT_GIVEN),
            "disagreement": _disagreement(line),
            "identity": line["identity"],
            "signal_id": next(item["value"] for item in found if item["scheme"] == SCHEME_SIGNAL_ID),
            "identifiers": found,
            "periods": signal_ids_of(svn, signal_ids),
        })
    return records


def embed(value):
    """JSON text that is safe inside a <script> block: no < > & can appear in it."""
    text = json.dumps(value)
    for char, escaped in SCRIPT_UNSAFE.items():
        text = text.replace(char, escaped)
    return text


def master_map_html(data):
    """The finished page: colours and fonts first, the data last so it is never searched for placeholders."""
    page = PAGE_FILE.read_text(encoding="utf-8")
    fills = {"__ROOT__": root_block(), "__FONT__": palette.FONT, "__FONT_NUMBERS__": palette.FONT_NUMBERS}
    for placeholder, text in fills.items():
        page = page.replace(placeholder, text)
    payload = {"records": master_map_records(data), "colours": palette.CONSTELLATION_COLOURS}
    return page.replace("__DATA__", embed(payload))


def master_map_canvas(data, height=720):
    """Show the map. data is ui.pages_data.load_master_map_data()."""
    from streamlit.components.v1 import html

    html(master_map_html(data), height=height, scrolling=False)
