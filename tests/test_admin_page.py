"""The admin page (views/admin.py, ui/admin.py): who gets in, what they see, and that outside text stays plain text."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
import streamlit
from streamlit.testing.v1 import AppTest

from evidence import decisions
from evidence.decision_settings import AFTER_CHANGES, APPROVE, KINDS, LABEL_PREFIX
from test_dashboard_shell import segmented_controls_rerun  # noqa: F401  (AppTest 1.45's segmented controls)
from test_decisions import NOW, pr
from ui import admin

ROOT = Path(__file__).resolve().parent.parent
SECRETS = {"auth": {field: "set" for field in ("redirect_uri", "cookie_secret", "client_id", "client_secret",
                                              "server_metadata_url")},
           "admin": {"allowed": ["member@example.com"], "github_token": "t0ken"}}


@pytest.fixture(autouse=True)
def fresh_reading():
    streamlit.cache_data.clear()


def signed_in(monkeypatch, email):
    user = {"email": email, "name": "A Member"} if email else {}
    monkeypatch.setattr(streamlit, "user", SimpleNamespace(is_logged_in=bool(email), get=user.get))


def run(secrets=SECRETS, then=None):
    at = AppTest.from_file(str(ROOT / "views/admin.py"), default_timeout=60)
    at.secrets = secrets
    at.run()
    if then:
        then(at)
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def page_text(at):
    return " ".join(part.proto.body for part in at.get("html"))


def test_without_its_settings_the_page_says_it_is_not_set_up(monkeypatch):
    signed_in(monkeypatch, None)

    at = run({"admin": {"allowed": ["member@example.com"]}})   # no sign-in, no token

    assert "not set up on this computer" in page_text(at) and not at.button


def test_a_sign_in_block_with_an_empty_field_counts_as_not_set_up(monkeypatch):
    signed_in(monkeypatch, None)

    at = run({**SECRETS, "auth": {**SECRETS["auth"], "client_secret": ""}})

    assert "not set up on this computer" in page_text(at) and not at.button


def test_a_signed_in_name_is_shown_as_plain_text(monkeypatch):
    monkeypatch.setattr(streamlit, "user", SimpleNamespace(
        is_logged_in=True, get={"email": "member@example.com", "name": "<b>Member</b>"}.get))
    monkeypatch.setattr(decisions, "fetch_open", lambda token: [])

    assert "Signed in as &lt;b&gt;Member&lt;/b&gt;." in page_text(run())


def test_someone_not_signed_in_is_offered_google_sign_in_and_sees_no_items(monkeypatch):
    signed_in(monkeypatch, None)
    monkeypatch.setattr(decisions, "fetch_open", lambda token: pytest.fail("read GitHub before sign-in"))

    at = run()

    assert [b.label for b in at.button] == ["Sign in with Google"]


def test_someone_signed_in_but_not_on_the_list_is_told_so_and_sees_no_items(monkeypatch):
    signed_in(monkeypatch, "stranger@example.com")
    monkeypatch.setattr(decisions, "fetch_open", lambda token: pytest.fail("read GitHub for a stranger"))

    at = run()

    assert "stranger@example.com, which is not on the list" in page_text(at)
    assert [b.label for b in at.button] == ["Sign out"]


def test_a_member_sees_each_waiting_item_in_its_group(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(decisions, "fetch_open", lambda token: [
        pr(5, ["decision: registry update"], title="Registry update from the IGS satellite metadata file",
           body="This is a proposed update.\n\n## What changed\n- G01: slot was blank, now A1."),
        pr(6, ["enhancement"], title="Some code change")])

    text = page_text(run())

    assert "Registry update from the IGS satellite metadata file" in text and "Some code change" not in text
    assert "Satellites" in text and "waiting for a decision" in text and "Pull request 5 on GitHub" in text
    assert "<li>G01: slot was blank, now A1.</li>" in text   # the evidence, as reading, in its section


def test_with_nothing_waiting_a_member_is_told_so(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(decisions, "fetch_open", lambda token: [])

    assert "Nothing is waiting for a decision." in page_text(run())


def test_when_github_refuses_the_token_a_member_is_told_in_plain_words_without_the_token(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    def refuse(token):
        raise requests.HTTPError("401", response=SimpleNamespace(status_code=401))

    monkeypatch.setattr(decisions, "fetch_open", refuse)

    text = page_text(run())

    assert "GitHub refused the page" in text and "may have expired" in text and "t0ken" not in text


def test_pull_request_text_is_read_as_plain_text_except_headings_lists_bold_and_web_links():
    html = admin.text_html('## What changed\n- **G01**: <script>x</script>\n\n'
                           '[archived copy](https://example.org/a?b=1&c=2) [bad](javascript:alert(1))\n\n    IGS line')

    assert "<h4>What changed</h4>" in html and "<li><b>G01</b>: &lt;script&gt;x&lt;/script&gt;</li>" in html
    assert '<a href="https://example.org/a?b=1&amp;c=2"' in html and 'href="javascript' not in html
    assert "<pre>IGS line</pre>" in html


def test_a_card_escapes_its_title_and_says_how_long_it_waited():
    item = decisions.pending([pr(9, ["decision: slot"], created="2026-10-01T00:00:00Z", title="<b>x</b>")], NOW)[0]

    html = admin.card(item)

    assert "&lt;b&gt;x&lt;/b&gt;" in html and "waiting 19 days, past a fortnightly call" in html
    assert 'class="wait warn"' in html and "width:100%" in html


def test_the_weekly_registry_job_labels_its_pull_request_with_a_kind_the_page_knows():
    workflow = (ROOT / ".github/workflows/registry-update.yml").read_text()

    assert f'--label "{LABEL_PREFIX}registry update"' in workflow and "registry update" in KINDS


def one_waiting(monkeypatch, decided):
    signed_in(monkeypatch, "member@example.com")
    monkeypatch.setattr(decisions, "fetch_open", lambda token: [pr(5, ["decision: registry update"])])
    monkeypatch.setattr(decisions, "decide", lambda *args: decided.append(args) or ("ok", "Approved and merged."))


def test_the_reason_box_appears_only_once_a_choice_is_made(monkeypatch):
    one_waiting(monkeypatch, [])

    assert not run().text_area
    at = run(then=lambda at: at.session_state.__setitem__("choice_5", AFTER_CHANGES))
    assert [t.label for t in at.text_area] == ["Reason (every decision needs one)", "Changes asked for"]
    assert "and leaves it open until the changes are made" in page_text(at)


def test_recording_a_decision_passes_who_decided_and_says_what_happened(monkeypatch):
    decided = []
    one_waiting(monkeypatch, decided)

    def decide(at):
        at.session_state["choice_5"] = APPROVE
        at.run()
        at.text_area(key="reason_5").set_value("Checked against the IGS file")
        at.button(key="record_5").click()

    at = run(then=decide)

    token, item, choice, reason, changes, who, email, accounts, _ = decided[0]
    assert (token, item["number"], choice, reason, who, email) == (
        "t0ken", 5, APPROVE, "Checked against the IGS file", "A Member", "member@example.com")
    assert "Approved and merged." in page_text(at)


def test_the_weekly_registry_job_starts_the_tests_on_its_pull_request():
    registry = (ROOT / ".github/workflows/registry-update.yml").read_text()
    tests = (ROOT / ".github/workflows/tests.yml").read_text()

    assert "gh workflow run tests.yml --ref registry-update" in registry and "actions: write" in registry
    assert "workflow_dispatch:" in tests
