"""The registry tables: built correctly from a sample, and sound as committed."""
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_registry import build_tables
from evidence.igs_metadata import sinex_time
from evidence.registry_tables import read_table
from evidence.settings import (REGISTRY_SATELLITE_COLUMNS, REGISTRY_SATELLITES_FILE, REGISTRY_SIGNAL_ID_COLUMNS,
                               REGISTRY_SIGNAL_IDS_FILE)
from test_check_satellite_ids import SAMPLE


def test_tables_from_sample():
    satellites, signal_ids = build_tables(SAMPLE)

    assert satellites == [
        ["C006", "BeiDou", "BDS-2G", "2010-057A", "37210", "", "", "", "Launched 2010-10-31; BEIDOU 6"],
        ["C217", "BeiDou", "BDS-3G", "2018-085A", "43683", "C04", "G", "140E", "Launched 2018-11-01; BEIDOU 3G1"],
    ]
    # Same-day handover keeps its time of day, and the notice number survives.
    assert signal_ids == [
        ["C006", "C04", "2010-10-31T00:00:00Z", "2026-04-21T08:00:00Z", "NABU 20260022"],
        ["C217", "C59", "2018-11-01T00:00:00Z", "2026-03-31T13:02:00Z", "NABU 20260005 + obs. data"],
        ["C217", "C62", "2026-03-31T13:20:00Z", "2026-04-21T08:00:00Z", "[PR04], NABU 20260022"],
        ["C217", "C04", "2026-04-21T12:00:00Z", "", "[PR04], NABU 20260022"],
    ]


def test_an_unknown_system_stops_the_build():
    with pytest.raises(ValueError, match="system letter 'S'"):
        build_tables(SAMPLE.replace(" C006 2010-057A", " S006 2010-057A"))


def test_sinex_time():
    assert sinex_time("2024:366:86399") == "2024-12-31T23:59:59Z"
    assert sinex_time("0000:000:00000") == ""


def test_committed_tables_are_sound():
    satellites, signal_ids = read_table(REGISTRY_SATELLITES_FILE), read_table(REGISTRY_SIGNAL_IDS_FILE)

    assert list(satellites[0]) == REGISTRY_SATELLITE_COLUMNS and list(signal_ids[0]) == REGISTRY_SIGNAL_ID_COLUMNS
    assert [row["svn"] for row in satellites] == sorted({row["svn"] for row in satellites})  # sorted, no repeats
    assert {row["svn"] for row in signal_ids} <= {row["svn"] for row in satellites}
    # A signal ID belongs to one satellite at a time, and a satellite has one at a time.
    held_now = [row for row in signal_ids if not row["valid_to"]]
    assert max(Counter(row["signal_id"] for row in held_now).values()) == 1
    assert max(Counter(row["svn"] for row in held_now).values()) == 1


# What config/config.py held, typed by hand, before the dashboard read the registry.
# Order matters: it is the order the dashboard shows them in.
DASHBOARD_SATELLITES_BEFORE_THE_SWITCH = {
    "NAVIK_SATS": {"IRNSS-1B": 39635, "IRNSS-1C": 40269, "IRNSS-1D": 40547, "IRNSS-1E": 41241,
                   "IRNSS-1F": 41384, "IRNSS-1G": 41469, "IRNSS-1I": 43286, "NVS-01": 56759},
    "QZSS_SATS": {"QZS-1R (Michibiki-1R)": 49336, "QZS-2 (Michibiki-2)": 42738, "QZS-3 (Michibiki-3)": 42917,
                  "QZS-4 (Michibiki-4)": 42965, "QZS-6 (Michibiki-6)": 62876},
    "BEIDOU3_SATS": {"BeiDou-3 G1": 43683, "BeiDou-3 G2": 45344, "BeiDou-3 G3": 45807, "BeiDou-3 G4": 56564,
                     "BeiDou-3 I1": 44204, "BeiDou-3 I2": 44337, "BeiDou-3 I3": 44709},
}


@pytest.mark.parametrize("list_name", DASHBOARD_SATELLITES_BEFORE_THE_SWITCH)
def test_dashboard_lists_did_not_change(list_name):
    import config.config

    now, before = getattr(config.config, list_name), DASHBOARD_SATELLITES_BEFORE_THE_SWITCH[list_name]
    assert list(now.items()) == list(before.items())


def test_a_tracked_satellite_missing_from_the_registry_is_left_out_and_named(monkeypatch):
    # The tracked list and the registry are each approved by a person, at different
    # times. While one is behind, the dashboard runs without that satellite and says so.
    from evidence import registry_tables
    from evidence.settings import REGISTRY_DASHBOARD_SATELLITES_FILE

    tracked = [{"svn": "I002", "dashboard_name": "IRNSS-1B"}, {"svn": "I999", "dashboard_name": "NVS-99"}]
    tables = {REGISTRY_DASHBOARD_SATELLITES_FILE: tracked}
    monkeypatch.setattr(registry_tables, "read_table", lambda name: tables.get(name) or read_table(name))

    assert registry_tables.dashboard_satellites("NavIC") == {"IRNSS-1B": 39635}
    assert registry_tables.dashboard_satellites_not_in_registry("NavIC") == ["NVS-99"]
    assert registry_tables.dashboard_satellites_not_in_registry("QZSS") == []


def test_every_tracked_satellite_is_in_the_committed_registry():
    # Strict where a person approves: a proposal that would leave a tracked satellite out fails here.
    import config.config

    assert config.config.TRACKED_NOT_IN_REGISTRY == {"NavIC": [], "QZSS": [], "BeiDou-3": []}
