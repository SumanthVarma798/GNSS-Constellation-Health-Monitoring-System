"""Contact inbox: mail people sent to contact@opengnss.org, as threads. One thread open at a time, its messages oldest
first, its clean attachments to download, and a reply box that answers the thread's correspondent."""
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

import requests
import streamlit as st

from console import common, pages
from evidence import contact
from evidence.console_settings import CONTACT_ADDRESS, CONTACT_READ_EVERY_SECONDS, CONTACT_TOKEN_KEY
from evidence.contact_settings import (
    DOWNLOAD, DOWNLOAD_FAILED, DOWNLOADS_KEPT, EMPTY, FROM_FORM, FROM_THEM, FROM_US, NO_SENDER, NO_TEXT, NOT_VERIFIED,
    OPEN_THREAD, REPLIES_FROM_US, REPLY_BY_EMAIL, REPLY_BY_EMAIL_NOTE, REPLY_CHARACTERS, REPLY_HELP, REPLY_LABEL,
    SCAN_AGAIN_SECONDS, SCAN_NOT_STARTED, SCAN_STARTED, SEND, THREAD_COLUMNS, THREAD_NOTE, THREADS, THREADS_NOTE,
)
from evidence.decision_settings import SECRETS_SECTION
from ui import console

PAGE = pages.CONTACT
REPLY_STATUS = "contact_reply_status"   # session_state: (thread, tone, words) after the last press of Send
STATE_TONES = {"clean": "ok", "wait": "warn", "bad": "bad", "note": "idle"}


@st.cache_data(ttl=CONTACT_READ_EVERY_SECONDS, show_spinner="Reading the contact inbox…")
def _inbox(token):
    return contact.messages(contact.read_messages(token))


@st.cache_data(max_entries=DOWNLOADS_KEPT, show_spinner=False)
def _file(token, attachment_id):   # a clean file never changes, so it is read once
    return contact.read_attachment(token, attachment_id)


@st.cache_data(ttl=SCAN_AGAIN_SECONDS, show_spinner=False)
def _scan(github_token):   # opening the inbox again within SCAN_AGAIN_SECONDS does not start a second run
    return datetime.now(timezone.utc).strftime("%H:%M"), contact.start_scan(github_token)


def _scan_notice(count):
    at, why = _scan(common.settings().get("github_token", ""))
    if why:
        return console.notice(SCAN_NOT_STARTED.format(count=count, why=why), "warn")
    return console.notice(SCAN_STARTED.format(count=count, at=at), "info")


def _correspondent(thread):
    marker = f' <span class="muted">· {NOT_VERIFIED}</span>' if thread["form"] else ""
    return escape(thread["correspondent"]) + marker


def _thread_row(thread):
    return [_correspondent(thread), escape(thread["subject"]), escape(console.when(thread["last"])), str(thread["count"])]


def _thread_label(thread):
    return f'{console.when(thread["last"])} · {thread["correspondent"]} · {thread["subject"]} ({thread["count"]})'


def _attachments(row):
    items = []
    for a in row["attachments"]:
        state, words = contact.attachment_state(a)
        items.append(f'<li><b>{escape(a["name"])}</b> <span class="muted">{escape(contact.size_words(a["size"]))}</span> '
                     f'{console.status(STATE_TONES[state], words)}</li>')
    return f'<ul class="c-files">{"".join(items)}</ul>' if items else ""


def _message(row):
    if row["direction"] == "out":
        who = FROM_US.format(to=row["to"] or NO_SENDER)
    else:
        who = FROM_THEM.format(sender=row["from"] or row["address"] or NO_SENDER)
    form = f' <span class="muted">· {FROM_FORM}</span>' if row["via"] == "form" else ""
    return (f'<div class="c-msg {row["direction"]}"><div class="c-msg-head"><b>{escape(who)}</b>{form}'
            f'<span>{escape(console.when(row["at"]))}</span></div>'
            f'<div class="c-mail">{escape(row["text"]) or NO_TEXT}</div>{_attachments(row)}</div>')


def _send_reply(token, thread):
    key = f"contact_reply_{thread['id']}"
    tone, words = contact.reply(token, thread["id"], st.session_state.get(key, ""), thread["address"])
    st.session_state[REPLY_STATUS] = (thread["id"], tone, words)
    if tone == "ok":   # in the button's callback, so the box can still be emptied before it is drawn
        st.session_state[key] = ""
        _inbox.clear()


def _downloads(token, thread):
    for row in thread["messages"]:
        for a in row["attachments"]:
            if contact.attachment_state(a)[0] != "clean":
                continue
            try:
                data = _file(token, a["id"])
            except requests.RequestException:
                st.html(console.notice(DOWNLOAD_FAILED.format(name=a["name"]), "warn"))
                continue
            st.download_button(DOWNLOAD.format(name=contact.label_text(a["name"]), size=contact.size_words(a["size"])), data, file_name=a["name"],
                               key=f"contact_file_{a['id']}", icon=":material/download:")


def _thread(token, thread):
    st.html(console.section(thread["subject"], "".join(_message(row) for row in thread["messages"]),
                            right=THREAD_NOTE.format(count=thread["count"])))
    _downloads(token, thread)
    if not thread["address"]:
        return
    if not REPLIES_FROM_US:
        subject = thread["subject"] if thread["subject"].lower().startswith("re:") else f"Re: {thread['subject']}"
        st.link_button(REPLY_BY_EMAIL, f"mailto:{quote(thread['address'], safe='@')}?subject={quote(subject)}",
                       icon=":material/mail:", help=REPLY_BY_EMAIL_NOTE)
        return
    label = REPLY_LABEL.format(address=contact.label_text(thread["address"])) + (f" ({NOT_VERIFIED})" if thread["form"] else "")
    st.text_area(label, key=f"contact_reply_{thread['id']}", max_chars=REPLY_CHARACTERS, height=140, help=REPLY_HELP)
    st.button(SEND, key=f"contact_send_{thread['id']}", type="primary", icon=":material/send:",
              on_click=_send_reply, args=(token, thread))
    said = st.session_state.get(REPLY_STATUS)
    if said and said[0] == thread["id"]:
        st.html(console.notice(said[2], said[1]))


body, actions = common.layout(PAGE.path, f"Mail sent to {CONTACT_ADDRESS}, as threads. Times in UTC.")

with body:
    token = contact.inbox_token(common.settings())
    if not token:
        st.html(console.notice(
            f"The contact inbox is not connected: the console has no token to read it. Set [{SECRETS_SECTION}] "
            f"{CONTACT_TOKEN_KEY} in the console's secrets (on Render the secret file secrets.toml; on a computer "
            ".streamlit/secrets.toml), or the environment variable CONTACT_READ_TOKEN, to the same value as the "
            "Worker's secret CONTACT_READ_TOKEN.", "info"))
    else:
        try:
            found = contact.threads(_inbox(token))
        except (requests.RequestException, KeyError, TypeError, ValueError) as error:
            st.html(console.notice(contact.trouble(error), "bad"))
        else:
            # ponytail: counts waiting files among the newest messages the Worker returns (200); a run scans every waiting
            # file, so an older one is caught by the next; a pending count from the Worker if that ever matters
            if count := contact.waiting(found):
                st.html(_scan_notice(count))
            if not found:
                st.html(console.section(THREADS, console.notice(EMPTY, "info")))
            else:
                st.html(console.section(THREADS, console.list_view(THREAD_COLUMNS, [_thread_row(t) for t in found], numeric=("Messages",)),
                                        right=THREADS_NOTE.format(count=len(found)), flush=True))
                by_id = {t["id"]: t for t in found}
                picked = st.selectbox(OPEN_THREAD, list(by_id), format_func=lambda t: _thread_label(by_id[t]), key="contact_thread")
                _thread(token, by_id[picked])

with actions:
    if st.button("Read again", key="contact_read_again", icon=":material/refresh:", help="Read the contact inbox again now"):
        _inbox.clear()
        st.rerun()
