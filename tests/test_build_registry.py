"""The registry tables: built correctly from a sample, and sound as committed."""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_registry import SATELLITE_COLUMNS, SIGNAL_ID_COLUMNS, build_tables, sinex_time
from test_check_satellite_ids import SAMPLE


def read(name):
    with open(ROOT / "registry" / name, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def test_sinex_time():
    assert sinex_time("2024:366:86399") == "2024-12-31T23:59:59Z"
    assert sinex_time("0000:000:00000") == ""


def test_committed_tables_are_sound():
    satellites, signal_ids = read("satellites.csv"), read("signal_ids.csv")

    assert list(satellites[0]) == SATELLITE_COLUMNS and list(signal_ids[0]) == SIGNAL_ID_COLUMNS
    assert [row["svn"] for row in satellites] == sorted({row["svn"] for row in satellites})  # sorted, no repeats
    assert {row["svn"] for row in signal_ids} <= {row["svn"] for row in satellites}
    # A signal ID belongs to one satellite at a time, and a satellite has one at a time.
    held_now = [row for row in signal_ids if not row["valid_to"]]
    assert max(Counter(row["signal_id"] for row in held_now).values()) == 1
    assert max(Counter(row["svn"] for row in held_now).values()) == 1


def test_every_dashboard_satellite_is_in_the_registry():
    from config.config import BEIDOU3_SATS, NAVIK_SATS, QZSS_SATS

    known = {int(row["catalogue_no"]) for row in read("satellites.csv")}
    tracked = {**NAVIK_SATS, **QZSS_SATS, **BEIDOU3_SATS}
    assert {name for name, norad in tracked.items() if norad not in known} == set()
