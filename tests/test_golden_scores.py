"""
Safety net: the health scores of the 20 existing satellites must not move.

This is a characterisation ("golden master") test. It does not say what the
scores should be; it records what the dashboard produces today and fails if a
later change moves any of them.

How it works
- The real app (app.py) is driven headlessly with Streamlit's AppTest, in
  bundled-data mode, once per constellation.
- The clock is frozen, because the app reads "now" for the 365-day pattern
  window, the default 90-day display range and the 24-hour longitude average.
- The golden file stores a fingerprint of the bundled data files. If the data
  changes (the weekly job rewrites it), the tests say so instead of reporting a
  code regression.

Re-record (only after the change in scores has been reviewed and approved):
    RECORD_GOLDEN=1 python -m pytest tests/test_golden_scores.py
"""

import hashlib
import json
import math
import os
from datetime import datetime
from functools import cache
from pathlib import Path

import pytest
import time_machine
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = Path(__file__).parent / "golden" / "health_scores.json"
DATA_FILES = sorted(p.name for p in (ROOT / "data").glob("*.json"))

# Sidebar label -> satellites the dashboard is configured to track.
CONSTELLATIONS = ["NavIC", "QZSS", "BeiDou-3"]

SCORE_FIELDS = ["Overall Score", "_inc_score", "_maintenance_score",
                "_uniformity_score", "_drift_score", "Lon Deviation Score"]
LABEL_FIELDS = ["Type", "Health Status"]
# Inputs to the scores, recorded so a failure shows *why* a score moved.
INPUT_FIELDS = ["Incl. (°)", "Current Drift (°/day)", "Lon Slot Deviation (°)",
                "EW Maneuvers", "NS Maneuvers"]


def data_fingerprint():
    return {name: hashlib.sha256((ROOT / "data" / name).read_bytes()).hexdigest()
            for name in DATA_FILES}


def _clean(value):
    """JSON-safe scalar: NaN and 'N/A' become None, numpy types become Python types."""
    if value is None or value == "N/A":
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


@cache
def run_app(constellation, frozen_utc):
    """Run the dashboard for one constellation and return {satellite: fields}."""
    with time_machine.travel(datetime.fromisoformat(frozen_utc), tick=False):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=600)
        at.run()
        at.sidebar.selectbox[0].set_value(constellation).run()
        next(b for b in at.button if "Load Bundled" in b.label).click().run()
        assert not at.exception, [e.value for e in at.exception]
        key = next(k for k in at.session_state.filtered_state
                   if str(k).startswith("health_df_"))
        health_df = at.session_state[key]
        graveyard = set(at.session_state["graveyard_sats"])

    result = {}
    for _, row in health_df.iterrows():
        result[row["Satellite"]] = {
            f: _clean(row[f]) for f in LABEL_FIELDS + SCORE_FIELDS + INPUT_FIELDS
        }
    for sat in graveyard:
        result[sat] = {"excluded": "graveyard orbit"}
    return result


def record():
    frozen_utc = os.environ.get("GOLDEN_FROZEN_UTC") or \
        datetime.now().astimezone().replace(microsecond=0).isoformat()
    golden = {
        "frozen_utc": frozen_utc,
        "data_sha256": data_fingerprint(),
        "satellites": {c: run_app(c, frozen_utc) for c in CONSTELLATIONS},
    }
    GOLDEN_PATH.parent.mkdir(exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(golden, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")


if os.environ.get("RECORD_GOLDEN"):
    record()

GOLDEN = json.loads(GOLDEN_PATH.read_text(encoding="utf-8")) if GOLDEN_PATH.exists() else None
CASES = [(c, s) for c, sats in (GOLDEN or {}).get("satellites", {}).items() for s in sats]


@pytest.fixture(scope="session")
def golden():
    assert GOLDEN is not None, "No golden file. Record one with RECORD_GOLDEN=1."
    assert GOLDEN["data_sha256"] == data_fingerprint(), (
        "The bundled data files in data/ have changed since the golden scores were "
        "recorded. This is a data change, not a code regression. Review the new "
        "scores, then re-record with RECORD_GOLDEN=1."
    )
    return GOLDEN


def test_all_twenty_satellites_are_covered(golden):
    assert sum(len(s) for s in golden["satellites"].values()) == 20


@pytest.mark.parametrize("constellation", CONSTELLATIONS)
def test_same_satellites_are_reported(golden, constellation):
    now = run_app(constellation, golden["frozen_utc"])
    assert set(now) == set(golden["satellites"][constellation])


@pytest.mark.parametrize("constellation,satellite", CASES)
def test_scores_unchanged(golden, constellation, satellite):
    expected = golden["satellites"][constellation][satellite]
    actual = run_app(constellation, golden["frozen_utc"])[satellite]
    for field, want in expected.items():
        got = actual.get(field)
        if isinstance(want, float):
            # Scores are stored rounded to 1 decimal place, inputs to 2-4.
            assert got == pytest.approx(want, abs=1e-6), f"{satellite}: {field}"
        else:
            assert got == want, f"{satellite}: {field}"
