"""The console's assistant (evidence/assistant.py) and its Ask page (console/ask.py): what it answers from, which model
it asks, what it sends, and how it fails."""
import json

import pytest
import requests

from evidence import assistant
from assistant_eval import QUESTIONS, missing_facts
from evidence.assistant_settings import (ANSWER_TOKENS, CONTEXT_TOKENS, DEEPSEEK, DEEPSEEK_MODEL, DEEPSEEK_URL, DOCUMENTS, EXAMPLES,
                                         HISTORY_TOKENS, HISTORY_TURNS, ISSUE_CHARACTERS, MODEL, OLLAMA, OLLAMA_URL,
                                         REMINDER, SOURCE_FILES, TRACKED)
from test_console import SECRETS, fresh_reading, run, signed_in  # noqa: F401  (each test reads afresh)
from test_dashboard_shell import segmented_controls_rerun  # noqa: F401  (AppTest 1.45's segmented controls)
from ui.components.system_design import PARTS

ISSUES = [{"number": 19, "title": "Operator status", "body": "word " * 500}]
PULLS = [{"number": 181, "title": "Archive retention", "merged_at": "2026-10-30T09:00:00Z"},
         {"number": 184, "title": "Ask page", "merged_at": "2026-10-31T06:00:00Z"},
         {"number": 177, "title": "Closed without merging", "merged_at": None}]
ON_DEEPSEEK = {**SECRETS, "assistant": {"provider": "deepseek", "key": "not-a-real-key"}}


def sse(*pieces):
    """DeepSeek's stream: one `data:` line per piece of the answer, blank lines between, and [DONE] at the end."""
    lines = []
    for piece in pieces:
        lines += [b"data: " + json.dumps({"choices": [{"index": 0, "delta": {"content": piece}}]}).encode(), b""]
    return lines + [b"data: [DONE]"]


def test_the_material_holds_the_documents_the_page_the_code_and_the_issues_each_under_its_label():
    text = assistant.material(ISSUES, PARTS, PULLS)

    for label in (*[f"[{path}]" for path in DOCUMENTS], *[f"[{path}]" for path in SOURCE_FILES],
                  "[docs/infrastructure.md]", "[evidence/settings.py]", f"[{TRACKED}]",
                  f"[{assistant.PAGE_LABEL}]", "[evidence/assistant.py]", "[console/design.py]",
                  "[issue #19] Operator status"):
        assert label in text, label
    issue_line = next(line for line in text.splitlines() if line.startswith("[issue #19]"))
    assert len(issue_line) < ISSUE_CHARACTERS + 40 and issue_line.endswith("…")


def test_the_material_holds_each_job_with_its_schedule_and_the_comment_that_explains_it():
    text = assistant.material([], PARTS)

    job = text[text.index("=== [.github/workflows/rinex-check.yml] ==="):]
    job = job[:job.index("\n\n===")]
    assert "pings Healthchecks.io (rinex-check)" in job and "name: RINEX check" in job
    assert "06:00 UTC = 11:30 India time" in job and "- cron: '0 6 * * *'" in job
    assert "runs-on" not in job and "steps:" not in job   # the job's steps stay out
    assert "[.github/workflows/archive.yml]" in text and "- cron: '15 1,8,14,20 * * *'" in text


def test_the_material_counts_the_tracked_satellites_and_lists_merged_pull_requests_newest_first_after_the_documents():
    text = assistant.material(ISSUES, PARTS, PULLS)
    with (assistant.ROOT / TRACKED).open() as handle:
        tracked = sum(1 for _ in handle) - 1

    assert f"{tracked} satellites tracked" in text
    assert text.index("[PR #184] Ask page (merged 2026-10-31)") < text.index("[PR #181] Archive retention")
    assert "[PR #177]" not in text   # closed without merging is not a change
    assert text.index("[docs/system-design.md]") < text.index("[PR #184]") < text.index("[issue #19]")   # what changes, last


@pytest.mark.parametrize("item", [q for q in QUESTIONS if not q.get("github") and not q.get("refuse")],
                         ids=lambda q: q["question"][:50])
def test_the_material_holds_the_facts_each_eval_question_needs(item):
    text = assistant.material([], PARTS).lower()

    for spellings in item["facts"]:
        assert any(s.lower() in text for s in spellings), spellings


def test_the_eval_matches_whole_words_and_wants_a_refusal_first():
    qzss = next(q for q in QUESTIONS if q["question"].startswith("How is QZSS"))
    refuse = next(q for q in QUESTIONS if q.get("refuse"))

    assert missing_facts("Each orbit is read [x].", qzss) == ["bit", "IS-QZSS-PNT-005"]   # "bit" is not in "orbit"
    assert missing_facts("Bit by bit, per IS-QZSS-PNT-005.", qzss) == []
    assert missing_facts("That isn't in the project's material.", refuse) == []
    assert missing_facts("It is 2 million. That isn't in the project's material, though.", refuse)


def conversation(turns, answer="It is built [docs/system-design.md]."):
    """`turns` questions, each with its answer, oldest first, as the Ask page keeps them."""
    return [turn for n in range(turns)
            for turn in ({"role": "user", "content": f"Question {n}?"}, {"role": "assistant", "content": f"{answer} {n}"})]


def assert_framed(messages, history, question):
    """The rules and material first, then the newest whole turns, then the reminder and the question, last."""
    first, *middle, reminder, last = messages
    assert first["role"] == "system" and "Answer ONLY from the MATERIAL" in first["content"]
    assert first["content"].endswith("MATERIAL TEXT")
    assert reminder == {"role": "system", "content": REMINDER} and last == {"role": "user", "content": question}
    assert middle == (history[-len(middle):] if middle else []) and (not middle or middle[0]["role"] == "user")
    return middle


def test_a_long_chat_keeps_the_newest_whole_turns_that_fit_in_the_token_room():
    long_answer = "x" * (3 * HISTORY_TOKENS // 3)   # about a third of the room each
    history = conversation(5, long_answer)

    kept = assistant.recent(history)

    assert kept == history[-4:]   # two whole turns fit; a third would not
    assert assistant.recent(conversation(30)) == conversation(30)[-2 * HISTORY_TURNS:]
    assert assistant.recent(conversation(2, "x" * 3 * HISTORY_TOKENS)) == []   # never cut in the middle


def test_on_ollama_a_full_context_leaves_no_room_for_the_chat_but_the_rules_and_question_always_go(monkeypatch):
    sent = {}
    monkeypatch.setattr(assistant.requests, "post", lambda url, json, **_: sent.update(json) or Reply([]))
    material_text = "MATERIAL TEXT".rjust(3 * CONTEXT_TOKENS)   # fills Ollama's whole context

    list(assistant.answer("And that one?", conversation(30), material_text))

    first, reminder, last = sent["messages"]
    assert first["content"].endswith("MATERIAL TEXT") and reminder["content"] == REMINDER
    assert last["content"] == "And that one?" and sent["options"]["num_predict"] == ANSWER_TOKENS


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


def test_a_30_turn_chat_sends_the_rules_and_material_first_then_recent_turns_the_reminder_and_the_question(monkeypatch):
    sent = {}

    def post(url, json, **_):
        sent.update(json)
        return Reply([{"message": {"content": "It is "}}, {"message": {"content": "CelesTrak [docs/system-design.md]."}}])

    monkeypatch.setattr(assistant.requests, "post", post)
    history = conversation(30)

    said = "".join(assistant.answer("Where do orbits come from?", history, "MATERIAL TEXT"))

    assert said == "It is CelesTrak [docs/system-design.md]."
    assert len(assert_framed(sent["messages"], history, "Where do orbits come from?")) == 2 * HISTORY_TURNS
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


def test_deepseek_is_asked_the_same_way_with_its_own_address_model_and_key(monkeypatch):
    sent = {}

    def post(url, json, headers, **_):
        sent.update(url=url, headers=headers, **json)
        return Reply(sse("It is ", "CelesTrak [docs/system-design.md]."))

    monkeypatch.setattr(assistant.requests, "post", post)
    history = conversation(30)

    said = "".join(assistant.answer("Where do orbits come from?", history, "MATERIAL TEXT", DEEPSEEK_URL, "k", DEEPSEEK))

    assert said == "It is CelesTrak [docs/system-design.md]."
    assert sent["url"] == "https://api.deepseek.com/chat/completions" and sent["headers"] == {"Authorization": "Bearer k"}
    assert sent["model"] == DEEPSEEK_MODEL and sent["stream"] is True and sent["thinking"] == {"type": "disabled"}
    assert sent["temperature"] == 0 and "options" not in sent and "think" not in sent
    assert len(assert_framed(sent["messages"], history, "Where do orbits come from?")) == 2 * HISTORY_TURNS


def test_deepseek_stream_skips_keep_alives_and_empty_pieces_and_ends_at_done(monkeypatch):
    lines = [b": keep-alive", b"", *sse("", "One", " two")[:-1],
             b'data: {"choices": [{"index": 0, "delta": {"content": null}, "finish_reason": "stop"}], "usage": {}}',
             b"data: [DONE]", b"data: not even json"]
    monkeypatch.setattr(assistant.requests, "post", lambda *_, **__: Reply(lines))

    assert "".join(assistant.answer("?", [], "", DEEPSEEK_URL, "k", DEEPSEEK)) == "One two"


@pytest.mark.parametrize("trouble, words", [
    (Reply([], status=401), r"DeepSeek does not accept the console's key. Check \[assistant\] key"),
    (Reply([], status=402), "run out of credit"),
    (Reply([], status=429), "too many questions"),
    (Reply([], status=503), "did not answer"),
    (Reply([b'data: {"error": {"message": "context too long"}}']), "context too long"),
    (requests.ConnectionError(), "DeepSeek's service is not reachable"),
    (Reply([b"data: null"]), "expected shape"),
    (Reply([b'data: {"choices": null}']), "expected shape"),
    (Reply(sse("Half an answer")[:-1]), "stopped part way"),
])
def test_each_deepseek_failure_says_in_plain_words_what_to_do(monkeypatch, trouble, words):
    def post(*_, **__):
        if isinstance(trouble, Exception):
            raise trouble
        return trouble

    monkeypatch.setattr(assistant.requests, "post", post)
    with pytest.raises(assistant.Unavailable, match=words):
        list(assistant.answer("?", [], "", DEEPSEEK_URL, "k", DEEPSEEK))


def test_deepseek_counts_as_here_when_a_key_is_set_without_asking_it(monkeypatch):
    def no_network(*_, **__):
        raise AssertionError("no request to check DeepSeek")

    monkeypatch.setattr(assistant.requests, "get", no_network)
    assert assistant.available(DEEPSEEK_URL, "k", DEEPSEEK) is True
    assert assistant.available(DEEPSEEK_URL, "", DEEPSEEK) is False


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


def test_the_ask_page_offers_the_example_questions_and_names_the_model(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    at = run(monkeypatch, secrets=ON_DEEPSEEK, page="console/ask.py")

    assert [b.label for b in at.button if b.key.startswith("ask_example_")] == list(EXAMPLES)
    assert 4 <= len(EXAMPLES) <= 6
    note = " ".join(c.value for c in at.caption)
    assert f"The model ({DEEPSEEK_MODEL}) runs on DeepSeek's hosted service" in note and "[brackets]" in note
    assert at.chat_input and not at.chat_message


def test_an_example_question_is_asked_when_pressed(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    asked = []
    monkeypatch.setattr(assistant, "answer", lambda question, *_: asked.append(question) or iter(["Daily [docs/system-design.md]."]))
    at = run(monkeypatch, secrets=ON_DEEPSEEK, page="console/ask.py")

    at.button(key="ask_example_0").click().run()

    assert asked == [EXAMPLES[0]]
    assert [m.name for m in at.chat_message] == ["user", "assistant"]
    assert at.chat_message[0].markdown[0].value == EXAMPLES[0]


@pytest.mark.parametrize("place, expected", [
    ({}, (OLLAMA, OLLAMA_URL, "")),
    ({"url": "https://mac.example.ts.net/", "key": "gate"}, (OLLAMA, "https://mac.example.ts.net", "gate")),
    ({"provider": "DeepSeek ", "key": "k"}, (DEEPSEEK, DEEPSEEK_URL, "k")),
    ({"provider": "deepseek", "key": "k", "url": "https://other.example/"}, (DEEPSEEK, "https://other.example", "k")),
])
def test_the_console_secrets_choose_the_model(monkeypatch, place, expected):
    signed_in(monkeypatch, "member@example.com")
    used = []
    monkeypatch.setattr(assistant, "available", lambda *_: True)
    monkeypatch.setattr(assistant, "answer", lambda q, h, t, url, key, provider: used.append((provider, url, key)) or iter(["Yes."]))
    at = run(monkeypatch, secrets={**SECRETS, "assistant": place}, page="console/ask.py")

    at.chat_input[0].set_value("Is it on?").run()

    assert used == [expected]


def test_deepseek_without_a_key_or_an_unknown_provider_turns_questions_off_and_says_why(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    at = run(monkeypatch, secrets={**SECRETS, "assistant": {"provider": "deepseek"}}, page="console/ask.py")
    assert "[assistant] key" in at.info[0].value and not at.chat_input

    at = run(monkeypatch, secrets={**SECRETS, "assistant": {"provider": "openai", "key": "k"}}, page="console/ask.py")
    assert 'must be "deepseek" or "ollama"' in at.info[0].value and not at.chat_input


def test_the_ask_page_shows_the_question_the_answer_and_any_unknown_source(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(assistant, "available", lambda *_: True)
    monkeypatch.setattr(assistant, "answer", lambda question, history, text, *_: iter(["Built ", "[docs/made-up.md]."]))
    at = run(monkeypatch, page="console/ask.py")

    at.chat_input[0].set_value("What is built?").run()

    assert not at.exception
    assert [m.name for m in at.chat_message] == ["user", "assistant"]
    assert "docs/made-up.md" in at.warning[0].value


def test_the_chat_survives_leaving_the_ask_page_and_coming_back(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(assistant, "available", lambda *_: True)
    monkeypatch.setattr(assistant, "answer", lambda question, history, text, *_: iter(["Built [docs/system-design.md]."]))
    at = run(monkeypatch, page="console/ask.py")

    at.chat_input[0].set_value("What is built?").run()
    assert [m.name for m in at.chat_message] == ["user", "assistant"]

    at.switch_page("console/jobs.py").run()
    at.switch_page("console/ask.py").run()

    assert [m.name for m in at.chat_message] == ["user", "assistant"]
    assert at.chat_message[0].markdown[0].value == "What is built?"
    assert at.chat_message[1].markdown[0].value == "Built [docs/system-design.md]."


def test_start_over_empties_the_chat(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(assistant, "available", lambda *_: True)
    monkeypatch.setattr(assistant, "answer", lambda question, history, text, *_: iter(["Built [docs/system-design.md]."]))
    at = run(monkeypatch, page="console/ask.py")

    at.chat_input[0].set_value("What is built?").run()
    assert [m.name for m in at.chat_message] == ["user", "assistant"]
    assert [b for b in at.button if b.key == "ask_start_over"]   # at once, with the first answer

    at.button(key="ask_start_over").click().run()

    assert not at.chat_message
    assert not [b for b in at.button if b.key == "ask_start_over"]


def test_where_no_model_runs_the_page_says_questions_are_off_and_offers_no_box(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(assistant, "available", lambda *_: False)

    at = run(monkeypatch, page="console/ask.py")

    assert "Questions are off on this copy" in at.info[0].value and not at.chat_input
    assert "runs on this computer" not in " ".join(c.value for c in at.caption)


def test_the_design_page_points_to_the_ask_page_and_holds_no_chat_of_its_own(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    at = run(monkeypatch, page="console/design.py")

    assert any("Ask page" in link.proto.label for link in at.get("page_link"))
    assert not at.chat_input


def test_the_model_counts_as_here_only_when_ollama_answers(monkeypatch):
    def refused(*_, **__):
        raise requests.ConnectionError()

    monkeypatch.setattr(assistant.requests, "get", refused)
    assert assistant.available() is False
    monkeypatch.setattr(assistant.requests, "get", lambda *_, **__: Reply([]))
    assert assistant.available() is True
