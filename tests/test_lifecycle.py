"""Lifecycle timelines (evidence/lifecycle.py, ui/components/lifecycle.*): the hand-kept table, the checklist, the page."""
import json
from datetime import datetime, timezone

from evidence.library_settings import (EVIDENCE_WORDS, FAILED, LIFECYCLE_EVENTS_COLUMNS, LIFECYCLE_EVENTS_FILE,
                                       LIFECYCLE_SERIES, LIFECYCLE_STEPS, NOTE_STEP, WHEN_WORDS)
from evidence.lifecycle import AHEAD, DONE, FAILED_STATE, IMPLIED, MISSED, checklist, life_used, timelines
from evidence.registry_tables import read_table
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
