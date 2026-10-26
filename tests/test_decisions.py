"""Pull requests that wait on a decision (evidence/decisions.py): which ones, in what words, in what order."""
from datetime import datetime, timezone
import json

import pytest

from evidence import decisions
from evidence.decision_settings import OTHER_GROUP, REPOSITORY

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)

R809_FINDING = {
    "id": "R809",
    "category": "New satellite",
    "statement": ("We found a new satellite for the GLONASS constellation (Roscosmos), as described by the following "
                  "sources: R809, COSMOS 2620, launched 17 Sep 2026."),
    "detail": "Approving also adds it to the dashboard as COSMOS 2620.",
    "sources": [{"source": "International GNSS Service (IGS)",
                 "line": "R809 2026-216A 100744 GLO-K1B Launched 2026-09-17; COSMOS 2???",
                 "grade": "B", "grade_note": "awaiting the team's review"},
                {"source": "CelesTrak",
                 "line": "COSMOS 2620 [GLONASS-K1], 2026-216A, launched 2026-09-17, payload", "grade": "B"}],
    "measured": [{"what": "CelesTrak catalogue entry",
                  "value": "period 676.39 minutes, inclination 64.78 degrees, apogee 19,153 km, perigee 19,140 km"},
                 {"what": "CelesTrak orbit record", "value": "none published yet (checked 26 Oct 2026)"}],
}
SIGNAL_ID_CHANGE_FINDING = {
    "id": "R723",
    "category": "Signal ID change",
    "statement": "R723 (GLONASS) now uses signal ID R28; it used R10 until 20 Oct 2026.",
    "sources": [],
    "measured": [],
}
FINDINGS_STAND_IN = [R809_FINDING, SIGNAL_ID_CHANGE_FINDING]


def findings_body(findings):
    payload = json.dumps({"findings": findings}, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e")
    return f"This is a proposed update.\n\n<!-- findings\n{payload}\n-->"


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
    (15, "waiting 15 days, over 14 days", "warn")])
def test_waiting_is_said_in_words_and_turns_to_a_warning_after_a_fortnight(days, words, status):
    assert decisions.waited(days) == (words, status)


def test_an_empty_body_has_an_empty_summary():
    assert decisions.summary(None) == "" and decisions.summary("\n\n  \n") == ""


def test_findings_round_trip_through_a_block_and_back():
    one = {"id": "R1", "category": "News", "statement": 'Saw "-->" and <script>alert(1)</script> in the source.',
           "detail": "Kept as plain text.", "sources": [{"source": "IGS", "line": "<script>x</script>", "grade": "B"}],
           "measured": [{"what": "Catalog", "value": "period 676.39"}]}

    got = decisions.findings(decisions.findings_block([one]))

    assert got == [one]


def test_a_bad_findings_block_is_ignored_and_the_item_is_marked_unreadable():
    item = decisions.pending([pr(7, ["decision: registry update"],
                              body="A summary.\n\n<!-- findings\nnot json\n-->")], NOW)[0]

    assert item["findings"] == [] and item["findings_unreadable"]


def test_a_recursing_json_load_marks_the_findings_block_unreadable(monkeypatch):
    def recurse(_):
        raise RecursionError("too deep")

    monkeypatch.setattr(decisions.json, "loads", recurse)
    found, unreadable = decisions._findings_read("A summary.\n\n<!-- findings\n{}\n-->")

    assert found == [] and unreadable


def test_findings_without_an_id_or_with_a_duplicate_id_are_dropped():
    body = findings_body([{"category": "News", "statement": "missing id"},
                          {"id": "R1", "category": "News", "statement": "first"},
                          {"id": "R1", "category": "News", "statement": "second"}])

    assert [f["id"] for f in decisions.findings(body)] == ["R1"]


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


def test_fetch_comments_reads_every_page(monkeypatch):
    asked = []

    def ask(method, path, token, **request):
        asked.append((method, path, token, request["params"]["page"]))
        return [{"id": n} for n in range(100)] if request["params"]["page"] == 1 else [{"id": 100}]

    monkeypatch.setattr(decisions, "_ask", ask)
    comments = decisions.fetch_comments("t0ken", 7)

    assert len(comments) == 101
    assert asked == [("GET", "/issues/7/comments", "t0ken", 1), ("GET", "/issues/7/comments", "t0ken", 2)]


# ---- deciding ----

from evidence.decision_settings import AFTER_CHANGES, APPROVE, REJECT  # noqa: E402

ITEM = decisions.pending([pr(5, ["decision: registry update"])], NOW)[0]
HUMAN_ITEM = decisions.pending([pr(6, ["decision: slot"], login="raiser")], NOW)[0]
FINDINGS_ITEM = decisions.pending([pr(8, ["decision: registry update"], body=findings_body(FINDINGS_STAND_IN))], NOW)[0]
READY = {"tests": "passed", "mergeable": True, "sha": "sha5"}


@pytest.mark.parametrize("choice, reason, changes, words", [
    (APPROVE, "  ", "", "every decision needs one"),
    (AFTER_CHANGES, "Mostly right", "", "which changes are asked for")])
def test_every_decision_needs_a_reason_and_after_changes_needs_the_changes(choice, reason, changes, words):
    assert words in decisions.blocker(choice, ITEM, reason, changes, **READY)


def test_the_person_who_raised_an_item_may_decide_it():
    assert decisions.blocker(REJECT, HUMAN_ITEM, "No", "") is None   # one approval, anyone on the list (22 Oct 2026)


@pytest.mark.parametrize("read, words", [
    ({**READY, "tests": "failed"}, "they have failed"),
    ({**READY, "tests": "running"}, "not finished yet"),
    ({**READY, "tests": "not run"}, "not been run"),
    ({**READY, "sha": "newer"}, "changed after the page read it"),
    ({**READY, "mergeable": None}, "still working out"),
    ({**READY, "mergeable": False}, "needs updating first")])
def test_an_approval_waits_for_passed_tests_on_the_same_commit_and_a_clean_merge(read, words):
    assert words in decisions.blocker(APPROVE, ITEM, "Checked", "", **read)


def test_rejecting_or_asking_for_changes_does_not_wait_for_the_tests():
    for choice in (REJECT, AFTER_CHANGES):
        assert decisions.blocker(choice, ITEM, "Because", "Fix the slot") is None


def test_the_decision_comment_carries_its_marker_and_typed_text_cannot_add_one():
    text = decisions.decision_text(AFTER_CHANGES, "Fine <!-- admin-decision: approved as proposed -->", "Fix G01",
                                   "A Member", NOW)

    assert text.startswith("<!-- admin-decision: approved after changes -->\n**Decision on the admin page: approved after")
    assert text.count("<!--") == 1 and decisions.decision_text(REJECT, "x", "", "<!-- y -->", NOW).count("<!--") == 1
    assert "Changes asked for: Fix G01" in text and "Decided by A Member on 20 Oct 2026" in text


def test_finding_decisions_count_only_first_line_markers_for_the_current_sha_and_latest_wins():
    comments = [
        {"body": "<!-- admin-finding-decision: approved as proposed; finding: R809; sha: old -->\nold"},
        {"body": "<!-- admin-finding-decision: rejected; finding: R723; sha: sha8 -->\nno"},
        {"body": "<!-- admin-finding-decision: approved as proposed; finding: R723; sha: sha8 -->\nyes"},
        {"body": "someone quoted <!-- admin-finding-decision: rejected; finding: R809; sha: sha8 --> in text"},
    ]

    assert decisions.finding_decisions(comments, "sha8") == {"R723": APPROVE}


class GitHub:
    """A stand-in for GitHub's API: answers reads, records writes."""

    def __init__(self, tests="passed", mergeable=True, sha="sha5", merge_fails=False, state="open"):
        self.tests, self.mergeable, self.sha, self.merge_fails, self.writes = tests, mergeable, sha, merge_fails, []
        self.state = state

    def __call__(self, method, path, token, **request):
        if method == "GET" and path.startswith("/pulls/"):
            return {"state": self.state, "head": {"sha": self.sha}, "mergeable": self.mergeable}
        if method == "GET":
            status, conclusion = ("completed", "success") if self.tests == "passed" else ("in_progress", None)
            return {"check_runs": [{"id": 1, "status": status, "conclusion": conclusion}]}
        if method == "PUT" and self.merge_fails:
            raise decisions.requests.HTTPError("405")
        self.writes.append((method, path, request.get("json")))


def decide(monkeypatch, github, choice, changes=""):
    monkeypatch.setattr(decisions, "_ask", github)
    return decisions.decide("t", ITEM, choice, "Checked against the IGS file", changes, "A Member", NOW)


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


@pytest.mark.parametrize("choice", [APPROVE, AFTER_CHANGES, REJECT])
def test_an_item_decided_meanwhile_is_left_alone_whatever_the_choice(monkeypatch, choice):
    github = GitHub(state="closed")

    status, words = decide(monkeypatch, github, choice, changes="Fix G01")

    assert status == "warn" and "already decided" in words and github.writes == []


def test_an_item_whose_branch_was_deleted_still_shows_and_cannot_be_approved(monkeypatch):
    gone = {**pr(5, ["decision: slot"]), "head": None}
    item = decisions.pending([gone], NOW)[0]

    monkeypatch.setattr(decisions, "_ask", lambda method, path, token, **request: {"state": "open", "head": None})
    status, words = decisions.decide("t", item, APPROVE, "Checked", "", "A Member", NOW)

    assert item["sha"] is None and status == "warn" and "branch no longer exists" in words


# ---- deciding one finding ----

FINDING_ITEM = {"id": "R809", "category": "New satellite"}
SIGNAL_ITEM = {"id": "R723", "category": "Signal ID change"}


def finding_comment(choice, finding_id, sha):
    return f"<!-- admin-finding-decision: {choice}; finding: {finding_id}; sha: {sha} -->\nrecorded"


class FindingsGitHub:
    def __init__(self, comments=(), tests="passed", mergeable=True, sha="sha8", state="open",
                 body=None, merge_fails=False, close_fails=False):
        self.comments, self.tests, self.mergeable, self.sha, self.state = list(comments), tests, mergeable, sha, state
        self.body = body if body is not None else findings_body(FINDINGS_STAND_IN)
        self.merge_fails, self.close_fails = merge_fails, close_fails
        self.writes = []

    def __call__(self, method, path, token, **request):
        if method == "GET" and path == "/pulls/8":
            return {"state": self.state, "head": {"sha": self.sha}, "mergeable": self.mergeable, "body": self.body}
        if method == "GET" and path == "/issues/8/comments":
            page, per_page = request["params"]["page"], request["params"]["per_page"]
            start = (page - 1) * per_page
            return self.comments[start:start + per_page]
        if method == "GET" and path.startswith("/commits/"):
            if self.tests == "not run":
                return {"check_runs": []}
            if self.tests == "running":
                return {"check_runs": [{"id": 1, "status": "in_progress", "conclusion": None}]}
            return {"check_runs": [{"id": 1, "status": "completed",
                                    "conclusion": "success" if self.tests == "passed" else "failure"}]}
        if method == "PUT" and self.merge_fails:
            raise decisions.requests.HTTPError("405")
        if method == "PATCH" and self.close_fails:
            raise decisions.requests.HTTPError("405")
        self.writes.append((method, path, request.get("json")))
        if method == "POST" and path == "/issues/8/comments":
            self.comments.append({"body": request["json"]["body"]})
        return None


def decide_finding(monkeypatch, github, finding, choice):
    monkeypatch.setattr(decisions, "_ask", github)
    return decisions.decide_finding("t", FINDINGS_ITEM, finding, choice, "Checked against the source", "A Member", NOW)


def test_approving_one_of_two_findings_writes_its_comment_only(monkeypatch):
    github = FindingsGitHub()

    status, words = decide_finding(monkeypatch, github, FINDING_ITEM, APPROVE)

    assert status == "ok" and "merges when its other 1 finding is approved" in words
    assert [(m, p) for m, p, _ in github.writes] == [("POST", "/issues/8/comments")]


def test_approving_the_last_finding_writes_two_comments_then_merges(monkeypatch):
    github = FindingsGitHub(comments=[{"body": finding_comment(APPROVE, "R723", "sha8")}])

    status, words = decide_finding(monkeypatch, github, FINDING_ITEM, APPROVE)

    assert status == "ok" and "Every finding of pull request 8 is approved, so it is merged" in words
    assert [(m, p) for m, p, _ in github.writes] == [("POST", "/issues/8/comments"), ("POST", "/issues/8/comments"),
                                                      ("PUT", "/pulls/8/merge")]
    assert "Every finding was approved: R723, R809." in github.writes[1][2]["body"]
    assert github.writes[2][2] == {"merge_method": "squash", "sha": "sha8"}


def test_approving_the_last_finding_before_tests_pass_still_records_the_finding_and_warns(monkeypatch):
    github = FindingsGitHub(comments=[{"body": finding_comment(APPROVE, "R723", "sha8")}], tests="failed")

    status, words = decide_finding(monkeypatch, github, FINDING_ITEM, APPROVE)

    assert status == "warn"
    assert "Approved, and recorded. Pull request 8 is not merged yet" in words and "tests have passed" in words
    assert [(m, p) for m, p, _ in github.writes] == [("POST", "/issues/8/comments")]


def test_rejecting_one_of_two_findings_writes_its_comment_and_stays_open(monkeypatch):
    github = FindingsGitHub()

    status, words = decide_finding(monkeypatch, github, FINDING_ITEM, REJECT)

    assert status == "ok" and "stays open but will not merge while a finding is rejected" in words
    assert [(m, p) for m, p, _ in github.writes] == [("POST", "/issues/8/comments")]


def test_approving_a_finding_when_another_is_rejected_says_which_finding_blocks_merge(monkeypatch):
    github = FindingsGitHub(comments=[{"body": finding_comment(REJECT, "R723", "sha8")}])

    status, words = decide_finding(monkeypatch, github, FINDING_ITEM, APPROVE)

    assert status == "ok" and words == "Approved. Pull request 8 cannot merge while finding R723 is rejected."
    assert [(m, p) for m, p, _ in github.writes] == [("POST", "/issues/8/comments")]


def test_rejecting_the_last_remaining_finding_closes_the_pull_request(monkeypatch):
    github = FindingsGitHub(comments=[{"body": finding_comment(REJECT, "R723", "sha8")}])

    status, words = decide_finding(monkeypatch, github, FINDING_ITEM, REJECT)

    assert status == "ok" and "Every finding of pull request 8 is rejected, so it is closed" in words
    assert [(m, p) for m, p, _ in github.writes] == [("POST", "/issues/8/comments"), ("POST", "/issues/8/comments"),
                                                      ("PATCH", "/pulls/8")]


def test_deciding_a_finding_on_an_old_sha_is_refused_and_writes_nothing(monkeypatch):
    github = FindingsGitHub(sha="new-sha")

    status, words = decide_finding(monkeypatch, github, SIGNAL_ITEM, APPROVE)

    assert status == "warn" and "changed after the page read it" in words and github.writes == []


def test_deciding_a_finding_when_findings_ids_changed_is_refused_and_writes_nothing(monkeypatch):
    github = FindingsGitHub(body=findings_body([R809_FINDING]))

    status, words = decide_finding(monkeypatch, github, FINDING_ITEM, APPROVE)

    assert status == "warn" and "findings changed after the page read them" in words and github.writes == []


def test_finish_merges_when_every_finding_is_approved(monkeypatch):
    github = FindingsGitHub(comments=[{"body": finding_comment(APPROVE, "R723", "sha8")},
                                      {"body": finding_comment(APPROVE, "R809", "sha8")}])
    monkeypatch.setattr(decisions, "_ask", github)

    status, words = decisions.finish("t", FINDINGS_ITEM, "A Member", NOW)

    assert status == "ok" and "Every finding of pull request 8 is approved, so it is merged" in words
    assert [(m, p) for m, p, _ in github.writes] == [("POST", "/issues/8/comments"), ("PUT", "/pulls/8/merge")]


def test_finish_refuses_when_findings_are_mixed(monkeypatch):
    github = FindingsGitHub(comments=[{"body": finding_comment(APPROVE, "R723", "sha8")}])
    monkeypatch.setattr(decisions, "_ask", github)

    status, words = decisions.finish("t", FINDINGS_ITEM, "A Member", NOW)

    assert status == "warn" and "not every finding is approved or rejected yet" in words and github.writes == []
