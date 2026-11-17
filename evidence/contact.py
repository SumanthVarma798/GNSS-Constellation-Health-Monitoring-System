"""The contact inbox: mail sent to contact@opengnss.org, read from the newsletters Worker for the console's Contact page."""
from datetime import datetime

import requests

from evidence.console_settings import CONTACT_INBOX_URL


def read_messages(token):
    """Every message the Worker returns (its newest 200), as it sent them."""
    answer = requests.get(CONTACT_INBOX_URL, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    answer.raise_for_status()
    return answer.json()


def messages(answer):
    """The messages newest first, each with `at` as a time and `via` ("form" from the dashboard's form, else "").
    Raises TypeError or ValueError on an answer of another shape."""
    if not isinstance(answer, list):
        raise TypeError("the inbox is not a list")
    rows = [{"at": datetime.fromisoformat(str(m["at"]).replace("Z", "+00:00")), "from": str(m.get("from") or ""),
             "subject": str(m.get("subject") or ""), "text": str(m.get("text") or ""), "via": str(m.get("via") or "")}
            for m in answer]
    return sorted(rows, key=lambda row: row["at"], reverse=True)


def trouble(error):
    """What went wrong reading the inbox, in plain words. Never the token."""
    if not isinstance(error, requests.RequestException):
        return "The contact inbox answered, but not in the shape the console expects, so it cannot be shown now."
    code = getattr(getattr(error, "response", None), "status_code", None)
    if code == 401:
        return ("The contact inbox refused the console's token: [admin] contact_read_token must be the same as the "
                "Worker's secret CONTACT_READ_TOKEN.")
    return "The contact inbox did not answer, so its messages cannot be shown now. Try again in a few minutes."
