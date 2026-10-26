"""Daily orbit ages are written to the archive and can fall back to Space-Track. No network."""
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from data.spacetrack import LoginRefused
from evidence.archive import read_runs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import orbit_ages  # noqa: E402

NOW = datetime(2026, 10, 26, 3, 30, tzinfo=timezone.utc)


def epoch(days):
    return (NOW - timedelta(days=days)).replace(tzinfo=None).isoformat()


def track(monkeypatch):
    monkeypatch.setattr(orbit_ages.config, "NAVIK_SATS", {"IRNSS-1B": 39635})
    monkeypatch.setattr(orbit_ages.config, "QZSS_SATS", {"QZS-2": 40547})
    monkeypatch.setattr(orbit_ages.config, "BEIDOU3_SATS", {"BeiDou-3 I1": 44204})
    monkeypatch.setattr(orbit_ages.config, "MEO_SATS", {"GPS": {"GPS IIF-1": 36585}, "GLONASS": {}, "Galileo": {}})


def by_name(rows):
    return {row["satellite"]: row for row in rows}


def test_statuses_space_track_fallback_and_outcome_json(monkeypatch, tmp_path):
    track(monkeypatch)
    asked = []

    def celestrak_fetch(norads):
        assert sorted(norads) == [36585, 39635, 40547, 44204]
        return {
            39635: {"EPOCH": epoch(1.9)},
            40547: {"EPOCH": epoch(2.0)},
            44204: {"EPOCH": epoch(3.0)},
        }, {36585, 39635, 40547, 44204}

    def spacetrack_fetch(username, password, norads):
        asked.append((username, password, list(norads)))
        return {
            40547: {"EPOCH": epoch(1.0)},
            44204: {"EPOCH": epoch(3.5)},
        }

    monkeypatch.setattr(orbit_ages.celestrak, "fetch", celestrak_fetch)
    monkeypatch.setattr(orbit_ages.spacetrack, "fetch", spacetrack_fetch)
    outcome = tmp_path / "outcome.json"

    orbit_ages.run(tmp_path, outcome, now=NOW,
                   env={"SPACETRACK_USERNAME": "member@example.com", "SPACETRACK_PASSWORD": "secret"})

    assert asked == [("member@example.com", "secret", [36585, 40547, 44204])]
    rows = list(csv.DictReader((tmp_path / "runs" / "orbit-age-by-satellite.csv").open(newline="", encoding="utf-8")))
    named = by_name(rows)
    assert named["IRNSS-1B"]["status"] == "ok" and named["IRNSS-1B"]["source"] == "CelesTrak"
    assert named["QZS-2"]["status"] == "ok" and named["QZS-2"]["source"] == "Space-Track"
    assert named["BeiDou-3 I1"]["status"] == "stale" and named["BeiDou-3 I1"]["source"] == "CelesTrak"
    assert named["GPS IIF-1"]["status"] == "missing" and named["GPS IIF-1"]["source"] == ""
    assert named["IRNSS-1B"]["age_days"] == "1.9"
    assert named["QZS-2"]["age_days"] == "1.0"
    assert named["BeiDou-3 I1"]["age_days"] == "3.0"
    assert named["GPS IIF-1"]["age_days"] == ""

    run_line = read_runs(tmp_path, "orbit-ages")[0]
    assert run_line["result"] == "success"
    assert "4 satellites" in run_line["changed"] and "1 from Space-Track" in run_line["changed"]
    saved = json.loads(outcome.read_text())
    assert not saved["all_fresh"]
    assert saved["line"] == run_line["changed"]
    assert saved["old"] == ["BeiDou-3 I1 3.0 days", "GPS IIF-1 missing"]


def test_space_track_login_refused_is_a_note_not_a_failure(monkeypatch, tmp_path):
    track(monkeypatch)
    monkeypatch.setattr(orbit_ages.celestrak, "fetch", lambda norads: ({39635: {"EPOCH": epoch(2.1)}}, set(norads)))
    monkeypatch.setattr(orbit_ages.spacetrack, "fetch",
                        lambda username, password, norads: (_ for _ in ()).throw(LoginRefused("no")))
    outcome = tmp_path / "outcome.json"

    orbit_ages.run(tmp_path, outcome, now=NOW, env={"SPACETRACK_USERNAME": "u", "SPACETRACK_PASSWORD": "p"})

    run_line = read_runs(tmp_path, "orbit-ages")[0]
    assert run_line["result"] == "success"
    assert "Space-Track: login refused" in run_line["changed"]
    assert json.loads(outcome.read_text())["all_fresh"] is False


def test_space_track_is_not_called_without_login_and_csv_header_is_written_once(monkeypatch, tmp_path):
    track(monkeypatch)
    called = []

    monkeypatch.setattr(orbit_ages.celestrak, "fetch", lambda norads: ({39635: {"EPOCH": epoch(1.0)}}, set(norads)))

    def should_not_run(*args, **kwargs):
        called.append((args, kwargs))
        raise AssertionError("Space-Track fetch called without a login")

    monkeypatch.setattr(orbit_ages.spacetrack, "fetch", should_not_run)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    orbit_ages.run(tmp_path, first, now=NOW, env={})
    orbit_ages.run(tmp_path, second, now=NOW + timedelta(minutes=1), env={})

    text = (tmp_path / "runs" / "orbit-age-by-satellite.csv").read_text(encoding="utf-8")
    assert text.count(",".join(orbit_ages.ORBIT_AGE_COLUMNS) + "\n") == 1
    assert not called
    assert "Space-Track: no login set" in read_runs(tmp_path, "orbit-ages")[0]["changed"]


def test_celestrak_failure_is_not_fatal(monkeypatch, tmp_path):
    track(monkeypatch)
    monkeypatch.setattr(orbit_ages.celestrak, "fetch",
                        lambda norads: (_ for _ in ()).throw(requests.Timeout("timed out")))
    monkeypatch.setattr(orbit_ages.spacetrack, "fetch", lambda username, password, norads: {})
    outcome = tmp_path / "outcome.json"

    orbit_ages.run(tmp_path, outcome, now=NOW, env={"SPACETRACK_USERNAME": "u", "SPACETRACK_PASSWORD": "p"})

    run_line = read_runs(tmp_path, "orbit-ages")[0]
    assert run_line["result"] == "success"
    assert "CelesTrak failed:" in run_line["changed"]
