"""Lifecycle timelines (evidence/lifecycle.py, ui/components/lifecycle.*): the hand-kept table, the checklist, the page."""
import json
from datetime import datetime, timezone

from evidence.library_settings import (EVIDENCE_WORDS, FAILED, LIFECYCLE_EVENTS_COLUMNS, LIFECYCLE_EVENTS_FILE,
                                       LIFECYCLE_SERIES, LIFECYCLE_STEPS, NOTE_STEP, WHEN_WORDS)
from evidence.lifecycle import AHEAD, DONE, FAILED_STATE, IMPLIED, MISSED, checklist, life_used, registry_events, timelines
from evidence.registry_tables import read_table
from ui import palette
from ui.components.lifecycle import FIRST_SHOWN, lifecycle_html

ROWS = read_table(LIFECYCLE_EVENTS_FILE)
TODAY = datetime(2026, 11, 5, tzinfo=timezone.utc)
STEPS = LIFECYCLE_STEPS["NVS"]


def _utc(text):
    assert text.endswith("Z"), text
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def test_every_row_is_a_known_step_with_a_public_source():
    with open(f"registry/{LIFECYCLE_EVENTS_FILE}", encoding="utf-8") as handle:
        assert handle.readline().strip().split(",") == LIFECYCLE_EVENTS_COLUMNS
    for row in ROWS:
        where = f"{row['satellite']}: {row['title']}"
        steps = {step for step, _ in LIFECYCLE_STEPS[LIFECYCLE_SERIES[row["satellite"]]]} | {NOTE_STEP}
        assert row["step"] in steps and row["title"] and row["detail"], where
        assert row["evidence"] in EVIDENCE_WORDS and row["result"] in ("", FAILED), where
        assert row["source_name"] and row["source_link"].startswith("https://"), where
        assert bool(row["picture"]) == bool(row["picture_credit"]), where
        if row["at_utc"]:
            assert row["when"] in WHEN_WORDS, where
            if row["from_utc"]:
                assert _utc(row["from_utc"]) < _utc(row["at_utc"]), where
        else:
            assert not row["from_utc"] and not row["when"], where


def test_each_satellite_has_one_dated_launch_and_the_first_shown_are_in_the_table():
    for name in {row["satellite"] for row in ROWS}:
        launches = [row for row in ROWS if row["satellite"] == name and row["step"] == "launch"]
        assert len(launches) == 1 and launches[0]["at_utc"], name
    assert set(FIRST_SHOWN) <= {row["satellite"] for row in ROWS}


def _events(*dated, failed=(), undated=()):
    return ([{"step": s, "at": "2026-01-01T00:00:00Z", "failed": False} for s in dated]
            + [{"step": s, "at": "2026-01-01T00:00:00Z", "failed": True} for s in failed]
            + [{"step": s, "at": "", "failed": False} for s in undated])


def test_a_step_before_a_dated_one_is_done_without_a_date_and_later_ones_are_ahead():
    states = {c["step"]: c["state"] for c in checklist(STEPS, _events("launch", "gso", undated=("slot",)))}
    assert states["built"] == IMPLIED and states["burn"] == IMPLIED and states["gso"] == DONE
    assert states["slot"] == AHEAD and states["disposal"] == AHEAD


def test_a_failed_step_stops_the_list():
    states = [c["state"] for c in checklist(STEPS, _events("launch", "separation", failed=("burn",)))]
    assert states[:4] == [IMPLIED, DONE, DONE, FAILED_STATE] and set(states[4:]) == {MISSED}


def test_life_used_counts_from_service_start_against_the_design_life():
    events = [{"step": "service", "at": "2020-11-05T00:00:00Z"}]
    assert abs(life_used("NVS", events, TODAY) - 6 / 12) < 0.01
    assert life_used("NVS", [{"step": "launch", "at": "2026-01-01T00:00:00Z"}], TODAY) is None
    assert life_used("NVS", [{"step": "service", "at": "2000-01-01T00:00:00Z"}], TODAY) == 1.0


def test_the_table_reads_as_nvs01_in_service_nvs02_stopped_and_nvs03_on_its_way():
    records = {r["name"]: r for r in timelines(ROWS, TODAY)}
    state = lambda name, step: next(c["state"] for c in records[name]["checklist"] if c["step"] == step)
    assert state("NVS-01", "service") == DONE and 0 < records["NVS-01"]["life_used"] < 1
    assert state("NVS-02", "burn") == FAILED_STATE and state("NVS-02", "service") == MISSED
    assert state("NVS-03", "gso") == DONE and state("NVS-03", "slot") == AHEAD
    for record in records.values():
        dated = [e["at"] for e in record["events"] if e["at"]]
        assert dated == sorted(dated)


def test_text_cannot_break_out_of_the_page_and_is_put_in_as_text():
    page = lifecycle_html(ROWS, TODAY)
    data = page[page.index("const DATA = ") + len("const DATA = "):page.index(";\nconst $")]
    assert "</script>" not in data and "<" not in data
    assert {s["name"] for s in json.loads(data)["satellites"]} == {row["satellite"] for row in ROWS}
    assert "innerHTML" not in page and "__" not in page.replace("__proto__", "")
    assert "https://commons.wikimedia.org/wiki/Special:FilePath/" in page


def test_a_step_before_a_failed_one_happened_even_without_a_date():
    states = {c["step"]: c["state"] for c in checklist(STEPS, _events("launch", failed=("burn",), undated=("separation",)))}
    assert states["separation"] == IMPLIED and states["burn"] == FAILED_STATE


def test_today_reaches_the_page_in_whole_seconds_and_the_first_pair_in_order():
    data = json.loads(lifecycle_html(ROWS, datetime(2026, 11, 5, 6, 12, 34, 123456, tzinfo=timezone.utc)).split("const DATA = ", 1)[1].split(";\nconst $", 1)[0])
    assert data["today"] == "2026-11-05T06:12:34Z" and data["first"] == list(FIRST_SHOWN)


def _registry():
    return {name: read_table(file) for name, file in (("satellites", "satellites.csv"), ("signal_ids", "signal_ids.csv"),
                                                      ("catalogue", "catalogue.csv"), ("tracked", "dashboard_satellites.csv"))}


def test_the_registry_gives_launch_signal_ids_and_the_end_of_operations():
    satellite = {"svn": "G999", "note": "Launched 2010-05-28; TEST"}
    periods = [{"signal_id": "G25", "valid_from": "2010-05-28T00:00:00Z", "valid_to": "2015-01-01T06:00:00Z"},
               {"signal_id": "G25", "valid_from": "2015-02-01T00:00:00Z", "valid_to": "2020-06-10T00:00:00Z"}]
    events = registry_events(satellite, periods, {"operations_ended": "2020 Jun", "mission_result": "S"})
    assert [(e["step"], e["title"], e["at"], e["when"]) for e in events] == [
        ("launch", "Launch", "2010-05-28T00:00:00Z", "on"),
        ("service", "Signal ID G25 assigned", "2010-05-28T00:00:00Z", "on"),
        ("note", "Signal ID G25 again", "2015-02-01T00:00:00Z", "on"),
        ("end", "Regular operations ended", "2020-06-01T00:00:00Z", "in"),   # GCAT gave the month only
        ("note", "Signal ID G25 withdrawn", "2020-06-10T00:00:00Z", "on")]
    # No date GCAT is sure of: the withdrawn signal ID is the end. A failure early is a failed end.
    unsure = registry_events(satellite, periods, {"operations_ended": "2025 Feb?", "mission_result": "S"})
    assert [(e["step"], e["title"]) for e in unsure][-1] == ("end", "Signal ID withdrawn")
    failed = registry_events(satellite, [], {"operations_ended": "*", "mission_result": "F"})
    assert failed[-1]["failed"] and failed[-1]["step"] == "end" and not failed[-1]["at"]


def test_every_registry_satellite_has_a_lifecycle_and_hand_rows_keep_their_own_steps():
    registry = _registry()
    records = {r["name"]: r for r in timelines(ROWS, TODAY, registry)}
    assert len(records) == len(registry["satellites"]) + 1   # and NVS-03, which only the hand-kept table has yet
    assert {r["system"] for r in records.values()} == {"GPS", "GLONASS", "Galileo", "BeiDou", "QZSS", "NavIC"}
    assert all(any(e["step"] == "launch" for e in r["events"]) for r in records.values())
    # NVS-02 had a signal ID but never entered service: from the registry that is a note, never its service step.
    nvs02 = records["NVS-02"]
    assert {e["title"]: e["step"] for e in nvs02["events"]}["Signal ID I11 assigned"] == "note"
    assert not any(e["step"] == "service" for e in nvs02["events"])
    # NVS-01's service date is ISRO's, from the table, not the IGS file's signal ID.
    assert [e["at"] for e in records["NVS-01"]["events"] if e["step"] == "service"] == ["2023-07-04T00:00:00Z"]
    assert records["IRNSS-1D"]["checklist"][-1]["state"] == DONE and records["IRNSS-1D"]["service_years"] > 9


def test_the_page_shares_each_text_once_and_keeps_the_first_one():
    data = json.loads(lifecycle_html(ROWS, TODAY, _registry()).split("const DATA = ", 1)[1].split(";\nconst $", 1)[0])
    events = [e for s in data["satellites"] for e in s["events"]]
    assert all(0 <= e["detail"] < len(data["texts"]) and 0 <= e["source"] < len(data["sources"]) for e in events)
    assert any(e["detail"] == 0 for e in events) and any(e["source"] == 0 for e in events)   # index 0 is not "empty"
    assert data["max_compared"] == 5 and len(set(data["colours"])) >= 5 and palette.BAD not in data["colours"]


def test_a_hand_kept_satellite_with_notes_keeps_the_registry_notes_too():
    row = dict.fromkeys(LIFECYCLE_EVENTS_COLUMNS, "")
    rows = [{**row, "satellite": "NVS-02", "step": "launch", "title": "Launch", "at_utc": "2025-01-29T00:53:00Z", "when": "at"},
            {**row, "satellite": "NVS-02", "step": "note", "title": "A note", "at_utc": "2025-03-01T00:00:00Z", "when": "on"}]
    registry = {"satellites": [{"svn": "I011", "constellation": "NavIC", "block": "IRS-2I", "note": "Launched 2025-01-29; NVS-02"}],
                "signal_ids": [{"svn": "I011", "signal_id": "I11", "valid_from": "2025-01-29T00:00:00Z", "valid_to": "2025-06-01T00:00:00Z"},
                               {"svn": "I011", "signal_id": "I12", "valid_from": "2025-07-01T00:00:00Z", "valid_to": ""}],
                "catalogue": [], "tracked": []}
    [record] = [r for r in timelines(rows, TODAY, registry) if r["name"] == "NVS-02"]
    titles = [e["title"] for e in record["events"]]
    assert "A note" in titles and "Signal ID I12" in titles and "Signal ID I11 assigned" in titles
