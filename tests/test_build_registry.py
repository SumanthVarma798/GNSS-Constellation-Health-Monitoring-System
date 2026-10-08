"""The registry tables: built correctly from a sample, and sound as committed."""
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_registry import build_tables
from evidence.igs_metadata import sinex_time
from evidence.registry_tables import SATELLITE_COLUMNS, SATELLITES, SIGNAL_ID_COLUMNS, SIGNAL_IDS, read_table
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
    satellites, signal_ids = read_table(SATELLITES), read_table(SIGNAL_IDS)

    assert list(satellites[0]) == SATELLITE_COLUMNS and list(signal_ids[0]) == SIGNAL_ID_COLUMNS
    assert [row["svn"] for row in satellites] == sorted({row["svn"] for row in satellites})  # sorted, no repeats
    assert {row["svn"] for row in signal_ids} <= {row["svn"] for row in satellites}
    # A signal ID belongs to one satellite at a time, and a satellite has one at a time.
    held_now = [row for row in signal_ids if not row["valid_to"]]
    assert max(Counter(row["signal_id"] for row in held_now).values()) == 1
    assert max(Counter(row["svn"] for row in held_now).values()) == 1


def test_every_dashboard_satellite_is_in_the_registry():
    from config.config import BEIDOU3_SATS, NAVIK_SATS, QZSS_SATS

    known = {int(row["catalogue_no"]) for row in read_table(SATELLITES)}
    tracked = {**NAVIK_SATS, **QZSS_SATS, **BEIDOU3_SATS}
    assert {name for name, catalogue_no in tracked.items() if catalogue_no not in known} == set()
