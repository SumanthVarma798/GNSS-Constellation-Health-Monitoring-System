"""The contact form (ui/contact.py): what it checks, its two limits, how it sends, and that it hides with nowhere to send."""
import threading
from collections import deque
from types import SimpleNamespace

import pytest
import requests
from streamlit.testing.v1 import AppTest

from ui import contact
from ui.contact_settings import (BAD_ADDRESS, EMPTY, NO_ANSWER, NOT_SET_UP, SENDS_PER_WINDOW, SESSION_COOLDOWN_SECONDS,
                                 TEXT_CHARACTERS, TOKEN_ENV, URL_ENV, WINDOW_SECONDS)

URL = "http://localhost:8787/contact"


@pytest.fixture(autouse=True)
def nowhere_to_send(monkeypatch):
    monkeypatch.delenv(URL_ENV, raising=False)
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    contact._sent_times.clear()


def configured(monkeypatch):
    monkeypatch.setenv(URL_ENV, URL)
    monkeypatch.setenv(TOKEN_ENV, "test-write-token")


def test_the_address_and_message_are_checked_before_sending():
    assert contact.problem("a@example.org", "Hello") == ""
    for address in ("", "a@example", "not an address", "A <a@example.org>", "a@b@c.org", f"{'a' * 250}@example.org"):
        assert contact.problem(address, "Hello") == BAD_ADDRESS, address
    assert contact.problem("a@example.org", "") == EMPTY
    assert contact.problem("a@example.org", "x" * TEXT_CHARACTERS) == ""
    assert "the most is 4000" in contact.problem("a@example.org", "x" * (TEXT_CHARACTERS + 1))


def test_one_visitor_waits_a_minute_between_messages():
    assert contact.session_wait(None, 1000.0) == 0
    assert contact.session_wait(1000.0, 1000.5) == SESSION_COOLDOWN_SECONDS
    assert contact.session_wait(1000.0, 1000.0 + SESSION_COOLDOWN_SECONDS) == 0


def test_every_visitor_together_sends_at_most_the_cap_in_a_window_and_old_sends_leave_it():
    times = deque([0.0] + [100.0] * (SENDS_PER_WINDOW - 1))

    assert contact.cap_wait(times, 200.0) == WINDOW_SECONDS - 200
    assert contact.cap_wait(times, float(WINDOW_SECONDS)) == 0 and len(times) == SENDS_PER_WINDOW - 1


def _attempt(times, send, last_sent=None, now=5000.0, address="a@example.org"):
    return contact.attempt(address, "Hello", last_sent, now, times, threading.Lock(), send)


def test_a_sent_message_names_the_reply_address_and_takes_a_place_under_the_cap():
    times = deque()

    assert _attempt(times, lambda a, m: "") == ("Sent. We will reply to a@example.org.", "ok")
    assert list(times) == [5000.0]


def test_a_failed_send_says_why_and_gives_its_place_back():
    times = deque()

    assert _attempt(times, lambda a, m: NO_ANSWER) == (f"Not sent: {NO_ANSWER}", "bad") and not times


def test_over_a_limit_nothing_is_sent_and_the_visitor_is_told_when_to_try_again():
    never = lambda a, m: pytest.fail("sent over a limit")   # noqa: E731

    words, status = _attempt(deque(), never, last_sent=4990.0)
    assert status == "warn" and "another in 50 seconds" in words
    words, status = _attempt(deque([4000.0] * SENDS_PER_WINDOW), never)
    assert status == "warn" and "Try again in 44 minutes" in words
    assert _attempt(deque(), never, address="nope")[1] == "bad"


class Answer:
    def __init__(self, status_code, body=None):
        self.status_code, self.body = status_code, body

    def json(self):
        if self.body is None:
            raise ValueError("no JSON")
        return self.body


@pytest.mark.parametrize("answer, words", [
    (Answer(201, {"ok": True}), ""),
    (Answer(400, {"ok": False, "problem": "text is empty"}), "the inbox refused it (text is empty)."),
    (Answer(400), "the inbox refused it (no reason given)."),
    (Answer(401), NOT_SET_UP),
    (Answer(500), NO_ANSWER),
    (requests.ConnectionError("down"), NO_ANSWER),
])
def test_a_post_carries_the_token_and_its_answer_reads_in_plain_words(monkeypatch, answer, words):
    seen = {}

    def post(url, json, headers, timeout):
        seen.update(url=url, json=json, headers=headers, timeout=timeout)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(contact.requests, "post", post)

    said = contact.post(URL, "tok", "a@example.org", "Hi")
    assert said == words and "tok" not in said
    assert seen == {"url": URL, "json": {"from": "a@example.org", "text": "Hi"},
                    "headers": {"Authorization": "Bearer tok"}, "timeout": 10}


def test_config_comes_from_the_environment_or_else_the_secrets(monkeypatch):
    assert contact.config() is None
    configured(monkeypatch)
    assert contact.config() == (URL, "test-write-token")


def _page():
    from ui import contact

    contact.section("library_contact", "library")


def test_with_nowhere_to_send_no_form_is_drawn():
    at = AppTest.from_function(_page).run()

    assert not at.checkbox and not at.text_input and not at.text_area


def _press_send(monkeypatch, said):
    configured(monkeypatch)
    posted = []
    monkeypatch.setattr(contact, "post", lambda url, token, a, m: posted.append((url, a, m)) or said)
    at = AppTest.from_function(_page).run()
    assert [box.label for box in at.checkbox] == ["**Contact us** write to the team; only the team reads it, and we reply by email"]
    at.text_input(key="contact_library_address").input(" a@example.org ")
    at.text_area(key="contact_library_message").input("Hello team")
    at.button[0].click().run()
    return at, posted


def test_sending_from_the_form_says_so_and_empties_the_fields(monkeypatch):
    at, posted = _press_send(monkeypatch, "")

    assert posted == [(URL, "a@example.org", "Hello team")]
    assert any("Sent. We will reply to a@example.org." in h.proto.body for h in at.get("html"))
    assert at.text_input(key="contact_library_address").value == "" and at.text_area(key="contact_library_message").value == ""


def test_a_failed_send_keeps_what_was_typed_and_says_why(monkeypatch):
    at, _ = _press_send(monkeypatch, NO_ANSWER)

    assert any(f"Not sent: {NO_ANSWER}" in h.proto.body and 'class="notice bad"' in h.proto.body for h in at.get("html"))
    assert at.text_area(key="contact_library_message").value == "Hello team"
