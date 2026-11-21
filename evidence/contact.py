"""The contact inbox: mail sent to contact@opengnss.org, read from the newsletters Worker for the console's Contact page,
grouped into threads; replies and attachment downloads go back through the same Worker."""
import os
from datetime import datetime

import requests

from evidence import github_api
from evidence.console_settings import CONTACT_INBOX_URL, CONTACT_SCAN_WORKFLOW, CONTACT_TOKEN_ENV, CONTACT_TOKEN_KEY
from evidence.contact_settings import (
    ATTACHMENT_URL, CLEAN, DOWNLOAD_TIMEOUT_SECONDS, INFECTED, MISSING, NO_SENDER, NO_SUBJECT, NOT_SENT, PENDING,
    REPLY_CHARACTERS, REPLY_EMPTY, REPLY_NO_ANSWER, REPLY_REFUSED, REPLY_TIMEOUT_SECONDS, REPLY_TOKEN, REPLY_TOO_LONG,
    REPLY_URL, SCAN_NO_ANSWER, SCAN_TOKEN_CANNOT, SENT,
)


def inbox_token(settings):
    """The console's token for the inbox: [admin] contact_read_token in its secrets, else the CONTACT_READ_TOKEN
    environment variable, else ""."""
    return str(settings.get(CONTACT_TOKEN_KEY) or os.environ.get(CONTACT_TOKEN_ENV) or "").strip()


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def read_messages(token):
    """Every message the Worker returns (its newest 200), as it sent them."""
    answer = requests.get(CONTACT_INBOX_URL, headers=_bearer(token), timeout=20)
    answer.raise_for_status()
    return answer.json()


def _attachment(a):
    return {"id": str(a.get("id") or ""), "name": str(a.get("name") or "attachment"), "size": int(a.get("size") or 0),
            "scan": str(a.get("scan") or ""), "signature": str(a.get("signature") or ""), "note": str(a.get("note") or "")}


def messages(answer):
    """The messages newest first, each with `at` as a time, its `thread` and `direction` ("in" or "out"), and its
    attachments. `via` is "form" for the dashboard's form. Raises TypeError or ValueError on an answer of another shape."""
    if not isinstance(answer, list):
        raise TypeError("the inbox is not a list")
    rows = [{"at": datetime.fromisoformat(str(m["at"]).replace("Z", "+00:00")), "id": str(m.get("id") or ""),
             "thread": str(m.get("thread") or m.get("id") or m["at"]), "direction": "out" if m.get("direction") == "out" else "in",
             "from": str(m.get("from") or ""), "address": str(m.get("address") or ""), "to": str(m.get("to") or ""),
             "subject": str(m.get("subject") or ""), "text": str(m.get("text") or ""), "via": str(m.get("via") or ""),
             "attachments": [_attachment(a) for a in m.get("attachments") or []]}
            for m in answer]
    return sorted(rows, key=lambda row: row["at"], reverse=True)


def threads(rows):
    """The messages as threads, the latest activity first: each with its correspondent (who wrote to us first), the
    first message's subject, when the last message came, how many there are, whether it began on the dashboard's form
    (its address not verified), and its messages oldest first."""
    grouped = {}
    for row in sorted(rows, key=lambda r: r["at"]):
        grouped.setdefault(row["thread"], []).append(row)
    found = []
    for thread, oldest_first in grouped.items():
        first_in = next((m for m in oldest_first if m["direction"] == "in"), None)
        found.append({
            "id": thread, "messages": oldest_first, "count": len(oldest_first), "last": oldest_first[-1]["at"],
            "correspondent": (first_in["from"] or first_in["address"]) if first_in else oldest_first[0]["to"] or NO_SENDER,
            "address": first_in["address"] if first_in else "", "subject": oldest_first[0]["subject"] or NO_SUBJECT,
            "form": bool(first_in and first_in["via"] == "form"),
        })
    return sorted(found, key=lambda t: t["last"], reverse=True)


def size_words(size):
    """A file's size as people read it: 512 B, 13 KB, 4.2 MB."""
    if size < 1024:
        return f"{size} B"
    return f"{size / 1024:.0f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"


def attachment_state(a):
    """(state, words) for one attachment: "clean" (it can be downloaded), "wait" (still being scanned), "bad"
    (removed, a virus found) or "note" (never kept, with why)."""
    if a["note"] or not a["id"]:
        return "note", a["note"] or MISSING
    if a["scan"] == "clean":
        return "clean", CLEAN
    if a["scan"] == "pending":
        return "wait", PENDING
    if a["scan"] == "infected":
        return "bad", INFECTED.format(signature=a["signature"] or "unnamed")
    return "note", MISSING


def read_attachment(token, attachment_id):
    """A clean attachment's bytes. The Worker refuses one not yet scanned clean (409)."""
    answer = requests.get(ATTACHMENT_URL.format(id=attachment_id), headers=_bearer(token), timeout=DOWNLOAD_TIMEOUT_SECONDS)
    answer.raise_for_status()
    return answer.content


def reply(token, thread, text, address):
    """Send one reply in a thread: (tone, words) saying what became of it. Never says the token."""
    text = text.strip()
    if not text:
        return "bad", NOT_SENT.format(why=REPLY_EMPTY)
    if len(text) > REPLY_CHARACTERS:
        return "bad", NOT_SENT.format(why=REPLY_TOO_LONG.format(length=len(text), limit=REPLY_CHARACTERS))
    try:
        answer = requests.post(REPLY_URL, json={"thread": thread, "text": text}, headers=_bearer(token),
                               timeout=REPLY_TIMEOUT_SECONDS)
    except requests.RequestException:
        return "warn", REPLY_NO_ANSWER
    if answer.status_code == 201:
        return "ok", SENT.format(address=address)
    if answer.status_code == 401:
        return "bad", NOT_SENT.format(why=REPLY_TOKEN)
    try:
        said = str(answer.json().get("problem") or "")
    except (ValueError, AttributeError):
        said = ""
    if not said and answer.status_code >= 500:   # the Worker names its own refusals; an unnamed failure may be after sending
        return "warn", REPLY_NO_ANSWER
    return "bad", NOT_SENT.format(why=REPLY_REFUSED.format(problem=said or f"answer {answer.status_code}"))


def trouble(error):
    """What went wrong reading the inbox, in plain words. Never the token."""
    if not isinstance(error, requests.RequestException):
        return "The contact inbox answered, but not in the shape the console expects, so it cannot be shown now."
    code = getattr(getattr(error, "response", None), "status_code", None)
    if code == 401:
        return ("The contact inbox refused the console's token: [admin] contact_read_token must be the same as the "
                "Worker's secret CONTACT_READ_TOKEN.")
    return "The contact inbox did not answer, so its messages cannot be shown now. Try again in a few minutes."


def label_text(text):
    """Text from outside as a widget label shows it: Streamlit reads labels as Markdown, so every punctuation mark is
    escaped. Otherwise an address or file name like ![x](http://...) would make the console load that address."""
    return "".join(f"\\{c}" if c in "\\`*_{}[]()#+-.!|<>~$:=^&\"'" else c for c in str(text))


def start_scan(github_token):
    """Starts the attachment scan (.github/workflows/contact-scan.yml) on main. "" when GitHub took it, else why not, in
    plain words. Never says the token."""
    try:
        github_api.ask("POST", f"/actions/workflows/{CONTACT_SCAN_WORKFLOW}/dispatches", github_token, json={"ref": "main"})
    except requests.HTTPError as error:
        code = getattr(error.response, "status_code", None)
        return SCAN_TOKEN_CANNOT if code in (401, 403, 404) else f"GitHub answered {code}"
    except requests.RequestException:
        return SCAN_NO_ANSWER
    return ""


def waiting(found):
    """How many attachments across the threads are waiting to be scanned."""
    return sum(attachment_state(a)[0] == "wait" for thread in found for row in thread["messages"] for a in row["attachments"])
