"""The registry tables: built correctly from a sample, and sound as committed."""
import sys
from collections import Counter
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_registry
from build_registry import build_tables
from evidence.igs_metadata import sinex_time
from evidence.registry_tables import read_table, tracked_list_in_step
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

    assert config.config.TRACKED_NOT_IN_REGISTRY == {"NavIC": [], "QZSS": [], "BeiDou-3": [],
                                                     "GPS": [], "GLONASS": [], "Galileo": []}


def test_tracked_list_in_step_adds_and_drops_satellites_for_the_three_meo_systems():
    satellites = [
        {"svn": "I002", "constellation": "NavIC", "signal_id_now": "I01"},
        {"svn": "G001", "constellation": "GPS", "signal_id_now": "G01"},
        {"svn": "G002", "constellation": "GPS", "signal_id_now": ""},
        {"svn": "R801", "constellation": "GLONASS", "signal_id_now": "R01"},
        {"svn": "R802", "constellation": "GLONASS", "signal_id_now": "R02"},
        {"svn": "R809", "constellation": "GLONASS", "signal_id_now": "R10"},
        {"svn": "E101", "constellation": "Galileo", "signal_id_now": "E01"},
        {"svn": "C217", "constellation": "BeiDou", "signal_id_now": "C04"},
    ]
    tracked = [
        {"svn": "I002", "dashboard_name": "IRNSS-1B"},
        {"svn": "G001", "dashboard_name": "NAVSTAR 1"},
        {"svn": "G002", "dashboard_name": "NAVSTAR 2"},
        {"svn": "R801", "dashboard_name": "COSMOS 1"},
        {"svn": "R802", "dashboard_name": "COSMOS 2"},
        {"svn": "E101", "dashboard_name": "GSAT0101"},
        {"svn": "C217", "dashboard_name": "BeiDou-3 G1"},
    ]

    updated = tracked_list_in_step(satellites, tracked, {"R809": "COSMOS 2620"})

    assert [row["svn"] for row in updated] == ["I002", "G001", "R801", "R802", "R809", "E101", "C217"]
    assert next(row for row in updated if row["svn"] == "R809")["dashboard_name"] == "COSMOS 2620"
    assert next(row for row in updated if row["svn"] == "I002")["dashboard_name"] == "IRNSS-1B"
    assert next(row for row in updated if row["svn"] == "C217")["dashboard_name"] == "BeiDou-3 G1"


def test_dashboard_name_for_a_new_satellite_prefers_catalogue_then_note_then_svn():
    from build_registry import dashboard_name_for_new_satellite

    satellite = {"svn": "R809", "note": "Launched 2026-09-17; COSMOS 2???"}
    named = {"OBJECT_NAME": "COSMOS 2620 [GLONASS-K1]"}

    assert dashboard_name_for_new_satellite(satellite, named) == ("COSMOS 2620", "CelesTrak's catalogue")
    assert dashboard_name_for_new_satellite(satellite, None) == ("COSMOS 2???", "the registry note")
    assert dashboard_name_for_new_satellite({"svn": "R809", "note": "Launched 2026-09-17"}, None) == ("R809", "its SVN")


def test_dashboard_updates_falls_back_to_the_note_when_celestrak_cannot_be_read(monkeypatch):
    before = [{"svn": "R801", "dashboard_name": "COSMOS 2471"}]
    satellites = [{"svn": "R801", "constellation": "GLONASS", "signal_id_now": "R01", "catalogue_no": "37372",
                   "note": "Launched 2011-02-26; COSMOS 2471"},
                  {"svn": "R809", "constellation": "GLONASS", "signal_id_now": "R10", "catalogue_no": "100744",
                   "note": "Launched 2026-09-17; COSMOS 2???"}]
    monkeypatch.setattr(build_registry.celestrak, "catalogue_entry", lambda *args: (_ for _ in ()).throw(requests.Timeout("down")))

    updated, lines, details, reads = build_registry.dashboard_updates(before, satellites)

    assert next(row for row in updated if row["svn"] == "R809")["dashboard_name"] == "COSMOS 2???"
    assert "CelesTrak could not be read" in lines[0]
    assert details["R809"] == "Approving also adds it to the dashboard as COSMOS 2???."
    assert reads["R809"]["checked"] is True and reads["R809"]["catalogue_status"] == "error"


def test_dashboard_updates_uses_passed_celestrak_reads_without_fetching_again(monkeypatch):
    before = [{"svn": "R801", "dashboard_name": "COSMOS 2471"}]
    satellites = [{"svn": "R801", "constellation": "GLONASS", "signal_id_now": "R01", "catalogue_no": "37372",
                   "note": "Launched 2011-02-26; COSMOS 2471"},
                  {"svn": "R809", "constellation": "GLONASS", "signal_id_now": "R10", "catalogue_no": "100744",
                   "note": "Launched 2026-09-17; COSMOS 2???"}]
    monkeypatch.setattr(build_registry.celestrak, "catalogue_entry",
                        lambda *args: (_ for _ in ()).throw(AssertionError("should not fetch")))

    updated, _, _, reads = build_registry.dashboard_updates(
        before, satellites, {"R809": {"checked": True, "catalogue_status": "ok",
                                      "catalogue_entry": {"OBJECT_NAME": "COSMOS 2620 [GLONASS-K1]"},
                                      "orbit_status": "none", "orbit_row": None}})

    assert next(row for row in updated if row["svn"] == "R809")["dashboard_name"] == "COSMOS 2620"
    assert reads["R809"]["checked"] is True


def test_celestrak_read_handles_no_orbit_record_and_read_failures(monkeypatch):
    monkeypatch.setattr(build_registry.celestrak, "catalogue_entry", lambda norad: {"OBJECT_NAME": f"N{norad}"})
    monkeypatch.setattr(build_registry.celestrak, "_get", lambda **kwargs: [])
    read = build_registry.celestrak_read("100744")

    assert read["catalogue_status"] == "ok" and read["orbit_status"] == "none" and read["orbit_row"] is None

    monkeypatch.setattr(build_registry.celestrak, "catalogue_entry",
                        lambda norad: (_ for _ in ()).throw(requests.Timeout("down")))
    monkeypatch.setattr(build_registry.celestrak, "_get",
                        lambda **kwargs: (_ for _ in ()).throw(requests.Timeout("down")))
    read = build_registry.celestrak_read("100744")

    assert read["catalogue_status"] == "error" and read["orbit_status"] == "error"


def test_finding_news_reads_archive_and_reports_errors(monkeypatch):
    monkeypatch.setattr(build_registry.news, "collected_items", lambda archive: ([{"title": "one"}], []))
    items, words = build_registry.findings_news("archive")
    assert items == [{"title": "one"}] and words == ""

    monkeypatch.setattr(build_registry.news, "collected_items",
                        lambda archive: ([{"title": "one"}], [("feed", "2026-10-20T00:00:00Z", "bad xml")]))
    items, words = build_registry.findings_news("archive")
    assert items == [{"title": "one"}]
    assert words == "News: 1 archived feed copies could not be read, so their items are left out."

    monkeypatch.setattr(build_registry.news, "collected_items",
                        lambda archive: (_ for _ in ()).throw(ValueError("broken feed")))
    items, words = build_registry.findings_news("archive")
    assert items == [] and words == "News could not be read from the archive: broken feed"
