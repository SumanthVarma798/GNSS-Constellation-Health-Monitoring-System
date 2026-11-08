"""A new satellite on its way to its slot is told apart from a failing one by its own orbit records. No network."""
import datetime as dt
import json
import shutil
from pathlib import Path

import pandas as pd

from analysis import commissioning
from analysis.bundled_run import assess_constellation
from data import tle_cache

FIXTURES = Path(__file__).resolve().parent / "fixtures"

NOW = dt.datetime(2026, 11, 6, 14, 0, tzinfo=dt.timezone.utc)
TRANSFER = (0.74, 2.14, 0.0)     # eccentricity, revolutions a day, drift along the belt (not meaningful yet)
DRIFTING = (0.005, 0.9965, -2.25)
PARKED = (0.0005, 1.0027, 0.01)
MEDIUM = (0.0006, 1.86, 40.0)    # a medium Earth orbit satellite: nowhere near the belt, and settled for its orbit


def history(name, *stages):
    """One record a day from `stages`: (first day, (eccentricity, motion, drift)) pairs, to 5 Nov."""
    days = pd.date_range("2026-10-30", "2026-11-05", freq="D")
    rows = []
    for day in days:
        state = [s for start, s in stages if day >= pd.Timestamp(start)][-1]
        rows.append({"satellite": name, "EPOCH": day, "ECCENTRICITY": str(state[0]), "MEAN_MOTION": state[1],
                     "LonDrift_deg_per_day": state[2]})
    return pd.DataFrame(rows)


def test_a_new_satellite_still_drifting_is_on_its_way():
    frame = history("NEW", ("2026-10-30", TRANSFER), ("2026-11-02", DRIFTING))

    assert list(commissioning.moving_to_slot(frame, NOW)) == ["NEW"]
    assert commissioning.commissioned_on(frame, "NEW") is None   # not parked yet


def test_once_parked_it_settles_for_a_while_then_is_scored_from_the_first_parked_record():
    frame = history("NEW", ("2026-10-30", TRANSFER), ("2026-11-02", DRIFTING), ("2026-11-04", PARKED))
    settled = dt.datetime(2026, 12, 5, tzinfo=dt.timezone.utc)   # 31 days after it parked

    assert list(commissioning.moving_to_slot(frame, NOW)) == ["NEW"]   # parked two days ago: no cadence to judge yet
    assert commissioning.moving_to_slot(frame, settled) == {}
    assert commissioning.commissioned_on(frame, "NEW") == pd.Timestamp("2026-11-04")


def test_a_satellite_parked_after_the_allowed_days_still_settles_before_it_is_scored():
    """QZS-7: first record 10 Aug 2026, parked 3 Nov, so past COMMISSIONING_DAYS while only days settled."""
    frame = history("QZS-7", ("2026-10-30", DRIFTING), ("2026-11-03", PARKED))
    first_plus_95 = dt.datetime(2027, 2, 2, tzinfo=dt.timezone.utc)   # 95 days after its first record, 91 after parking

    assert list(commissioning.moving_to_slot(frame, dt.datetime(2026, 11, 8, tzinfo=dt.timezone.utc))) == ["QZS-7"]
    assert commissioning.moving_to_slot(frame, first_plus_95) == {}


def test_a_satellite_that_was_parked_from_its_first_record_has_nothing_to_skip():
    frame = history("OLD", ("2026-10-30", PARKED))

    assert commissioning.moving_to_slot(frame, NOW) == {}
    assert commissioning.commissioned_on(frame, "OLD") is None


def test_a_medium_earth_orbit_satellite_is_never_judged_by_the_belt():
    assert commissioning.moving_to_slot(history("MEO", ("2026-10-30", MEDIUM)), NOW) == {}


def test_a_satellite_not_parked_after_the_allowed_days_is_scored_like_any_other():
    late = dt.datetime(2027, 2, 15, tzinfo=dt.timezone.utc)   # 108 days after its first record
    assert commissioning.moving_to_slot(history("STRANDED", ("2026-10-30", DRIFTING)), late) == {}


def test_nvs_03_is_on_its_way_and_out_of_the_scores_and_the_burns(monkeypatch, tmp_path):
    # The frozen NavIC data plus NVS-03's five real records, 30 Oct to 4 Nov 2026 (tests/fixtures/nvs03_gp_rows.json).
    shutil.copytree(FIXTURES / "bundled_data", tmp_path / "data")
    path = tmp_path / "data" / "navic_gp_history.json"
    history = json.loads(path.read_text())
    history["satellites"]["NVS-03"] = json.loads((FIXTURES / "nvs03_gp_rows.json").read_text())
    path.write_text(json.dumps(history))
    monkeypatch.setattr(tle_cache, "DATA_DIR", tmp_path / "data")

    result = assess_constellation("NavIC", NOW)

    assert list(result["moving"]) == ["NVS-03"]
    assert "NVS-03" not in set(result["health"]["Satellite"])
    assert "NVS-03" not in set(result["burns"]["satellite"])
    assert "IRNSS-1B" in set(result["health"]["Satellite"])   # the working ones are scored as before
