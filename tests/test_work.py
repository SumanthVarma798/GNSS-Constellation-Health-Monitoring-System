"""The work in the private mirror (evidence/work.py): open issues and pull requests as rows."""
from datetime import datetime, timezone

from evidence import work

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def issue(number, title, updated="2026-10-19T00:00:00Z", labels=(), pull=False, login="SumanthVarma798"):
    found = {"number": number, "title": title, "user": {"login": login}, "comments": 2, "created_at": "2026-10-01T00:00:00Z",
             "updated_at": updated, "html_url": f"https://github.com/x/issues/{number}",
             "labels": [{"name": n, "color": c} for n, c in labels]}
    return {**found, "pull_request": {}} if pull else found


def test_pull_requests_listed_among_issues_are_left_out_page_by_page(monkeypatch):
    pages = {1: [issue(n, "x") for n in range(99)] + [issue(99, "a pull request", pull=True)], 2: [issue(100, "last")]}
    monkeypatch.setattr(work.github_api, "ask", lambda method, path, token, params: pages[params["page"]])

    got = work.fetch_open_issues("t")

    assert len(got) == 100 and all("pull_request" not in i for i in got)


def test_issues_come_most_recently_updated_first_and_can_be_found_by_title():
    issues = [issue(1, "Old work", updated="2026-10-01T00:00:00Z"), issue(2, "Fresh work", updated="2026-10-20T08:00:00Z")]

    assert [r["number"] for r in work.issue_rows(issues, NOW)] == [2, 1]
    assert [r["number"] for r in work.issue_rows(issues, NOW, find="OLD")] == [1]
    assert work.issue_rows(issues, NOW)[1]["updated_days"] == 19


def test_a_label_colour_that_is_not_six_hex_digits_is_left_grey():
    assert work.labels(issue(1, "x", labels=[("bug", "d73a4a"), ("odd", "red;}")])) == [("bug", "#d73a4a"), ("odd", "#8a8a8a")]


def test_a_pull_request_says_whether_it_waits_on_a_decision():
    prs = [{**issue(7, "Registry update", labels=[("decision: registry update", "7fb0ff")], login="github-actions[bot]"), "draft": False},
           {**issue(8, "Some code", updated="2026-10-20T00:00:00Z"), "draft": True}]

    rows = {r["number"]: r for r in work.pull_rows(prs, NOW)}

    assert rows[7]["decision"] == "registry update" and rows[7]["by"] == "the weekly job"
    assert rows[8]["decision"] is None and rows[8]["draft"]


def test_ages_read_naturally():
    assert [work.age_words(d) for d in (0, 1, 12)] == ["today", "1 day", "12 days"]
