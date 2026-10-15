"""The newest element set of each tracked satellite from CelesTrak's public GP API, no credentials.

The rows are held in memory only and merged onto the bundled history when it is read; the
tracked data/*.json files are never rewritten. CelesTrak asks that unchanged data is not
fetched more than every 2 hours, so a fetch happens at most that often unless the last one failed.
"""
import math
from datetime import timedelta
from threading import Lock

import requests
from sgp4 import exporter, omm
from sgp4.api import Satrec

URL = "https://celestrak.org/NORAD/elements/gp.php"
TIMEOUT = 8          # seconds per request
EVERY = timedelta(hours=2)
MU = 398600.4418     # km^3/s^2: Space-Track's SEMIMAJOR_AXIS comes from the mean motion with this

# rows: {norad: [history row, ...]}; tried: when the last fetch was tried; fetched: the last one that
# brought rows; ok: whether the last try worked. One copy per server, shared by every viewer.
# ponytail: rows grow by one per satellite per fetch while the server runs; trim them if it stays up for months.
state = {"rows": {}, "tried": None, "fetched": None, "ok": True}
_lock = Lock()


def as_history_row(row):
    """A CelesTrak OMM row in the bundled history's shape: values as text, plus SEMIMAJOR_AXIS and the TLE lines."""
    satellite = Satrec()
    omm.initialize(satellite, row)
    line1, line2 = exporter.export_tle(satellite)
    radians_per_second = float(row["MEAN_MOTION"]) * 2 * math.pi / 86400
    text = {key: value if value is None or isinstance(value, str) else str(value) for key, value in row.items()}
    return {**text, "SEMIMAJOR_AXIS": f"{(MU / radians_per_second ** 2) ** (1 / 3):.3f}",
            "TLE_LINE1": line1, "TLE_LINE2": line2}


def _get(**query):
    reply = requests.get(URL, params={**query, "FORMAT": "json"}, timeout=TIMEOUT)
    if reply.status_code == 404:   # "No GP data found" for that satellite
        return []
    reply.raise_for_status()
    return reply.json()


def fetch(norad_ids):
    """{norad: history row} for each satellite CelesTrak has: the GNSS group in one request, then one per satellite left out.

    Raises requests.RequestException, or ValueError/KeyError on a reply that is not GP JSON.
    """
    wanted = set(norad_ids)
    rows = [row for row in _get(GROUP="gnss") if int(row["NORAD_CAT_ID"]) in wanted]
    for norad in sorted(wanted - {int(row["NORAD_CAT_ID"]) for row in rows}):
        rows += _get(CATNR=norad)
    return {int(row["NORAD_CAT_ID"]): as_history_row(row) for row in rows}


def refresh(norad_ids, now, clicked=False):
    """Fetch when the last try is EVERY old, or on a click after a failed try; otherwise keep what is held.

    Returns a copy of `state`. A failure keeps the rows already held and sets ok to False.
    """
    with _lock:
        tried = state["tried"]
        if tried is None or now - tried >= EVERY or (clicked and not state["ok"]):
            state["tried"] = now
            try:
                found = fetch(norad_ids)
            except (requests.RequestException, ValueError, KeyError):
                state["ok"] = False
            else:
                for norad, row in found.items():
                    held = state["rows"].setdefault(norad, [])
                    if row["EPOCH"] not in {r["EPOCH"] for r in held}:
                        held.append(row)
                state["ok"] = True
                state["fetched"] = now if found else state["fetched"]
        return {**state, "rows": {norad: list(rows) for norad, rows in state["rows"].items()}}


def due(now):
    """Whether the next automatic fetch is due."""
    return state["tried"] is None or now - state["tried"] >= EVERY
