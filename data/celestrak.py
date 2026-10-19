"""The newest element set of each wanted satellite from CelesTrak's public GP API, no credentials.

Each fetch also keeps which satellites CelesTrak's GNSS group lists: the dashboard's
meaning of "in service".

The rows are held in memory only and merged onto the bundled history when it is read; the
tracked data/*.json files are never rewritten. CelesTrak asks that unchanged data is not
fetched more than every 2 hours, so a fetch happens at most that often unless the last one failed.
The last state is also saved to a file outside the repository, so a restarted dashboard reads it instead of
downloading again: restarts in a row once got this machine blocked (17 Oct 2026, issue 76).
"""
import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock

import requests
from sgp4 import exporter, omm
from sgp4.api import Satrec

URL = "https://celestrak.org/NORAD/elements/gp.php"
TIMEOUT = 8          # seconds per request
EVERY = timedelta(hours=2)
# One saved copy per user, shared by every checkout and worktree on the machine, outside the repository.
SAVED = Path.home() / ".cache" / "gnss-health-monitor" / "celestrak.json"
MU = 398600.4418     # km^3/s^2: Space-Track's SEMIMAJOR_AXIS comes from the mean motion with this

# rows: {norad: [history row, ...]}; listed: the NORAD IDs in the GNSS group at the last fetch that
# worked, None before one has; tried: when the last fetch was tried; fetched: the last one that
# brought rows; ok: whether the last try worked. One copy per server, shared by every viewer.
# ponytail: rows grow by one per satellite per fetch while the server runs; trim them if it stays up for months.
state = {"rows": {}, "listed": None, "tried": None, "fetched": None, "ok": True}
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
    """({norad: history row} for each wanted satellite CelesTrak has, {NORAD IDs the GNSS group lists}).

    The GNSS group in one request, then one per wanted satellite it leaves out.
    Raises requests.RequestException, or ValueError/KeyError on a reply that is not GP JSON.
    """
    wanted, group = set(norad_ids), _get(GROUP="gnss")
    listed = {int(row["NORAD_CAT_ID"]) for row in group}
    rows = [row for row in group if int(row["NORAD_CAT_ID"]) in wanted]
    for norad in sorted(wanted - listed):
        rows += _get(CATNR=norad)
    return {int(row["NORAD_CAT_ID"]): as_history_row(row) for row in rows}, listed


def _save():
    """Write `state` to SAVED, whole or not at all."""
    SAVED.parent.mkdir(parents=True, exist_ok=True)
    held = {"rows": {str(norad): rows for norad, rows in state["rows"].items()},
            "listed": None if state["listed"] is None else sorted(state["listed"]), "ok": state["ok"],
            "tried": state["tried"] and state["tried"].isoformat(),
            "fetched": state["fetched"] and state["fetched"].isoformat()}
    spare = SAVED.with_suffix(".tmp")
    spare.write_text(json.dumps(held))
    os.replace(spare, SAVED)


def _load():
    """Fill an empty `state` from SAVED. A missing or unreadable file leaves it empty."""
    try:
        held = json.loads(SAVED.read_text())
        state.update(rows={int(norad): rows for norad, rows in held["rows"].items()},
                     listed=None if held["listed"] is None else set(held["listed"]), ok=held["ok"],
                     tried=held["tried"] and datetime.fromisoformat(held["tried"]),
                     fetched=held["fetched"] and datetime.fromisoformat(held["fetched"]))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return


def refresh(norad_ids, now, clicked=False):
    """Fetch when the last try is EVERY old, or on a click after a failed try; otherwise keep what is held.

    Returns a copy of `state`. A failure keeps the rows and the listing already held and sets ok to False.
    Every try, failed or not, is saved, so a restart keeps to the same 2 hours.
    """
    with _lock:
        if state["tried"] is None:
            _load()
        tried = state["tried"]
        if tried is None or now - tried >= EVERY or (clicked and not state["ok"]):
            state["tried"] = now
            try:
                found, listed = fetch(norad_ids)
            except (requests.RequestException, ValueError, KeyError):
                state["ok"] = False
            else:
                for norad, row in found.items():
                    held = state["rows"].setdefault(norad, [])
                    if row["EPOCH"] not in {r["EPOCH"] for r in held}:
                        held.append(row)
                state["ok"], state["listed"] = True, listed
                state["fetched"] = now if found else state["fetched"]
            try:
                _save()
            except OSError:
                pass   # an unwritable disk costs only the saved copy, never the dashboard
        return {**state, "rows": {norad: list(rows) for norad, rows in state["rows"].items()}}


def due(now):
    """Whether the next automatic fetch is due."""
    return state["tried"] is None or now - state["tried"] >= EVERY
