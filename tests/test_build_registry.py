"""The registry tables: built correctly from a sample, and sound as committed."""
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_registry
from build_registry import build_tables
from evidence.igs_metadata import sinex_time
from evidence.registry_tables import read_table, recently_added, tracked_list_in_step
from evidence.settings import (REGISTRY_SATELLITE_COLUMNS, REGISTRY_SATELLITES_FILE, REGISTRY_SIGHTINGS_FILE,
                               REGISTRY_SIGNAL_ID_COLUMNS,
                               REGISTRY_SIGNAL_IDS_FILE, REGISTRY_DASHBOARD_SATELLITES_FILE,
                               REGISTRY_DASHBOARD_SATELLITE_COLUMNS)
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
# Order matters: it is the order the dashboard shows them in. Satellites added since, through an approved
# proposal, carry an added date and are left out of the comparison.
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
    added = {row["dashboard_name"] for row in read_table(REGISTRY_DASHBOARD_SATELLITES_FILE) if row["added"]}
    assert [item for item in now.items() if item[0] not in added] == list(before.items())


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

    assert config.config.TRACKED_NOT_IN_REGISTRY == {"NavIC": [], "QZSS": [], "BeiDou-3": [], "BeiDou-3 MEO": [],
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
        {"svn": "I002", "dashboard_name": "IRNSS-1B", "added": ""},
        {"svn": "G001", "dashboard_name": "NAVSTAR 1", "added": ""},
        {"svn": "G002", "dashboard_name": "NAVSTAR 2", "added": ""},
        {"svn": "R801", "dashboard_name": "COSMOS 1", "added": "2026-09-05"},
        {"svn": "R802", "dashboard_name": "COSMOS 2", "added": ""},
        {"svn": "E101", "dashboard_name": "GSAT0101", "added": ""},
        {"svn": "C217", "dashboard_name": "BeiDou-3 G1", "added": ""},
    ]

    updated = tracked_list_in_step(satellites, tracked, {"R809": "COSMOS 2620"}, "2026-10-26")

    assert [row["svn"] for row in updated] == ["I002", "G001", "R801", "R802", "R809", "E101", "C217"]
    assert next(row for row in updated if row["svn"] == "R809")["dashboard_name"] == "COSMOS 2620"
    assert next(row for row in updated if row["svn"] == "R809")["added"] == "2026-10-26"
    assert next(row for row in updated if row["svn"] == "I002")["dashboard_name"] == "IRNSS-1B"
    assert next(row for row in updated if row["svn"] == "C217")["dashboard_name"] == "BeiDou-3 G1"
    assert next(row for row in updated if row["svn"] == "R801")["added"] == "2026-09-05"


def test_dashboard_name_for_a_new_satellite_prefers_catalogue_then_note_then_svn():
    from build_registry import dashboard_name_for_new_satellite

    satellite = {"svn": "R809", "note": "Launched 2026-09-17; COSMOS 2???"}
    named = {"OBJECT_NAME": "COSMOS 2620 [GLONASS-K1]"}

    assert dashboard_name_for_new_satellite(satellite, named) == ("COSMOS 2620", "CelesTrak's catalogue")
    assert dashboard_name_for_new_satellite(satellite, None) == ("COSMOS 2???", "the registry note")
    assert dashboard_name_for_new_satellite({"svn": "R809", "note": "Launched 2026-09-17"}, None) == ("R809", "its SVN")


def test_dashboard_updates_falls_back_to_the_note_when_celestrak_cannot_be_read(monkeypatch):
    before = [{"svn": "R801", "dashboard_name": "COSMOS 2471", "added": "2026-08-10"}]
    satellites = [{"svn": "R801", "constellation": "GLONASS", "signal_id_now": "R01", "catalogue_no": "37372",
                   "note": "Launched 2011-02-26; COSMOS 2471"},
                  {"svn": "R809", "constellation": "GLONASS", "signal_id_now": "R10", "catalogue_no": "100744",
                   "note": "Launched 2026-09-17; COSMOS 2???"}]
    monkeypatch.setattr(build_registry.celestrak, "catalogue_entry", lambda *args: (_ for _ in ()).throw(requests.Timeout("down")))

    updated, lines, details, reads = build_registry.dashboard_updates(before, satellites, "2026-10-26")

    assert next(row for row in updated if row["svn"] == "R809")["dashboard_name"] == "COSMOS 2???"
    assert next(row for row in updated if row["svn"] == "R809")["added"] == "2026-10-26"
    assert next(row for row in updated if row["svn"] == "R801")["added"] == "2026-08-10"
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
        before, satellites, "2026-10-26", {"R809": {"checked": True, "catalogue_status": "ok",
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


def test_recently_added_filters_by_date_and_ignores_blank_or_bad_dates(monkeypatch):
    from evidence import registry_tables

    tracked = [
        {"svn": "G001", "dashboard_name": "NAVSTAR 1", "added": "2026-10-26"},
        {"svn": "G002", "dashboard_name": "NAVSTAR 2", "added": "2026-09-26"},
        {"svn": "G003", "dashboard_name": "NAVSTAR 3", "added": "2026-09-25"},
        {"svn": "G004", "dashboard_name": "NAVSTAR 4", "added": ""},
        {"svn": "G005", "dashboard_name": "NAVSTAR 5", "added": "not-a-date"},
        {"svn": "R801", "dashboard_name": "COSMOS 1", "added": "2026-10-26"},
    ]
    monkeypatch.setattr(registry_tables, "constellation_names", lambda: {"G": "GPS", "R": "GLONASS"})
    monkeypatch.setattr(registry_tables, "read_table",
                        lambda name: tracked if name == REGISTRY_DASHBOARD_SATELLITES_FILE else [])

    assert recently_added("GPS", date(2026, 10, 26)) == [("NAVSTAR 1", "2026-10-26"), ("NAVSTAR 2", "2026-09-26")]


def test_main_writes_dashboard_satellite_rows_with_the_added_column(monkeypatch):
    writes = []
    monkeypatch.setattr(build_registry, "read_metadata", lambda _: "IGS META")
    monkeypatch.setattr(build_registry, "build_tables",
                        lambda _: ([["G001", "GPS", "", "", "12345", "G01", "", "", ""]],
                                   [["G001", "G01", "2026-01-01T00:00:00Z", "", ""]]))
    monkeypatch.setattr(build_registry, "read_table",
                        lambda name: [{"svn": "G001", "dashboard_name": "NAVSTAR 1", "added": "2026-08-01"}]
                        if name == REGISTRY_DASHBOARD_SATELLITES_FILE else [])
    monkeypatch.setattr(build_registry, "dashboard_updates",
                        lambda before, satellites, today, reads=None:
                        ([{"svn": "G001", "dashboard_name": "NAVSTAR 1", "added": "2026-08-01"}], [], {}, {}))
    monkeypatch.setattr(build_registry, "write_table",
                        lambda name, columns, rows: writes.append((name, list(columns), [list(row) for row in rows])))
    monkeypatch.setattr(build_registry.celestrak, "_get", lambda **kwargs: [])
    monkeypatch.setattr(sys, "argv", ["build_registry.py", "--metadata", "sample.snx"])

    build_registry.main()

    dashboard_write = next(write for write in writes if write[0] == REGISTRY_DASHBOARD_SATELLITES_FILE)
    assert dashboard_write[1] == REGISTRY_DASHBOARD_SATELLITE_COLUMNS
    assert dashboard_write[2] == [["G001", "NAVSTAR 1", "2026-08-01"]]


NVS_03 = {"NORAD_CAT_ID": 101228, "OBJECT_NAME": "NVS-03 (IRNSS-1L)", "OBJECT_ID": "2026-245A"}
SIGHTED = {"svn": "I-101228", "constellation": "NavIC", "block": "", "cospar_id": "2026-245A", "catalogue_no": "101228",
           "signal_id_now": "", "plane": "", "slot": "", "note": "Launched 2026-10-30; NVS-03 (IRNSS-1L)"}


def test_celestrak_names_the_igs_file_lacks_become_sightings_until_the_igs_file_lists_them(monkeypatch):
    monkeypatch.setattr(build_registry, "celestrak_read", lambda catalogue_no: {
        "checked": True, "catalogue_status": "ok", "catalogue_entry": {"LAUNCH_DATE": "2026-10-30"}})
    igs = [{"svn": "I010", "catalogue_no": "56759"}]
    group = [NVS_03, {"NORAD_CAT_ID": 56759, "OBJECT_NAME": "IRNSS-1J (NVS-01)"},
             {"NORAD_CAT_ID": 99999, "OBJECT_NAME": "GPS BIII-9 (PRN 01)"}]

    rows, reads, listed = build_registry.sightings_update([], igs, group)
    assert SIGHTED in [dict(zip(SIGHTED, row)) for row in rows] and set(reads) == {"I-101228", "G-99999"} and listed == {}
    assert build_registry.sightings_update([SIGHTED], igs, None)[0] == [list(SIGHTED.values())]  # CelesTrak down
    listed_now = build_registry.sightings_update([SIGHTED], igs + [{"svn": "I012", "catalogue_no": "101228"}], group)
    assert listed_now[2] == {"I-101228": "I012"} and set(listed_now[1]) == {"G-99999"}


def test_every_system_has_a_name_that_makes_a_sighting_and_the_augmentation_satellites_have_none():
    named = {"GPS": "GPS BIII-9 (PRN 01)", "GLONASS": "COSMOS 2620 (709K)", "Galileo": "GSAT0234 (GALILEO 34)",
             "BeiDou": "BEIDOU-3 M23 (C45)", "QZSS": "QZS-6 (QZSS/PRN 200)", "NavIC": "NVS-03 (IRNSS-1L)"}
    for system, name in named.items():
        matches = [other for other, pattern in build_registry.SIGHTING_NAMES.items() if re.match(pattern, name)]
        assert matches == [system], (name, matches)
    for name in ("GSAT-10 (GAGAN/PRN 128)", "ASTRA 5B (EGNOS/PRN 123)", "LUCH 5A (SDCM/PRN 140)", "SES-15 (WAAS/PRN 133)"):
        assert not any(re.match(pattern, name) for pattern in build_registry.SIGHTING_NAMES.values()), name


def test_a_sighting_is_tracked_after_its_system_and_moves_to_the_igs_svn_once_listed():
    tracked = [{"svn": "I010", "dashboard_name": "NVS-01", "added": ""},
               {"svn": "J003", "dashboard_name": "QZS-2", "added": ""}]
    rows = build_registry.dashboard_with_sightings(tracked, [SIGHTED], {}, "2026-11-05")
    assert [(row["svn"], row["dashboard_name"], row["added"]) for row in rows] == [
        ("I010", "NVS-01", ""), ("I-101228", "NVS-03", "2026-11-05"), ("J003", "QZS-2", "")]
    moved = build_registry.dashboard_with_sightings(rows, [], {"I-101228": "I012"}, "2026-12-01")
    assert [row["svn"] for row in moved] == ["I010", "I012", "J003"] and moved[1]["added"] == "2026-11-05"


def test_a_new_sighting_is_a_new_satellite_finding_with_celestrak_as_its_source():
    from evidence.registry_changes import registry_findings
    read = {"checked": True, "catalogue_status": "ok", "orbit_status": "none",
            "catalogue_entry": {"OBJECT_NAME": "NVS-03 (IRNSS-1L)", "OBJECT_ID": "2026-245A", "OBJECT_TYPE": "PAY",
                                "LAUNCH_DATE": "2026-10-30"}}
    [finding] = registry_findings([], [SIGHTED], [], [], {}, {}, {}, {"I-101228": read}, date(2026, 11, 5))
    assert finding["category"] == "New satellite" and "launched 30 Oct 2026" in finding["statement"]
    assert [row["source"] for row in finding["sources"]] == ["CelesTrak satellite catalogue"]


def test_committed_sightings_use_stand_in_svns_for_satellites_the_igs_file_lacks():
    sightings, satellites = read_table(REGISTRY_SIGHTINGS_FILE), read_table(REGISTRY_SATELLITES_FILE)
    with open(f"registry/{REGISTRY_SIGHTINGS_FILE}", encoding="utf-8") as handle:
        assert handle.readline().strip().split(",") == REGISTRY_SATELLITE_COLUMNS
    letters = {name: letter for letter, name in build_registry.constellation_names().items()}
    for row in sightings:
        assert row["svn"] == f"{letters[row['constellation']]}-{row['catalogue_no']}", row
    assert not {row["catalogue_no"] for row in sightings} & {row["catalogue_no"] for row in satellites}
