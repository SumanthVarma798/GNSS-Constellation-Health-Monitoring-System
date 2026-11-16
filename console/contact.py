"""Contact inbox: mail people sent to contact@opengnss.org, newest first, each message's text folded under it."""
from html import escape

import requests
import streamlit as st

from console import common, pages
from evidence import contact
from evidence.console_settings import CONTACT_ADDRESS, CONTACT_READ_EVERY_SECONDS, CONTACT_TOKEN_KEY
from evidence.decision_settings import SECRETS_SECTION
from ui import console

PAGE = pages.CONTACT


@st.cache_data(ttl=CONTACT_READ_EVERY_SECONDS, show_spinner="Reading the contact inbox…")
def _inbox(token):
    return contact.messages(contact.read_messages(token))


def _message(row):
    head = " · ".join(escape(part) for part in (console.when(row["at"]), row["from"] or "no sender", row["subject"] or "(no subject)"))
    return f'<details class="c-more"><summary>{head}</summary><div class="c-mail">{escape(row["text"]) or "(no text)"}</div></details>'


body, actions = common.layout(PAGE.path, f"Mail sent to {CONTACT_ADDRESS}, newest first. Times in UTC.")

with body:
    token = str(common.settings().get(CONTACT_TOKEN_KEY) or "").strip()
    if not token:
        st.html(console.notice(
            f"The contact inbox is not connected: the console has no token to read it. Set [{SECRETS_SECTION}] "
            f"{CONTACT_TOKEN_KEY} in the console's secrets (on Render the secret file secrets.toml; on a computer "
            ".streamlit/secrets.toml) to the same value as the Worker's secret CONTACT_READ_TOKEN.", "info"))
    else:
        try:
            rows = _inbox(token)
            st.html(console.section("Messages", "".join(_message(row) for row in rows) if rows else
                                    console.notice("No message has arrived yet.", "info"),
                                    right=f"{len(rows)}, the newest first; click one to read it"))
        except (requests.RequestException, KeyError, TypeError, ValueError) as error:
            st.html(console.notice(contact.trouble(error), "bad"))

with actions:
    if st.button("Read again", key="contact_read_again", icon=":material/refresh:", help="Read the contact inbox again now"):
        _inbox.clear()
        st.rerun()
