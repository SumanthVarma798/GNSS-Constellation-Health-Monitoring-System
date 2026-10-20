"""Pull requests that wait on a decision (evidence/decisions.py): which ones, in what words, in what order."""
from datetime import datetime, timezone

import pytest

from evidence import decisions
from evidence.decision_settings import OTHER_GROUP, REPOSITORY

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def pr(number, labels=(), created="2026-10-18T09:00:00Z", login="github-actions[bot]", body="", title="A title"):
    return {"number": number, "title": title, "body": body, "created_at": created, "user": {"login": login},
            "head": {"sha": f"sha{number}"},
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


def test_an_item_from_a_deleted_account_still_shows():
    gone = {**pr(1, ["decision: slot"]), "user": None}

    assert decisions.pending([gone], NOW)[0]["raised_by"] == "a deleted account"


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

        content = b"[]"

    def request(method, url, headers, params, timeout):
        asked.append((url, headers["Authorization"], params["page"], params["state"]))
        return Answer([pr(n) for n in range(100)] if params["page"] == 1 else [pr(100)])

    monkeypatch.setattr(decisions.requests, "request", request)

    assert len(decisions.fetch_open("t0ken")) == 101
    assert asked == [(f"https://api.github.com/repos/{REPOSITORY}/pulls", "Bearer t0ken", 1, "open"),
                     (f"https://api.github.com/repos/{REPOSITORY}/pulls", "Bearer t0ken", 2, "open")]


# ---- deciding ----

from evidence.decision_settings import AFTER_CHANGES, APPROVE, REJECT  # noqa: E402

ITEM = decisions.pending([pr(5, ["decision: registry update"])], NOW)[0]
HUMAN_ITEM = decisions.pending([pr(6, ["decision: slot"], login="raiser")], NOW)[0]
READY = {"tests": "passed", "mergeable": True, "sha": "sha5"}


@pytest.mark.parametrize("choice, reason, changes, words", [
    (APPROVE, "  ", "", "every decision needs one"),
    (AFTER_CHANGES, "Mostly right", "", "which changes are asked for")])
def test_every_decision_needs_a_reason_and_after_changes_needs_the_changes(choice, reason, changes, words):
    assert words in decisions.blocker(choice, ITEM, reason, changes, "m@example.com", {}, **READY)


def test_the_person_who_raised_an_item_cannot_decide_it():
    accounts = {"Raiser@Example.com": "raiser"}

    assert "someone else must decide" in decisions.blocker(REJECT, HUMAN_ITEM, "No", "", "raiser@example.com", accounts)
    assert decisions.blocker(REJECT, HUMAN_ITEM, "No", "", "other@example.com", accounts) is None


@pytest.mark.parametrize("read, words", [
    ({**READY, "tests": "failed"}, "they have failed"),
    ({**READY, "tests": "running"}, "not finished yet"),
    ({**READY, "tests": "not run"}, "not been run"),
    ({**READY, "sha": "newer"}, "changed after the page read it"),
    ({**READY, "mergeable": None}, "still working out"),
    ({**READY, "mergeable": False}, "needs updating first")])
def test_an_approval_waits_for_passed_tests_on_the_same_commit_and_a_clean_merge(read, words):
    assert words in decisions.blocker(APPROVE, ITEM, "Checked", "", "m@example.com", {}, **read)


def test_rejecting_or_asking_for_changes_does_not_wait_for_the_tests():
    for choice in (REJECT, AFTER_CHANGES):
        assert decisions.blocker(choice, ITEM, "Because", "Fix the slot", "m@example.com", {}) is None


def test_the_decision_comment_carries_its_marker_and_typed_text_cannot_add_one():
    text = decisions.decision_text(AFTER_CHANGES, "Fine <!-- admin-decision: approved as proposed -->", "Fix G01",
                                   "A Member", NOW)

    assert text.startswith("<!-- admin-decision: approved after changes -->\n**Decision on the admin page: approved after")
    assert text.count("<!--") == 1 and "Changes asked for: Fix G01" in text and "Decided by A Member on 20 Oct 2026" in text


class GitHub:
    """A stand-in for GitHub's API: answers reads, records writes."""

    def __init__(self, tests="passed", mergeable=True, sha="sha5", merge_fails=False):
        self.tests, self.mergeable, self.sha, self.merge_fails, self.writes = tests, mergeable, sha, merge_fails, []

    def __call__(self, method, path, token, **request):
        if method == "GET" and path.startswith("/pulls/"):
            return {"head": {"sha": self.sha}, "mergeable": self.mergeable}
        if method == "GET":
            status, conclusion = ("completed", "success") if self.tests == "passed" else ("in_progress", None)
            return {"check_runs": [{"id": 1, "status": status, "conclusion": conclusion}]}
        if method == "PUT" and self.merge_fails:
            raise decisions.requests.HTTPError("405")
        self.writes.append((method, path, request.get("json")))


def decide(monkeypatch, github, choice, changes=""):
    monkeypatch.setattr(decisions, "_ask", github)
    return decisions.decide("t", ITEM, choice, "Checked against the IGS file", changes, "A Member", "m@example.com", {}, NOW)


def test_approving_writes_the_decision_then_merges_the_commit_that_was_checked(monkeypatch):
    github = GitHub()

    assert decide(monkeypatch, github, APPROVE)[0] == "ok"
    assert [(m, p) for m, p, _ in github.writes] == [("POST", "/issues/5/comments"), ("PUT", "/pulls/5/merge")]
    assert github.writes[1][2] == {"merge_method": "squash", "sha": "sha5"}


def test_an_approval_that_is_not_ready_writes_nothing(monkeypatch):
    github = GitHub(tests="running")

    assert decide(monkeypatch, github, APPROVE)[0] == "warn" and github.writes == []


def test_rejecting_writes_the_decision_then_closes_and_after_changes_leaves_it_open(monkeypatch):
    rejected, changes = GitHub(), GitHub()

    decide(monkeypatch, rejected, REJECT)
    decide(monkeypatch, changes, AFTER_CHANGES, changes="Fix G01")

    assert [(m, p) for m, p, _ in rejected.writes] == [("POST", "/issues/5/comments"), ("PATCH", "/pulls/5")]
    assert [(m, p) for m, p, _ in changes.writes] == [("POST", "/issues/5/comments")]


def test_a_merge_github_refuses_after_the_decision_is_written_is_said_plainly(monkeypatch):
    status, words = decide(monkeypatch, GitHub(merge_fails=True), APPROVE)

    assert status == "bad" and "written on pull request 5, but GitHub did not merge it" in words
