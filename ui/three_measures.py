"""Orbit kept, station held, clock steady and the burn record: the four measures on one constellation's own page, one step deeper than
Home. A strip at the top declares the counts; a section lists every satellite with what each measure read and the
figure behind it. What counts for each measure is in ui/limits.py (MEASURES, CLOCK_STEADY_NS).
"""
from html import escape

from evidence.registry_tables import clock_record, judged_by_plane
from ui import burn_ledger, limits, meo_overview, palette, reveal, surfaces, systems, tooltip

# (key in ui.system_summary's counts, the words on the page), in the order shown everywhere.
MEASURES = [("orbit", "Orbit kept"), ("station", "Station held"), ("clock", "Clock steady"), ("care", "Burn record")]
# The table's columns: (heading, one plain line), by how the constellation is judged.
STATION_LINE = {"slot": "in its slot and not drifting", "plane": "in step with its plane"}
FLAG = {"ok": ("healthy", "ok"), "bad": ("unhealthy", "bad"), "silent": ("not in the IGS daily broadcast file", "idle"),
        None: ("not read", "idle")}


def _chip(words, count, of):
    if not of:
        return surfaces.chip(f"{words}: not read", "idle")
    return surfaces.chip(f"{words} {count} of {of}", surfaces.share_tone(100 * count / of))


def _whole_points(rates, score):
    """Each part's points as whole numbers that add up to the score shown: each rounded down, then the points left
    given to the parts that lost the most to rounding (so 29.64 + 19.76 shows as 29 + 20 beside a score of 49)."""
    exact = [rate * weight for _, rate, weight in rates]
    whole = [int(value) for value in exact]
    for at in sorted(range(len(exact)), key=lambda i: exact[i] - whole[i], reverse=True)[:score - sum(whole)]:
        whole[at] += 1
    return whole


def score_sum(summary):
    """The score opened into its parts, so it can be checked: one bar of 100 cut into each attribute's share (its
    weight for the constellation's mission), each share filled as far as its pass rate, so the filled length is the
    score; under it each attribute's pass rate × weight = its points, adding up to the score. Home's open card and the
    constellation's own page show the same."""
    score, rates = summary["score"], summary["score_parts"]
    if score is None:
        return '<p class="small">No score: none of the attributes could be read today.</p>'
    names = dict(MEASURES)
    mission = limits.MISSION.get(systems.system_of(summary["name"]), "global")
    # read aloud in full; on the page the bar says it: each part's name over it, its points under it
    words = ", ".join(f"{names[key]} {rate:.0f}% of its {weight:.0%} share: {rate * weight:.1f} points"
                      for key, rate, weight in rates)
    words += f"; score {score} out of 100, weighed for a {mission} constellation"
    if len(rates) < len(MEASURES):
        words += f"; {len(MEASURES) - len(rates)} not read today, so the others count for its share"
    # each part as wide as its weight, its weight said over it; filled as far as its pass rate; the points it adds under
    parts = "".join(
        f'<div class="ss-seg" style="flex:{weight:.4f}"><span class="ss-head"><span class="ss-name">'
        f'{escape(names[key].split()[0])}</span><span class="ss-w num">{weight:.0%}</span></span>'
        f'<span class="ss-slot"><i class="{surfaces.share_tone(rate)}" style="width:{rate:.1f}%"></i></span>'
        f'<span class="ss-pts">+<b class="num">{points}</b></span></div>'
        for (key, rate, weight), points in zip(rates, _whole_points(rates, score)))
    key = ('<div class="ssum-key small" aria-hidden="true"><span><b class="k-width">↔</b>width: its weight</span>'
           '<span><i class="k-fill"></i>filled: satellites that pass</span><span><b>+</b> points it adds</span></div>')
    return (f'<div class="ssum-wrap" role="img" aria-label="{escape(words)}">{key}<div class="ssum">'
            f'<div class="ssum-bar" aria-hidden="true">{parts}</div><span class="ss-eq" aria-hidden="true">=</span>'
            f'<div class="ss-total {surfaces.band(score)}" aria-hidden="true"><b class="num">{score}</b>'
            f'<small>/100</small></div></div></div>')


PARTS_WORDS = "{system}'s score counts every satellite of its parts once, so it sits between their own scores"


def part_scores(system, current=""):
    """A constellation of several parts (BeiDou-3: IGSO & GEO, MEO): each part's own score in a small box beside the
    whole's, the part being read marked, and one line saying how the whole is made. "" for a one-part constellation."""
    if not system.get("part_scores"):
        return ""
    boxes = "".join(
        f'<span class="ps-box{" here" if label == current else ""} {surfaces.band(score) if score is not None else "idle"}">'
        f'<small>{escape(label)}</small><b class="num">{score if score is not None else "–"}</b></span>'
        for label, score in system["part_scores"])
    return (f'<div class="ps"><div class="ps-boxes">{boxes}</div>'
            f'<p class="small">{escape(PARTS_WORDS.format(system=system["name"]))}</p></div>')


def strip(summary):
    """The score and its sum, then the three counts and the constellation's own flag, as chips: declared before
    anything else on the page. Home's score for this constellation is opened up here; every satellite's result is in
    the section under the page (section())."""
    part = systems.part_name(summary["name"])   # on one part's page the chip names the part, never the whole
    label = f"{part} score" if part else "Score"
    lead = (surfaces.chip(f"{label} {summary['score']} of 100", surfaces.band(summary["score"]))
            if summary["score"] is not None else surfaces.chip(f"{label}: not read", "idle"))
    chips = [_chip(words, *summary[key]) for key, words in _read(summary)]
    chips.append(_chip("Says healthy", summary["flagged_healthy"], summary["checked"]))
    return (f'<div class="measures" role="group" aria-label="Score, orbit, station-keeping and clock">{lead}'
            f'{"".join(chips)}</div>{score_sum(summary) if summary["score"] is not None else ""}'
            f'{record_line(summary["name"])}{burn_ledger.bar(summary.get("burn_record"))}')


def _read(summary):
    """The measures to show for a constellation: all four, but the burn record only where burns were found (the
    medium-orbit constellations have too little history to find any)."""
    return [(key, words) for key, words in MEASURES if key != "care" or summary.get("burn_record")]


def record_line(name):
    """The constellation's clock track record beside its clock score: how many of the satellites it launched lost
    atomic clocks in orbit, with the sources in a tip. "" when the registry holds no entry for it."""
    found = clock_record(name)
    if not found:
        return ""
    lost, launched = found
    words, tip = limits.CLOCK_RECORD
    sources = "".join(
        f'<span>{escape(row["name"])}: {escape(row["what"])} ({escape(row["when"])}); '
        f'<a class="tt-src" href="{escape(row["source_link"], quote=True)}" target="_blank" rel="noopener noreferrer">'
        f'{escape(row["source_name"])}</a></span><br>' for row in lost)
    return (f'<p class="small clock-record">{escape(words.format(lost=len(lost), launched=launched, name=name))} '
            f'{tooltip.tip_html("Sources", escape(tip) + "<br>" + sources, key=name)}</p>')


def _cell(now, status, should="", note=""):
    return {"now": now, "status": status, "should": should, "note": note}


def _weakest(sat, parts, labels):
    """'tilt scores 55' for the lowest of `parts` that has a score, or ''."""
    scored = [(sat["parts"][part], part) for part in parts if sat["parts"].get(part) is not None]
    if not scored:
        return ""
    score, part = min(scored)
    return f"{labels.get(part, part).lower()} scores {score:.0f}"


def _judged(sat, key, kind, yes, no, labels):
    if sat[key] is None:
        return _cell("not judged", "idle")
    return _cell(yes if sat[key] else no, "ok" if sat[key] else "warn",
                 note=_weakest(sat, limits.MEASURES[key][kind], labels))


def _station(sat, kind, labels):
    cell = _judged(sat, "station", kind, "held", "not held", labels)
    if sat["station"] is None:
        return cell
    extra = [sat["state"]] if kind == "slot" or sat["state"] == palette.SLOT_OFF else []
    if kind == "slot":   # how it is kept there: its burns, shown beside the measure and not counted in it
        extra += [f"{part.lower()} {sat['parts'][part]:.0f}" for part in limits.BURN_PARTS
                  if sat["parts"].get(part) is not None]
    return {**cell, "note": " · ".join(filter(None, [cell["note"], *extra]))}


def _care(sat):
    if sat.get("care") is None:
        return _cell("not judged", "idle", note="fewer than " + str(limits.CARE_MIN_JUDGED) + " judged burns in 365 days")
    return _cell("passes" if sat["care"] else "irregular burns", "ok" if sat["care"] else "warn",
                 should=f"no irregular burn in {limits.CARE_RECENT_DAYS} days, at most {limits.CARE_MAX_SHARE:.0%} in 365")


def _clock(sat):
    clock = sat.get("clock")
    if not clock or sat["clock_steady"] is None:
        return _cell("not heard" if sat["broadcast"] in (None, "silent") else "too few messages", "idle")
    return _cell("steady" if sat["clock_steady"] else "stepped", "ok" if sat["clock_steady"] else "bad",
                 should=f"up to {limits.CLOCK_STEADY_NS:g} ns",
                 note=f"largest step {clock['largest_step_ns']:,.1f} ns · typical {clock['typical_step_ns']:.2f} ns · "
                      f"drift {clock['drift_ns_per_day']:,.0f} ns a day")


def table(summary):
    """Every satellite against the three measures and its own flag, with the figure behind each."""
    kind = "plane" if judged_by_plane(summary["name"]) else "slot"
    labels = meo_overview.LABELS if kind == "plane" else {"Inclination": "tilt", "Drift": "drift"}
    columns = [("Satellite", ""), ("Orbit kept", "on the orbit it should be on"),
               ("Station held", STATION_LINE[kind]),
               ("Clock steady", f"no step past {limits.CLOCK_STEADY_NS:g} ns in the day"),
               ("Says healthy", "its own broadcast flag")]
    burns = bool(summary.get("burn_record"))
    if burns:
        columns.insert(4, ("Burn record", "how regularly it is looked after"))
    rows = [(sat["name"], [_judged(sat, "orbit", kind, "kept", "not kept", labels), _station(sat, kind, labels),
                           _clock(sat)] + [_care(sat)] * burns + [_cell(*FLAG[sat["broadcast"]])])
            for sat in summary["sats"]]
    return surfaces.table(columns, rows)


def section(summary):
    """The section under the page: every satellite, measure by measure."""
    said = " · ".join(f"{words.lower()} {count} of {of}" if of else f"{words.lower()} not read"
                      for (key, words) in _read(summary) for count, of in [summary[key]])
    reveal.section(f"three_measures_{summary['name']}", "The score, satellite by satellite",
                   said, table(summary))
