"""The master map: each answer built from small hand-made rows, and the facts it must
reproduce from the committed tables and the bundled orbit data."""
import json
from pathlib import Path

import pytest

from evidence.master_map import (agreement, display_name, holders_of, identifiers, orbit_feed_checked, orbit_feed_names,
                                 signal_ids_of, summary)
from evidence.registry_tables import read_table
from evidence.settings import (MAP_ACCENT, MAP_IDLE, MAP_OK, MAP_WARN, NOT_RECORDED, REGISTRY_CATALOGUE_FILE,
                               REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_SATELLITES_FILE,
                               REGISTRY_SIGNAL_IDS_FILE)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def satellite(svn, **given):
    row = {"svn": svn, "constellation": "BeiDou", "block": "", "cospar_id": "2018-085A", "catalogue_no": "43683",
           "signal_id_now": "C04", "plane": "", "slot": "", "note": "Launched 2018-11-01; BEIDOU 3G1"}
    return {**row, **given}


def entry(svn, **given):
    row = {"svn": svn, "cospar_id": "2018-085A", "name": "Beidou-3 G1Q", "owner": "CNSA", "state": "CN",
           "status": "O", "orbit_class": "GEO/S", "last_known_active": "2023 Feb", "operations_ended": "*",
           "mission_result": "S"}
    return {**row, **given}


def blank_entry(svn):
    return {key: "" for key in entry(svn)} | {"svn": svn}


def period(svn, signal_id, start, end="", note=""):
    return {"svn": svn, "signal_id": signal_id, "valid_from": f"{start}T00:00:00Z",
            "valid_to": f"{end}T00:00:00Z" if end else "", "note": note}


def tracked(svn, name):
    return {"svn": svn, "dashboard_name": name}


# Three signal IDs in turn, the last still held: the shape of the real C217.
HISTORY = [period("X1", "C59", "2018-11-01", "2026-03-31"), period("X1", "C62", "2026-03-31", "2026-04-21"),
           period("X1", "C04", "2026-04-21")]


def feed_line(feed_name, history=HISTORY, **given):
    """The orbit feed line for one hand-made spacecraft with the given feed name."""
    lines = identifiers("X1", [satellite("X1", **given)], [entry("X1")], [], history, {43683: feed_name})
    return next(line for line in lines if line["scheme"].startswith("Orbit feed"))


# --- display_name ---

@pytest.mark.parametrize("tracked_rows, catalogue_rows, note, expected", [
    ([tracked("X1", "Dashboard X")], [entry("X1")], "Launched 2018; Note Name", "Dashboard X"),
    ([], [entry("X1")], "Launched 2018; Note Name", "Beidou-3 G1Q"),
    ([], [blank_entry("X1")], "Launched 2018; Note Name", "Note Name"),
    ([], [], "Launched 2025-01-29; NVS-02; GTO", "NVS-02"),  # the name follows the first semicolon, not the last
    ([], [], "Launched 2018", "X1"),
    ([], [], "Launched 2018; ", "X1"),
])
def test_display_name_prefers_dashboard_then_catalogue_then_note_then_svn(tracked_rows, catalogue_rows, note, expected):
    assert display_name("X1", [satellite("X1", note=note)], catalogue_rows, tracked_rows) == expected


def test_display_name_of_an_unknown_svn_is_the_svn():
    assert display_name("Z9", [], [], []) == "Z9"


# --- identifiers ---

def lines_of(**given):
    sat = satellite("X1", **given.pop("satellite", {}))
    return identifiers("X1", [sat], given.get("catalogue", [entry("X1")]), given.get("tracked", []),
                       given.get("signal_ids", HISTORY), given.get("feed_names"), given.get("feed_checked"))


def test_identifiers_come_in_the_stated_order_with_plain_scheme_names():
    lines = lines_of(tracked=[tracked("X1", "Dash")], feed_names={43683: "BEIDOU-3 G1 (C04)"})
    assert [line["scheme"] for line in lines] == [
        "US catalogue number (NORAD)", "Launch designator (COSPAR)", "Catalogue of space objects (GCAT)",
        "Signal ID today (PRN)", "Orbit feed name (CelesTrak)", "Dashboard name"]
    assert [line["value"] for line in lines][:2] == ["43683", "2018-085A"]
    assert lines[-1] == {"scheme": "Dashboard name", "value": "Dash", "status": MAP_ACCENT, "remark": "",
                         "issuer": "this project's registry", "checked": NOT_RECORDED}


def test_each_identifier_says_who_issued_it_and_only_the_orbit_feed_has_a_checked_day():
    lines = lines_of(tracked=[tracked("X1", "Dash")], feed_names={43683: "BEIDOU-3 G1 (C04)"},
                     feed_checked={43683: "2026-10-04"})
    assert [(line["issuer"], line["checked"]) for line in lines] == [
        ("the US Space Force space catalogue, via Space-Track", NOT_RECORDED), ("COSPAR", NOT_RECORDED),
        ("GCAT, Jonathan McDowell", NOT_RECORDED), ("China Satellite Navigation Office", NOT_RECORDED),
        ("CelesTrak", "2026-10-04"), ("this project's registry", NOT_RECORDED)]


@pytest.mark.parametrize("constellation, issuer", [("NavIC", "ISRO"), ("QZSS", "Cabinet Office of Japan"),
                                                   ("Atlantis", NOT_RECORDED)])
def test_a_signal_id_is_issued_by_its_systems_operator(constellation, issuer):
    line = lines_of(satellite={"constellation": constellation})[3]
    assert line["scheme"].startswith("Signal ID") and line["issuer"] == issuer


def test_an_orbit_feed_line_without_a_fetch_day_says_not_recorded():
    line = lines_of(feed_names={43683: "BEIDOU-3 G1 (C04)"})[4]
    assert line["scheme"].startswith("Orbit feed") and line["checked"] == NOT_RECORDED


def test_catalogue_line_agrees_when_the_launch_designators_match():
    line = lines_of()[2]
    assert (line["value"], line["status"], line["remark"]) == ("Beidou-3 G1Q", MAP_OK, "agrees")


def test_catalogue_line_warns_when_the_launch_designators_differ():
    line = lines_of(catalogue=[entry("X1", cospar_id="2018-085B")])[2]
    assert (line["status"], line["remark"]) == (MAP_WARN, "launch designator differs")


@pytest.mark.parametrize("catalogue_rows", [[blank_entry("X1")], []])
def test_catalogue_line_is_idle_when_the_catalogue_does_not_list_it_yet(catalogue_rows):
    line = lines_of(catalogue=catalogue_rows)[2]
    assert (line["value"], line["status"], line["remark"]) == ("none", MAP_IDLE, "not in the catalogue yet")


def test_signal_id_line_says_since_when():
    line = lines_of()[3]
    assert (line["value"], line["status"], line["remark"]) == ("C04", MAP_OK, "since 2026-04-21")


def test_a_spacecraft_with_no_signal_id_shows_none():
    ended = [period("X1", "C59", "2018-11-01", "2026-03-31")]
    line = lines_of(satellite={"signal_id_now": ""}, signal_ids=ended)[3]
    assert (line["value"], line["status"]) == ("none", MAP_IDLE)


def test_a_spacecraft_with_no_signal_id_history_at_all_shows_none():
    line = lines_of(satellite={"signal_id_now": ""}, signal_ids=[])[3]
    assert (line["value"], line["status"]) == ("none", MAP_IDLE)


def test_identifiers_skip_empty_values_but_keep_the_idle_ones():
    lines = lines_of(satellite={"catalogue_no": "", "cospar_id": ""}, catalogue=[blank_entry("X1")])
    assert [line["scheme"] for line in lines] == ["Catalogue of space objects (GCAT)", "Signal ID today (PRN)"]


def test_no_orbit_feed_line_without_feed_names_or_without_this_catalogue_number():
    assert all(not line["scheme"].startswith("Orbit feed") for line in lines_of())
    assert all(not line["scheme"].startswith("Orbit feed") for line in lines_of(feed_names={11111: "OTHER (C01)"}))


@pytest.mark.parametrize("feed_name, status, remark", [
    ("BEIDOU-3 G1 (C04)", MAP_OK, "current"),
    ("BEIDOU-3 G1 (C62)", MAP_WARN, "one signal ID out of date"),
    ("BEIDOU-3 G1 (C59)", MAP_WARN, "two signal IDs out of date"),
    ("BEIDOU-3 G1 (C99)", MAP_WARN, "the signal ID in the name is not in this spacecraft's history"),
    ("BEIDOU-3 G1", MAP_IDLE, "the name carries no signal ID to compare"),
    ("BEIDOU-3 G1 (C59) extra", MAP_IDLE, "the name carries no signal ID to compare"),
])
def test_orbit_feed_line_is_judged_by_the_signal_id_in_brackets(feed_name, status, remark):
    line = feed_line(feed_name)
    assert (line["value"], line["status"], line["remark"]) == (feed_name, status, remark)


def test_orbit_feed_name_with_a_signal_id_that_has_since_ended_is_one_change_out_of_date():
    ended = HISTORY[:1]
    assert feed_line("X (C59)", history=ended, signal_id_now="")["remark"] == "one signal ID out of date"


def test_orbit_feed_counts_from_the_latest_time_a_signal_id_was_held():
    returned = [period("X1", "C19", "2017-01-01", "2018-01-01"), period("X1", "C47", "2018-01-01", "2018-06-01"),
                period("X1", "C19", "2018-06-01")]
    assert feed_line("X (C19)", history=returned, signal_id_now="C19")["remark"] == "current"
    assert feed_line("X (C47)", history=returned, signal_id_now="C19")["remark"] == "one signal ID out of date"


def test_unknown_svn_has_no_identifiers():
    assert identifiers("Z9", [satellite("X1")], [], [], []) == []


# --- signal_ids_of and holders_of ---

def test_signal_ids_of_gives_periods_oldest_first_with_dates_only():
    shuffled = [HISTORY[2], period("Y1", "C01", "2000-01-01"), HISTORY[0], HISTORY[1]]
    assert signal_ids_of("X1", shuffled) == [
        {"label": "C59", "start": "2018-11-01", "end": "2026-03-31", "current": False},
        {"label": "C62", "start": "2026-03-31", "end": "2026-04-21", "current": False},
        {"label": "C04", "start": "2026-04-21", "end": "", "current": True}]


def test_signal_ids_of_an_unknown_spacecraft_is_empty():
    assert signal_ids_of("Z9", HISTORY) == []


def test_holders_of_a_signal_id_that_returned_to_an_earlier_holder_lists_each_stretch():
    rows = [period("A", "C19", "2018-11-15"), period("B", "C19", "2018-06-14", "2018-11-11"),
            period("A", "C19", "2017-11-05", "2018-06-13"), period("A", "C47", "2018-07-19", "2018-11-15")]
    held = holders_of("C19", rows, [satellite("A"), satellite("B")], [entry("A", name="Alpha")],
                      [tracked("B", "Bravo")])
    assert [(h["label"], h["start"], h["end"], h["current"]) for h in held] == [
        ("A, Alpha", "2017-11-05", "2018-06-13", False), ("B, Bravo", "2018-06-14", "2018-11-11", False),
        ("A, Alpha", "2018-11-15", "", True)]
    assert [h["svn"] for h in held] == ["A", "B", "A"]


def test_holders_of_a_signal_id_nobody_held_is_empty():
    assert holders_of("C99", HISTORY, [], [], []) == []


# --- agreement ---

def line_for(sat, catalogue_row):
    return agreement([sat], [catalogue_row] if catalogue_row else [])[0]


def test_both_sources_say_operating():
    line = line_for(satellite("X1"), entry("X1"))
    assert (line["identity"], line["service"], line["remark"]) == ("two sources agree", "agree: operating", "")


def test_both_sources_say_not_in_service():
    line = line_for(satellite("X1", signal_id_now=""), entry("X1", operations_ended="2020 Mar 31"))
    assert line["service"] == "agree: not in service"


def test_a_failed_mission_with_no_signal_id_also_agrees_it_is_not_in_service():
    line = line_for(satellite("X1", signal_id_now=""), entry("X1", mission_result="F"))
    assert line["service"] == "agree: not in service"


def test_igs_in_service_but_catalogue_gives_an_end_date():
    line = line_for(satellite("X1"), entry("X1", operations_ended="2025 Jul 10"))
    assert (line["service"], line["remark"]) == ("disagree", "the catalogue says regular operations ended 2025 Jul 10")


def test_igs_in_service_but_catalogue_gives_no_end_date():
    line = line_for(satellite("X1"), entry("X1", operations_ended=""))
    assert line["remark"] == "the catalogue says regular operations ended at a date it does not give"


def test_igs_in_service_but_catalogue_records_a_failed_mission():
    line = line_for(satellite("X1"), entry("X1", mission_result="F", operations_ended="2025 Feb?"))
    assert (line["service"], line["remark"]) == ("disagree", "the catalogue records the mission as failed")


def test_igs_gives_no_signal_id_but_catalogue_believes_it_is_operating():
    line = line_for(satellite("X1", signal_id_now=""), entry("X1"))
    assert (line["service"], line["remark"]) == ("disagree", "the catalogue believes it is still operating")


def test_launch_designators_that_differ_are_reported_with_both():
    line = line_for(satellite("X1"), entry("X1", cospar_id="2018-085B"))
    assert line["identity"] == "sources differ"
    assert line["remark"] == "the IGS file says 2018-085A, the catalogue says 2018-085B"


@pytest.mark.parametrize("catalogue_row", [blank_entry("X1"), None])
def test_a_spacecraft_the_catalogue_does_not_list_yet_has_one_source_only(catalogue_row):
    line = line_for(satellite("X1"), catalogue_row)
    assert (line["identity"], line["service"], line["remark"]) == (
        "one source only", "not in the catalogue yet", "not in the catalogue yet")


def test_agreement_keeps_registry_order_and_names_the_constellation():
    lines = agreement([satellite("B2", constellation="GPS"), satellite("A1")], [entry("A1"), entry("B2")])
    assert [(line["svn"], line["constellation"]) for line in lines] == [("B2", "GPS"), ("A1", "BeiDou")]


# --- summary ---

def test_summary_counts_systems_confirmed_and_reused_signal_ids():
    sats = [satellite("A", constellation="GPS"), satellite("B"), satellite("C"), satellite("D")]
    cat = [entry("A"), entry("B"), entry("C", cospar_id="other"), blank_entry("D")]
    rows = [period("A", "G01", "2000-01-01", "2010-01-01"), period("B", "G01", "2010-01-01"),
            period("C", "C02", "2012-01-01"), period("A", "G03", "2011-01-01")]
    assert summary(sats, cat, rows) == {"spacecraft": 4, "systems": 2, "confirmed": 2, "signal_ids": 3,
                                        "signal_ids_reused": 1}


# --- orbit_feed_names ---

ELEMENTS = ("{name}\n1 {number:05d}U 18085A   26276.67445900 -.00000119  00000+0  00000+0 0  9994\n"
            "2 {number:05d}   2.6618  94.2962 0005125  28.3655 292.5952  1.00270736 29149\n")


def write_feed(folder, file_name, text, **more):
    (folder / file_name).write_text(json.dumps({"tle_data": text, **more}), encoding="utf-8")


def test_orbit_feed_names_reads_every_feed_file_and_keys_by_catalogue_number(tmp_path):
    write_feed(tmp_path, "a_tles.json", ELEMENTS.format(name="ONE (C01)", number=43683) +
               ELEMENTS.format(name="TWO", number=7))
    write_feed(tmp_path, "b_tles.json", ELEMENTS.format(name="THREE (C03)", number=62850))
    write_feed(tmp_path, "c_gp_history.json", ELEMENTS.format(name="IGNORED", number=1))
    assert orbit_feed_names(tmp_path) == {43683: "ONE (C01)", 7: "TWO", 62850: "THREE (C03)"}


def test_orbit_feed_names_skips_files_that_cannot_be_read(tmp_path):
    write_feed(tmp_path, "good_tles.json", ELEMENTS.format(name="GOOD", number=5))
    (tmp_path / "broken_tles.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "empty_tles.json").write_text("{}", encoding="utf-8")
    (tmp_path / "wrong_tles.json").write_text('{"tle_data": 5}', encoding="utf-8")
    (tmp_path / "list_tles.json").write_text("[]", encoding="utf-8")
    assert orbit_feed_names(tmp_path) == {5: "GOOD"}


def test_orbit_feed_names_skips_a_malformed_set_but_keeps_the_rest(tmp_path):
    write_feed(tmp_path, "x_tles.json", "NO NUMBER\nnot a line one\nnot a line two\n" + ELEMENTS.format(name="OK", number=9))
    assert orbit_feed_names(tmp_path) == {9: "OK"}


def test_orbit_feed_names_of_a_missing_folder_is_empty(tmp_path):
    assert orbit_feed_names(tmp_path / "nowhere") == {}


def test_orbit_feed_checked_is_each_files_own_fetch_day(tmp_path):
    write_feed(tmp_path, "a_tles.json", ELEMENTS.format(name="ONE", number=1) + ELEMENTS.format(name="TWO", number=2),
               timestamp="2026-10-04T04:19:42.382938+00:00")
    write_feed(tmp_path, "b_tles.json", ELEMENTS.format(name="THREE", number=3), timestamp="2026-09-30T23:00:00Z")
    write_feed(tmp_path, "c_tles.json", ELEMENTS.format(name="NO DAY", number=4))
    write_feed(tmp_path, "d_tles.json", ELEMENTS.format(name="NOT A DAY", number=5), timestamp="Unknown")
    assert orbit_feed_checked(tmp_path) == {1: "2026-10-04", 2: "2026-10-04", 3: "2026-09-30"}


# --- facts from the committed tables and bundled data (checked 12 Oct 2026) ---

@pytest.fixture(scope="module")
def real():
    tables = {"satellites": read_table(REGISTRY_SATELLITES_FILE), "signal_ids": read_table(REGISTRY_SIGNAL_IDS_FILE),
              "catalogue": read_table(REGISTRY_CATALOGUE_FILE), "tracked": read_table(REGISTRY_DASHBOARD_SATELLITES_FILE)}
    tables["feeds"] = orbit_feed_names(DATA_DIR)
    tables["checked"] = orbit_feed_checked(DATA_DIR)
    return tables


def test_real_orbit_feed_days_are_the_bundled_files_fetch_days(real):
    assert set(real["checked"]) == set(real["feeds"])
    assert set(real["checked"].values()) == {"2026-10-04"}


def test_real_summary(real):
    assert summary(real["satellites"], real["catalogue"], real["signal_ids"]) == {
        "spacecraft": 294, "systems": 6, "confirmed": 292, "signal_ids": 170, "signal_ids_reused": 90}


def test_real_signal_ids_of_c217(real):
    assert [(p["label"], p["start"], p["end"], p["current"]) for p in signal_ids_of("C217", real["signal_ids"])] == [
        ("C59", "2018-11-01", "2026-03-31", False), ("C62", "2026-03-31", "2026-04-21", False),
        ("C04", "2026-04-21", "", True)]


def test_real_holders_of_c01(real):
    held = holders_of("C01", real["signal_ids"], real["satellites"], real["catalogue"], real["tracked"])
    assert [(h["svn"], h["start"], h["end"], h["current"]) for h in held] == [
        ("C003", "2010-01-16", "2020-03-31", False), ("C020", "2020-03-31", "2026-04-20", False),
        ("C231", "2026-04-20", "", True)]


def test_real_c19_went_back_to_its_first_holder(real):
    held = holders_of("C19", real["signal_ids"], real["satellites"], real["catalogue"], real["tracked"])
    assert [h["svn"] for h in held] == ["C201", "C102", "C201"]


def test_real_c217_orbit_feed_name_is_two_signal_ids_out_of_date(real):
    lines = identifiers("C217", real["satellites"], real["catalogue"], real["tracked"], real["signal_ids"], real["feeds"])
    feed = next(line for line in lines if line["scheme"] == "Orbit feed name (CelesTrak)")
    assert (feed["value"], feed["status"], feed["remark"]) == ("BEIDOU-3 G1 (C59)", MAP_WARN,
                                                               "two signal IDs out of date")


def test_real_agreement_for_the_three_spacecraft_the_brief_names(real):
    found = {line["svn"]: line for line in agreement(real["satellites"], real["catalogue"])}
    assert found["I004"]["service"] == "disagree"
    assert found["I011"]["service"] == "disagree"
    assert (found["J008"]["identity"], found["J008"]["service"]) == ("one source only", "not in the catalogue yet")


def test_real_text_has_no_dash_characters_or_emoji(real):
    shown = []
    for sat in real["satellites"]:
        shown += [v for line in identifiers(sat["svn"], real["satellites"], real["catalogue"], real["tracked"],
                                            real["signal_ids"], real["feeds"]) for k, v in line.items()
                  if k in ("scheme", "remark")]
    shown += [line["remark"] for line in agreement(real["satellites"], real["catalogue"])]
    assert not [text for text in shown if "–" in text or "—" in text or not text.isascii()]
