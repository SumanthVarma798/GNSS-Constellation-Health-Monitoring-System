"""Scheduled update_tle_data script behavior: resilient auth handling, paced queries, and safe merges."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import update_bundled_data as updater  # noqa: E402


FROZEN_NOW = datetime(2026, 10, 26, 11, 30, tzinfo=timezone.utc)


class FrozenDateTime(datetime):
    """Freeze datetime.now() so date-window assertions stay stable."""

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return FROZEN_NOW.replace(tzinfo=None)
        return FROZEN_NOW.astimezone(tz)


class Reply:
    def __init__(self, status_code=200, text="", rows=None):
        self.status_code = status_code
        self.text = text
        self._rows = rows or []

    def json(self):
        return self._rows


def set_args(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["update_bundled_data.py", *args])


def use_small_targets(monkeypatch):
    monkeypatch.setattr(updater, "NAVIK_SATS", {"SAT-A": 1001, "SAT-B": 1002})
    monkeypatch.setattr(updater, "QZSS_SATS", {})
    monkeypatch.setattr(updater, "BEIDOU3_SATS", {})
    monkeypatch.setattr(updater, "MEO_SATS", {})


def test_no_login_exits_zero_and_still_updates_tles(monkeypatch, capsys):
    use_small_targets(monkeypatch)
    monkeypatch.delenv("SPACETRACK_USERNAME", raising=False)
    monkeypatch.delenv("SPACETRACK_PASSWORD", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "1")
    monkeypatch.setattr(updater, "load_credentials_from_secrets", lambda: (None, None))

    tle_updates = []
    gp_updates = []
    monkeypatch.setattr(
        updater,
        "update_constellation_tles",
        lambda name, sat_dict, verbose=True: tle_updates.append((name, sat_dict)) or True,
    )
    monkeypatch.setattr(
        updater,
        "update_constellation_gp_history",
        lambda *args, **kwargs: gp_updates.append((args, kwargs)),
    )
    set_args(monkeypatch, "--constellation", "navic")

    code = updater.main()
    out = capsys.readouterr().out

    assert code == 0
    assert "Space-Track: no login set; orbit history not updated, CelesTrak orbit records only" in out
    assert "::notice::Space-Track: no login set; orbit history not updated, CelesTrak orbit records only" in out
    assert [name for name, _ in tle_updates] == ["navic"]
    assert gp_updates == []


def test_refused_login_exits_two_without_gp_queries(monkeypatch, capsys):
    use_small_targets(monkeypatch)
    monkeypatch.setenv("SPACETRACK_USERNAME", "user")
    monkeypatch.setenv("SPACETRACK_PASSWORD", "pass")
    monkeypatch.setenv("GITHUB_ACTIONS", "1")

    class Session:
        def __init__(self):
            self.posts = 0
            self.logouts = 0

        def post(self, *args, **kwargs):
            self.posts += 1
            return Reply(status_code=200, text="Login Failed")

        def get(self, url, timeout):
            assert timeout == 30
            self.logouts += 1
            assert url == updater.SPACETRACK_LOGOUT_URL
            return Reply(status_code=200)

    session = Session()
    monkeypatch.setattr(requests, "Session", lambda: session)

    tle_updates = []
    gp_updates = []
    monkeypatch.setattr(
        updater,
        "update_constellation_tles",
        lambda name, sat_dict, verbose=True: tle_updates.append((name, sat_dict)) or True,
    )
    monkeypatch.setattr(
        updater,
        "update_constellation_gp_history",
        lambda *args, **kwargs: gp_updates.append((args, kwargs)),
    )
    set_args(monkeypatch, "--constellation", "navic")

    code = updater.main()
    out = capsys.readouterr().out

    assert code == 2
    assert [name for name, _ in tle_updates] == ["navic"]
    assert gp_updates == []
    assert session.posts == 1 and session.logouts == 1
    assert "Space-Track: login refused; orbit history not updated" in out
    assert "::error::Space-Track: login refused; orbit history not updated" in out


def test_one_login_handles_many_satellites_and_paces_queries(monkeypatch):
    use_small_targets(monkeypatch)
    monkeypatch.setattr(updater, "datetime", FrozenDateTime)
    monkeypatch.setattr(updater, "load_bundled_gp_history", lambda constellation: {})
    sleeps = []
    monkeypatch.setattr(updater.time, "sleep", sleeps.append)

    saved = {}
    monkeypatch.setattr(
        updater,
        "save_gp_history_to_bundle",
        lambda constellation, satellite_data, start_date, end_date: saved.update(
            {
                "constellation": constellation,
                "satellite_data": satellite_data,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        or True,
    )

    class Session:
        def __init__(self):
            self.posts = 0
            self.logouts = 0
            self.queries = []

        def post(self, url, data, timeout):
            self.posts += 1
            assert url == updater.SPACETRACK_LOGIN_URL
            assert data == {"identity": "user", "password": "pass"}
            assert timeout == 30
            return Reply(status_code=200, text="ok")

        def get(self, url, timeout):
            if url == updater.SPACETRACK_LOGOUT_URL:
                self.logouts += 1
                assert timeout == 30
                return Reply(status_code=200, text="bye")
            self.queries.append(url)
            assert timeout == 120
            return Reply(rows=[{"EPOCH": "2026-10-26T01:00:00"}])

    session = Session()
    monkeypatch.setattr(requests, "Session", lambda: session)
    set_args(
        monkeypatch,
        "--history-only",
        "--constellation",
        "navic",
        "--username",
        "user",
        "--password",
        "pass",
    )

    code = updater.main()

    assert code == 0
    assert session.posts == 1 and session.logouts == 1
    assert len(session.queries) == 2
    assert sleeps == [3]
    assert set(saved["satellite_data"]) == {"SAT-A", "SAT-B"}


def test_query_starts_from_newest_bundled_epoch_date(monkeypatch):
    monkeypatch.setattr(updater, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        updater,
        "load_bundled_gp_history",
        lambda constellation: {
            "satellites": {"SAT-A": [{"EPOCH": "2026-10-24T10:00:00"}]},
        },
    )

    asked = []
    monkeypatch.setattr(
        updater,
        "fetch_gp_history_for_satellite",
        lambda session, norad_id, start_date, end_date: asked.append(
            (norad_id, start_date, end_date)
        )
        or [],
    )
    monkeypatch.setattr(updater, "save_gp_history_to_bundle", lambda *args, **kwargs: True)

    updater.update_constellation_gp_history(
        "navic", {"SAT-A": 1001}, object(), days=365, verbose=False
    )

    assert asked == [(1001, "2026-10-24", "2026-10-26")]


def test_merge_deduplicates_and_keeps_existing_rows_when_query_fails(monkeypatch):
    monkeypatch.setattr(updater, "datetime", FrozenDateTime)
    existing = {
        "satellites": {
            "SAT-A": [
                {"EPOCH": "2026-10-24T00:00:00", "v": "old-a1"},
                {"EPOCH": "2026-10-25T00:00:00", "v": "old-a2"},
            ],
            "SAT-B": [{"EPOCH": "2026-10-23T00:00:00", "v": "old-b1"}],
        }
    }
    monkeypatch.setattr(updater, "load_bundled_gp_history", lambda constellation: existing)

    def fetch(session, norad_id, start_date, end_date):
        if norad_id == 1001:
            return [
                {"EPOCH": "2026-10-25T00:00:00", "v": "dup"},
                {"EPOCH": "2026-10-26T00:00:00", "v": "new"},
            ]
        raise RuntimeError("network issue")

    monkeypatch.setattr(updater, "fetch_gp_history_for_satellite", fetch)

    saved = {}
    monkeypatch.setattr(
        updater,
        "save_gp_history_to_bundle",
        lambda constellation, satellite_data, start_date, end_date: saved.update(
            {
                "constellation": constellation,
                "satellite_data": satellite_data,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        or True,
    )

    updater.update_constellation_gp_history(
        "navic",
        {"SAT-A": 1001, "SAT-B": 1002},
        object(),
        days=365,
        verbose=False,
    )

    assert [row["EPOCH"] for row in saved["satellite_data"]["SAT-A"]] == [
        "2026-10-24T00:00:00",
        "2026-10-25T00:00:00",
        "2026-10-26T00:00:00",
    ]
    assert saved["satellite_data"]["SAT-B"] == existing["satellites"]["SAT-B"]


def test_http_429_stops_further_queries(monkeypatch):
    monkeypatch.setattr(updater, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        updater,
        "load_bundled_gp_history",
        lambda constellation: {
            "satellites": {
                "SAT-A": [{"EPOCH": "2026-10-20T00:00:00"}],
                "SAT-B": [{"EPOCH": "2026-10-20T00:00:00"}],
                "SAT-C": [{"EPOCH": "2026-10-20T00:00:00"}],
            }
        },
    )

    asked = []

    def fetch(session, norad_id, start_date, end_date):
        asked.append(norad_id)
        if norad_id == 1002:
            err = requests.HTTPError("busy")
            err.response = type("Response", (), {"status_code": 429})()
            raise err
        return [{"EPOCH": "2026-10-26T00:00:00"}]

    monkeypatch.setattr(updater, "fetch_gp_history_for_satellite", fetch)
    monkeypatch.setattr(updater.time, "sleep", lambda *_: None)

    saved = {}
    monkeypatch.setattr(
        updater,
        "save_gp_history_to_bundle",
        lambda constellation, satellite_data, start_date, end_date: saved.update(
            {
                "satellite_data": satellite_data,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        or True,
    )

    result = updater.update_constellation_gp_history(
        "navic",
        {"SAT-A": 1001, "SAT-B": 1002, "SAT-C": 1003},
        object(),
        days=365,
        verbose=False,
    )

    assert asked == [1001, 1002]
    assert result["busy_stop"] is True
    assert result["processed_satellites"] == 1
    assert result["total_satellites"] == 3
    assert saved["satellite_data"]["SAT-C"] == [{"EPOCH": "2026-10-20T00:00:00"}]


@pytest.mark.parametrize("answer", [requests.Timeout("slow"), Reply(status_code=503)])
def test_a_login_that_gets_no_answer_is_busy_not_a_crash(monkeypatch, capsys, answer):
    use_small_targets(monkeypatch)
    monkeypatch.setenv("SPACETRACK_USERNAME", "user")
    monkeypatch.setenv("SPACETRACK_PASSWORD", "pass")
    gp_updates = []
    monkeypatch.setattr(updater, "update_constellation_tles", lambda *args, **kwargs: True)
    monkeypatch.setattr(updater, "update_constellation_gp_history", lambda *args, **kwargs: gp_updates.append(args))

    class Session:
        def post(self, *args, **kwargs):
            if isinstance(answer, Exception):
                raise answer
            return answer

        def get(self, url, timeout):
            return Reply(status_code=200)

    monkeypatch.setattr(requests, "Session", Session)
    set_args(monkeypatch, "--constellation", "navic")

    assert updater.main() == 0
    assert gp_updates == []
    assert "Space-Track: busy; stopped after 0 of 2 satellites" in capsys.readouterr().out


def test_epochs_without_an_offset_are_utc_and_the_window_starts_at_midnight():
    assert updater.parse_epoch("2026-10-01T23:30:00.000000").isoformat() == "2026-10-01T23:30:00+00:00"
    cutoff = datetime(2025, 10, 26, tzinfo=timezone.utc)
    kept = updater.merge_rows_by_epoch([{"EPOCH": "2025-10-26T00:10:00"}, {"EPOCH": "2025-10-25T23:50:00"}], [], cutoff)
    assert [row["EPOCH"] for row in kept] == ["2025-10-26T00:10:00"]
