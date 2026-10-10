"""The dashboard says so when a satellite it tracks is left out. It never stops, and never goes quiet.

These drive the real app (app.py) without a browser, as tests/test_golden_scores.py does.
"""
from datetime import datetime
from pathlib import Path

import time_machine
from streamlit.testing.v1 import AppTest

import config.config
from test_golden_scores import GOLDEN

ROOT = Path(__file__).resolve().parent.parent


def run_dashboard(load_data):
    """The warnings shown for NavIC, before or after loading the bundled data."""
    with time_machine.travel(datetime.fromisoformat(GOLDEN["frozen_utc"]), tick=False):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=600)
        at.run()
        if load_data:
            next(b for b in at.button if "Load Bundled" in b.label).click().run()
        assert not at.exception, [e.value for e in at.exception]
        return [warning.value for warning in at.warning]


def test_no_notice_when_nothing_is_left_out():
    warnings = run_dashboard(load_data=True)

    assert not any("Left out" in text or "No orbit data" in text for text in warnings)


def test_a_tracked_satellite_missing_from_the_registry_is_named_on_the_page(monkeypatch):
    monkeypatch.setitem(config.config.TRACKED_NOT_IN_REGISTRY, "NavIC", ["NVS-99"])

    assert any("Left out, awaiting a registry update:** NVS-99" in text for text in run_dashboard(load_data=False))


def test_a_tracked_satellite_with_no_orbit_data_is_named_on_the_page(monkeypatch):
    monkeypatch.setitem(config.config.NAVIK_SATS, "NVS-02", 62850)   # in the registry; not in the bundled data

    warnings = run_dashboard(load_data=True)

    assert any("No orbit data for 1 tracked satellite(s):** NVS-02" in text for text in warnings)
    assert not any("IRNSS-1D" in text and "No orbit data" in text for text in warnings)   # set aside for its orbit, not missing
