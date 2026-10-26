"""The newest GP orbit record of each wanted satellite from Space-Track's API."""
from datetime import datetime, timezone

import requests

from data import celestrak
from evidence.settings import USER_AGENT

LOGIN = "https://www.space-track.org/ajaxauth/login"
LOGOUT = "https://www.space-track.org/ajaxauth/logout"
QUERY = "https://www.space-track.org/basicspacedata/query/class/gp/NORAD_CAT_ID/{ids}/format/json"


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
