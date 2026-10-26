"""The newest GP orbit record of each wanted satellite from Space-Track's API."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

import requests

from data import celestrak
from evidence.archive import min_gap
from evidence.settings import USER_AGENT

LOGIN = "https://www.space-track.org/ajaxauth/login"
LOGOUT = "https://www.space-track.org/ajaxauth/logout"
QUERY = "https://www.space-track.org/basicspacedata/query/class/gp/NORAD_CAT_ID/{ids}/format/json"
EVERY = min_gap(LOGIN)
# Repeated wrong logins can lock the account.
REFUSED_WAIT = timedelta(hours=24)
SAVED = Path.home() / ".cache" / "gnss-health-monitor" / "spacetrack.json"

# rows: {norad: [history row, ...]}; tried: the last refresh try; fetched: the last try that brought rows;
# refused_until: while a refused login is cooling down; note: short status words for the dashboard.
state = {"rows": {}, "tried": None, "fetched": None, "refused_until": None, "note": "ok"}
_lock = Lock()


class SpaceTrackError(Exception):
    """Space-Track did not answer with GP JSON we can use."""


class LoginRefused(SpaceTrackError):
    """The login details were refused."""


class Busy(SpaceTrackError):
    """Space-Track refused or did not answer this time."""


def _epoch(text):
    at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _login_failed(text):
    said = (text or "").lower()
    packed = "".join(ch for ch in said if ch not in " \t\r\n\"'")
    return "loginfailed" in packed or "login:failed" in packed


def _check(reply, login=False):
    status = reply.status_code
    if status == 200:
        return
    if login and status in (401, 403):
        raise LoginRefused("Space-Track login refused.")
    if status == 429 or status >= 500:
        raise Busy("Space-Track is busy.")
    raise SpaceTrackError(f"Space-Track status {status}.")


def fetch(username, password, norad_ids):
    """{NORAD ID: newest GP row in bundled-history shape} for the wanted satellites Space-Track has."""
    if not norad_ids:
        return {}

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    try:
        try:
            login = session.post(LOGIN, data={"identity": username, "password": password}, timeout=30)
        except requests.RequestException as error:
            raise Busy("Space-Track is busy.") from error
        _check(login, login=True)
        if _login_failed(getattr(login, "text", "")):
            raise LoginRefused("Space-Track login refused.")

        ids = ",".join(str(norad) for norad in sorted({int(norad) for norad in norad_ids}))
        try:
            reply = session.get(QUERY.format(ids=ids), timeout=60)
        except requests.RequestException as error:
            raise Busy("Space-Track is busy.") from error
        _check(reply)

        rows = reply.json()
        newest = {}
        for row in rows:
            norad = int(row["NORAD_CAT_ID"])
            if norad not in newest or _epoch(row["EPOCH"]) > _epoch(newest[norad]["EPOCH"]):
                newest[norad] = row
        return {norad: celestrak.as_history_row(row) for norad, row in newest.items()}
    except (ValueError, KeyError, TypeError) as error:
        raise SpaceTrackError("Space-Track reply was not GP JSON.") from error
    finally:
        try:
            session.get(LOGOUT, timeout=30)
        except Exception:
            pass


def _copy():
    return {**state, "rows": {norad: list(rows) for norad, rows in state["rows"].items()}}


def _save():
    """Write `state` to SAVED, whole or not at all."""
    SAVED.parent.mkdir(parents=True, exist_ok=True)
    held = {
        "rows": {str(norad): rows for norad, rows in state["rows"].items()},
        "tried": state["tried"] and state["tried"].isoformat(),
        "fetched": state["fetched"] and state["fetched"].isoformat(),
        "refused_until": state["refused_until"] and state["refused_until"].isoformat(),
        "note": state["note"],
    }
    spare = SAVED.with_suffix(".tmp")
    spare.write_text(json.dumps(held))
    os.replace(spare, SAVED)


def _load():
    """Fill an empty `state` from SAVED. A missing or unreadable file leaves it empty."""
    try:
        held = json.loads(SAVED.read_text())
        state.update(
            rows={int(norad): rows for norad, rows in held["rows"].items()},
            tried=held["tried"] and datetime.fromisoformat(held["tried"]),
            fetched=held["fetched"] and datetime.fromisoformat(held["fetched"]),
            refused_until=held.get("refused_until") and datetime.fromisoformat(held["refused_until"]),
            note=held.get("note", "ok"),
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return


def refresh(norad_ids, now, login):
    """Fetch stale satellites when due and a login is present; otherwise keep what is held."""
    with _lock:
        if state["tried"] is None:
            _load()
        if not norad_ids:
            return _copy()
        if login is None:
            state["note"] = "no login"
            return _copy()
        if state["refused_until"] and now < state["refused_until"]:
            state["note"] = "login refused"
            return _copy()
        if state["tried"] and now - state["tried"] < EVERY:
            return _copy()

        state["tried"] = now
        try:
            found = fetch(login[0], login[1], norad_ids)
        except LoginRefused:
            state["note"] = "login refused"
            state["refused_until"] = now + REFUSED_WAIT
        except Busy:
            state["note"] = "busy"
            state["refused_until"] = None
        except SpaceTrackError:
            state["note"] = "busy"
            state["refused_until"] = None
        else:
            for norad, row in found.items():
                held = state["rows"].setdefault(norad, [])
                if row["EPOCH"] not in {old["EPOCH"] for old in held}:
                    held.append(row)
            state["note"] = "ok"
            state["refused_until"] = None
            state["fetched"] = now if found else state["fetched"]
        try:
            _save()
        except OSError:
            pass
        return _copy()
