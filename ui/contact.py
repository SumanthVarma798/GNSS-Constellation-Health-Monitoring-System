"""The contact form: a visitor's email address and message, sent to the team's private contact inbox.

Drawn in the footer of every page and on the Library page, each in a section (ui/reveal.py), with widget keys from a
prefix so the two do not collide. With nothing configured to send to, nothing is drawn. Words and limits are in
ui/contact_settings.py.
"""
import math
import os
import re
import threading
import time
from collections import deque

import requests
import streamlit as st

from ui import reveal, surfaces
from ui.contact_settings import (
    ADDRESS_CHARACTERS, ADDRESS_LABEL, ADDRESS_PLACEHOLDER, BAD_ADDRESS, CAP_WAIT, EMPTY, MESSAGE_LABEL, NO_ANSWER,
    NOT_SENT, NOT_SET_UP, REFUSED, SECRETS_SECTION, SEND, SEND_TIMEOUT_SECONDS, SENDS_PER_WINDOW, SENT, SESSION_COOLDOWN_SECONDS,
    SESSION_WAIT, SUMMARY, TEXT_CHARACTERS, TITLE, TOKEN_ENV, TOKEN_KEY, TOO_LONG, URL_ENV, URL_KEY, WINDOW_SECONDS,
)

LAST_SENT = "contact_last_sent"   # session_state: when this visitor last sent, from either form
_ADDRESS = re.compile(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+")   # as the Worker checks it


def config():
    """(url, token) from the server's env or secrets, else None."""
    url, token = os.environ.get(URL_ENV), os.environ.get(TOKEN_ENV)
    if url and token:
        return url, token
    try:
        section = st.secrets[SECRETS_SECTION]
        url, token = section[URL_KEY], section[TOKEN_KEY]
        return (url, token) if url and token else None
    except Exception:
        return None


def problem(address, message):
    """Why the form cannot be sent as typed, in plain words, or "" when it can. Both already trimmed."""
    if len(address) > ADDRESS_CHARACTERS or not _ADDRESS.fullmatch(address):
        return BAD_ADDRESS
    if not message:
        return EMPTY
    if len(message) > TEXT_CHARACTERS:
        return TOO_LONG.format(length=len(message), limit=TEXT_CHARACTERS)
    return ""


def session_wait(last_sent, now):
    """Whole seconds this visitor must still wait before sending again; 0 when they may."""
    return 0 if last_sent is None else max(0, math.ceil(last_sent + SESSION_COOLDOWN_SECONDS - now))


def cap_wait(times, now):
    """Whole seconds until the shared cap has room again; 0 when it has. `times` (a deque, oldest first) loses the
    sends that have left the window."""
    while times and times[0] <= now - WINDOW_SECONDS:
        times.popleft()
    return 0 if len(times) < SENDS_PER_WINDOW else math.ceil(times[0] + WINDOW_SECONDS - now)


@st.cache_resource
def _sent_times():
    # ponytail: one server process holds the count; with several, each would allow SENDS_PER_WINDOW
    return deque(), threading.Lock()


def post(url, token, address, message):
    """Send one message. "" when the inbox kept it, else why not, in plain words. Never says the token."""
    try:
        answer = requests.post(url, json={"from": address, "text": message},
                               headers={"Authorization": f"Bearer {token}"}, timeout=SEND_TIMEOUT_SECONDS)
    except requests.RequestException:
        return NO_ANSWER
    if answer.status_code == 201:
        return ""
    if answer.status_code == 400:
        try:
            said = str(answer.json().get("problem") or "")
        except (ValueError, AttributeError):
            said = ""
        return REFUSED.format(problem=said or "no reason given")
    return NOT_SET_UP if answer.status_code == 401 else NO_ANSWER


def attempt(address, message, last_sent, now, times, lock, send):
    """(words, status) for one press of Send: checks the message, then both limits, then sends with `send`.
    A send that fails gives its place under the cap back."""
    why, status = problem(address, message), "bad"
    if not why and (wait := session_wait(last_sent, now)):
        why, status = SESSION_WAIT.format(seconds=wait), "warn"
    if not why:
        with lock:
            wait = cap_wait(times, now)
            if not wait:
                times.append(now)
        if wait:
            why, status = CAP_WAIT.format(minutes=math.ceil(wait / 60)), "warn"
        elif why := send(address, message):
            with lock:
                if now in times:
                    times.remove(now)
    return (NOT_SENT.format(why=why), status) if why else (SENT.format(address=address), "ok")


def _keys(prefix):
    return f"contact_{prefix}_address", f"contact_{prefix}_message", f"contact_{prefix}_status"


def _send(prefix):
    address_key, message_key, status_key = _keys(prefix)
    settings = config()
    if not settings:
        return
    address, message, now = st.session_state[address_key].strip(), st.session_state[message_key].strip(), time.time()
    times, lock = _sent_times()
    words, status = attempt(address, message, st.session_state.get(LAST_SENT), now, times, lock,
                            lambda a, m: post(*settings, a, m))
    st.session_state[status_key] = (words, status)
    if status == "ok":   # in the button's callback, so the fields can still be emptied before they are drawn
        st.session_state[LAST_SENT] = now
        st.session_state[address_key] = st.session_state[message_key] = ""


def form(prefix):
    """The form and, after a press of Send, what became of it. Nothing when there is nowhere to send."""
    if not config():
        return
    address_key, message_key, status_key = _keys(prefix)
    with st.container(key=f"contact_form_{prefix}"):
        with st.form(f"contact_{prefix}_form", border=False):
            st.text_input(ADDRESS_LABEL, key=address_key, max_chars=ADDRESS_CHARACTERS, placeholder=ADDRESS_PLACEHOLDER,
                          autocomplete="email")
            st.text_area(MESSAGE_LABEL, key=message_key, max_chars=TEXT_CHARACTERS)
            st.form_submit_button(SEND, on_click=_send, args=(prefix,), icon=":material/send:")
        if status_key in st.session_state:
            surfaces.show(surfaces.notice(*st.session_state[status_key], inline=True))


def section(key, prefix):
    """The form in a closed section titled "Contact us", or nothing when there is nowhere to send."""
    if config():
        reveal.section(key, TITLE, SUMMARY, lambda: form(prefix))
