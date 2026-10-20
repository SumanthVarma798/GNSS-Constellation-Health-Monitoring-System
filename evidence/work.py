"""The work in the private mirror, for the administration console: open issues and open pull requests, as rows.

Read through evidence/github_api.py; nothing is kept. Pull requests are read by evidence/decisions.py (fetch_open),
so the console asks GitHub for them once.
"""
import re
from datetime import datetime

from evidence.decision_settings import RAISED_BY
from evidence.decisions import kind_of
from evidence import github_api

PAGE_SIZE = 100
_HEX = re.compile(r"[0-9a-fA-F]{6}")


def fetch_open_issues(token):
    """Every open issue, without the pull requests GitHub lists among issues."""
    rows, page = [], 1
    while True:
        got = github_api.ask("GET", "/issues", token, params={"state": "open", "per_page": PAGE_SIZE, "page": page})
        rows += [issue for issue in got if "pull_request" not in issue]
        if len(got) < PAGE_SIZE:
            return rows
        page += 1


def labels(item):
    """[(name, '#rrggbb')] for its labels; a colour GitHub did not give as six hex digits is left grey."""
    return [(label["name"], f"#{label['color']}" if _HEX.fullmatch(label.get("color") or "") else "#8a8a8a")
            for label in item.get("labels", [])]


def _who(item):
    login = (item.get("user") or {}).get("login", "a deleted account")
    return RAISED_BY.get(login, login)


def _days(text, now):
    return (now - datetime.fromisoformat(text)).days


def issue_rows(issues, now, find=""):
    """Open issues, the most recently updated first; `find` keeps only titles that contain it (any case)."""
    rows = [{"number": i["number"], "title": i["title"], "by": _who(i), "labels": labels(i), "comments": i.get("comments", 0),
             "opened_days": _days(i["created_at"], now), "updated_days": _days(i["updated_at"], now), "link": i["html_url"]}
            for i in issues if find.lower() in i["title"].lower()]
    return sorted(rows, key=lambda r: (r["updated_days"], -r["number"]))


def pull_rows(prs, now):
    """Open pull requests, the newest first, each saying whether it waits on a decision and of what kind."""
    rows = [{"number": p["number"], "title": p["title"], "by": _who(p), "labels": labels(p), "draft": bool(p.get("draft")),
             "decision": kind_of(p), "opened_days": _days(p["created_at"], now), "link": p["html_url"]} for p in prs]
    return sorted(rows, key=lambda r: (r["opened_days"], -r["number"]))


def age_words(days):
    """'today', '1 day', '12 days'."""
    return "today" if days < 1 else f"{days} day{'' if days == 1 else 's'}"
