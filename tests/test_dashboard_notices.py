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


def run_dashboard(load_data, then_interact=False):
    """The notices shown for NavIC: before loading the bundled data, after it, or after one more interaction."""
    with time_machine.travel(datetime.fromisoformat(GOLDEN["frozen_utc"]), tick=False):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=600)
        at.run()
        if load_data:
            next(b for b in at.button if "Load Bundled" in b.label).click().run()
        if then_interact:
            at.run()
        assert not at.exception, [e.value for e in at.exception]
        return [notice.value for notice in [*at.warning, *at.info]]


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


def test_a_satellite_set_aside_for_its_orbit_stays_named_after_the_next_click():
    notices = run_dashboard(load_data=True, then_interact=True)

    assert any("Set aside, in a graveyard orbit:** IRNSS-1D" in text for text in notices)


def test_a_satellite_scored_without_its_longitude_part_is_named():
    # True of the bundled data today: it holds no current orbit record for IRNSS-1F.
    notices = run_dashboard(load_data=True)

    assert any("Scored without the longitude part:** IRNSS-1F." in text for text in notices)


def test_every_name_typed_in_the_config_is_a_tracked_satellite():
    # Requirements, commission dates and the inactive list are keyed by dashboard name.
    # A name that matches no tracked satellite would be ignored without a word.
    tracked = {**config.config.NAVIK_SATS, **config.config.QZSS_SATS, **config.config.BEIDOU3_SATS}
    typed = [*config.config.NAVIK_SERVICE_REQUIREMENTS, *config.config.QZSS_SERVICE_REQUIREMENTS,
             *config.config.BEIDOU3_SERVICE_REQUIREMENTS, *config.config.COMMISSION_DATES, *config.config.INACTIVE_SATELLITES]

    assert [name for name in typed if name not in tracked] == []
