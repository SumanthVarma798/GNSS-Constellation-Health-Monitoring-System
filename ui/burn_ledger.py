"""The burn ledger in pictures: one 100% bar per constellation, and for each satellite a row of marks in time order.

Shape says the kind of manoeuvre (a circle for east-west, a diamond for north-south: ui/figures/burns.py KIND_SYMBOL), the
fill says what the burn was, and a tooltip says it in words with the tests it passed. Colour is never the only signal:
planned moves are hatched, burns not judged are outlined and empty, and every group has its words in the key.
Plain HTML and CSS (ui/theme.css, "burn ledger"): no chart to build on the free host.
"""
from html import escape

import pandas as pd

from analysis import burn_class_settings as S
from analysis.burn_classes import IRREGULAR
from ui import burn_record as record
from ui import tooltip
from ui.burn_groups import ARTEFACT_GROUP, CONFIDENCE_WORDS, GROUPS, VERDICT, group_of

EAST_WEST = "east-west"


def _swatch(group):
    return f'<i class="lb-sw {group}" aria-hidden="true"></i>'


def key(counts=None):
    """The words for each part of the picture, with its count when `counts` is given."""
    parts = "".join(f'<span>{_swatch(group)}{escape(words)}'
                    + (f' <b class="num">{counts[group]}</b>' if counts is not None else "") + "</span>"
                    for group, words in GROUPS if counts is None or counts[group])
    return f'<div class="lb-key small">{parts}</div>'


def bar(rec, title="Burn record, last 365 days"):
    """The constellation's burns in the last 365 days as one 100% bar, the counts written in it, then the key and the
    plain sentence (ui.burn_record.words). "" when there are no burns."""
    if not rec:
        return ""
    shown = [(group, rec[group]) for group, _ in GROUPS if rec[group]]
    total = sum(count for _, count in shown)
    if not total:
        return ""
    said = ", ".join(f"{count} {dict(GROUPS)[group]}" for group, count in shown)
    segments = "".join(f'<span class="lb-seg {group}" style="flex:{count}"><b class="num">{count}</b></span>'
                       for group, count in shown)
    left_out = (f' {rec[ARTEFACT_GROUP]} detections left out as errors in the records.' if rec[ARTEFACT_GROUP] else "")
    sentence = record.words(rec)
    return (f'<div class="lb"><div class="lb-head"><b>{escape(title)}</b>'
            f'<span class="small">{escape(sentence + ".") if sentence else ""}'
            f'{escape(left_out)}</span></div>'
            f'<div class="lb-bar" role="img" aria-label="{escape(title)}: {escape(said)}">{segments}</div>'
            f'{key(rec)}</div>')


def _confidence(level):
    return CONFIDENCE_WORDS.get(level, str(level))


def _mark(row):
    """One burn's mark with its tooltip: the kind of manoeuvre and what it was, how sure, and each test with its value."""
    group = group_of(row["burn_class"], bool(row["counted"]))
    when = pd.Timestamp(row["window_end"])
    east_west = row["kind"] == EAST_WEST
    lines = [("", "Kind", f"{row['burn_class']} ({VERDICT[group]})"),
             ("", "Sure", _confidence(row["confidence"]))]
    lines += [("", "Test", test.strip()) for test in str(row["tests"] or "").split("; ") if test.strip()]
    if row.get("note"):
        lines.append(("", "Note", str(row["note"])))
    title = f"{row['satellite']}: {row['kind']} burn, {when.day} {when:%b %Y}"
    trigger = (f'<i class="bm {"ew" if east_west else "ns"} {group}" role="img" '
               f'aria-label="{escape(title)}: {escape(row["burn_class"])}, {escape(_confidence(row["confidence"]))}"></i>')
    return tooltip.tip_html(trigger, tooltip.glance(title, lines), key=f"{row['satellite']}{when:%Y%m%d%H}{row['kind']}")


def satellites(table, names, now=None):
    """One row per satellite in `names`: its name, its burns of the last 365 days as marks in time order (oldest
    first), and how many were irregular of the judged ones. `table` is ui.burn_record.classified()'s."""
    if table is None:
        return ""
    now = record._now(now)
    window = table[(table["when"] > now - pd.Timedelta(days=S.WINDOW_DAYS)) & (table["when"] <= now)]
    care = record.care_of(table, now)
    rows = []
    for name in names:
        own = window[window["satellite"] == name].sort_values("when")
        if own.empty:
            continue
        judged = own[own["counted"].astype(bool)]
        irregular = int(judged["burn_class"].isin(IRREGULAR).sum())
        verdict = {True: "passes", False: "does not pass", None: "not judged"}[care.get(name)]
        marks = "".join(_mark(row) for row in own.to_dict("records"))
        rows.append(f'<div class="lm-row"><b>{escape(name)}</b><span class="lm-marks">{marks}</span>'
                    f'<span class="lm-sum small"><span class="num">{f"{irregular} of {len(judged)} irregular" if len(judged) else "no judged burns"}</span>'
                    f'<span>{verdict}</span></span></div>')
    shape = ('<div class="lb-key small"><span><i class="bm ew shape" aria-hidden="true"></i>east-west</span>'
             '<span><i class="bm ns shape" aria-hidden="true"></i>north-south</span></div>')
    return f'<div class="lm">{shape}{"".join(rows)}</div>' if rows else ""
