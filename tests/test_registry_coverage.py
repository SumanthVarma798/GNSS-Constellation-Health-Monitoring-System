"""Every satellite broadcasting today is on the dashboard or left out on purpose, with why and a source.

The BeiDou MEO satellites were missing for weeks and only a reviewer's question found it. This turns that kind of
hole into a failing test: a new signal ID in the IGS file must be tracked or explained before the registry
proposal can merge.
"""
import pytest

from config.config import MEO_SYSTEMS
from evidence.registry_tables import constellation_names, dashboard_satellites, left_out, left_out_notice, read_table
from evidence.settings import (REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_LEFT_OUT_FILE, REGISTRY_SATELLITES_FILE,
                               REGISTRY_SIGHTINGS_FILE)

PAGES = ("NavIC", "QZSS", "BeiDou", *MEO_SYSTEMS)


@pytest.mark.coverage_gate   # the registry job skips this to open its proposal; the proposal's own Tests run keeps it
def test_every_satellite_with_a_signal_id_today_is_tracked_or_left_out_with_a_reason():
    broadcasting = {row["svn"] for row in read_table(REGISTRY_SATELLITES_FILE) if row["signal_id_now"]}
    tracked = {row["svn"] for row in read_table(REGISTRY_DASHBOARD_SATELLITES_FILE)}
    explained = {row["svn"] for row in read_table(REGISTRY_LEFT_OUT_FILE)}

    assert broadcasting - tracked - explained == set()
    assert tracked & explained == set()                 # never both
    assert explained <= broadcasting                    # a satellite that stopped needs no reason to be left out


def test_each_left_out_row_has_a_reason_and_a_source_link():
    for row in read_table(REGISTRY_LEFT_OUT_FILE):
        assert row["name"] and row["reason"] and "https://" in row["source"], row["svn"]


def test_every_tracked_and_left_out_satellite_belongs_to_exactly_one_page():
    names_on_pages = [name for page in PAGES for name in dashboard_satellites(page)]
    signal_ids = {row["svn"] for row in read_table(REGISTRY_SATELLITES_FILE) + read_table(REGISTRY_SIGHTINGS_FILE)}
    tracked_in_registry = [row for row in read_table(REGISTRY_DASHBOARD_SATELLITES_FILE) if row["svn"] in signal_ids]
    assert len(names_on_pages) == len(set(names_on_pages)) == len(tracked_in_registry)

    shown = [name for page in PAGES for name, _, _ in left_out(page)]
    assert sorted(shown) == sorted(row["name"] for row in read_table(REGISTRY_LEFT_OUT_FILE))
    assert set(constellation_names().values()) >= {"NavIC", "QZSS", "BeiDou"}


def test_the_pages_say_who_is_left_out_and_why():
    assert "IRNSS-1A: all three of its atomic clocks failed" in left_out_notice("NavIC")
    assert "NVS-02" in left_out_notice("NavIC")
    assert "QZS-1 (Michibiki-1)" in left_out_notice("QZSS")
    assert left_out_notice("BeiDou-3") == "" and left_out_notice("GPS") == ""


def test_every_tracked_regional_satellite_with_a_slot_has_its_targets():
    """A satellite added to the tracked list but not to the targets is scored with no longitude or inclination target
    (QZS-7 and the three BeiDou IGSO satellites were, for a day). One the registry gives no slot for yet (NVS-03,
    still a sighting) cannot have a target and is let through."""
    from config.config import (BEIDOU3_SATS, BEIDOU3_SERVICE_REQUIREMENTS, NAVIK_SATS, NAVIK_SERVICE_REQUIREMENTS,
                               QZSS_SATS, QZSS_SERVICE_REQUIREMENTS)
    from evidence.registry_tables import dashboard_registry_rows

    for page, sats, targets in (("NavIC", NAVIK_SATS, NAVIK_SERVICE_REQUIREMENTS), ("QZSS", QZSS_SATS, QZSS_SERVICE_REQUIREMENTS),
                                ("BeiDou", BEIDOU3_SATS, BEIDOU3_SERVICE_REQUIREMENTS)):
        rows = dashboard_registry_rows(page)
        missing = [name for name in sats if name not in targets and rows.get(name, {}).get("slot")]
        assert missing == [], page
