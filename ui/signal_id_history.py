"""Signal IDs that changed spacecraft, as pictures: one timeline per signal ID, a bar for each stretch a spacecraft
held it, in the constellation's colour, and a mark where it passed on, which opens the shared tooltip with why.

Reads evidence/master_map.py signal_id_changes; the reason is what the IGS satellite metadata file shows, or a notice
in ui/changes.py where ui/master_map_settings.py ID_NOTICES names one. Every builder returns HTML.
"""
from collections import Counter
from datetime import date
from html import escape

from ui import marks, palette, tooltip
from ui.changes import CHANGES
from ui.master_map_page import _day
from ui.master_map_settings import CHANGE_KINDS, FEATURED_MAX, ID_NOTICES

_NOTICES = {change.id: change for change in CHANGES}


def with_notices(items):
    """items with each change's notices (ui/changes.py Change) under "notices", and its kind set by a notice that gives
    one. A new list; items is not changed."""
    out = []
    for item in items:
        changes = []
        for change in item["changes"]:
            found = [(key, rule) for key, rule in ID_NOTICES.items() if change["on"][:7] == rule["month"] and (
                item["signal_id"] in rule.get("signal_ids", ()) or {change["from"], change["to"]} & set(rule.get("svns", ())))]
            kind = next((rule["kind"] for _, rule in found if "kind" in rule), change["kind"])
            changes.append({**change, "kind": kind, "notices": [_NOTICES[key] for key, _ in found if key in _NOTICES]})
        out.append({**item, "changes": changes})
    return out


def _holders(item):
    return list(dict.fromkeys(p["svn"] for p in item["periods"]))


def featured(items):
    """[(item, why it is brought forward)], at most FEATURED_MAX: the signal ID most spacecraft held, the first swap,
    the first change each notice bears on, then the most-held signal ID of each constellation not yet shown. A swap
    shows once, not again under the other signal ID of the pair."""
    most = sorted(items, key=lambda i: (-len(_holders(i)), -len(i["changes"]), i["signal_id"]))
    picked, seen = [], set()

    def take(item, why):
        if item and item["signal_id"] not in seen and len(picked) < FEATURED_MAX:
            picked.append((item, why))
            seen.add(item["signal_id"])
            seen.update(c["then"] for c in item["changes"] if c["kind"] == "swap")   # its pair

    if most:
        take(most[0], f"{len(_holders(most[0]))} spacecraft")
    take(next((i for i in items if any(c["kind"] == "swap" for c in i["changes"])), None), "swap")
    for key in ID_NOTICES:
        take(next((i for i in items if any(n.id == key for c in i["changes"] for n in c["notices"])), None), "notice")
    shown = {i["signal_id"][0] for i, _ in picked}
    for item in most:
        if item["signal_id"][0] not in shown:
            take(item, f"{len(_holders(item))} spacecraft")
            shown.add(item["signal_id"][0])
    return picked


def _axis(start, today):
    """(x(day) -> percent along the track, the tick marks' HTML) for start .. today."""
    t0, t1 = date.fromisoformat(start).toordinal(), today.toordinal()
    span = max(1, t1 - t0)
    x = lambda day: (date.fromisoformat(day).toordinal() - t0) / span * 100 if day else 100.0
    years = today.year - date.fromisoformat(start).year
    step = 2 if years <= 12 else 5 if years <= 30 else 10
    ticks = [f'<span style="left:{x(f"{year}-01-01"):.2f}%">{year}</span>'
             for year in range(date.fromisoformat(start).year + 1, today.year + 1) if year % step == 0
             and 4 < x(f"{year}-01-01") < 85]   # clear of the ends' labels
    return x, f'<div class="sx-axis">{"".join(ticks)}<span class="end">now</span></div>'


def _bar(period, x, name, colour, alt):
    left, right = x(period["start"]), x(period["end"])
    held = f"{_day(period['start'])} to {_day(period['end']) if period['end'] else 'now'}"
    lines = [("", "Held", f"{period['label']}, {held}")]
    if period["note"]:
        lines.append(("", "IGS note", period["note"]))
    body = tooltip.glance(f"{period['svn']} · {name}", lines)
    trigger = f'<span class="sr">{escape(period["svn"])}, {escape(held)}</span>'
    return (f'<span class="sx-at sx-bar{" alt" if alt else ""}{" now" if period["current"] else ""}" '
            f'style="left:{left:.2f}%;width:max(5px,{right - left:.2f}%);--c:{colour}">'
            f'{tooltip.tip_html(trigger, body, key=period["label"] + period["start"])}</span>')


def _says(item, change):
    """What the table shows about one change, in a few words; "" when only a notice speaks."""
    old, new, then, kind = change["from"], change["to"], change["then"], change["kind"]
    if kind == "swap":
        return f"{old} took {then} from {new}; {new} took {item['signal_id']}"
    if kind == "replaced":
        return f"{old} has no signal ID after {_day(change['ended'])}"
    if kind == "reassigned":
        return f"{old} moved to {then}" if then else ""
    if then == item["signal_id"]:
        return f"{old} held {then} again later"
    return f"{old} took {then} more than a month later" if then else ""


def _mark(item, change, x, names):
    glyph, words, meaning = CHANGE_KINDS[change["kind"]]
    lines = [("", "When", _day(change["on"])),
             ("", "Passed", f"{change['from']} {names.get(change['from'], '')} → {change['to']} {names.get(change['to'], '')}")]
    if _says(item, change):
        lines.append(("", "Shows", _says(item, change)))
    lines += [("", "Notice", f"{n.headline} Source: {n.source}") for n in change["notices"]]
    body = tooltip.glance(f"{glyph} {words}", lines, meaning)
    trigger = (f'<span class="sx-g" aria-hidden="true">{glyph}</span>'
               f'<span class="sr">{escape(item["signal_id"])} {escape(words)}, {escape(_day(change["on"]))}</span>')
    return (f'<span class="sx-at sx-mk {change["kind"]}" style="left:{x(change["on"]):.2f}%">'
            f'{tooltip.tip_html(trigger, body, key=item["signal_id"] + change["on"])}</span>')


def _colour(constellation):
    return palette.css(palette.CONSTELLATION_COLOURS.get(constellation, palette.FILL))


def card(item, why, names, constellations, today):
    """One signal ID brought forward: a lane per spacecraft that held it, each change marked in the new holder's lane."""
    holders, constellation = _holders(item), constellations.get(item["periods"][0]["svn"], "")
    x, axis = _axis(item["periods"][0]["start"], today)
    colour = _colour(constellation)
    lanes = ""
    for svn in holders:
        bars = "".join(_bar(p, x, names.get(svn, svn), colour, False) for p in item["periods"] if p["svn"] == svn)
        marks_html = "".join(_mark(item, c, x, names) for c in item["changes"] if c["to"] == svn)
        lanes += (f'<div class="sx-lane"><span class="sx-who"><b class="num">{escape(svn)}</b>'
                  f'<span class="small muted">{escape(names.get(svn, ""))}</span></span>'
                  f'<div class="sx-track">{bars}{marks_html}</div></div>')
    kinds = Counter(c["kind"] for c in item["changes"])
    tally = "".join(f'<span class="sx-tally {kind}"><span class="sx-g" aria-hidden="true">{CHANGE_KINDS[kind][0]}</span>'
                    f'<b class="num">{n}</b> {escape(CHANGE_KINDS[kind][1])}</span>' for kind, n in kinds.items())
    return (f'<div class="raised sx-card"><div class="sx-head">{marks.mark(constellation)}'
            f'<b class="big num">{escape(item["signal_id"])}</b><span class="chip accent">{escape(why)}</span>'
            f'<span class="sx-tallies">{tally}</span></div>'
            f'<div class="sx-lanes">{lanes}<div class="sx-lane"><span></span>{axis}</div></div></div>')


def _row(item, x, names, colour):
    """One signal ID in the full list: all its holders on one track, neighbours told apart by shade."""
    order = {svn: i for i, svn in enumerate(_holders(item))}
    bars = "".join(_bar(p, x, names.get(p["svn"], p["svn"]), colour, order[p["svn"]] % 2) for p in item["periods"])
    marks_html = "".join(_mark(item, c, x, names) for c in item["changes"])
    return (f'<div class="sx-lane"><span class="sx-who"><b class="num">{escape(item["signal_id"])}</b>'
            f'<span class="small muted">{len(order)} spacecraft</span></span>'
            f'<div class="sx-track">{bars}{marks_html}</div></div>')


def listing(items, names, constellations, today):
    """Every signal ID that changed spacecraft, grouped by constellation, each group on one time axis."""
    groups = {}
    for item in items:
        groups.setdefault(constellations.get(item["periods"][0]["svn"], ""), []).append(item)
    html = ""
    for constellation, group in groups.items():
        x, axis = _axis(min(p["start"] for i in group for p in i["periods"]), today)
        rows = "".join(_row(item, x, names, _colour(constellation)) for item in group)
        html += (f'<div class="sx-group"><div class="sx-gh">{marks.mark(constellation)}<b>{escape(constellation)}</b>'
                 f'<span class="muted small">{len(group)} signal IDs</span></div>'
                 f'<div class="sx-lanes">{rows}<div class="sx-lane"><span></span>{axis}</div></div></div>')
    return f'<div class="sx-list">{html}</div>'


def key(items):
    """The count of signal IDs and of each kind of change, each kind with its mark: the picture's legend."""
    kinds = Counter(c["kind"] for item in items for c in item["changes"])
    tiles = "".join(
        f'<div class="sx-k {kind}">' + tooltip.tip_html(
            f'<span class="sx-g" aria-hidden="true">{glyph}</span><b class="num">{kinds.get(kind, 0)}</b>'
            f'<span class="small">{escape(words)}</span>', escape(meaning), key="key" + kind) + '</div>'
        for kind, (glyph, words, meaning) in CHANGE_KINDS.items())
    return (f'<div class="sx-key"><div class="sx-k total"><b class="big num">{len(items)}</b>'
            f'<span class="small">signal IDs held by more than one spacecraft</span></div>{tiles}</div>')
