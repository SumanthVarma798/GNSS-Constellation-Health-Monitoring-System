"""The master map as one interactive canvas: an identity card per spacecraft on an endless, pannable plane.

The page itself is ui/components/master_map.html (plain JavaScript, no network). This
module turns the registry tables into one record per spacecraft, puts them and the
dashboard's colours into the page, and shows it with Streamlit.
"""
import json
from pathlib import Path

from evidence.master_map import agreement, display_name, identifiers, signal_ids_of
from evidence.settings import (COUNTRY_NAMES, COUNTRY_NOT_GIVEN, IDENTITY_AGREE, IDENTITY_DIFFER, IDENTITY_ONE_SOURCE,
                               SCHEME_ORBIT_FEED, SCHEME_SIGNAL_ID, SERVICE_DISAGREE)
from ui import palette
from ui.master_map_settings import IDENTITY_WORDS, ISSUER_NAMES, SCHEME_SHORT, SIGHTING_WORDS, SOURCE_NAMES
from ui.theme import root_block
from ui.tooltip import CARD_CSS

PAGE_FILE = Path(__file__).with_name("master_map.html")

# Characters that could end a <script> block early or start markup, written as JSON escapes.
SCRIPT_UNSAFE = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026"}


def _disagreement(line):
    """Why the two sources disagree about one spacecraft, or "" when they do not."""
    return line["remark"] if line["identity"] == IDENTITY_DIFFER or line["service"] == SERVICE_DISAGREE else ""


def _named(item):
    """One identifier with its issuer and sources named in full, as a reader sees them."""
    return {**item, "issuer": ISSUER_NAMES.get(item["issuer"], item["issuer"]),
            "sources": [{**s, "source": SOURCE_NAMES.get(s["source"], s["source"])} for s in item["sources"]]}


def compared(found):
    """What was checked against what: one plain line per identifier that two sources hold, or that is judged against
    another source (the GCAT name by its launch designator, the CelesTrak name by its signal ID). Empty when nothing
    was compared, so a card never says "none need a look" about identifiers no one checked."""
    lines = []
    for item in found:
        what = SCHEME_SHORT.get(item["scheme"], item["scheme"])
        held = [s for s in item["sources"] if s["status"] != "idle"]
        if len(held) >= 2:
            if all(s["status"] == "ok" for s in held):
                lines.append(f'{what}: {" and ".join(_short(s["source"]) for s in held)} agree')
            else:
                lines.append(f'{what}: ' + "; ".join(
                    f'{_short(s["source"])} {s["note"] or "says " + item["value"]}' for s in held))
        elif item["scheme"] == SCHEME_ORBIT_FEED and item["status"] != "idle":   # its signal ID against the IGS file's
            lines.append(f'{what}: {item["remark"]}')
    return lines   # the GCAT name's own check is the launch designator line, so it is not said twice


def _short(source):
    """A source's name without its gloss, for a short line: 'GCAT (J. McDowell's ...)' -> 'GCAT'."""
    return source.split(" (")[0]


def _identity_words(line, sighted):
    """How the IGS satellite metadata file and GCAT stand on who the spacecraft is, naming both."""
    if sighted and line["identity"] == IDENTITY_ONE_SOURCE:
        return "only CelesTrak's GNSS group lists it so far; GCAT does not yet"
    if line["identity"] == IDENTITY_DIFFER:
        return line["remark"]   # names both: "launch designator: the IGS satellite metadata file says ..., GCAT says ..."
    return IDENTITY_WORDS.get(line["identity"], line["identity"])


def master_map_records(data):
    """One record per spacecraft, in registry order and then each sighting, from load_master_map_data()'s dict."""
    satellites, catalogue, tracked = data["satellites"] + data["sightings"], data["catalogue"], data["tracked"]
    signal_ids, feed_names, feed_checked = data["signal_ids"], data["feed_names"], data["feed_checked"]
    states = {row["svn"]: row["state"] for row in catalogue}
    sighted = {row["svn"] for row in data["sightings"]}
    records = []
    for line in agreement(satellites, catalogue):
        svn = line["svn"]
        found = [_named(item) for item in
                 identifiers(svn, satellites, catalogue, tracked, signal_ids, feed_names, feed_checked, svn in sighted)]
        records.append({
            "svn": svn,
            "name": display_name(svn, satellites, catalogue, tracked),
            "constellation": line["constellation"],
            "country": COUNTRY_NAMES.get(states.get(svn, ""), COUNTRY_NOT_GIVEN),
            "disagreement": _disagreement(line),
            "identity": _identity_words(line, svn in sighted),
            "sighting": SIGHTING_WORDS if svn in sighted else "",
            "compared": compared(found),
            "names": [SCHEME_SHORT.get(item["scheme"], item["scheme"]) for item in found],
            # said on the card's tip only when it adds to "compared": the sources differ, or only one lists it
            "who": "" if line["identity"] == IDENTITY_AGREE and not _disagreement(line) else
                   (_disagreement(line) or _identity_words(line, svn in sighted)),
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


def master_map_html(data, focus=None, records=None):
    """The finished page: colours and fonts first, the data last so it is never searched for placeholders.

    focus names a constellation the map opens filtered to (chosen on the page around it), or None for every one.
    records is master_map_records(data) when the caller has made it already."""
    page = PAGE_FILE.read_text(encoding="utf-8")
    fills = {"__ROOT__": root_block(), "__FONT__": palette.FONT, "__FONT_NUMBERS__": palette.FONT_NUMBERS, "__TIP__": CARD_CSS}
    for placeholder, text in fills.items():
        page = page.replace(placeholder, text)
    payload = {"records": records if records is not None else master_map_records(data),
               "colours": palette.CONSTELLATION_COLOURS, "focus": focus}
    return page.replace("__DATA__", embed(payload))


def master_map_canvas(data, focus=None, records=None, height=560):
    """Show the map. data is ui.pages_data.load_master_map_data(), with the live feed laid over it. height is only a
    first guess: the frame then fits the page it holds."""
    from streamlit.components.v1 import html

    html(master_map_html(data, focus, records), height=height, scrolling=False)
