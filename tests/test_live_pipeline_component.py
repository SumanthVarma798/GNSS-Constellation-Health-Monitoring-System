"""Live pipeline component and wording data."""
import json
from pathlib import Path

from evidence import jobs, pipeline
from evidence import console_settings
from evidence.console_settings import WORKFLOWS_DIR
from evidence.pipeline_words import SETTING_SENTENCES, STAGES
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


def test_flow_repository_nodes_use_short_names_with_full_paths():
    rows = _stage_rows()
    data = payload(rows, None, None, _workflow_texts())
    news = next(card for card in data["cards"] if card["key"] == "archive_news")

    repositories = [node for node in news["flow"]["nodes"] if node["id"].startswith("repo_")]
    assert [node["label"] for node in repositories] == ["project repository", "archive repository"]
    assert repositories[0]["path"] == "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System"
    assert repositories[1]["path"] == "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System-archive"


def test_payload_carries_schedule_marks_for_daily_weekly_and_event_stages():
    rows = _stage_rows()
    upcoming = pipeline.what_next(rows, NOW, hours=24)
    next_key, next_at = ((upcoming[0]["key"], upcoming[0]["at"]) if upcoming else (None, None))
    data = payload(rows, next_key, next_at, _workflow_texts())

    news = next(card for card in data["cards"] if card["key"] == "archive_news")
    assert news["schedule_visual"]["kind"] == "daily"
    assert len(news["schedule_visual"]["marks"]) == 8
    assert [mark["utc"] for mark in news["schedule_visual"]["marks"][:4]] == ["00:50", "03:50", "06:50", "09:50"]
    next_marks = [mark for mark in news["schedule_visual"]["marks"] if mark["is_next"]]
    assert len(next_marks) == 1 and next_marks[0]["utc"] == "15:50"

    registry = next(card for card in data["cards"] if card["key"] == "registry_update")
    assert registry["schedule_visual"]["kind"] == "weekly"
    assert registry["schedule_visual"]["marks"] == [{"weekday": "Sun", "weekday_index": 6, "minute_of_day": 60,
                                                     "utc": "Sun 01:00", "is_next": True}]

    waiting = next(card for card in data["cards"] if card["key"] == "decision_waiting")
    assert waiting["schedule_visual"] == {"kind": "event", "note": "runs when the step before it finishes"}


def test_payload_settings_cards_have_sentences_and_backoff_steps():
    rows = _stage_rows()
    data = payload(rows, None, None, _workflow_texts())
    news = next(card for card in data["cards"] if card["key"] == "archive_news")

    cards = {row["name"]: row for row in news["settings_cards"]}
    assert cards["DOWNLOAD_TRIES"]["value"] == "3"
    assert cards["WAIT_BETWEEN_TRIES_SECONDS"]["value"] == "60 seconds"
    assert cards["REFUSAL_STATUSES"]["value"] == "403, 429"
    assert cards["BACKOFF_FIRST"]["value"] == "1 hour"
    assert cards["BACKOFF_FIRST"]["raw_value"] == "datetime.timedelta(seconds=3600)"
    assert cards["BACKOFF_LONGEST"]["value"] == "7 days"
    assert cards["NEVER_FETCH"]["value"] == "vimpel, spacemapper"
    assert cards["DOWNLOAD_TRIES"]["file"] == "evidence/settings.py"
    assert cards["DOWNLOAD_TRIES"]["sentence"].startswith("How many times one failed download")
    assert cards["BACKOFF_FIRST"]["sentence"].startswith("How long a source is held off")

    backoff = news["retry_backoff"]
    assert backoff["tries"] == 3
    assert backoff["wait_between_tries_seconds"] == 60
    assert backoff["first_wait_seconds"] == 3600
    assert backoff["longest_wait_seconds"] == 7 * 24 * 60 * 60
    assert backoff["steps_seconds"][:4] == [3600, 7200, 14400, 28800]
    assert backoff["steps_seconds"][-1] == 7 * 24 * 60 * 60


def test_payload_visual_data_contains_no_markup():
    rows = _stage_rows()
    data = payload(rows, None, None, _workflow_texts())
    news = next(card for card in data["cards"] if card["key"] == "archive_news")

    for mark in news["schedule_visual"]["marks"]:
        assert "<" not in mark["utc"] and ">" not in mark["utc"]
    for setting in news["settings_cards"]:
        assert "<" not in setting["sentence"] and ">" not in setting["sentence"]
    assert "<" not in news["retry_backoff"]["note"] and ">" not in news["retry_backoff"]["note"]


def test_payload_includes_overview_link_cadence_words_for_scheduled_and_event_links():
    rows = _stage_rows()
    upcoming = pipeline.what_next(rows, NOW, hours=24)
    next_key, next_at = ((upcoming[0]["key"], upcoming[0]["at"]) if upcoming else (None, None))
    data = payload(rows, next_key, next_at, _workflow_texts())

    links = {(item["from"], item["to"]): item["cadence_words"] for item in data["overview_links"]}
    assert links[("archive_documents", "archive")] == "daily 00:30 UTC"
    assert links[("archive_news", "archive")] == "every 3 h from 00:50 UTC"
    assert links[("decision_waiting", "decision_made")] == "when a person decides"


def test_component_modes_embed_view_sync_and_frame_height_message():
    rows = _stage_rows()
    data = payload(rows, None, None, _workflow_texts())

    overview_page = live_pipeline_html(":root{}", "sans-serif", data, mode="overview")
    panel_page = live_pipeline_html(":root{}", "sans-serif", data, mode="panel")

    overview_json = overview_page[overview_page.index("const DATA = ") + len("const DATA = "):overview_page.index(";\nconst cards")]
    panel_json = panel_page[panel_page.index("const DATA = ") + len("const DATA = "):panel_page.index(";\nconst cards")]
    assert json.loads(overview_json)["view_mode"] == "overview"
    assert json.loads(panel_json)["view_mode"] == "panel"
    assert "live_pipeline_view" in overview_page and "live_pipeline_view" in panel_page
    assert "BroadcastChannel" in panel_page
    assert "window.frameElement.style.height" in panel_page   # the panel sizes its own frame; it never scrolls inside


def test_schedule_visual_uses_client_clock_for_now_marker():
    rows = _stage_rows()
    data = payload(rows, None, None, _workflow_texts())
    daily = next(card for card in data["cards"] if card["key"] == "archive_news")
    weekly = next(card for card in data["cards"] if card["key"] == "registry_update")

    assert "now" not in daily["schedule_visual"]
    assert "now" not in weekly["schedule_visual"]


def test_level_2_words_avoid_internal_jargon():
    banned = ("collector", "graded source", "candidate sources", "claim extraction", "evidence trail", "workflow")
    for key, words in STAGES.items():
        text = " ".join(words["what_happens"] + [words["why_it_matters"]]).lower()
        for term in banned:
            assert term not in text, (key, term)
        if "pull request" in text:
            assert "(pull request)" in text, key


def test_fact_checked_setting_sentence_entries_are_exact():
    assert SETTING_SENTENCES["ARCHIVE_VERSIONS_FILE"] == (
        "CSV file name inside the archive repository that records every change (a changed copy or a page becoming gone)."
    )
    assert SETTING_SENTENCES["BACKOFF_FIRST"] == (
        "How long a source is held off after its first refusal before it may be asked again."
    )
    assert SETTING_SENTENCES["MIN_GAP_BETWEEN_DOWNLOADS"] == (
        "Per-site minimum wait between two requests to the same site (a named host or any host under it)."
    )
    assert SETTING_SENTENCES["NEVER_FETCH"] == (
        "Host-name fragments the archive fetcher refuses before any request, including redirects to them."
    )
    assert SETTING_SENTENCES["WAIT_WARN_DAYS"] == (
        "Days a waiting decision item may wait before it is shown as overdue (warning once it has waited longer than this)."
    )
