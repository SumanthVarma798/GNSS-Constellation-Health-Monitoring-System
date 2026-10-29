"""A viewer's own Space-Track login: kept only in session_state, used only for their session, never written down.

No network: ``spacetrack.fetch`` is monkeypatched, and the dashboard tests reuse the frozen clock.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
import time_machine
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import ButtonGroup

from data import celestrak, spacetrack
from ui import data as dashboard_data

ROOT = Path(__file__).resolve().parent.parent
FROZEN = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
LOGIN_KEY = "_spacetrack_login"
ROWS_KEY = "_spacetrack_rows"
TRIED_KEY = "_spacetrack_tried"
NOTE_KEY = "_spacetrack_note"


@pytest.fixture(autouse=True)
def segmented_controls_rerun(monkeypatch):
    """AppTest 1.45 reads a segmented control's single value (a string or number) as a list of choices and
    fails on the next run. This reads it as one choice."""
    def indices(self):
        chosen = self.value if isinstance(self.value, list) else [] if self.value is None else [self.value]
        return [self.options.index(self.format_func(v)) for v in chosen]
    monkeypatch.setattr(ButtonGroup, "indices", property(indices))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """The dashboard's sources answer without network unless a test replaces their fetch."""
    monkeypatch.setattr(celestrak, "state", {"rows": {}, "listed": None, "tried": None, "fetched": None, "ok": True,
                                             "failing_since": None, "copy_at": None})
    monkeypatch.setattr(celestrak, "fetch", lambda norads: ({}, set()))
    monkeypatch.setattr(celestrak, "fetch_copy", lambda norads: ({}, set(), None))
    monkeypatch.setattr(spacetrack, "state", {"rows": {}, "tried": None, "fetched": None,
                                              "refused_until": None, "note": "ok"})
    monkeypatch.setattr(spacetrack, "refresh",
                        lambda norads, now, login: {"rows": {}, "tried": now if login else None, "fetched": None,
                                                    "refused_until": None, "note": "ok" if login else "no login"})
    monkeypatch.setattr(spacetrack, "fetch", lambda username, password, norads: {})


@pytest.fixture(autouse=True)
def clear_own_login():
    """The own login lives in the real Streamlit session proxy in unit tests; leave it empty."""
    for key in (LOGIN_KEY, ROWS_KEY, TRIED_KEY, NOTE_KEY):
        st.session_state.pop(key, None)
    yield
    for key in (LOGIN_KEY, ROWS_KEY, TRIED_KEY, NOTE_KEY):
        st.session_state.pop(key, None)


def run(setup=lambda at: None, now=FROZEN):
    """Open the dashboard, let `setup` change the state or widgets, and run it again."""
    with time_machine.travel(now, tick=False):
        at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=600).run()
        setup(at)
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def own_popover(at):
    """The login popover in the top bar."""
    for popover in at.get("popover"):
        if any(text_input.label == "Username" for text_input in popover.text_input):
            return popover
    raise AssertionError("login popover not found")


def page_text(at):
    """Every word the page renders as markdown, text, caption or HTML."""
    parts = []
    for markdown in at.get("markdown"):
        parts.append(markdown.value)
    for text in at.get("text"):
        parts.append(text.value)
    for caption in at.get("caption"):
        parts.append(caption.value)
    for html in at.get("html"):
        parts.append(html.proto.body)
    return " ".join(parts)


def test_submitting_the_form_keeps_the_login_only_under_its_key_and_never_renders_it():
    username = "member@example.com"
    password = "very-secret-password"

    def setup(at):
        popover = own_popover(at)
        inputs = {text_input.label: text_input for text_input in popover.text_input}
        inputs["Username"].input(username)
        inputs["Password"].input(password)
        popover.button[0].click()

    at = run(setup)

    state = at.session_state.filtered_state
    assert state[LOGIN_KEY] == (username, password)
    assert all(value not in (password, username) for key, value in state.items() if key != LOGIN_KEY)
    rendered = page_text(at)
    assert username not in rendered
    assert password not in rendered
    for saved in (spacetrack.SAVED, celestrak.SAVED):   # the page's whole refresh ran with the login held
        if saved.exists():
            assert username not in saved.read_text(encoding="utf-8")
            assert password not in saved.read_text(encoding="utf-8")


def test_a_refresh_with_the_own_login_never_writes_it_to_either_saved_file(tmp_path):
    username, password = "member@example.com", "no-leaks-please"
    spacetrack.SAVED.write_text('{"rows": {}}')
    celestrak.SAVED.write_text('{"rows": {}}')

    def fetch(got_username, got_password, norads):
        assert (got_username, got_password) == (username, password)
        return {39635: {"EPOCH": "2026-10-25T00:00:00.000000"}}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(dashboard_data.spacetrack, "fetch", fetch)
    st.session_state[LOGIN_KEY] = (username, password)
    try:
        dashboard_data.own_refresh([39635], FROZEN)
    finally:
        monkeypatch.undo()

    assert spacetrack.state["rows"] == {}
    assert spacetrack.state["tried"] is None
    assert username not in spacetrack.SAVED.read_text(encoding="utf-8")
    assert password not in spacetrack.SAVED.read_text(encoding="utf-8")
    assert username not in celestrak.SAVED.read_text(encoding="utf-8")
    assert password not in celestrak.SAVED.read_text(encoding="utf-8")


def test_own_refresh_tries_at_most_once_per_hour_per_session(monkeypatch):
    calls = []

    def fetch(username, password, norads):
        calls.append((username, password, list(norads)))
        return {39635: {"EPOCH": "2026-10-25T00:00:00.000000"}}

    monkeypatch.setattr(dashboard_data.spacetrack, "fetch", fetch)
    st.session_state[LOGIN_KEY] = ("member@example.com", "secret")

    dashboard_data.own_refresh([39635], FROZEN)
    dashboard_data.own_refresh([39635], FROZEN + timedelta(minutes=30))
    dashboard_data.own_refresh([39635], FROZEN + timedelta(hours=1))

    assert len(calls) == 2
    assert calls[0][2] == [39635]
    assert calls[1][2] == [39635]


def test_a_refused_login_is_forgotten_at_once_and_not_tried_again(monkeypatch):
    calls = []

    def fetch(username, password, norads):
        calls.append((username, password, list(norads)))
        raise spacetrack.LoginRefused("no")

    monkeypatch.setattr(dashboard_data.spacetrack, "fetch", fetch)
    st.session_state[LOGIN_KEY] = ("member@example.com", "wrong")

    dashboard_data.own_refresh([39635], FROZEN)
    dashboard_data.own_refresh([39635], FROZEN + timedelta(hours=2))

    assert LOGIN_KEY not in st.session_state
    assert st.session_state[NOTE_KEY] == "login refused"
    assert len(calls) == 1


def test_forget_my_login_removes_the_login_its_rows_and_note_but_not_the_last_try():
    def setup(at):
        popover = own_popover(at)
        inputs = {text_input.label: text_input for text_input in popover.text_input}
        inputs["Username"].input("member@example.com")
        inputs["Password"].input("secret")
        popover.button[0].click()

    at = run(setup)
    assert LOGIN_KEY in at.session_state

    forget = next(button for button in at.button if button.label == "Forget my login")
    forget.click().run()

    assert not at.exception
    for key in (LOGIN_KEY, ROWS_KEY, NOTE_KEY):
        assert key not in at.session_state


def test_a_new_login_after_forgetting_still_waits_out_the_hour(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_data.spacetrack, "fetch", lambda u, p, norads: calls.append(u) or {})
    st.session_state[LOGIN_KEY] = ("first@example.com", "one")
    dashboard_data.own_refresh([39635], FROZEN)
    for key in (LOGIN_KEY, ROWS_KEY, NOTE_KEY):   # what "Forget my login" removes
        st.session_state.pop(key, None)
    st.session_state[LOGIN_KEY] = ("second@example.com", "two")
    dashboard_data.own_refresh([39635], FROZEN + timedelta(minutes=10))
    assert calls == ["first@example.com"]


def test_a_refused_login_also_drops_the_rows_it_brought(monkeypatch):
    def fetch(username, password, norads):
        raise spacetrack.LoginRefused("no")

    monkeypatch.setattr(dashboard_data.spacetrack, "fetch", fetch)
    st.session_state[LOGIN_KEY] = ("member@example.com", "changed")
    st.session_state[ROWS_KEY] = {39635: [{"EPOCH": "2026-10-05T00:00:00.000000"}]}
    dashboard_data.own_refresh([39635], FROZEN)
    assert ROWS_KEY not in st.session_state and LOGIN_KEY not in st.session_state


def test_own_rows_reach_orbit_ages_as_your_login():
    st.session_state[ROWS_KEY] = {39635: [{"EPOCH": "2026-10-25T00:00:00.000000"}]}
    result = {"history": pd.DataFrame(columns=["satellite", "EPOCH"])}

    rows = dashboard_data.orbit_ages("NavIC", result)

    own = next(row for row in rows if row["satellite"] == "IRNSS-1B")
    assert own["source"] == "Space-Track (your login)"


def test_own_note_says_your_login_while_in_use_and_refused_after_a_refusal():
    st.session_state[LOGIN_KEY] = ("member@example.com", "secret")
    assert dashboard_data.own_note() == "your login"

    del st.session_state[LOGIN_KEY]
    st.session_state[NOTE_KEY] = "login refused"
    assert dashboard_data.own_note() == "your login was refused"
