"""Live pipeline component and wording data."""
import json
from pathlib import Path

from evidence import jobs, pipeline
from evidence import console_settings
from evidence.console_settings import WORKFLOWS_DIR
from evidence.pipeline_words import STAGES
from test_jobs import LOG, NOW, RUNS, WORKFLOWS
from ui.components.live_pipeline import live_pipeline_html, payload

ROOT = Path(__file__).resolve().parent.parent


def _workflow_texts():
    names = ("archive.yml", "registry-update.yml", "tests.yml")
    return {name: (WORKFLOWS_DIR / name).read_text(encoding="utf-8") for name in names}


def _stage_rows():
    return pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [], _workflow_texts(), NOW)


def test_every_stage_key_has_all_three_levels_filled():
    keys = {row["key"] for row in _stage_rows()}
    assert keys == set(STAGES)
    for key, words in STAGES.items():
        assert words["plain_name"] and len(words["what_happens"]) >= 2 and words["why_it_matters"], key
        technical = words["technical"]
        for field in ("commands", "inputs", "outputs", "settings", "limits", "paths"):
            assert technical[field], (key, field)


def test_every_path_named_in_technical_facts_exists():
    for key, words in STAGES.items():
        for path in words["technical"]["paths"]:
            assert (ROOT / path).exists(), (key, path)


def test_component_payload_is_safe_and_page_sets_text_with_textcontent():
    rows = _stage_rows()
    upcoming = pipeline.what_next(rows, NOW, hours=24)
    next_key, next_at = ((upcoming[0]["key"], upcoming[0]["at"]) if upcoming else (None, None))
    data = payload(rows, next_key, next_at, _workflow_texts())
    page = live_pipeline_html(":root{}", "sans-serif", data)

    serialized = page[page.index("const DATA = ") + len("const DATA = "):page.index(";\nconst cards")]
    assert "</script>" not in serialized
    loaded = json.loads(serialized)
    assert loaded["cards"][0]["plain_name"]
    assert "innerHTML" not in page and "textContent" in page


def test_component_uses_plain_headings_and_group_label():
    rows = _stage_rows()
    data = payload(rows, None, None, _workflow_texts())
    page = live_pipeline_html(":root{}", "sans-serif", data)

    for words in ("The pipeline at a glance", "About this step", "Then review and go live", "Technical details"):
        assert words in page
    assert "Level 1 · Pipeline picture" not in page
    assert "Level 2 · Stage details" not in page
    assert "Level 3 · Technical details" not in page


def test_waiting_state_words_are_plain_waiting():
    rows = _stage_rows()
    data = payload(rows, None, None, _workflow_texts())
    waiting = [card for card in data["cards"] if card["state_technical"] == "waiting"]

    assert waiting
    assert all(card["state_plain"] == "waiting" for card in waiting)


def test_settings_show_name_equals_value_and_source_file_from_runtime_module(monkeypatch):
    monkeypatch.setattr(console_settings, "TESTS_WORKFLOW", "tests-from-test.yml")

    rows = _stage_rows()
    data = payload(rows, None, None, _workflow_texts())
    dashboard = next(card for card in data["cards"] if card["key"] == "dashboard")

    assert "TESTS_WORKFLOW = tests-from-test.yml (evidence/console_settings.py)" in dashboard["settings"]


def test_level_2_words_avoid_internal_jargon():
    banned = ("collector", "graded source", "candidate sources", "claim extraction", "evidence trail", "workflow")
    for key, words in STAGES.items():
        text = " ".join(words["what_happens"] + [words["why_it_matters"]]).lower()
        for term in banned:
            assert term not in text, (key, term)
        if "pull request" in text:
            assert "(pull request)" in text, key
