"""Pull requests that wait on a decision, read from GitHub and put in plain words for the admin page (issue 17).

Nothing is stored here: the pull request stays the only record, and the page reads it afresh. The settings (which
labels, which groups, how long is too long) are in evidence/decision_settings.py.
"""
from datetime import datetime

import requests

from evidence.decision_settings import (GROUPS, KINDS, LABEL_PREFIX, OTHER_GROUP, RAISED_BY, REPOSITORY,
                                        WAIT_WARN_DAYS)

API = "https://api.github.com"
PAGE_SIZE = 100   # GitHub's largest page
TIMEOUT_SECONDS = 20


def fetch_open(token, repository=REPOSITORY):
    """Every open pull request in `repository`, as GitHub's JSON. Raises requests' errors when GitHub does not answer."""
    rows, page = [], 1
    while True:
        answer = requests.get(f"{API}/repos/{repository}/pulls", timeout=TIMEOUT_SECONDS,
                              headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                              params={"state": "open", "per_page": PAGE_SIZE, "page": page})
        answer.raise_for_status()
        rows += answer.json()
        if len(answer.json()) < PAGE_SIZE:
            return rows
        page += 1


def kind_of(pr):
    """The kind from the pull request's first "decision: <kind>" label, or None when it waits on no decision."""
    return next((label["name"][len(LABEL_PREFIX):] for label in pr["labels"] if label["name"].startswith(LABEL_PREFIX)),
                None)


def summary(body):
    """The first paragraph of a pull request's text: issue 16 puts the plain-language summary there."""
    return (body or "").strip().split("\n\n")[0].strip()


def pending(prs, now):
    """The pull requests that wait on a decision, as plain items, the longest waiting first."""
    items = []
    for pr in prs:
        kind = kind_of(pr)
        if kind is None:
            continue
        opened = datetime.fromisoformat(pr["created_at"])
        login = pr["user"]["login"]
        items.append({"number": pr["number"], "title": pr["title"], "kind": kind, "group": KINDS.get(kind, OTHER_GROUP),
                      "summary": summary(pr["body"]), "body": pr["body"] or "", "link": pr["html_url"],
                      "raised_by": RAISED_BY.get(login, login), "opened": opened, "waited_days": (now - opened).days})
    return sorted(items, key=lambda item: item["opened"])


def grouped(items):
    """[(group, items)] in the order of GROUPS, then OTHER_GROUP; a group with nothing waiting is left out."""
    return [(group, its) for group in GROUPS + [OTHER_GROUP] if (its := [i for i in items if i["group"] == group])]


def waited(days):
    """('waiting 3 days', 'ok'); a warning once an item has waited past a fortnightly call."""
    words = "opened today" if days < 1 else f"waiting {days} day{'' if days == 1 else 's'}"
    return (f"{words}, past a fortnightly call", "warn") if days > WAIT_WARN_DAYS else (words, "ok")


def access(logged_in, email, allowed):
    """'sign in', 'not on the list' or 'in'. Addresses are compared without regard to capitals."""
    if not logged_in:
        return "sign in"
    return "in" if (email or "").lower() in {a.lower() for a in allowed} else "not on the list"
