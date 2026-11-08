"""analysis/bundled_run.py must give the same health results as app.py.

The oracle is tests/golden/health_scores.json (recorded from app.py with the clock frozen).
Fields are compared exactly as tests/test_golden_scores.py compares them.
"""
from datetime import datetime
from functools import cache

import pytest

from analysis.bundled_run import assess_constellation
from test_golden_scores import (
    CONSTELLATIONS, GOLDEN, INPUT_FIELDS, LABEL_FIELDS, SCORE_FIELDS, _clean, data_fingerprint,
)

FIELDS = LABEL_FIELDS + SCORE_FIELDS + INPUT_FIELDS


@cache
def run(constellation):
    return assess_constellation(constellation, datetime.fromisoformat(GOLDEN["frozen_utc"]))


@pytest.fixture(scope="module", autouse=True)
def same_data():
    assert GOLDEN["data_sha256"] == data_fingerprint(), "bundled data changed since the golden file was recorded"


@pytest.mark.parametrize("constellation", CONSTELLATIONS)
def test_same_scores_as_app(constellation):
    expected = GOLDEN["satellites"][constellation]
    result = run(constellation)
    health = {r["Satellite"]: r for _, r in result["health"].iterrows()}
    set_aside = {s for s, v in expected.items() if "excluded" in v}

    assert set(result["set_aside"]) == set_aside
    assert set(health) == set(expected) - set_aside
    for sat, want_fields in expected.items():
        if sat in set_aside:
            continue
        for field, want in want_fields.items():
            got = _clean(health[sat][field])
            if isinstance(want, float):
                assert got == pytest.approx(want, abs=1e-6), f"{sat}: {field}"
            else:
                assert got == want, f"{sat}: {field}"


@pytest.mark.parametrize("constellation", CONSTELLATIONS)
def test_every_golden_field_is_checked(constellation):
    """Guard against the golden file gaining fields this test does not compare."""
    for sat, fields in GOLDEN["satellites"][constellation].items():
        assert set(fields) <= set(FIELDS) | {"excluded"}, sat


def test_navic_burns():
    burns = run("NavIC")["burns"]
    assert not burns.empty
    assert set(burns["kind"]) == {"east-west", "north-south"}
    assert (burns["window_start"] < burns["window_end"]).all()
    assert set(burns["satellite"]) <= set(run("NavIC")["history"]["satellite"])


def test_returns_history_and_data_time():
    result = run("NavIC")
    assert {"satellite", "EPOCH", "SEMIMAJOR_AXIS", "INCLINATION"} <= set(result["history"].columns)
    assert result["data_time"]


def test_the_app_and_the_dashboard_leave_out_the_same_satellite_while_it_moves_to_its_slot(monkeypatch):
    """Both leave a satellite on its way to its slot out of the scores, and score the rest alike; app.py once kept it."""
    import pandas as pd

    from analysis import commissioning
    from test_golden_scores import run_app

    real, moving = commissioning.moving_to_slot, "QZS-6 (Michibiki-6)"

    def with_one_moving(history, now):
        found = real(history, now)
        if moving in set(history["satellite"]):
            found[moving] = pd.Timestamp("2026-10-01")
        return found

    monkeypatch.setattr(commissioning, "moving_to_slot", with_one_moving)
    frozen = GOLDEN["frozen_utc"]
    app = run_app.__wrapped__("QZSS", frozen)   # not the cached golden run
    dashboard = assess_constellation("QZSS", datetime.fromisoformat(frozen))
    scored = {r["Satellite"]: r for _, r in dashboard["health"].iterrows()}

    assert moving in dashboard["moving"] and moving not in scored and moving not in app
    assert set(app) == set(scored) | set(dashboard["set_aside"])
    for sat, fields in app.items():
        for field, want in fields.items():
            if sat in scored:
                got = _clean(scored[sat][field])
                assert got == (pytest.approx(want, abs=1e-6) if isinstance(want, float) else want), f"{sat}: {field}"
