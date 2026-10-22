"""The System design assistant (evidence/assistant.py): what it answers from, what it sends, and how it fails."""
import json

import pytest
import requests
import streamlit

from evidence import assistant
from evidence.assistant_settings import DOCUMENTS, ISSUE_CHARACTERS, MODEL, SOURCE_FILES
from test_console import run, signed_in
from test_dashboard_shell import segmented_controls_rerun  # noqa: F401  (AppTest 1.45's segmented controls)
from ui.components.system_design import PARTS

ISSUES = [{"number": 19, "title": "Operator status", "body": "word " * 500}]


def test_the_material_holds_the_documents_the_page_the_code_and_the_issues_each_under_its_label():
    text = assistant.material(ISSUES, PARTS)

    for label in (*[f"[{path}]" for path in DOCUMENTS], *[f"[{path}]" for path in SOURCE_FILES],
                  f"[{assistant.PAGE_LABEL}]", "[evidence/assistant.py]", "[console/design.py]",
                  "[issue #19] Operator status"):
        assert label in text, label
    issue_line = next(line for line in text.splitlines() if line.startswith("[issue #19]"))
    assert len(issue_line) < ISSUE_CHARACTERS + 40 and issue_line.endswith("…")


class Reply:
    def __init__(self, lines, status=200):
        self.lines, self.status_code = lines, status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    @property
    def ok(self):
        return self.status_code < 400

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def iter_lines(self):
        return [line if isinstance(line, bytes) else json.dumps(line).encode() for line in self.lines]


def test_it_sends_the_rules_and_material_first_then_recent_turns_then_the_question(monkeypatch):
    sent = {}

    def post(url, json, **_):
        sent.update(json)
        return Reply([{"message": {"content": "It is "}}, {"message": {"content": "CelesTrak [docs/system-design.md]."}}])

    monkeypatch.setattr(assistant.requests, "post", post)
    history = [{"role": "user", "content": f"q{n}"} for n in range(30)]

    said = "".join(assistant.answer("Where do orbits come from?", history, "MATERIAL TEXT"))

    assert said == "It is CelesTrak [docs/system-design.md]."
    first, *middle, last = sent["messages"]
    assert first["role"] == "system" and "Answer ONLY from the MATERIAL" in first["content"]
    assert first["content"].endswith("MATERIAL TEXT") and last["content"] == "Where do orbits come from?"
    assert len(middle) < len(history) and middle[-1] == history[-1]
    assert sent["model"] == MODEL and sent["think"] is False and sent["options"]["temperature"] == 0


@pytest.mark.parametrize("trouble, words", [
    (requests.ConnectionError(), "ollama serve"),
    (Reply([], status=404), f"ollama pull {MODEL}"),
    (Reply([{"error": "out of memory"}]), "out of memory"),
    (Reply([], status=500), "did not answer"),
    (requests.ReadTimeout(), "did not answer"),
    (Reply([b"<html>not json</html>"]), "expected shape"),
])
def test_each_failure_says_in_plain_words_what_to_do(monkeypatch, trouble, words):
    def post(*_, **__):
        if isinstance(trouble, Exception):
            raise trouble
        return trouble

    monkeypatch.setattr(assistant.requests, "post", post)
    with pytest.raises(assistant.Unavailable, match=words):
        list(assistant.answer("?", [], ""))


def test_an_answer_that_runs_past_its_time_is_stopped(monkeypatch):
    clock = iter([0, 1, assistant.ANSWER_SECONDS + 1])
    monkeypatch.setattr(assistant.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(assistant.requests, "post", lambda *_, **__: Reply([{"message": {"content": "a"}}] * 3))

    with pytest.raises(assistant.Unavailable, match="longer than"):
        list(assistant.answer("?", [], ""))


def test_a_source_the_material_does_not_have_is_named():
    text = "=== [docs/system-design.md] ===\n...\n[issue #19] Operator status"
    answer = "Built [docs/system-design.md]; planned [issue #19, docs/system-design.md]. Also [docs/made-up.md]."

    assert assistant.unknown_sources(answer, text) == ["docs/made-up.md"]


def test_the_design_page_shows_the_question_the_answer_and_any_unknown_source(monkeypatch):
    streamlit.cache_data.clear()
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(assistant, "available", lambda: True)
    monkeypatch.setattr(assistant, "answer", lambda question, history, text: iter(["Built ", "[docs/made-up.md]."]))
    at = run(monkeypatch, page="console/design.py")

    at.chat_input[0].set_value("What is built?").run()

    assert not at.exception
    assert [m.name for m in at.chat_message] == ["user", "assistant"]
    assert "docs/made-up.md" in at.warning[0].value


def test_the_chat_survives_leaving_the_design_page_and_coming_back(monkeypatch):
    streamlit.cache_data.clear()
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(assistant, "available", lambda: True)
    monkeypatch.setattr(assistant, "answer", lambda question, history, text: iter(["Built [docs/system-design.md]."]))
    at = run(monkeypatch, page="console/design.py")

    at.chat_input[0].set_value("What is built?").run()
    assert [m.name for m in at.chat_message] == ["user", "assistant"]

    at.switch_page("console/jobs.py").run()
    at.switch_page("console/design.py").run()

    assert [m.name for m in at.chat_message] == ["user", "assistant"]
    assert at.chat_message[0].markdown[0].value == "What is built?"
    assert at.chat_message[1].markdown[0].value == "Built [docs/system-design.md]."


def test_start_over_empties_the_chat(monkeypatch):
    streamlit.cache_data.clear()
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(assistant, "available", lambda: True)
    monkeypatch.setattr(assistant, "answer", lambda question, history, text: iter(["Built [docs/system-design.md]."]))
    at = run(monkeypatch, page="console/design.py")

    at.chat_input[0].set_value("What is built?").run()
    assert [m.name for m in at.chat_message] == ["user", "assistant"]
    at.run()
    assert [b for b in at.button if b.key == "design_chat_start_over"]

    at.button(key="design_chat_start_over").click().run()

    assert not at.chat_message
    assert not [b for b in at.button if b.key == "design_chat_start_over"]


def test_where_no_model_runs_the_page_says_questions_are_off_and_offers_no_box(monkeypatch):
    streamlit.cache_data.clear()
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(assistant, "available", lambda: False)

    at = run(monkeypatch, page="console/design.py")

    assert "Questions are off on this copy" in at.info[0].value and not at.chat_input
    assert "runs on this computer" not in " ".join(c.value for c in at.caption)


def test_the_model_counts_as_here_only_when_ollama_answers(monkeypatch):
    def refused(*_, **__):
        raise requests.ConnectionError()

    monkeypatch.setattr(assistant.requests, "get", refused)
    assert assistant.available() is False
    monkeypatch.setattr(assistant.requests, "get", lambda *_, **__: Reply([]))
    assert assistant.available() is True
