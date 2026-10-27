"""The administration console (admin.py, console/*): who gets in, what each page shows, and deciding on a change.

GitHub is never called: console.common.github is replaced by a stand-in that answers from the figures below.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
import streamlit
from streamlit.testing.v1 import AppTest

from console import common
from evidence import alerts, decisions, jobs, pipeline as live_pipeline
from evidence.decision_settings import AFTER_CHANGES, APPROVE, KINDS, LABEL_PREFIX, REJECT
from test_dashboard_shell import segmented_controls_rerun  # noqa: F401  (AppTest 1.45's segmented controls)
from test_decisions import FINDINGS_STAND_IN, NOW, finding_comment, findings_body, pr
from test_jobs import LOG, RUNS, WORKFLOWS, run as workflow_run
from ui import admin, console as ui_console

ROOT = Path(__file__).resolve().parent.parent
SECRETS = {"auth": {field: "set" for field in common.SIGN_IN_FIELDS},
           "admin": {"allowed": ["member@example.com"], "github_token": "t0ken"}}


class GitHub:
    """Stands in for console.common.github: the figures above, and any pull requests a test gives it."""

    def __init__(self, prs=(), fail=None, issues=(), comments=None):
        self.prs, self.fail, self.asked, self.issues = list(prs), fail, 0, list(issues)
        self.comments = comments or {}

    def __call__(self, token):
        self.asked += 1
        if self.fail:
            raise self.fail
        return {"workflows": WORKFLOWS, "runs": RUNS, "log": jobs.run_log(LOG), "prs": self.prs, "decision_prs": self.prs,
                "comments": self.comments,
                "issues": self.issues, "archive_commits": {},
                "problems": [], "read_at": NOW}

    def clear(self):
        pass


@pytest.fixture(autouse=True)
def fresh_reading():
    streamlit.cache_data.clear()


def signed_in(monkeypatch, email, name="A Member"):
    user = {"email": email, "name": name} if email else {}
    monkeypatch.setattr(streamlit, "user", SimpleNamespace(is_logged_in=bool(email), get=user.get))


def run(monkeypatch, github=None, secrets=SECRETS, page=None, then=None):
    monkeypatch.setattr(common, "github", github or GitHub())
    at = AppTest.from_file(str(ROOT / "admin.py"), default_timeout=60)
    at.secrets = secrets
    at.run()
    if page:
        at.switch_page(page).run()
    if then:
        then(at)
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def text(at):
    return " ".join(part.proto.body for part in at.get("html"))


# ---- who gets in ----

def test_without_its_settings_the_console_says_it_is_not_set_up(monkeypatch):
    signed_in(monkeypatch, None)

    at = run(monkeypatch, secrets={"admin": {"allowed": ["member@example.com"]}})

    page = text(at)
    assert "not set up" in page and not at.button
    assert "[auth] client_id" in page and "[admin] github_token" in page and "[admin] allowed" not in page


def test_a_sign_in_block_with_an_empty_field_counts_as_not_set_up(monkeypatch):
    signed_in(monkeypatch, None)

    at = run(monkeypatch, secrets={**SECRETS, "auth": {**SECRETS["auth"], "client_secret": ""}})

    page = text(at)
    assert "Missing or empty: [auth] client_secret." in page   # named, and only that one
    assert "t0ken" not in page   # names only, never a value


def test_someone_not_signed_in_is_offered_google_sign_in_and_github_is_not_read(monkeypatch):
    signed_in(monkeypatch, None)
    github = GitHub()

    at = run(monkeypatch, github)

    assert [b.label for b in at.button] == ["Sign in with Google"] and github.asked == 0


def test_someone_not_on_the_list_is_told_so_and_github_is_not_read(monkeypatch):
    signed_in(monkeypatch, "stranger@example.com")
    github = GitHub()

    at = run(monkeypatch, github)

    assert "stranger@example.com, which is not on the list" in text(at)
    assert [b.label for b in at.button] == ["Sign out"] and github.asked == 0


def test_a_signed_in_name_is_shown_as_plain_text(monkeypatch):
    signed_in(monkeypatch, "member@example.com", name="<b>Member</b>")

    assert "Signed in as <b>&lt;b&gt;Member&lt;/b&gt;</b>" in text(run(monkeypatch))


# ---- the pages ----

def test_the_summary_puts_what_needs_attention_first_and_the_status_bar_counts_it(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    page = text(run(monkeypatch))

    assert page.index("Needs attention") < page.index("At a glance") < page.index("Recent events")
    assert "Archive: news: failed: 6 of 44 sources" in page and "Update orbit data is turned off on GitHub" in page
    assert "candidate sources do not answer" in page and "No decisions waiting" in page
    assert "1 job failing" in page and "1 turned off" in page and "0 waiting for a decision" in page


def test_the_jobs_page_lists_every_job_with_its_schedule_in_words(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    page = text(run(monkeypatch, page="console/jobs.py"))

    for words in ("Archive: documents", "daily 00:30", "every 3 hours from 00:50", "Sundays 01:00", "Turned off",
                  "Reliability, day by day", "Run log", "failed: 6 of 44 sources"):
        assert words in page, words


def test_the_admin_console_lists_the_alerts_page(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    at = run(monkeypatch, page="console/alerts.py")

    page = text(at)
    assert "Alerts" in page and "Healthchecks.io checks" in page


def test_alerts_page_handles_a_malformed_healthchecks_answer(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(alerts, "read_checks", lambda key: {"oops": 1})

    page = text(run(monkeypatch, page="console/alerts.py", secrets={**SECRETS, "alerts": {"key": "s3cr3t-key"}}))

    assert "Healthchecks.io did not answer" in page
    assert "Checks are not available right now." in page


def test_alerts_page_with_a_key_lists_checks_and_missing_slugs_without_showing_the_key(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    checks = [
        {"slug": "archive-documents", "name": "Archive documents", "unique_key": "u-docs", "status": "up",
         "last_ping": "2026-10-20T10:00:00Z", "next_ping": "2026-10-20T13:00:00Z"},
        {"slug": "archive-catalogues", "name": "Archive catalogues", "unique_key": "u-catalogues", "status": "up",
         "last_ping": "2026-10-20T10:00:00Z", "next_ping": "2026-10-20T13:00:00Z"},
        {"slug": "archive-orbital", "name": "Archive orbital", "unique_key": "u-orbital", "status": "up",
         "last_ping": "2026-10-20T10:00:00Z", "next_ping": "2026-10-20T13:00:00Z"},
        {"slug": "archive-social", "name": "Archive social", "unique_key": "u-social", "status": "up",
         "last_ping": "2026-10-20T10:00:00Z", "next_ping": "2026-10-20T13:00:00Z"},
        {"slug": "registry-update", "name": "Registry update", "unique_key": "u-registry", "status": "up",
         "last_ping": "2026-10-20T10:00:00Z", "next_ping": "2026-10-20T13:00:00Z"},
        {"slug": "update-tle-data", "name": "Update TLE data", "unique_key": "u-tle", "status": "up",
         "last_ping": "2026-10-20T10:00:00Z", "next_ping": "2026-10-20T13:00:00Z"},
        {"slug": "orbit-ages", "name": "Orbit ages", "unique_key": "u-ages", "status": "up",
         "last_ping": "2026-10-20T10:00:00Z", "next_ping": "2026-10-20T13:00:00Z"},
        {"slug": "orbit-fresh", "name": "Orbit fresh", "unique_key": "u-fresh", "status": "up",
         "last_ping": "2026-10-20T10:00:00Z", "next_ping": "2026-10-20T13:00:00Z"},
        {"slug": "rinex-check", "name": "RINEX check", "unique_key": "u-rinex", "status": "up",
         "last_ping": "2026-10-20T10:00:00Z", "next_ping": "2026-10-20T13:00:00Z"},
        {"slug": "extra-watch", "name": "Extra watch", "unique_key": "u-extra", "status": "down",
         "last_ping": "2026-10-20T10:00:00Z", "next_ping": "2026-10-20T13:00:00Z"},
    ]
    flips = {"u-extra": [{"up": 0}], "u-docs": [{"up": 1}]}
    monkeypatch.setattr(alerts, "read_checks", lambda key: checks)
    monkeypatch.setattr(alerts, "read_flips", lambda key, unique_key, seconds: flips.get(unique_key, []))

    page = text(run(monkeypatch, page="console/alerts.py", secrets={**SECRETS, "alerts": {"key": "s3cr3t-key"}}))

    assert "Healthchecks.io checks" in page and "Down, last 14 days" in page
    assert "No check on Healthchecks.io for: archive-news." in page
    assert "extra-watch" in page
    assert "s3cr3t-key" not in page


def test_when_github_cannot_be_read_the_page_says_why_without_the_token(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    page = text(run(monkeypatch, GitHub(fail=requests.HTTPError("404", response=SimpleNamespace(status_code=404)))))

    assert "may not have access to that repository" in page and "t0ken" not in page


@pytest.mark.parametrize("scheme, dark_always", [("light", False), ("dark", True)])
def test_light_and_dark_can_be_chosen_and_auto_follows_the_computer(monkeypatch, scheme, dark_always):
    signed_in(monkeypatch, "member@example.com")

    def pick(at):
        at.session_state["console_scheme"] = scheme

    style = text(run(monkeypatch, then=pick))

    assert ("--pane: #0d1117" in style.split("@media")[0]) is dark_always
    assert "prefers-color-scheme" not in style


def test_the_ask_about_section_styles_follow_the_console_palette():
    css = (ROOT / "ui" / "console.css").read_text()

    for selector in ('[data-testid="stHeading"]', '[data-testid="stCaptionContainer"]',
                     '[data-testid="stAlertContainer"]', '[data-testid="stChatMessage"]',
                     '[data-testid="stChatInput"]', '[data-testid="stSpinner"]'):
        assert selector in css
    assert '[data-testid="stHeading"], [data-testid="stCaptionContainer"], [data-testid="stSpinner"] { color: var(--ink); }' in css
    assert '[data-testid="stCaptionContainer"] { color: var(--muted); }' in css
    assert '[data-testid="stChatInputTextArea"] { background: var(--input-bg) !important; color: var(--ink) !important;' in css
    assert '.c-sect > .in.flush { padding: 0; display: flow-root; }' in css
    assert '[data-testid="stButtonGroup"] [data-baseweb="button-group"] { display: flex; flex-wrap: wrap;' in css
    assert '.c-subhead { margin: 8px 0 4px; font-size: 12px; font-weight: 800; color: var(--ink); }' in css


# ---- approvals ----

REGISTRY_PR = pr(5, ["decision: registry update"], title="Registry update from the IGS satellite metadata file",
                 body="This is a proposed update.\n\n## What changed\n- G01: slot was blank, now A1.")
FINDINGS_PR = pr(8, ["decision: registry update"], title="Weekly registry findings",
                 body=findings_body(FINDINGS_STAND_IN))


def test_approvals_list_each_waiting_item_with_its_evidence(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    at = run(monkeypatch, GitHub([REGISTRY_PR, pr(6, ["enhancement"], title="Some code change")]), page="console/approvals.py")

    page = text(at)
    assert "Registry update from the IGS satellite metadata file" in page and "Some code change" not in page
    assert "<li>G01: slot was blank, now A1.</li>" in page and "pull request 5" in page


def test_approvals_show_findings_by_category_before_old_style_items(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    findings = [{**FINDINGS_STAND_IN[0], "statement": "We saw <script>alert(1)</script> in one source."},
                FINDINGS_STAND_IN[1]]
    findings_pr = {**FINDINGS_PR, "body": findings_body(findings)}
    at = run(monkeypatch, GitHub([findings_pr, REGISTRY_PR], comments={8: []}), page="console/approvals.py")

    page = text(at)
    assert "New satellite" in page and "Signal ID change" in page
    assert "Pull request 5: Registry update from the IGS satellite metadata file" in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page and "<script>alert(1)</script>" not in page


def test_a_finding_stays_open_once_a_decision_on_it_is_under_way(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    at = run(monkeypatch, GitHub([FINDINGS_PR], comments={8: []}), page="console/approvals.py")
    assert not any(e.proto.expanded for e in at.expander)

    at.radio(key=f"finding_choice_8_{FINDINGS_STAND_IN[0]['id']}").set_value(APPROVE).run()

    opened = [e.label for e in at.expander if e.proto.expanded]
    assert opened == [f"{FINDINGS_STAND_IN[0]['id']}: sources, what we measured, decision"]


def test_approvals_show_a_finding_result_notice_once_at_the_top_of_the_findings_area(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    def after_read(at):
        at.session_state["admin_finding_result"] = ((8, "R809"), "ok", "Approved one finding.")

    at = run(monkeypatch, GitHub([FINDINGS_PR], comments={8: [{"body": finding_comment(APPROVE, "R809", "sha8")}]}),
             page="console/approvals.py", then=after_read)

    assert "Approved one finding." in text(at)
    assert "admin_finding_result" not in at.session_state


def test_approvals_show_a_finish_notice_and_merge_button_when_all_findings_are_approved(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    comments = {8: [{"body": finding_comment(APPROVE, "R809", "sha8")},
                    {"body": finding_comment(APPROVE, "R723", "sha8")}]}

    at = run(monkeypatch, GitHub([FINDINGS_PR], comments=comments), page="console/approvals.py")

    page = text(at)
    assert "Pull request 8: every finding is approved, but it is not merged yet." in page
    assert [b.label for b in at.button if b.key == "finish_8"] == ["Merge pull request 8"]


def test_the_finish_button_calls_finish_and_shows_its_result_notice(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    comments = {8: [{"body": finding_comment(REJECT, "R809", "sha8")},
                    {"body": finding_comment(REJECT, "R723", "sha8")}]}
    called = []
    monkeypatch.setattr(decisions, "finish", lambda *args: called.append(args) or ("ok", "Closed from Findings."))
    at = run(monkeypatch, GitHub([FINDINGS_PR], comments=comments), page="console/approvals.py")

    at.button(key="finish_8").click().run()

    token, item, who, _ = called[0]
    assert (token, item["number"], who) == ("t0ken", 8, "A Member")
    assert "Closed from Findings." in text(at)


def test_finding_statement_is_listed_once_and_expander_label_uses_the_finding_id(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    at = run(monkeypatch, GitHub([FINDINGS_PR], comments={8: []}), page="console/approvals.py")
    page = text(at)

    assert page.count(FINDINGS_STAND_IN[0]["statement"]) == 1
    assert "R809: sources, what we measured, decision" in [expander.label for expander in at.expander]


def test_the_reason_box_appears_only_once_a_choice_is_made(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    at = run(monkeypatch, GitHub([REGISTRY_PR]), page="console/approvals.py")
    assert not at.text_area

    at.radio(key="choice_5").set_value(AFTER_CHANGES).run()

    assert [t.label for t in at.text_area] == ["Reason (every decision needs one)", "Changes asked for"]


def test_recording_a_decision_passes_who_decided_and_says_what_happened(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    decided = []
    monkeypatch.setattr(decisions, "decide", lambda *args: decided.append(args) or ("ok", "Approved and merged."))
    at = run(monkeypatch, GitHub([REGISTRY_PR]), page="console/approvals.py")

    at.radio(key="choice_5").set_value(APPROVE).run()
    at.text_area(key="reason_5").set_value("Checked against the IGS file")
    at.button(key="record_5").click().run()

    token, item, choice, reason, changes, who, _ = decided[0]
    assert (token, item["number"], choice, reason, who) == ("t0ken", 5, APPROVE, "Checked against the IGS file", "A Member")
    assert "Approved and merged." in text(at)


def test_a_decision_that_cannot_go_through_is_said_beside_its_item_and_the_choice_is_kept(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(decisions, "decide", lambda *args: ("warn", "Write the reason first: every decision needs one."))
    at = run(monkeypatch, GitHub([REGISTRY_PR]), page="console/approvals.py")

    at.radio(key="choice_5").set_value(APPROVE).run()
    at.button(key="record_5").click().run()

    assert "Write the reason first" in text(at) and at.radio(key="choice_5").value == APPROVE


# ---- parts that stand alone ----

def test_pull_request_text_is_read_as_plain_text_except_headings_lists_bold_and_web_links():
    html = admin.text_html('## What changed\n- **G01**: <script>x</script>\n\n'
                           '[archived copy](https://example.org/a?b=1&c=2) [bad](javascript:alert(1))\n\n    IGS line')

    assert "<h4>What changed</h4>" in html and "<li><b>G01</b>: &lt;script&gt;x&lt;/script&gt;</li>" in html
    assert '<a href="https://example.org/a?b=1&amp;c=2"' in html and 'href="javascript' not in html
    assert "<pre>IGS line</pre>" in html


def test_the_dashboard_no_longer_has_an_admin_tab():
    from ui.shell import OWN_FILTERS, PAGES

    assert "Admin" not in OWN_FILTERS and all("admin" not in path for _, path in PAGES)


def test_the_weekly_registry_job_labels_its_pull_request_and_starts_its_tests():
    registry = (ROOT / ".github/workflows/registry-update.yml").read_text()
    tests = (ROOT / ".github/workflows/tests.yml").read_text()

    assert f'--label "{LABEL_PREFIX}registry update"' in registry and "registry update" in KINDS
    assert "gh workflow run tests.yml --ref registry-update" in registry and "actions: write" in registry
    assert "workflow_dispatch:" in tests


def test_google_sign_in_keeps_its_state_with_the_installed_authlib():
    """Streamlit 1.45 passes no session; Authlib 1.6.6+ writes to one anyway, and sign-in failed with "'NoneType'
    object does not support item assignment". ui/sign_in_fix.py keeps the state in the cache, as Streamlit 1.53 does."""
    from streamlit.web.server.authlib_tornado_integration import TornadoIntegration

    from ui import sign_in_fix

    assert sign_in_fix.needed(), "Streamlit now has this fix itself: delete ui/sign_in_fix.py and its two uses"
    sign_in_fix.apply()

    class Cache:   # like Streamlit's AuthCache: a plain object, so it is never empty-and-false like a dict
        def __init__(self):
            self.kept = {}

        def get(self, key):
            return self.kept.get(key)

        def set(self, key, value, expires=None):
            self.kept[key] = value

        def delete(self, key):
            self.kept.pop(key, None)

    sign_in = TornadoIntegration("google", cache=Cache())
    sign_in.set_state_data(None, "state", {"nonce": "n"})

    assert sign_in.get_state_data(None, "state") == {"nonce": "n"}
    sign_in.clear_state_data(None, "state")
    assert sign_in.get_state_data(None, "state") is None


def test_runs_are_read_page_by_page_and_the_tests_on_main_on_their_own(monkeypatch):
    asked = []

    def ask(method, path, token, repository=None, **request):
        asked.append((path, request["params"]))
        page = request["params"].get("page", 1)
        return {"workflow_runs": [{}] * (100 if page == 1 and "archive" in path else 3)}

    monkeypatch.setattr(common.github_api, "ask", ask)

    assert len(common._runs("t", "archive.yml")) == 103 and len(common._runs("t", "tests.yml")) == 3
    assert asked[0][1]["created"].startswith(">=") and asked[1][1]["page"] == 2
    assert asked[2][1] == {"branch": "main", "event": "push", "per_page": 10}


def test_a_workflow_missing_on_github_is_named_and_the_rest_still_shows(monkeypatch):
    def ask(method, path, token, repository=None, **request):
        if path == "/commits":
            return []
        if "update-tle-data" in path:
            raise requests.HTTPError("404", response=SimpleNamespace(status_code=404))
        return {"workflow_runs": [], "workflows": []}

    monkeypatch.setattr(common.github_api, "ask", ask)
    monkeypatch.setattr(common.github_api, "file_text", lambda *args: "job,started,ended,result,changed\n")
    monkeypatch.setattr(decisions, "fetch_open", lambda token: [])
    monkeypatch.setattr(decisions, "fetch_recent_closed", lambda token: [])

    seen = common.github.__wrapped__("t") if hasattr(common.github, "__wrapped__") else common.github("t")

    assert any("update-tle-data.yml" in problem for problem in seen["problems"])


def test_github_reads_comments_only_for_open_decision_pull_requests_with_findings_blocks(monkeypatch):
    called = []

    monkeypatch.setattr(decisions, "fetch_open", lambda token: [FINDINGS_PR, REGISTRY_PR, pr(9, ["enhancement"])])
    monkeypatch.setattr(decisions, "fetch_recent_closed", lambda token: [])
    monkeypatch.setattr(decisions, "fetch_comments", lambda token, number: called.append(number) or [{"id": number}])
    monkeypatch.setattr(common.github_api, "ask", lambda *args, **kwargs: {"workflows": [], "workflow_runs": []})
    monkeypatch.setattr(common.github_api, "file_text", lambda *args: "job,started,ended,result,changed\n")
    monkeypatch.setattr(common.work, "fetch_open_issues", lambda token: [])
    monkeypatch.setattr(common, "_archive_commits", lambda token: {})

    seen = common.github.__wrapped__("t") if hasattr(common.github, "__wrapped__") else common.github("t")

    assert called == [8]
    assert seen["comments"] == {8: [{"id": 8}]}


def test_the_work_page_lists_open_pull_requests_and_issues_and_finds_by_title(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    issues = [{"number": 87, "title": "Signal-to-noise per source", "user": {"login": "SumanthVarma798"}, "comments": 0,
               "created_at": "2026-10-19T16:04:46Z", "updated_at": "2026-10-19T16:04:46Z", "html_url": "https://github.com/x/issues/87",
               "labels": []},
              {"number": 47, "title": "Demo tracker", "user": {"login": "SumanthVarma798"}, "comments": 4,
               "created_at": "2026-10-10T00:00:00Z", "updated_at": "2026-10-20T07:00:00Z", "html_url": "https://github.com/x/issues/47",
               "labels": [{"name": "documentation", "color": "0075ca"}]}]
    at = run(monkeypatch, GitHub([REGISTRY_PR], issues=issues), page="console/work.py")

    page = text(at)
    assert "Registry update from the IGS satellite metadata file" in page and "waits on a decision: registry update" in page
    assert page.index("Demo tracker") < page.index("Signal-to-noise per source")   # the most recently updated first
    assert "background:#0075ca" in page

    at.text_input(key="work_find").set_value("signal").run()
    assert "Signal-to-noise per source" in text(at) and "Demo tracker" not in text(at)


def test_the_summary_leads_with_one_figure_and_draws_grades_in_one_blue_ramp(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    page = text(run(monkeypatch))

    assert page.count('class="c-hero') == 1 and "things need a look" in page
    assert "var(--g-a)" in page and "var(--c-ok)\" title=\"A" not in page


def test_an_answer_github_gives_in_another_shape_is_said_plainly(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    assert "not in the shape the console expects" in text(run(monkeypatch, GitHub(fail=KeyError("workflows"))))


def test_the_hero_says_in_words_whether_any_of_it_is_failing(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    assert "things need a look, 1 of them failing" in text(run(monkeypatch))


def test_refresh_reads_github_again_and_shows_when_it_was_read(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    github = GitHub()
    at = run(monkeypatch, github)
    asked = github.asked
    assert not at.toast

    at.button(key="console_refresh").click().run()

    assert github.asked > asked
    assert at.toast and "Read again from GitHub at" in at.toast[0].value


def test_the_system_design_page_opens_with_its_picture(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    at = run(monkeypatch, page="console/design.py")

    assert "How the system works" in text(at) and at.get("iframe")


def test_the_live_pipeline_page_opens_with_its_sections_and_links(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    at = run(monkeypatch, page="console/pipeline.py")
    page = text(at)
    links = [link.label for link in at.get("page_link")]

    assert "Live pipeline" in page
    assert "Running now" in page and "Next up" in page and "Proof of work" in page
    assert "Collect official documents" in page and "Collect news" in page
    assert "Open proof" not in page
    assert at.get("iframe")
    assert links == ["Jobs", "Approvals"]


def test_the_live_pipeline_component_defaults_to_what_runs_next(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    stage_rows = live_pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [], common.workflow_texts(), NOW)
    upcoming = live_pipeline.what_next(stage_rows, NOW, hours=24)
    expected = upcoming[0]["key"] if upcoming else stage_rows[0]["key"]

    at = run(monkeypatch, page="console/pipeline.py")
    frame = at.get("iframe")[0].proto.srcdoc

    assert '"default_key"' in frame and expected in frame


def test_the_live_pipeline_component_defaults_to_the_stage_running_now(monkeypatch):
    class RunningGitHub(GitHub):
        def __call__(self, token):
            seen = super().__call__(token)
            seen["runs"] = [workflow_run("registry-update.yml", "2026-10-20T14:30:00Z", status="in_progress"),
                            *seen["runs"]]
            return seen

    signed_in(monkeypatch, "member@example.com")
    at = run(monkeypatch, github=RunningGitHub(), page="console/pipeline.py")
    frame = at.get("iframe")[0].proto.srcdoc

    assert '"default_key"' in frame and "registry_update" in frame


def test_the_live_pipeline_uses_clear_fallback_words_for_proof_links(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    page = text(run(monkeypatch, page="console/pipeline.py"))

    assert "GitHub run" in page and ">run</a>" not in page


def test_the_pipeline_diagram_numbers_the_chain_without_dangling_right_arrows():
    stage_rows = live_pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [], common.workflow_texts(), NOW)
    picture = ui_console.pipeline_diagram(stage_rows)
    chain_names = ["Archive", "Registry update", "Pull request waiting for a decision",
                   "Decided on the Approvals page", "Merged to main", "Dashboard"]

    assert picture.count("c-pipe-arrow") == 1
    assert picture.count('class="order"') == len(chain_names)


def test_the_pipeline_diagram_does_not_hide_stage_words_from_screen_readers():
    stage_rows = live_pipeline.stages(WORKFLOWS, RUNS, jobs.run_log(LOG), [], common.workflow_texts(), NOW)
    picture = ui_console.pipeline_diagram(stage_rows)

    assert 'role="img"' not in picture
    assert "Archive: documents" in picture
    assert "Registry update" in picture


def test_back_and_forward_follow_the_pages_visited_and_the_browser_own_buttons():
    trail = {"back": [], "forward": [], "at": None}
    for path in ("", "jobs", "work"):
        common.follow(trail, path)
    assert trail == {"back": ["", "jobs"], "forward": [], "at": "work"}

    common.follow(trail, "jobs")   # back one step
    assert trail == {"back": [""], "forward": ["work"], "at": "jobs"}
    common.follow(trail, "work")   # forward again
    assert trail == {"back": ["", "jobs"], "forward": [], "at": "work"}
    common.follow(trail, "jobs")
    common.follow(trail, "approvals")   # somewhere new: forward is gone
    assert trail == {"back": ["", "jobs"], "forward": [], "at": "approvals"}
    common.follow(trail, "approvals")   # the same page again (a refresh) is no step
    assert trail["back"] == ["", "jobs"]


def test_back_and_forward_show_only_when_there_is_a_page_that_way(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    at = run(monkeypatch)
    assert not [b for b in at.button if b.key in ("console_back", "console_forward")]

    at.switch_page("console/jobs.py").run()
    assert [b.key for b in at.button if b.key in ("console_back", "console_forward")] == ["console_back"]
    assert "Monitoring › <b>Jobs</b>" in text(at)

    at.button(key="console_back").click().run()
    assert "Overview › <b>Summary</b>" in text(at)
    assert [b.key for b in at.button if b.key in ("console_back", "console_forward")] == ["console_forward"]


def test_back_is_not_offered_to_a_page_that_no_longer_exists(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    at = run(monkeypatch)
    at.session_state["console_trail"] = {"back": ["gone"], "forward": [], "at": ""}

    at.run()

    assert not at.exception and not [b for b in at.button if b.key == "console_back"]


def test_sign_out_forgets_the_session_and_signs_out(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    out = []
    monkeypatch.setattr(streamlit, "logout", lambda: out.append(True))
    at = run(monkeypatch)
    at.session_state["design_chat"] = [{"role": "user", "content": "kept?"}]

    at.button(key="console_sign_out").click().run()

    assert out == [True] and "design_chat" not in at.session_state


def test_a_secrets_file_that_cannot_be_read_is_named_with_its_line(monkeypatch):
    import toml
    from streamlit.errors import StreamlitSecretNotFoundError

    class Broken:
        def get(self, *_):
            try:
                toml.loads('a = "1"\na = "2"\n')
            except toml.TomlDecodeError as reason:
                raise StreamlitSecretNotFoundError("Error parsing secrets file") from reason

    monkeypatch.setattr(streamlit, "secrets", Broken())
    said = common.missing()[0]

    assert said.startswith("a readable secrets file (Duplicate keys!") and "line 2" in said and '"2"' not in said
