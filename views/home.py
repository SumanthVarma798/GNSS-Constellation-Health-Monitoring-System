"""Home: every system side by side, for a reader new to them. One row per system, one dot per satellite.

The page reads in the order the whole dashboard follows: all the satellites (the count), each system (the rows),
what stands out (Worth a look), then what is measured, how, what is left out and what comes next (the section).
A row opens that system's Overview, where the same count is the headline.
"""
from html import escape

import streamlit as st

from ui import data, findings, palette, reveal, shell, surfaces, time_range, tooltip
from ui.home_settings import CAVEATS, FINDINGS_SHOWN, HOW, RULES, SYSTEMS
from ui.system_summary import summary

# One dot per satellite: (class, what it means), in the order the legend lists them.
DOTS = [("ok", "healthy and in place"), ("warn", "needs a look"), ("bad", "set aside"), ("accent", "settling in")]
DOT_COLOURS = {"ok": palette.OK, "warn": palette.WARN, "bad": palette.BAD, "accent": palette.ACCENT}


def _dot(sat):
    return "ok" if sat["ok"] else "bad" if sat["state"] == palette.SLOT_LEFT else "warn"


def _dots(system):
    """The system's satellites as dots, a small gap between its planes or orbit types, those settling in last."""
    groups = {}
    for sat in system["sats"]:
        groups.setdefault(sat["group"], []).append(_dot(sat))
    if system["settling"]:
        groups["settling"] = ["accent"] * len(system["settling"])
    counts = {kind: sum(dot == kind for dots in groups.values() for dot in dots) for kind, _ in DOTS}
    words = ", ".join(f"{counts[kind]} {meaning}" for kind, meaning in DOTS if counts[kind])
    spans = "".join(f'<span class="dg">{"".join(f"<i class={kind}></i>" for kind in dots)}</span>'
                    for dots in groups.values())
    return f'<div class="dots" role="img" aria-label="{escape(words)}">{spans}</div>'


def _measure(count, total, words):
    """One count out of a total with a bar under it, coloured by the share's band."""
    if count is None:
        return f'<div class="sys-m"><span class="s idle">not read</span><span class="small">{escape(words)}</span></div>'
    share = 100 * count / total if total else 0
    band = surfaces.band(share)
    return (f'<div class="sys-m"><span class="s num {band}">{count} of {total}</span>'
            f'<i class="hbar"><i class="{band}" style="width:{share:.0f}%"></i></i>'
            f'<span class="small">{escape(words)}</span></div>')


def _row(system):
    """One system: who runs it, its satellites as dots, the two counts, and what the page leaves out for it."""
    name = system["name"]
    who, where = SYSTEMS.get(name, ("", ""))
    share = 100 * system["healthy"] / system["total"] if system["total"] else 0
    notes = [f"{reveal.count(len(system['settling']), 'satellite')} settling in, not counted yet"] * bool(system["settling"])
    notes += [CAVEATS[name]] if name in CAVEATS else []
    return (f'<div class="sys {surfaces.band(share)}">'
            f'<div class="sys-id"><b>{escape(name)}</b><span class="small">{escape(" · ".join(filter(None, [who, where])))}</span></div>'
            f'<div class="sys-mid">{_dots(system)}'
            + "".join(f'<div class="small">{escape(note)}</div>' for note in notes) + '</div>'
            f'{_measure(system["healthy"], system["total"], "healthy and in place")}'
            f'{_measure(system["flagged_healthy"], system["checked"], "broadcasting healthy")}'
            '<span class="sys-go" aria-hidden="true">&rsaquo;</span></div>')


def _failed(name, error):
    return (f'<div class="sys idle"><div class="sys-id"><b>{escape(name)}</b></div>'
            f'<div class="sys-mid small">Could not be read just now: {escape(_why(error))}. '
            'The other systems are not affected.</div></div>')


def _why(error):
    """A ValueError is the assessment saying in plain words what is missing; anything else is named by its kind."""
    return str(error) if isinstance(error, ValueError) else f"{type(error).__name__}: {error}"


def _pair(pair):
    """The two things a finding compares, as two bars on one scale."""
    top = max(value for _, value in pair) or 1
    return '<div class="pair">' + "".join(
        f'<span class="small">{escape(label)}</span><i class="hbar"><i class="{kind}" style="width:{100 * value / top:.0f}%"></i></i>'
        f'<b class="num">{value:g}</b>' for (label, value), kind in zip(pair, ("idle", "accent"))) + '</div>'


def _finding(finding):
    rule = RULES[finding["rule"]][0]
    why = f'<div class="small">Expected: {escape(finding["explained"])}</div>' if finding["explained"] else ""
    return (f'<div class="find"><div class="find-w">{surfaces.chip(rule, "idle" if finding["explained"] else "warn")}'
            f'<b>{escape(finding["system"])}</b> <span>{escape(finding["line"])}</span>'
            f'<div class="small">{escape(finding["numbers"])}</div>{why}</div>{_pair(finding["pair"])}</div>')


def _open(key, name):
    """The button laid over a row (ui/theme.css): the whole row opens that system's Overview."""
    st.button(f"Open {name}'s overview", key=key, on_click=shell.open_system, args=(name,))


def _how():
    return "".join(f'<div class="how"><div class="part-title">{escape(title)}</div>'
                   f'<ul class="small meanings">{"".join(f"<li>{escape(line)}</li>" for line in lines)}</ul></div>'
                   for title, lines in HOW)


def page():
    window_days = st.session_state.get("window_days", time_range.DEFAULT_DAYS)
    gap = data.orbit_gap()
    systems, failed = [], {}
    for name in shell.CONSTELLATIONS:   # one that fails says why in its row; the others still show (issue 39)
        try:
            systems.append(summary(name, data.load(name, window_days), gap))
        except Exception as error:
            failed[name] = error
    healthy, total = sum(s["healthy"] for s in systems), sum(s["total"] for s in systems)
    surfaces.show(f'<div class="head"><span class="big num">{healthy} of {total}</span>'
                  f'<span class="muted">navigation satellites healthy and in place, across '
                  f'{reveal.count(len(systems), "system")}</span>'
                  f'<span class="right">{tooltip.legend([(DOT_COLOURS[kind], meaning) for kind, meaning in DOTS], "What a dot means")}</span></div>'
                  '<p class="lede small">One row per system, one dot per satellite. A row opens that system, where every '
                  'satellite and every number behind these counts is shown.</p>')
    by_name = {system["name"]: system for system in systems}
    with st.container(key="home_systems"):
        for index, name in enumerate(shell.CONSTELLATIONS):
            with st.container(key=f"home_row_{index}"):
                st.html(_row(by_name[name]) if name in by_name else _failed(name, failed[name]))
                _open(f"home_open_{index}", name)

    listed, explained = findings.find(systems)
    line = (f"{reveal.count(len(listed), 'thing')} stand{'s' if len(listed) == 1 else ''} out today" if listed
            else "nothing stands out today") + (f" · {len(explained)} more expected" if explained else "")
    surfaces.show(surfaces.group_head("Worth a look", line, tooltip.tip_html(
        '<span class="small">how these are found</span>', tooltip.glance("Each comes from a rule, never a hand pick", [
            ("", name, compares) for name, compares in RULES.values()]), key="home_rules")))
    with st.container(key="home_findings"):
        for index, finding in enumerate(listed[:FINDINGS_SHOWN]):
            with st.container(key=f"home_row_f{index}"):
                st.html(_finding(finding))
                _open(f"home_open_f{index}", finding["system"])
    rest = listed[FINDINGS_SHOWN:] + explained
    if rest:
        reveal.section("home_more", "The rest", " · ".join(filter(None, [
            f"{len(listed) - FINDINGS_SHOWN} more" if len(listed) > FINDINGS_SHOWN else "",
            f"{len(explained)} expected" if explained else ""])), "".join(_finding(finding) for finding in rest))
    reveal.section("home_how", "How to read this page",
                   "what is measured, how, what is left out, what comes next", _how())


page()
