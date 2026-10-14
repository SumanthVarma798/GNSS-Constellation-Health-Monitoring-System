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
