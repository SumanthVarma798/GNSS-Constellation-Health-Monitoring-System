"""Pull requests that wait on a decision (evidence/decisions.py): which ones, in what words, in what order."""
from datetime import datetime, timezone

import pytest

from evidence import decisions
from evidence.decision_settings import OTHER_GROUP, REPOSITORY

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def pr(number, labels=(), created="2026-10-18T09:00:00Z", login="github-actions[bot]", body="", title="A title"):
    return {"number": number, "title": title, "body": body, "created_at": created, "user": {"login": login},
            "html_url": f"https://github.com/{REPOSITORY}/pull/{number}", "labels": [{"name": n} for n in labels]}


def test_only_pull_requests_with_a_decision_label_are_pending():
    prs = [pr(1, ["decision: registry update"]), pr(2, ["enhancement"]), pr(3)]

    assert [i["number"] for i in decisions.pending(prs, NOW)] == [1]


def test_an_item_says_its_kind_group_who_raised_it_and_how_long_it_waited():
    one = decisions.pending([pr(7, ["bug", "decision: registry update"], login="github-actions[bot]",
                                   body="This is a proposed update.\nStill the first paragraph.\n\n## Details\n- x")], NOW)[0]

    assert one["kind"] == "registry update" and one["group"] == "Satellites"
    assert one["raised_by"] == "the weekly job"
    assert one["waited_days"] == 2
    assert one["summary"] == "This is a proposed update.\nStill the first paragraph."
    assert one["link"].endswith("/pull/7")


def test_a_person_who_raised_an_item_is_named_by_their_account():
    assert decisions.pending([pr(1, ["decision: slot"], login="someone")], NOW)[0]["raised_by"] == "someone"


def test_a_kind_not_in_the_settings_is_still_shown_under_other_kinds():
    one = decisions.pending([pr(1, ["decision: new source"])], NOW)[0]

    assert one["kind"] == "new source" and one["group"] == OTHER_GROUP


def test_the_longest_waiting_comes_first():
    prs = [pr(1, ["decision: slot"], created="2026-10-19T00:00:00Z"),
           pr(2, ["decision: slot"], created="2026-10-01T00:00:00Z")]

    assert [i["number"] for i in decisions.pending(prs, NOW)] == [2, 1]


def test_groups_come_in_the_settings_order_with_other_kinds_last_and_empty_groups_left_out():
    items = decisions.pending([pr(1, ["decision: new source"]), pr(2, ["decision: status"])], NOW)

    assert [(group, [i["number"] for i in its]) for group, its in decisions.grouped(items)] == [
        ("Satellites", [2]), (OTHER_GROUP, [1])]


@pytest.mark.parametrize("days, words, status", [
    (0, "opened today", "ok"), (1, "waiting 1 day", "ok"), (14, "waiting 14 days", "ok"),
    (15, "waiting 15 days, past a fortnightly call", "warn")])
def test_waiting_is_said_in_words_and_turns_to_a_warning_after_a_fortnight(days, words, status):
    assert decisions.waited(days) == (words, status)


def test_an_empty_body_has_an_empty_summary():
    assert decisions.summary(None) == "" and decisions.summary("\n\n  \n") == ""


@pytest.mark.parametrize("logged_in, email, answer", [
    (False, None, "sign in"), (True, "stranger@example.com", "not on the list"),
    (True, "Member@Example.com", "in")])
def test_only_signed_in_people_on_the_list_get_in(logged_in, email, answer):
    assert decisions.access(logged_in, email, ["member@example.com"]) == answer


def test_reading_asks_github_for_every_page_of_open_pull_requests_with_the_token(monkeypatch):
    asked = []

    class Answer:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            pass

        def json(self):
            return self.rows

    def get(url, headers, params, timeout):
        asked.append((url, headers["Authorization"], params["page"], params["state"]))
        return Answer([pr(n) for n in range(100)] if params["page"] == 1 else [pr(100)])

    monkeypatch.setattr(decisions.requests, "get", get)

    assert len(decisions.fetch_open("t0ken")) == 101
    assert asked == [(f"https://api.github.com/repos/{REPOSITORY}/pulls", "Bearer t0ken", 1, "open"),
                     (f"https://api.github.com/repos/{REPOSITORY}/pulls", "Bearer t0ken", 2, "open")]
