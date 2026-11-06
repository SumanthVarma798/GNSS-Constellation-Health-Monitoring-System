"""Space-Track's list of payloads launched lately, kept as a raw copy, and which of them could be navigation satellites.

Space-Track holds the US Space Force's catalogue, so a new payload is listed there as soon as it is tracked, weeks
before the IGS satellite file lists it. The list says an object exists, not that it is a navigation satellite or whose,
so `candidates` only picks out those in an orbit shaped like one; a person decides, in the weekly registry pull request.
The login comes from the SPACETRACK_USERNAME and SPACETRACK_PASSWORD environment variables and is never printed.
"""
import json
import os

from data import spacetrack
from evidence.archive import FetchFailed
from evidence.settings import NAVIGATION_ORBITS

JSON_TYPE = "application/json"


def fetch(address, environ=None, read=spacetrack.read):
    """(status, body, content type) like evidence.archive.fetch, for the Space-Track address."""
    env = os.environ if environ is None else environ
    username, password = env.get("SPACETRACK_USERNAME"), env.get("SPACETRACK_PASSWORD")
    if not username or not password:
        raise FetchFailed(f"{address}: no Space-Track login set, so Space-Track cannot be read")
    try:
        return 200, read(address, username, password), JSON_TYPE
    except spacetrack.SpaceTrackError as failure:   # a refused login and a busy server are both kinds of it
        raise FetchFailed(f"{address}: {failure}") from failure


def _field(entry, *names):
    """The first of these fields the entry has, as text: Space-Track's catalogue has named some of them two ways."""
    return next((str(entry[name]).strip() for name in names if entry.get(name) not in (None, "")), "")


def _number(text):
    try:
        return float(text)
    except ValueError:
        return None


def candidates(body):
    """Rows for registry/unidentified.csv from a copy of the list: the payloads in a navigation orbit, by catalogue number."""
    rows = []
    for entry in json.loads(body):
        catalogue_no = _field(entry, "NORAD_CAT_ID")
        period, inclination = _number(_field(entry, "PERIOD")), _number(_field(entry, "INCLINATION"))
        if not catalogue_no.isdigit() or period is None or inclination is None:
            continue
        orbit = next((name for name, minutes, degrees in NAVIGATION_ORBITS
                      if minutes[0] <= period <= minutes[1] and degrees[0] <= inclination <= degrees[1]), None)
        if orbit:
            rows.append([catalogue_no, _field(entry, "OBJECT_NAME", "SATNAME"), _field(entry, "OBJECT_ID", "INTLDES"),
                         _field(entry, "LAUNCH", "LAUNCH_DATE"), orbit, f"{period:g}", f"{inclination:g}"])
    return sorted(rows, key=lambda row: int(row[0]))
