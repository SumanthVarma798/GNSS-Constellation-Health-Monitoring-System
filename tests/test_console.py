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
from evidence import decisions, jobs
from evidence.decision_settings import AFTER_CHANGES, APPROVE, KINDS, LABEL_PREFIX
from test_dashboard_shell import segmented_controls_rerun  # noqa: F401  (AppTest 1.45's segmented controls)
from test_decisions import NOW, pr
from test_jobs import LOG, RUNS, WORKFLOWS
from ui import admin

ROOT = Path(__file__).resolve().parent.parent
SECRETS = {"auth": {field: "set" for field in common.SIGN_IN_FIELDS},
           "admin": {"allowed": ["member@example.com"], "github_token": "t0ken"}}


class GitHub:
    """Stands in for console.common.github: the figures above, and any pull requests a test gives it."""

    def __init__(self, prs=(), fail=None, issues=()):
        self.prs, self.fail, self.asked, self.issues = list(prs), fail, 0, list(issues)

    def __call__(self, token):
        self.asked += 1
        if self.fail:
            raise self.fail
        return {"workflows": WORKFLOWS, "runs": RUNS, "log": jobs.run_log(LOG), "prs": self.prs, "issues": self.issues,
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


# ---- approvals ----

REGISTRY_PR = pr(5, ["decision: registry update"], title="Registry update from the IGS satellite metadata file",
                 body="This is a proposed update.\n\n## What changed\n- G01: slot was blank, now A1.")


def test_approvals_list_each_waiting_item_with_its_evidence(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    at = run(monkeypatch, GitHub([REGISTRY_PR, pr(6, ["enhancement"], title="Some code change")]), page="console/approvals.py")

    page = text(at)
    assert "Registry update from the IGS satellite metadata file" in page and "Some code change" not in page
    assert "<li>G01: slot was blank, now A1.</li>" in page and "pull request 5" in page


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

    token, item, choice, reason, changes, who, email, accounts, _ = decided[0]
    assert (token, item["number"], choice, reason, who, email) == (
        "t0ken", 5, APPROVE, "Checked against the IGS file", "A Member", "member@example.com")
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
        if "update-tle-data" in path:
            raise requests.HTTPError("404", response=SimpleNamespace(status_code=404))
        return {"workflow_runs": [], "workflows": []}

    monkeypatch.setattr(common.github_api, "ask", ask)
    monkeypatch.setattr(common.github_api, "file_text", lambda *args: "job,started,ended,result,changed\n")
    monkeypatch.setattr(decisions, "fetch_open", lambda token: [])

    seen = common.github.__wrapped__("t") if hasattr(common.github, "__wrapped__") else common.github("t")

    assert any("update-tle-data.yml" in problem for problem in seen["problems"])


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
def test_the_system_design_page_opens_with_its_picture(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    at = run(monkeypatch, page="console/design.py")

    assert "How the system works" in text(at) and at.get("iframe")


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
