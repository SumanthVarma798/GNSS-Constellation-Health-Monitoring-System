"""Pull requests that wait on a decision: read from GitHub, put in plain words, and decided (issue 17).

Nothing is stored here: the pull request stays the only record. A decision is written on it as a comment, then the
pull request is merged, left open or closed. The settings are in evidence/decision_settings.py.
"""
from datetime import datetime

import requests

from evidence.decision_settings import (AFTER_CHANGES, APPROVE, DECISION_MARKER, GROUPS, KINDS, LABEL_PREFIX,
                                        MERGE_METHOD, OTHER_GROUP, RAISED_BY, REJECT, REQUIRED_CHECK, WAIT_WARN_DAYS)
from evidence.github_api import ask as _ask

PAGE_SIZE = 100   # GitHub's largest page


def fetch_open(token):
    """Every open pull request, as GitHub's JSON."""
    rows, page = [], 1
    while True:
        rows += (got := _ask("GET", "/pulls", token, params={"state": "open", "per_page": PAGE_SIZE, "page": page}))
        if len(got) < PAGE_SIZE:
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
        login = (pr.get("user") or {}).get("login", "a deleted account")   # GitHub sends no user for a deleted one
        items.append({"number": pr["number"], "title": pr["title"], "kind": kind, "group": KINDS.get(kind, OTHER_GROUP),
                      "summary": summary(pr["body"]), "body": pr["body"] or "", "link": pr["html_url"],
                      "login": login, "raised_by": RAISED_BY.get(login, login), "sha": (pr.get("head") or {}).get("sha"),
                      "opened": opened, "waited_days": (now - opened).days})
    return sorted(items, key=lambda item: item["opened"])


def grouped(items):
    """[(group, items)] in the order of GROUPS, then OTHER_GROUP; a group with nothing waiting is left out."""
    return [(group, its) for group in GROUPS + [OTHER_GROUP] if (its := [i for i in items if i["group"] == group])]


def waited(days):
    """('waiting 3 days', 'ok'); a warning once an item has waited longer than WAIT_WARN_DAYS."""
    words = "opened today" if days < 1 else f"waiting {days} day{'' if days == 1 else 's'}"
    return (f"{words}, over {WAIT_WARN_DAYS} days", "warn") if days > WAIT_WARN_DAYS else (words, "ok")


def access(logged_in, email, allowed):
    """'sign in', 'not on the list' or 'in'. Addresses are compared without regard to capitals."""
    if not logged_in:
        return "sign in"
    return "in" if (email or "").lower() in {a.lower() for a in allowed} else "not on the list"


def tests_state(token, sha):
    """'passed', 'failed', 'running' or 'not run': the newest REQUIRED_CHECK run on that commit."""
    runs = _ask("GET", f"/commits/{sha}/check-runs", token, params={"check_name": REQUIRED_CHECK})["check_runs"]
    if not runs:
        return "not run"
    newest = max(runs, key=lambda run: run["id"])
    return "running" if newest["status"] != "completed" else "passed" if newest["conclusion"] == "success" else "failed"


def blocker(choice, item, reason, changes, email, accounts, state="open", tests=None, mergeable=None, sha=None):
    """Why this decision cannot be made now, in plain words, or None when it can.

    accounts: {email: GitHub account} for the people on the list, so the person who raised an item is known. `state`
    is the pull request's, read just now; for an approval as proposed, so are `tests`, `mergeable` and `sha`.
    """
    if state != "open":
        return "It was already decided (merged or closed) after the page read it. Nothing more was written."
    if not reason.strip():
        return "Write the reason first: every decision needs one."
    if choice == AFTER_CHANGES and not changes.strip():
        return "Say which changes are asked for."
    if {e.lower(): login.lower() for e, login in accounts.items()}.get((email or "").lower()) == item["login"].lower():
        return "You raised this item, so someone else must decide it."
    if choice != APPROVE:
        return None
    # ponytail: the tests ran on the branch as it stands, not merged with a newer main; the Tests job runs on main
    # after every merge. Requiring the branch to be up to date would block most weekly registry updates, which
    # wait up to a fortnight for a call; add it with an "update the branch" step if a merge ever breaks main.
    if sha != item["sha"]:
        return "The pull request changed after the page read it. Read the new version before approving it."
    if tests != "passed":
        return f"It can be merged only once its tests have passed on it, and they have {_TESTS_WORDS[tests]}."
    if mergeable is None:
        return "GitHub is still working out whether it can be merged. Try again in a minute."
    if not mergeable:
        return "GitHub cannot merge it as it stands: it clashes with later changes and needs updating first."
    return None


_TESTS_WORDS = {"failed": "failed", "running": "not finished yet", "not run": "not been run", None: "not been checked"}


def decision_text(choice, reason, changes, who, when):
    """The comment written on the pull request. It starts with a marker so outcomes can be counted later; what was
    typed cannot fake one."""
    def plain(text):
        return text.strip().replace("<!--", "&lt;!--")
    return "\n".join([f"<!-- {DECISION_MARKER}: {choice} -->", f"**Decision on the admin page: {choice}.**", "",
                      f"Reason: {plain(reason)}"] + (["", f"Changes asked for: {plain(changes)}"] if changes.strip() else [])
                     + ["", f"Decided by {plain(who)} on {when.day} {when:%b %Y, %H:%M} UTC, signed in on the admin page."])


def decide(token, item, choice, reason, changes, who, email, accounts, now):
    """Write the decision on the pull request, then merge it, leave it open or close it. ('ok' | 'warn' | 'bad', words).

    For an approval the pull request, its tests and whether it can merge are read again first, and the merge names
    the commit that was checked, so what is merged is what was approved. Every choice first checks it is still open."""
    number = item["number"]
    pull = _ask("GET", f"/pulls/{number}", token)   # read again: someone may have decided it meanwhile
    read = {"state": pull["state"]}
    if choice == APPROVE and pull["state"] == "open" and not (pull.get("head") or {}).get("sha"):
        return "warn", "Its branch no longer exists, so it cannot be merged. Look at the pull request on GitHub."
    if choice == APPROVE and pull["state"] == "open":
        read |= {"sha": pull["head"]["sha"], "mergeable": pull["mergeable"], "tests": tests_state(token, pull["head"]["sha"])}
    problem = blocker(choice, item, reason, changes, email, accounts, **read)
    if problem:
        return "warn", problem
    _ask("POST", f"/issues/{number}/comments", token, json={"body": decision_text(choice, reason, changes, who, now)})
    try:
        if choice == APPROVE:
            _ask("PUT", f"/pulls/{number}/merge", token, json={"merge_method": MERGE_METHOD, "sha": read["sha"]})
            return "ok", f"Approved and merged. The decision is written on pull request {number}."
        if choice == REJECT:
            _ask("PATCH", f"/pulls/{number}", token, json={"state": "closed"})
            return "ok", f"Rejected and closed. The decision is written on pull request {number}."
    except requests.RequestException:
        # ponytail: the comment is already written; nothing undoes it. Rare (the merge was checked just before).
        return "bad", (f"The decision is written on pull request {number}, but GitHub did not "
                       f"{'merge' if choice == APPROVE else 'close'} it. Do that on GitHub, not here: deciding again would write the decision twice.")
    return "ok", f"Approved after changes. The decision is written on pull request {number}, which stays open."
