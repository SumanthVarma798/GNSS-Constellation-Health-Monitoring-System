"""CelesTrak's newest element sets, merged onto the bundled history in memory. No network: replies are canned."""
from datetime import datetime, timedelta, timezone

import pytest
import requests
from skyfield.api import EarthSatellite

from analysis.bundled_run import load_bundled_gp_as_dataframes
from config.config import NAVIK_SATS
from data import celestrak

# One row of a real reply from gp.php?CATNR=39635&FORMAT=json (IRNSS-1B), taken 15 Oct 2026.
IRNSS_1B = {"OBJECT_NAME": "IRNSS-1B", "OBJECT_ID": "2014-017A", "EPOCH": "2026-10-07T23:09:31.463136",
            "MEAN_MOTION": 1.00268531, "ECCENTRICITY": 0.00188221, "INCLINATION": 29.1863,
            "RA_OF_ASC_NODE": 238.4676, "ARG_OF_PERICENTER": 190.3339, "MEAN_ANOMALY": 350.3525,
            "EPHEMERIS_TYPE": 0, "CLASSIFICATION_TYPE": "U", "NORAD_CAT_ID": 39635, "ELEMENT_SET_NO": 999,
            "REV_AT_EPOCH": 4592, "BSTAR": 0, "MEAN_MOTION_DOT": 7.6e-07, "MEAN_MOTION_DDOT": 0}
NOW = datetime(2026, 10, 15, 10, 42, tzinfo=timezone.utc)


class Reply:
    def __init__(self, rows, status=200):
        self.rows, self.status_code = rows, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(self.status_code)

    def json(self):
        return self.rows


class ReplyText:
    def __init__(self, text):
        self.status_code, self.text = 200, text

    def raise_for_status(self):
        pass

    def json(self):
        raise ValueError("not json")


def empty_state():
    return {"rows": {}, "listed": None, "tried": None, "fetched": None, "ok": True, "failing_since": None}


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(celestrak, "state", empty_state())


def test_a_row_takes_the_bundled_shape():
    row = celestrak.as_history_row(IRNSS_1B)

    assert row["INCLINATION"] == "29.1863" and row["NORAD_CAT_ID"] == "39635"
    # Space-Track's SEMIMAJOR_AXIS for the bundled row with mean motion 1.00275866 is 42163.588 km.
    assert celestrak.as_history_row({**IRNSS_1B, "MEAN_MOTION": 1.00275866})["SEMIMAJOR_AXIS"] == "42163.588"
    satellite = EarthSatellite(row["TLE_LINE1"], row["TLE_LINE2"])
    assert satellite.model.satnum == 39635
    assert satellite.epoch.utc_datetime().isoformat().startswith("2026-10-07T23:09:31")


def test_fetch_keeps_the_group_and_asks_only_for_each_wanted_satellite_it_left_out(monkeypatch):
    asked = []

    def get(url, params, timeout):
        asked.append(params)
        if params.get("GROUP") == "gnss":
            return Reply([IRNSS_1B, {**IRNSS_1B, "NORAD_CAT_ID": 1}])   # a satellite not tracked is left out
        return Reply([], 404) if params["CATNR"] == 41384 else Reply([{**IRNSS_1B, "NORAD_CAT_ID": 40547}])

    monkeypatch.setattr(requests, "get", get)
    rows, listed = celestrak.fetch([39635, 40547, 41384])

    assert set(rows) == {39635, 40547}
    assert listed == {39635, 1}   # every satellite the group lists, wanted or not
    assert [p.get("GROUP") or p["CATNR"] for p in asked] == ["gnss", 40547, 41384]


def test_refresh_keeps_to_every_two_hours_and_a_click_retries_only_after_a_failure(monkeypatch):
    calls = []

    def fetch(norads):
        calls.append(norads)
        if len(calls) == 2:
            raise requests.ConnectionError("down")
        return {39635: celestrak.as_history_row(IRNSS_1B)}, {39635}

    monkeypatch.setattr(celestrak, "fetch", fetch)
    first = celestrak.refresh([39635], NOW)
    assert len(calls) == 1 and first["ok"] and first["fetched"] == NOW and len(first["rows"][39635]) == 1
    assert first["listed"] == {39635}

    celestrak.refresh([39635], NOW + timedelta(minutes=30), clicked=True)   # worked last time: no fetch
    assert len(calls) == 1 and not celestrak.due(NOW + timedelta(minutes=119))

    failed = celestrak.refresh([39635], NOW + timedelta(hours=2))            # due: fetches, and fails
    assert len(calls) == 2 and not failed["ok"] and failed["rows"][39635] and failed["fetched"] == NOW
    assert failed["listed"] == {39635}   # a failure keeps the listing held

    again = celestrak.refresh([39635], NOW + timedelta(hours=2, minutes=1), clicked=True)
    assert len(calls) == 3 and again["ok"] and len(again["rows"][39635]) == 1   # same epoch, held once


def test_the_rows_join_the_bundled_history_once():
    row = celestrak.as_history_row(IRNSS_1B)
    before = load_bundled_gp_as_dataframes("navic", NAVIK_SATS)
    after = load_bundled_gp_as_dataframes("navic", NAVIK_SATS, {39635: [row, row]})

    def irnss_1b(dfs):
        return next(df for df in dfs if df["satellite"].iloc[0] == "IRNSS-1B")

    added = irnss_1b(after)
    assert len(added) == len(irnss_1b(before)) + 1
    newest = added.iloc[-1]
    assert str(newest["EPOCH"]).startswith("2026-10-07 23:09:31")
    assert newest["SEMIMAJOR_AXIS"] == pytest.approx(42165.644, abs=0.001) and newest["INCLINATION"] == 29.1863


def test_the_dashboard_asks_for_every_satellite_of_its_generations_and_no_other(monkeypatch):
    from ui import data

    asked = []
    monkeypatch.setattr(celestrak, "refresh", lambda norads, now, clicked: asked.extend(norads))
    data.refresh()
    # IRNSS-1B tracked; BeiDou-3 M7 (plane A, slot A-4), IRNSS-1A and a BeiDou-3S test satellite are not
    assert {39635, 43107, 39199, 40549} <= set(asked)
    assert 31115 not in asked   # a BeiDou-2 satellite: another generation


def test_a_restart_reads_the_saved_copy_instead_of_downloading_again(monkeypatch):
    calls = []

    def fetch(norads):
        calls.append(norads)
        return {39635: celestrak.as_history_row(IRNSS_1B)}, {39635}

    monkeypatch.setattr(celestrak, "fetch", fetch)
    celestrak.refresh([39635], NOW)
    monkeypatch.setattr(celestrak, "state", empty_state())               # the dashboard restarts
    after = celestrak.refresh([39635], NOW + timedelta(minutes=5))
    assert len(calls) == 1 and after["tried"] == NOW and after["listed"] == {39635}
    assert after["rows"][39635][0]["TLE_LINE1"] == celestrak.as_history_row(IRNSS_1B)["TLE_LINE1"]

    monkeypatch.setattr(celestrak, "state", empty_state())               # restarts again, 2 hours on
    celestrak.refresh([39635], NOW + timedelta(hours=2))
    assert len(calls) == 2


def test_a_failed_try_is_saved_too_so_restarts_do_not_hammer_a_refusing_server(monkeypatch):
    calls = []

    def refused(norads):
        calls.append(norads)
        raise requests.HTTPError(403)

    monkeypatch.setattr(celestrak, "fetch", refused)
    celestrak.refresh([39635], NOW)
    monkeypatch.setattr(celestrak, "state", empty_state())
    after = celestrak.refresh([39635], NOW + timedelta(minutes=5))
    assert len(calls) == 1 and not after["ok"]


def test_an_unreadable_saved_copy_is_ignored(monkeypatch):
    celestrak.SAVED.write_text("{not json")
    monkeypatch.setattr(celestrak, "fetch", lambda norads: ({}, {39635}))
    assert celestrak.refresh([39635], NOW)["tried"] == NOW


def test_failing_since_is_the_first_failure_in_a_row_and_survives_a_restart(monkeypatch):
    replies = [requests.ConnectionError("down"), requests.HTTPError(403), ({}, {39635})]

    def fetch(norads):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(celestrak, "fetch", fetch)
    celestrak.refresh([39635], NOW)
    assert celestrak.refresh([39635], NOW + timedelta(hours=2))["failing_since"] == NOW
    monkeypatch.setattr(celestrak, "state", empty_state())               # the dashboard restarts
    assert celestrak.refresh([39635], NOW + timedelta(hours=2, minutes=5))["failing_since"] == NOW
    assert celestrak.refresh([39635], NOW + timedelta(hours=4))["failing_since"] is None


def test_catalogue_entry_returns_none_when_celestrak_lists_nothing(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: ReplyText("No SATCAT records found"))
    assert celestrak.catalogue_entry(100744) is None
