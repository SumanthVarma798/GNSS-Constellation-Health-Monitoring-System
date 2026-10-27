"""Pull requests that wait on a decision: read from GitHub, put in plain words, and decided (issue 17).

Nothing is stored here: the pull request stays the only record. A decision is written on it as a comment, then the
pull request is merged, left open or closed. The settings are in evidence/decision_settings.py.
"""
from datetime import datetime
import json
import re

import requests

from evidence.decision_settings import (AFTER_CHANGES, APPROVE, DECISION_MARKER, GROUPS, KINDS, LABEL_PREFIX,
                                        MERGE_METHOD, OTHER_GROUP, RAISED_BY, REJECT, REQUIRED_CHECK, WAIT_WARN_DAYS)
from evidence.github_api import ask as _ask

PAGE_SIZE = 100   # GitHub's largest page
FINDING_DECISION_MARKER = "admin-finding-decision"
_FINDINGS_BLOCK = re.compile(r"<!--\s*findings\s*\r?\n(.*?)\r?\n-->", re.DOTALL)
_VALID_FID = re.compile(r"^[A-Za-z0-9_-]+$")
_FINDING_LINE = re.compile(rf"^<!-- {FINDING_DECISION_MARKER}: ({re.escape(APPROVE)}|{re.escape(REJECT)}); "
                           r"finding: ([A-Za-z0-9_-]+); sha: (\S+) -->$")


def _fetch(token, state):
    """Pull requests in one GitHub state, as GitHub's JSON."""
    rows, page = [], 1
    while True:
        rows += (got := _ask("GET", "/pulls", token, params={"state": state, "per_page": PAGE_SIZE, "page": page}))
        if len(got) < PAGE_SIZE:
            return rows
        page += 1


def fetch_open(token):
    """Every open pull request, as GitHub's JSON."""
    return _fetch(token, "open")


def fetch_recent_closed(token):
    """The most recently updated closed pull requests: one page, enough for the Live pipeline's recent decisions and
    merges. Not every closed one ever: that list only grows, and the page reads GitHub every few minutes."""
    return _ask("GET", "/pulls", token, params={"state": "closed", "sort": "updated", "direction": "desc",
                                                 "per_page": PAGE_SIZE})


def fetch_comments(token, number):
    """All comments on one pull request's issue thread, page by page."""
    rows, page = [], 1
    while True:
        got = _ask("GET", f"/issues/{number}/comments", token, params={"per_page": PAGE_SIZE, "page": page})
        rows += got
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


def findings_block(findings):
    """One hidden findings block for a pull request body."""
    payload = json.dumps({"findings": findings}, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e")
    return f"<!-- findings\n{payload}\n-->"


def has_findings_block(body):
    """Whether a pull request body carries a findings block."""
    return bool(_FINDINGS_BLOCK.search(body or ""))


def findings(body):
    """Findings from a pull request body, or [] if there is no readable block."""
    return _findings_read(body)[0]


def _findings_read(body):
    """(findings, unreadable): unreadable only when a block is present but cannot be read as the expected JSON shape."""
    match = _FINDINGS_BLOCK.search(body or "")
    if not match:
        return [], False
    try:
        payload = json.loads(match.group(1))
    except (TypeError, ValueError, RecursionError):
        return [], True
    if not isinstance(payload, dict) or not isinstance(payload.get("findings"), list):
        return [], True
    cleaned, seen_ids = [], set()
    for raw in payload["findings"]:
        finding = _clean_finding(raw, seen_ids)
        if finding:
            cleaned.append(finding)
    return cleaned, False


def _clean_finding(raw, seen_ids):
    if not isinstance(raw, dict):
        return None
    finding_id, category, statement = raw.get("id"), raw.get("category"), raw.get("statement")
    if not all(isinstance(value, str) and value for value in (finding_id, category, statement)):
        return None
    if not _VALID_FID.match(finding_id) or finding_id in seen_ids:
        return None
    seen_ids.add(finding_id)
    row = {"id": finding_id, "category": category, "statement": statement}
    if isinstance(raw.get("detail"), str):
        row["detail"] = raw["detail"]
    row["sources"] = _clean_rows(raw.get("sources"), ("source", "line", "grade"), ("grade_note", "link"))
    row["measured"] = _clean_rows(raw.get("measured"), ("what", "value"), ("link",))
    return row


def _clean_rows(raw_rows, required, optional):
    rows = []
    if not isinstance(raw_rows, list):
        return rows
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        if not all(isinstance(raw.get(name), str) and raw[name] for name in required):
            continue
        row = {name: raw[name] for name in required}
        for name in optional:
            if isinstance(raw.get(name), str):
                row[name] = raw[name]
        rows.append(row)
    return rows


def pending(prs, now):
    """The pull requests that wait on a decision, as plain items, the longest waiting first."""
    items = []
    for pr in prs:
        kind = kind_of(pr)
        if kind is None:
            continue
        opened = datetime.fromisoformat(pr["created_at"])
        login = (pr.get("user") or {}).get("login", "a deleted account")   # GitHub sends no user for a deleted one
        body = pr["body"] or ""
        found, unreadable = _findings_read(body)
        items.append({"number": pr["number"], "title": pr["title"], "kind": kind, "group": KINDS.get(kind, OTHER_GROUP),
                      "summary": summary(body), "body": body, "findings": found, "findings_unreadable": unreadable,
                      "link": pr["html_url"],
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


def blocker(choice, item, reason, changes, state="open", tests=None, mergeable=None, sha=None):
    """Why this decision cannot be made now, in plain words, or None when it can.

    `state` is the pull request's, read just now; for an approval as proposed, so are `tests`, `mergeable` and `sha`.
    Anyone on the list may decide any item, including one they raised (decided 22 Oct 2026, issue 17).
    """
    if state != "open":
        return "It was already decided (merged or closed) after the page read it. Nothing more was written."
    if not reason.strip():
        return "Write the reason first: every decision needs one."
    if choice == AFTER_CHANGES and not changes.strip():
        return "Say which changes are asked for."
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


def plain(text):
    return text.strip().replace("<!--", "&lt;!--")


def decision_text(choice, reason, changes, who, when):
    """The comment written on the pull request. It starts with a marker so outcomes can be counted later; what was
    typed cannot fake one."""
    return "\n".join([f"<!-- {DECISION_MARKER}: {choice} -->", f"**Decision on the admin page: {choice}.**", "",
                      f"Reason: {plain(reason)}"] + (["", f"Changes asked for: {plain(changes)}"] if changes.strip() else [])
                     + ["", f"Decided by {plain(who)} on {when.day} {when:%b %Y, %H:%M} UTC, signed in on the admin page."])


def finding_decisions(comments, sha):
    """{finding id: choice} from comment markers on this sha, latest comment per finding winning."""
    by_id = {}
    for comment in comments:
        parsed = _finding_marker(comment.get("body", ""))
        if parsed and parsed["sha"] == sha:
            by_id[parsed["id"]] = parsed["choice"]
    return by_id


def finding_stale_ids(comments, sha):
    """Finding ids that have a decision marker, but only on an older sha."""
    stale, current = set(), set()
    for comment in comments:
        parsed = _finding_marker(comment.get("body", ""))
        if not parsed:
            continue
        (current if parsed["sha"] == sha else stale).add(parsed["id"])
    return stale - current


def _finding_marker(body):
    first = (body or "").splitlines()[0] if body else ""
    if not (match := _FINDING_LINE.match(first)):
        return None
    return {"choice": match.group(1), "id": match.group(2), "sha": match.group(3)}


def finding_decision_text(finding, choice, reason, who, when, sha):
    """The comment for one finding decision on a specific pull request sha."""
    words = "approved" if choice == APPROVE else "rejected"
    return "\n".join([f"<!-- {FINDING_DECISION_MARKER}: {choice}; finding: {finding['id']}; sha: {sha} -->",
                      f"**Decision on finding {plain(finding['id'])} ({plain(finding['category'])}): {words}.**", "",
                      f"Reason: {plain(reason)}", "",
                      f"Decided by {plain(who)} on {when.day} {when:%b %Y, %H:%M} UTC, signed in on the admin page."])


def decide(token, item, choice, reason, changes, who, now):
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
    problem = blocker(choice, item, reason, changes, **read)
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


def decide_finding(token, item, finding, choice, reason, who, now):
    """Write a decision on one finding, and merge or close when that finishes the pull request's outcome."""
    number = item["number"]
    if choice not in {APPROVE, REJECT}:
        return "warn", "Choose Approve or Reject."
    if not reason.strip():
        return "warn", "Write the reason first: every decision needs one."
    pull = _ask("GET", f"/pulls/{number}", token)
    if pull["state"] != "open":
        return "warn", "It was already decided (merged or closed) after the page read it. Nothing more was written."
    if not (sha := (pull.get("head") or {}).get("sha")):
        return "warn", "Its branch no longer exists, so it cannot be merged. Look at the pull request on GitHub."
    if sha != item["sha"]:
        return "warn", "The pull request changed after the page read it. Read the new version before deciding."
    finding_ids = [row["id"] for row in item["findings"]]
    pull_finding_ids = [row["id"] for row in findings(pull.get("body") or "")]
    if sorted(pull_finding_ids) != sorted(finding_ids):
        return "warn", "Its findings changed after the page read them. Read the new version before deciding."
    if finding["id"] not in pull_finding_ids:
        return "warn", "That finding is no longer on the pull request. Read the new version before deciding."
    now_by_id = finding_decisions(fetch_comments(token, number), sha)
    after_by_id = {**now_by_id, finding["id"]: choice}
    approved = [fid for fid in finding_ids if after_by_id.get(fid) == APPROVE]
    rejected = [fid for fid in finding_ids if after_by_id.get(fid) == REJECT]
    all_approved = all(after_by_id.get(fid) == APPROVE for fid in finding_ids)
    all_rejected = all(after_by_id.get(fid) == REJECT for fid in finding_ids)

    _ask("POST", f"/issues/{number}/comments", token, json={"body": finding_decision_text(finding, choice, reason, who, now, sha)})
    if all_approved or all_rejected:
        status, words = finish(token, item, who, now)
        if status == "warn":   # the finding is recorded; the page offers Merge or Close once the reason is resolved
            return "warn", (f"{'Approved' if choice == APPROVE else 'Rejected'}, and recorded. Pull request {number} is not "
                            f"{'merged' if all_approved else 'closed'} yet: {words} Use the button on the page then.")
        return status, words

    if choice == APPROVE:
        if rejected:
            return "ok", f"Approved. Pull request {number} cannot merge while finding {sorted(rejected)[0]} is rejected."
        left = len(finding_ids) - len(approved)
        return "ok", (f"Approved. Pull request {number} merges when its other {left} finding"
                      f"{'' if left == 1 else 's'} {'is' if left == 1 else 'are'} approved.")
    return "ok", (f"Rejected. Pull request {number} stays open but will not merge while a finding is rejected: it needs "
                  "changing to drop that change (the weekly job proposes again next run), or reject its other findings to close it.")


def finish(token, item, who, now):
    """Finish a pull request once its findings have all been approved or all rejected."""
    number = item["number"]
    pull = _ask("GET", f"/pulls/{number}", token)
    if pull["state"] != "open":
        return "warn", "It was already decided (merged or closed) after the page read it. Nothing more was written."
    if not (sha := (pull.get("head") or {}).get("sha")):
        return "warn", "Its branch no longer exists, so it cannot be merged. Look at the pull request on GitHub."
    if sha != item["sha"]:
        return "warn", "The pull request changed after the page read it. Read the new version before deciding."
    item_finding_ids = [row["id"] for row in item["findings"]]
    pull_finding_ids = [row["id"] for row in findings(pull.get("body") or "")]
    if sorted(pull_finding_ids) != sorted(item_finding_ids):
        return "warn", "Its findings changed after the page read them. Read the new version before deciding."

    by_id = finding_decisions(fetch_comments(token, number), sha)
    all_approved = item_finding_ids and all(by_id.get(fid) == APPROVE for fid in item_finding_ids)
    all_rejected = item_finding_ids and all(by_id.get(fid) == REJECT for fid in item_finding_ids)
    if not all_approved and not all_rejected:
        return "warn", f"Pull request {number} is still waiting: not every finding is approved or rejected yet."

    if all_approved:
        read = {"state": pull["state"], "sha": sha, "mergeable": pull["mergeable"], "tests": tests_state(token, sha)}
        if problem := blocker(APPROVE, item, "Every finding was approved.", "", **read):
            return "warn", problem
        try:
            _ask("POST", f"/issues/{number}/comments", token,
                 json={"body": decision_text(APPROVE, f"Every finding was approved: {', '.join(sorted(item_finding_ids))}.",
                                             "", who, now)})
            _ask("PUT", f"/pulls/{number}/merge", token, json={"merge_method": MERGE_METHOD, "sha": sha})
        except requests.RequestException:
            return "bad", (f"The decision is written on pull request {number}, but GitHub did not merge it. Do that on "
                           "GitHub, not here: deciding again would write the decision twice.")
        return "ok", f"Approved. Every finding of pull request {number} is approved, so it is merged."

    try:
        _ask("POST", f"/issues/{number}/comments", token,
             json={"body": decision_text(REJECT, f"Every finding was rejected: {', '.join(sorted(item_finding_ids))}.",
                                         "", who, now)})
        _ask("PATCH", f"/pulls/{number}", token, json={"state": "closed"})
    except requests.RequestException:
        return "bad", (f"The decision is written on pull request {number}, but GitHub did not close it. Do that on "
                       "GitHub, not here: deciding again would write the decision twice.")
    return "ok", f"Rejected. Every finding of pull request {number} is rejected, so it is closed."
