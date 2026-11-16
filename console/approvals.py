"""Approvals: the changes waiting for a person, with their context, and the decision on each.

Each item is an open pull request labelled "decision: <kind>" (evidence/decisions.py). The decision is written on the
pull request as a comment, then it is merged, left open or closed (decided 20 Oct 2026, issue 17).
"""
from html import escape

import requests
import streamlit as st

from console import common
from evidence import decisions, table_changes
from evidence.decision_settings import (ACTIONS, AFTER_CHANGES, APPROVE, CHOICES, FINDING_ACTIONS, FINDING_CATEGORIES,
                                        MERGE_WORDS, OTHER_FINDINGS, REJECT, REPOSITORY, TESTS_WORDS)
from ui import admin, console

FINDING_CHOICES = {APPROVE: "Approve", REJECT: "Reject"}


def waiting(days):
    """How long an item has waited, as a status: decisions.waited gives (words, tone)."""
    words, tone = decisions.waited(days)
    return console.status(tone, words)


def decide(item, config, who):
    """The call on one item: a choice, then the reason (and the changes asked for), then one button that records it."""
    number = item["number"]
    with st.container(key=f"decide_{number}"):
        said = st.session_state.get("admin_result")
        if said and said[0] == number:   # why the last try on this item did not go through, beside it
            st.html(console.notice(said[2], said[1]))
            del st.session_state["admin_result"]
        choice = st.radio("Decision", list(CHOICES), format_func=CHOICES.get, key=f"choice_{number}", index=None,
                          horizontal=True)
        if choice is None:
            return
        reason = st.text_area("Reason (every decision needs one)", key=f"reason_{number}", height=80)
        changes = (st.text_area("Changes asked for", key=f"changes_{number}", height=80) if choice == AFTER_CHANGES
                   else "")
        st.html(f'<p class="c-legend">This writes the decision on pull request {number}, {escape(ACTIONS[choice])}.</p>')
        if st.button(f"Record: {CHOICES[choice]}", key=f"record_{number}", type="primary"):
            try:
                result = decisions.decide(config["github_token"], item, choice, reason, changes, who, common.now())
            except requests.RequestException as error:
                result = "bad", common.github_trouble(error)
            st.session_state["admin_result"] = (number, *result)
            common.github.clear()   # read again: GitHub may have changed, whatever the outcome
            if result[0] == "ok":
                for key in (f"choice_{number}", f"reason_{number}", f"changes_{number}"):
                    st.session_state.pop(key, None)
            st.rerun()


def finding_status(item, by_id, finding_id):
    if by_id.get(finding_id) == APPROVE:
        return console.status("ok", "approved")
    if by_id.get(finding_id) == REJECT:
        return console.status("bad", "rejected")
    return waiting(item["waited_days"])


def finding_row(link, words):
    return f'<a href="{escape(link, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(words)}</a>'


def source_name(source):
    if source.get("link", "").startswith("https://"):
        return finding_row(source["link"], source["source"])
    return escape(source["source"])


def grade_text(source):
    note = f' <span class="muted">({escape(source["grade_note"])})</span>' if source.get("grade_note") else ""
    return f'{escape(source["grade"])}{note}'


def measured_value(row):
    value = escape(row["value"])
    return f'{value} · {finding_row(row["link"], "link")}' if row.get("link", "").startswith("https://") else value


def finding_decide(item, finding, by_id, config, who):
    number, finding_id = item["number"], finding["id"]
    choice = st.radio("Decision", [APPROVE, REJECT], format_func=FINDING_CHOICES.get,
                      key=f"finding_choice_{number}_{finding_id}", index=None, horizontal=True)
    if choice is None:
        return
    reason = st.text_area("Reason (every decision needs one)", key=f"finding_reason_{number}_{finding_id}", height=80)
    others = [row["id"] for row in item["findings"] if row["id"] != finding_id]
    last_approval = choice == APPROVE and all(by_id.get(other) == APPROVE for other in others)
    legend = (f"This {escape(FINDING_ACTIONS[choice])} and, once tests have passed, merges pull request {number}."
              if last_approval else f"This {escape(FINDING_ACTIONS[choice])}.")
    st.html(f'<p class="c-legend">{legend}</p>')
    if st.button(f"Record: {FINDING_CHOICES[choice]}", key=f"record_finding_{number}_{finding_id}", type="primary"):
        try:
            result = decisions.decide_finding(config["github_token"], item, finding, choice, reason, who, common.now())
        except requests.RequestException as error:
            result = "bad", common.github_trouble(error)
        st.session_state["admin_finding_result"] = ((number, finding_id), *result)
        common.github.clear()
        if result[0] == "ok":
            for key in (f"finding_choice_{number}_{finding_id}", f"finding_reason_{number}_{finding_id}"):
                st.session_state.pop(key, None)
        st.rerun()


def one_finding(item, finding, by_id, stale, decided_count, config, who):
    # Kept open while a decision on it is under way: choosing or typing reruns the page, which would fold it shut.
    deciding = st.session_state.get(f"finding_choice_{item['number']}_{finding['id']}") is not None
    with st.expander(f"{escape(finding['id'])}: sources, what we measured, decision", expanded=deciding):
        if finding.get("detail"):
            st.html(f"<p class='c-pr-tag'>{escape(finding['detail'])}</p>")
        st.html("<p class='c-subhead'>Sources</p>")
        st.html(console.list_view(["Source", "What it says", "Grade"],
                                  [[source_name(source), escape(source["line"]), grade_text(source)]
                                   for source in finding["sources"]]))
        st.html("<p class='c-subhead'>What we measured</p>")
        if finding["measured"]:
            st.html(console.list_view(["What", "Value"],
                                      [[escape(row["what"]), measured_value(row)] for row in finding["measured"]]))
        else:
            st.html('<p class="muted">Nothing measured for this finding.</p>')
        number = item["number"]
        st.html(f'<p class="muted c-pr-tag" data-pr="{number}">Pull request '
                f'<a href="{escape(item["link"], quote=True)}" target="_blank" rel="noopener noreferrer">{number}</a> · '
                f'finding {escape(finding["id"])} · {decided_count} of {len(item["findings"])} findings decided</p>')
        if finding["id"] in stale and finding["id"] not in by_id:
            st.html(console.notice("Decided on an earlier version of the pull request; decide again.", "warn"))
        if finding["id"] not in by_id:
            finding_decide(item, finding, by_id, config, who)


def finding_finish(item, by_id, all_approved, config, who):
    number = item["number"]
    if all_approved:
        st.html(console.notice(f"Pull request {number}: every finding is approved, but it is not merged yet.", "warn"))
        label = f"Merge pull request {number}"
    else:
        st.html(console.notice(f"Pull request {number}: every finding is rejected, but it is not closed yet.", "warn"))
        label = f"Close pull request {number}"
    if st.button(label, key=f"finish_{number}", type="primary"):
        try:
            result = decisions.finish(config["github_token"], item, who, common.now())
        except requests.RequestException as error:
            result = "bad", common.github_trouble(error)
        st.session_state["admin_result"] = (number, *result)
        common.github.clear()
        st.rerun()


def show_findings(items, comments, reviews, config, who):
    for item in items:   # what each pull request asks, as for any other; its findings are decided one by one below
        changes = changes_of(reviews.get(item["number"]))
        look = table_changes.needs_a_look(changes)
        review_summary(item, reviews.get(item["number"]), changes, look)
        changes_by_kind(item, changes, look)
        deeper(item, reviews.get(item["number"]), changes)
    rows = []
    finish_rows = []
    for item in items:
        by_id = decisions.finding_decisions(comments.get(item["number"], []), item["sha"])
        stale = decisions.finding_stale_ids(comments.get(item["number"], []), item["sha"])
        decided_count = sum(finding["id"] in by_id for finding in item["findings"])
        finding_ids = [finding["id"] for finding in item["findings"]]
        all_approved = finding_ids and all(by_id.get(fid) == APPROVE for fid in finding_ids)
        all_rejected = finding_ids and all(by_id.get(fid) == REJECT for fid in finding_ids)
        if all_approved or all_rejected:
            finish_rows.append((item, by_id, all_approved))
        for finding in item["findings"]:
            rows.append({"item": item, "finding": finding, "by_id": by_id, "stale": stale, "decided_count": decided_count,
                         "category": finding["category"] if finding["category"] in FINDING_CATEGORIES else OTHER_FINDINGS,
                         "waiting": finding["id"] not in by_id})
    for item, by_id, all_approved in finish_rows:
        finding_finish(item, by_id, all_approved, config, who)
    for category in [*FINDING_CATEGORIES, OTHER_FINDINGS]:
        grouped = [row for row in rows if row["category"] == category]
        if not grouped:
            continue
        waiting_count = sum(row["waiting"] for row in grouped)
        st.html(console.section(category, console.list_view(
            ["Finding", "Status"], [[escape(row["finding"]["statement"]),
                                     finding_status(row["item"], row["by_id"], row["finding"]["id"])] for row in grouped]),
                                right=f"{waiting_count} waiting", flush=True))
        for row in grouped:
            one_finding(row["item"], row["finding"], row["by_id"], row["stale"], row["decided_count"], config, who)


def source_html(settings):
    name, link = settings["source"] if settings else ("–", "")
    return finding_row(link, name) if link else escape(name)


def changes_of(reading):
    return [table_changes.table_change(f["path"], f["patch"], f["additions"], f["deletions"])
            for f in (reading or {}).get("files", [])]


def review_summary(item, reading, changes, look):
    """What is asked and what it does, its checks, how much needs a look, then who raised it: one property sheet."""
    opened, number = item["opened"], item["number"]
    if reading:
        asked = escape(table_changes.asked(item["raised_by"], changes))
        checks = " ".join([console.status(*TESTS_WORDS.get(reading["tests"], TESTS_WORDS["not run"])),
                           console.status(*MERGE_WORDS.get(reading["mergeable"], MERGE_WORDS[None]))])
        unusual = (console.status("warn", f"{len(look)} thing{'' if len(look) == 1 else 's'}") if look
                   else console.status("ok", "nothing unusual"))
        rows = [("Asked", asked), ("If approved", escape(table_changes.shown_text(changes))), ("Checks", checks),
                ("Needs a look", unusual)]
    else:
        rows = [("Asked", admin.text_html(item["summary"]) if item["summary"] else "<span class='muted'>no summary</span>"),
                ("Checks", console.status("warn", "GitHub did not give its changes or checks: look on GitHub"))]
    rows += [("Raised by", f"{escape(item['raised_by'])}, {opened.day} {opened:%b %Y}, {waiting(item['waited_days'])}"),
             ("On GitHub", finding_row(item["link"], f"pull request {number}"))]
    st.html(console.section(f"Pull request {number}: {item['title']}", console.key_values(rows)))


def changes_by_kind(item, changes, look):
    """The changes as a short list by kind, the routine ones apart, then what is unusual, separated from them."""
    if changes:
        rows = [[escape(kind), escape(change["settings"]["name"] if change["settings"] else change["path"]),
                 escape(f"{count}: {said}" if count is not None else said), source_html(change["settings"])]
                for kind, change, count, said in table_changes.by_kind(changes)]
        st.html(console.section("Changes, by kind", console.list_view(["Kind", "Table", "Rows", "From"], rows),
                                right=f"pull request {item['number']}", flush=True))
    if look:
        st.html(console.section("Needs a look", console.attention([(tone, title, detail, None) for tone, title, detail in look]),
                                right=f"pull request {item['number']}", flush=True))


def each_change_html(change):
    """One table's rows, old value beside new, routine rows folded away, and where they come from."""
    settings = change["settings"]
    rows = [[escape(table_changes.label(row, settings)), "added", "–", escape(table_changes.details(row, settings))]
            for row in change["added"]]
    rows += [[escape(table_changes.label(row["row"], settings)), escape(table_changes.words(column)), escape(was or "blank"),
              escape(now or "blank")] for row in change["changed"] for column, was, now in row["differs"]]
    rows += [[escape(table_changes.label(row, settings)), "removed", escape(table_changes.details(row, settings)), "–"]
             for row in change["removed"]]
    columns = ["Row", "What", "Was", "Now"]
    html = console.list_view(columns, rows) if rows else ""
    if routine := change["routine"]:
        html += (f'<details class="c-more"><summary>{len(routine)} routine: '
                 f'{escape(table_changes.ROUTINE_WORDS.get(change["path"], "routine"))}</summary>'
                 + console.list_view(columns, [[escape(table_changes.label(row["row"], settings)),
                                                escape(table_changes.words(column)), escape(was), escape(now)]
                                               for row in routine for column, was, now in row["differs"]]) + "</details>")
    return html + f'<p class="c-legend">From {source_html(settings)}</p>'


def deeper(item, reading, changes):
    """One step deeper, on request: each change with its source, the description by its headings, the raw diff."""
    readable = [change for change in changes if change["readable"]]
    if readable:
        with st.expander("Each change: old and new value, and its source"):
            for change in readable:
                st.html(console.section(change["settings"]["name"], each_change_html(change), right=change["path"]))
    with st.expander("The pull request's description, by heading"):
        st.html(admin.description_html(decisions.without_findings_block(item["body"])))
    if reading and reading["files"]:
        with st.expander("The raw diff, file by file"):
            st.html("".join(f'<details class="c-more"><summary>{escape(f["path"])} (+{f["additions"]} −{f["deletions"]})'
                            f'</summary><pre class="c-diff">{escape(f["patch"] or "GitHub gives no diff for a file this large.")}'
                            "</pre></details>" for f in reading["files"]))


def old_style_item(item, reading, config, who):
    if item["findings_unreadable"]:
        st.html(console.notice("Its findings block could not be read, so it is shown as one item.", "warn"))
    changes = changes_of(reading)
    look = table_changes.needs_a_look(changes)
    review_summary(item, reading, changes, look)
    changes_by_kind(item, changes, look)
    decide(item, config, who)
    deeper(item, reading, changes)


config = common.settings()
email = st.user.get("email")
who = st.user.get("name") or email
seen = common.read()
items = decisions.pending(seen["prs"], common.now())
finding_items = [item for item in items if item["findings"] and not item["findings_unreadable"]]
old_items = [item for item in items if item["findings_unreadable"] or not item["findings"]]

body, actions = common.layout("approvals", "Approvals", "Changes the system proposes, and changes made from this "
                                                        "console. Each is a pull request; approving merges it.")
with body:
    said = st.session_state.get("admin_result")
    if said and (said[1] == "ok" or said[0] not in {i["number"] for i in items}):   # its item has left the list
        st.html(console.notice(said[2], said[1]))
        del st.session_state["admin_result"]
    finding_said = st.session_state.get("admin_finding_result")
    if finding_said:
        st.html(console.notice(finding_said[2], finding_said[1]))
        del st.session_state["admin_finding_result"]
    if not items:
        st.html(console.notice(f"Nothing is waiting for a decision. GitHub lists {len(seen['prs'])} open pull "
                               f"request{'' if len(seen['prs']) == 1 else 's'}, none labelled for a decision.", "ok"))
    if finding_items:
        show_findings(finding_items, seen.get("comments", {}), seen.get("reviews", {}), config, who)
    for group, its in decisions.grouped(old_items):
        st.html(console.section(group, console.list_view(
            ["Item", "Kind", "Raised by", "Waiting"],
            [[escape(i["title"]), escape(i["kind"]), escape(i["raised_by"]), waiting(i["waited_days"])]
             for i in its]), right=f"{len(its)} waiting, the longest first", flush=True))
        for item in its:
            old_style_item(item, seen.get("reviews", {}).get(item["number"]), config, who)

with actions:
    common.refresh_action()
    st.html('<p class="c-actions-sub">On GitHub</p>')
    st.link_button("Open pull requests", f"https://github.com/{REPOSITORY}/pulls", icon=":material/open_in_new:")
