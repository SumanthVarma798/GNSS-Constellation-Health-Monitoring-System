"""A pull request's change to the registry tables, row by row: what is added, changed and removed, what the dashboard
shows from it, and what in it needs a person's look.

It reads a unified diff: the console's Approvals page gets one per file from GitHub, the weekly job from `git diff`
(scripts/describe_table_changes.py), so both say the same. The words and the per-table settings are in
evidence/table_change_settings.py.
"""
import csv

from evidence.table_change_settings import COLUMN_WORDS, NAMED_AT_MOST, ROUTINE_WORDS, TABLES


def split_diff(text):
    """{path: patch} from `git diff` output: each file's lines from its first @@ on."""
    patches, path = {}, None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            path = line.split(" b/", 1)[1]
            patches[path] = None
        elif path and (line.startswith("@@") or patches[path] is not None):
            patches[path] = (patches[path] or []) + [line]
    return {path: "\n".join(lines or []) for path, lines in patches.items()}


def table_change(path, patch, additions=0, deletions=0):
    """One file's change. A table listed in TABLES is read row by row; any other file, or a table GitHub gave no diff
    for (too large), is only counted in lines ("readable" False)."""
    settings = TABLES.get(path)
    change = {"path": path, "settings": settings, "lines": (additions, deletions), "readable": False,
              "added": [], "removed": [], "changed": [], "routine": []}
    if settings is None or patch is None:
        return change
    columns, header = settings["columns"], ",".join(settings["columns"])
    old, new = {}, {}
    for line in patch.splitlines():
        if line[:1] not in ("+", "-") or line[1:] == header:
            continue
        row = dict(zip(columns, next(csv.reader([line[1:]]), [])))
        (new if line[0] == "+" else old)[tuple(row.get(column, "") for column in settings["key"])] = row
    change["readable"] = True
    change["added"] = [row for key, row in new.items() if key not in old]
    change["removed"] = [row for key, row in old.items() if key not in new]
    for key in [key for key in new if key in old]:
        differs = [(column, old[key].get(column, ""), new[key].get(column, "")) for column in columns
                   if old[key].get(column, "") != new[key].get(column, "")]
        if differs:
            routine = all(column in settings.get("routine", ()) for column, _, _ in differs)
            change["routine" if routine else "changed"].append({"row": new[key], "differs": differs})
    return change


def label(row, settings):
    """A row's name for a reader from its label columns: 'OBJECT A (2026-252A)', 'GLONASS'."""
    first, *rest = [row[column] for column in settings.get("label", settings["key"]) if row.get(column)] or [""]
    return f"{first} ({', '.join(rest)})" if rest else first


def named(rows, settings):
    """Up to NAMED_AT_MOST rows by name, then how many more."""
    names = [label(row.get("row", row), settings) for row in rows]
    if (more := len(names) - NAMED_AT_MOST) > 0:
        return f"{', '.join(names[:NAMED_AT_MOST])} and {more} more"
    return " and ".join([", ".join(names[:-1]), names[-1]]) if len(names) > 1 else "".join(names)


def words(column):
    return COLUMN_WORDS.get(column, column.replace("_", " "))


def details(row, settings):
    """What an added or removed row holds, in words, leaving out what names it; 'every detail blank' when nothing."""
    shown = set(settings["key"]) | set(settings.get("label", ()))
    parts = [f"{words(column)}: {value}" for column, value in row.items() if column not in shown and value]
    return "; ".join(parts) or "every detail blank"


def differs_text(differs):
    """'registry satellites 101 → 102; not found in GCAT 1 → 2'."""
    return "; ".join(f"{words(column)} {was or 'blank'} → {now or 'blank'}" for column, was, now in differs)


def counts(changes):
    """(rows added, rows changed, rows removed) over the tables read row by row; routine changes count as changed."""
    tables = [change for change in changes if change["readable"]]
    return (sum(len(c["added"]) for c in tables), sum(len(c["changed"]) + len(c["routine"]) for c in tables),
            sum(len(c["removed"]) for c in tables))


def _rows(number, one="row"):
    return "none" if number == 0 else f"{number} {one}{'' if number == 1 else 's'}"


def asked(who, changes):
    """The ask in one sentence: 'The weekly job asks to change 4 registry tables: 3 rows added, 27 changed, none removed.'"""
    tables = sum(change["readable"] for change in changes)
    files = len(changes) - tables
    added, changed, removed = counts(changes)
    what = " and ".join(part for part in (f"{tables} registry table{'' if tables == 1 else 's'}" if tables else "",
                                          f"{files} other file{'' if files == 1 else 's'}" if files else "") if part)
    sentence = f"{who[:1].upper()}{who[1:]} asks to change {what or 'nothing'}"
    if tables:
        sentence += (f": {_rows(added)} added, {'none' if not changed else changed} changed, "
                     f"{'none' if not removed else removed} removed")
    return sentence + "."


def shown(changes):
    """What the dashboard shows differently once it is merged: ([(page, [what, ...])], [table names no page shows])."""
    pages, unseen = {}, []
    for change in changes:
        if not (settings := change["settings"]) or not (change["added"] or change["removed"] or change["changed"]
                                                         or change["routine"] or not change["readable"]):
            continue
        if not settings["shows"]:
            unseen.append(settings["name"])
        for page, what in settings["shows"].items():
            if what not in pages.setdefault(page, []):
                pages[page].append(what)
    return list(pages.items()), unseen


def shown_text(changes):
    """'the Library (owner and status, the counts) and the Master map (owner and status). No page shows: payloads ...'"""
    pages, unseen = shown(changes)
    parts = [f"{page} ({', '.join(what)})" for page, what in pages]
    text = (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else "".join(parts))
    text = f"On the dashboard: {text}." if text else "Nothing on the dashboard reads these files."
    return text + (f" No page shows {', '.join(unseen).lower()}." if unseen and pages else "")


def needs_a_look(changes):
    """What is unusual or risky, apart from the routine rows: [(tone, title, detail)]."""
    found = []
    for change in changes:
        settings = change["settings"]
        if settings is None:
            continue
        if not change["readable"]:
            found.append(("warn", f"{settings['name']}: GitHub gave no row-by-row change",
                          f"{change['path']} is too large to show here. Look at it on GitHub before deciding."))
            continue
        source = settings["source"][0]
        if change["removed"]:
            found.append(("warn", f"{_rows(len(change['removed']))} removed from {settings['name']}",
                          f"{named(change['removed'], settings)}. A removal takes effect only with this approval, and the "
                          "decision is the record of it."))
        if flag := settings.get("flag_added"):
            if rows := change["added"]:
                found.append(("warn", f"{len(rows)} {flag[0] if len(rows) == 1 else flag[1]}",
                              f"{named(rows, settings)}, from {source}. {flag[2]}"))
            continue
        blank = [row for row in change["added"] if details(row, settings) == "every detail blank"]
        if blank:
            found.append(("warn", f"{named(blank, settings)} added with every detail blank",
                          f"{source[:1].upper()}{source[1:]} has no entry for {'it' if len(blank) == 1 else 'them'} yet, "
                          f"so {'its row' if len(blank) == 1 else 'their rows'} in {settings['name']} "
                          f"{'is' if len(blank) == 1 else 'are'} empty."))
    return found


def by_kind(changes):
    """[(kind, change, rows, words)] for a short list: what was added, changed (the routine apart) and removed."""
    rows = []
    for kind, part in (("Added", "added"), ("Changed", "changed"), ("Changed, routine", "routine"), ("Removed", "removed")):
        for change in changes:
            if change["readable"] and change[part]:
                settings = change["settings"]
                said = (ROUTINE_WORDS.get(change["path"], "routine") if part == "routine"
                        else named(change[part], settings))
                rows.append((kind, change, len(change[part]), said))
    rows += [("Changed", change, None, f"{change['lines'][0]} lines added, {change['lines'][1]} removed")
             for change in changes if not change["readable"]]
    return rows


def markdown(changes):
    """The same change as a pull request section, for GitHub."""
    out = ["## What changed, table by table", ""]
    for change in changes:
        settings = change["settings"]
        if not change["readable"]:
            out += [f"- `{change['path']}`: {change['lines'][0]} lines added, {change['lines'][1]} removed.", ""]
            continue
        name, link = settings["source"]
        added, changed, removed = counts([change])
        out += [f"### {settings['name']}: {_rows(added)} added, {changed or 'none'} changed, {removed or 'none'} removed",
                "", f"From {f'[{name}]({link})' if link else name}.", ""]
        out += [f"- Added {label(row, settings)}: {details(row, settings)}." for row in change["added"]]
        out += [f"- {label(row['row'], settings)}: {differs_text(row['differs'])}." for row in change["changed"]]
        if change["routine"]:
            out.append(f"- {len(change['routine'])} routine: {ROUTINE_WORDS.get(change['path'], 'routine')} "
                       f"({named(change['routine'], settings)}).")
        out += [f"- Removed {label(row, settings)}: {details(row, settings)}." for row in change["removed"]]
        out.append("")
    look = needs_a_look(changes)
    out += ["## Needs a look", ""] + ([f"- **{title}.** {detail}" for _, title, detail in look] or ["- Nothing unusual."])
    return "\n".join(out) + "\n"
