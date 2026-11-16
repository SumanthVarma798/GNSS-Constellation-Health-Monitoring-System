"""Home: every system side by side, for a reader new to them. One row per system: how its satellites split, and its counts.

The page reads in the order the whole dashboard follows: all the satellites (the count), each system (the rows),
what stands out (Worth a look), then what is measured, how, what is left out and what comes next (the section).
A row opens that system's Overview, where the same count is the headline.
"""
from html import escape

import streamlit as st
import streamlit.components.v1 as components

from ui import data, findings, home_data, icons, marks, palette, reveal, shell, surfaces, time_range, tooltip
from ui.home_settings import CAVEATS, FINDINGS_SHOWN, HOW, HOW_LINKS, RULES, SYSTEMS
from ui.system_summary import whole
from ui.systems import SYSTEMS as SYSTEMS_PARTS, part_name

# The states a satellite can be in: (class, what it means), in the order a row lists them. Each has its own mark
# (ui/theme.css: round, diamond, square, ring), so the colour only backs it up.
STATES = [("ok", "healthy and in place"), ("warn", "needs a look"), ("bad", "set aside"), ("accent", "new, not scored yet")]


def _dot(sat):
    return "ok" if sat["ok"] else "bad" if sat["state"] == palette.SLOT_LEFT else "warn"


def _mix(system):
    """How the system's satellites split across the states: one bar in proportion, then each count beside its mark.
    A mark per satellite could not say which satellite it was, so only the counts are drawn."""
    counts = {kind: 0 for kind, _ in STATES}
    for sat in system["sats"]:
        counts[_dot(sat)] += 1
    counts["accent"] = len(system["settling"])
    shown = [(kind, meaning, counts[kind]) for kind, meaning in STATES if counts[kind]]
    if not shown:
        return ""   # nothing to draw
    bar = "".join(f'<i class="{kind}" style="flex:{count}"></i>' for kind, _, count in shown)
    words = "".join(f'<span><i class="{kind}"></i>{count} {escape(meaning)}</span>' for kind, meaning, count in shown)
    return f'<div class="mix"><i class="mixbar" aria-hidden="true">{bar}</i><div class="dots mixw small">{words}</div></div>'


def _anchor(heading):
    """The id of one "How to read this page" card, from its heading: 'What is measured' -> 'how-what-is-measured'."""
    return "how-" + heading.lower().replace(" ", "-")


def _explained(words):
    """Words on a row that "How to read this page" explains, as a link to the card that explains them (dotted under,
    like every word that opens an explanation); other words as they are. Following the link opens that section and
    scrolls to the card (_how_links_script); without scripts it still jumps to the card."""
    if words not in HOW_LINKS:
        return escape(words)
    return (f'<a class="how-link" href="#{_anchor(HOW_LINKS[words])}" '
            f'title="What this means: opens How to read this page">{escape(words)}</a>')


def _measure(count, total, words):
    """One count out of a total with a bar under it, coloured by the share's band."""
    if count is None:
        return f'<div class="sys-m"><span class="s idle">not read</span><span class="small">{_explained(words)}</span></div>'
    share = 100 * count / total if total else 0
    band = surfaces.band(share)
    return (f'<div class="sys-m"><span class="s num {band}">{count} of {total}</span>'
            f'<i class="hbar"><i class="{band}" style="width:{share:.0f}%"></i></i>'
            f'<span class="small">{_explained(words)}</span></div>')


def _measures(system):
    """The three measures of a constellation's health and its own flag, one line each: the words, a bar, the count.
    The lines sit in the same place in every row, so the constellations compare down the page."""
    lines = [("orbit kept", *system["orbit"]), ("station held", *system["station"]),
             ("clock steady", *system["clock"]), ("says healthy", system["flagged_healthy"], system["checked"])]
    return '<div class="ms">' + "".join(_measure_line(*line) for line in lines) + "</div>"


def _measure_line(words, count, of):
    """One line of _measures. With nothing to judge (no broadcast check read, or no part scored) it says so."""
    if not of:
        return (f'<span class="small">{_explained(words)}</span><i class="hbar"></i>'
                '<b class="idle">not read</b>')
    share = 100 * count / of
    band = surfaces.band(share)
    return (f'<span class="small">{_explained(words)}</span>'
            f'<i class="hbar"><i class="{band}" style="width:{share:.0f}%"></i></i>'
            f'<b class="num {band}">{count} of {of}</b>')


def _row(system, unread=None):
    """One system: who runs it, how its satellites split, the count in place, the three measures and its own flag,
    and what the page leaves out for it.
    For a system of several parts, each part's count is a line under the split, and a part in `unread`
    ({part's name: the error}) says why it is missing."""
    name = system["name"]
    who, where = SYSTEMS.get(name, ("", ""))
    share = 100 * system["healthy"] / system["total"] if system["total"] else 0
    notes = [f"{escape(new)} is new ({escape(stage)}) and is {_explained('not scored yet')}"   # each note is markup
             for new, stage in system["settling"].items()]
    notes += [escape(CAVEATS[name])] if name in CAVEATS else []
    notes = ([escape(" · ".join(f"{label} {count} of {of}" for label, count, of in system["parts"]))] * bool(system["parts"])
             + [escape(f"{label} could not be read just now: {_why(error)}") for label, error in (unread or {}).items()]
             + notes)
    return (f'<div class="sys {surfaces.band(share)}">'
            f'<div class="sys-id"><b>{marks.mark(name)}{escape(name)}</b><span class="small">{escape(" · ".join(filter(None, [who, where])))}</span></div>'
            f'<div class="sys-mid">{_mix(system)}'
            + "".join(f'<div class="small">{note}</div>' for note in notes) + '</div>'
            f'{_measure(system["healthy"], system["total"], "healthy and in place")}'
            f'{_measures(system)}'
            '<span class="sys-go" aria-hidden="true">&rsaquo;</span></div>')


def _failed(name, error):
    return (f'<div class="sys idle"><div class="sys-id"><b>{marks.mark(name)}{escape(name)}</b></div>'
            f'<div class="sys-mid small">Could not be read just now: {escape(_why(error))}. '
            'The other constellations are not affected.</div></div>')


def _waiting(name):
    """A row before its constellation has been counted: its name is there at once, the counts follow."""
    who, where = SYSTEMS.get(name, ("", ""))
    return (f'<div class="sys idle"><div class="sys-id"><b>{marks.mark(name)}{escape(name)}</b>'
            f'<span class="small">{escape(" · ".join(filter(None, [who, where])))}</span></div>'
            '<div class="sys-mid small">counting its satellites</div></div>')


def _headline(wholes=None, made=None):
    """The count across every constellation, when it was counted if that was not just now (`made`, the published
    copy's time), and what a row is. Before the counting is done (wholes is None) the count's place says so."""
    if wholes is None:
        count, words = "…", "counting every constellation"
    else:
        healthy, total = sum(s["healthy"] for s in wholes.values()), sum(s["total"] for s in wholes.values())
        count = f"{healthy} of {total}"
        words = f"navigation satellites healthy and in place, across {reveal.count(len(wholes), 'constellation')}"
        words += f" · counted {made:%d %b %H:%M} UTC" if made else ""
    # One status for the whole page, in both states, so a screen reader hears "counting" and then the count, not six
    # rows each saying so.
    return (f'<div class="head"><span role="status"><span class="big num">{count}</span> '
            f'<span class="muted">{words}</span></span></div>'
            '<p class="lede small">One row per constellation. A row opens that constellation, where every satellite '
            'and every number behind these counts is shown.</p>')


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
            f'<b>{marks.mark(finding["system"])}{escape(finding["system"])}</b> <span>{escape(finding["line"])}</span>'
            f'<div class="small">{escape(finding["numbers"])}</div>{why}</div>{_pair(finding["pair"])}</div>')


def _open(key, part, name=""):
    """The button laid over a row (ui/theme.css): the whole row opens the Overview of `part`, a system or one part
    of it, said as `name` when that differs."""
    st.button(f"Open {name or part}'s overview", key=key, on_click=shell.open_system, args=(part,))


def _how():
    """Four cards, in the order every page follows: an icon and a heading, then each point led by its term."""
    return '<div class="how-grid">' + "".join(
        f'<div class="how well" id="{_anchor(title)}"><div class="how-h">{icons.mask(icon)}<span>{escape(title)}</span></div>'
        + "".join(f"<p><b>{escape(term)}.</b> {escape(words)}</p>" for term, words in points) + "</div>"
        for icon, title, points in HOW) + "</div>"


# Run once in the page itself: a click on a row's explained words opens "How to read this page" by its own header
# (so the section's state stays the reader's) and scrolls to the card. st.html drops scripts, so a frame of no height
# adds it to the page; a browser that blocks that still follows the link to the card.
_HOW_LINKS_SCRIPT = """<script>
const page = window.parent.document;
if (!page.getElementById("how-links")) {
  const script = page.createElement("script"); script.id = "how-links";
  script.textContent = `document.addEventListener("click", event => {
    const link = event.target.closest && event.target.closest("a.how-link");
    if (!link) return;
    const card = document.getElementById(link.getAttribute("href").slice(1));
    const header = document.querySelector(".st-key-rvx_home_how input");
    if (!card || !header) return;
    event.preventDefault();
    if (!header.checked) header.click();
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setTimeout(() => { card.scrollIntoView({behavior: calm ? "auto" : "smooth", block: "center"});
                       card.classList.add("lit"); setTimeout(() => card.classList.remove("lit"), 1600); }, 260);
  });`;
  page.head.appendChild(script);
}
</script>"""


def page():
    """The rows are drawn as each constellation is counted, so a first visit (when nothing is kept yet and the
    counting takes a while) shows every name at once and fills in row by row; the count across all of them comes last."""
    window_days = st.session_state.get("window_days", time_range.DEFAULT_DAYS)
    made, ready = home_data.published(window_days)
    kept = home_data.keys(data.orbit_gap()) if len(ready) < sum(map(len, SYSTEMS_PARTS.values())) else None
    head = st.empty()
    head.html(_headline())
    parts, failed, wholes = {}, {}, {}
    with st.container(key="home_systems"):
        slots = [st.empty() for _ in SYSTEMS_PARTS]
        for slot, system in zip(slots, SYSTEMS_PARTS):
            slot.html(_waiting(system))
        for index, (system, names) in enumerate(SYSTEMS_PARTS.items()):
            for name in names:   # one that fails says why in its row; the others still show (issue 39)
                try:
                    parts[name] = ready[name] if name in ready else home_data.part_summary(name, window_days, *kept)
                except Exception as error:
                    failed[name] = error
            if any(name in parts for name in names):
                wholes[system] = whole(system, [parts[name] for name in names if name in parts])
            with slots[index].container(key=f"home_row_{index}"):
                unread = {part_name(name) or name: failed[name] for name in names if name in failed}
                st.html(_row(wholes[system], unread) if system in wholes else _failed(system, failed[names[0]]))
                _open(f"home_open_{index}", next((name for name in names if name in parts), names[0]), system)
    head.html(_headline(wholes, made if set(parts) <= set(ready) else None))

    listed, explained = findings.find(list(parts.values()))
    line = (f"{reveal.count(len(listed), 'thing')} stand{'s' if len(listed) == 1 else ''} out today" if listed
            else "nothing stands out today") + (f" · {len(explained)} more expected" if explained else "")
    surfaces.show(surfaces.group_head("Worth a look", line, tooltip.tip_html(
        '<span class="small">how these are found</span>', tooltip.glance("Each comes from a rule, never a hand pick", [
            ("", name, compares) for name, compares in RULES.values()]), key="home_rules")))
    with st.container(key="home_findings"):
        for index, finding in enumerate(listed[:FINDINGS_SHOWN]):
            with st.container(key=f"home_row_f{index}"):
                st.html(_finding(finding))
                _open(f"home_open_f{index}", finding["system"])   # the part the finding is about
    rest = listed[FINDINGS_SHOWN:] + explained
    if rest:
        reveal.section("home_more", "The rest", " · ".join(filter(None, [
            f"{len(listed) - FINDINGS_SHOWN} more" if len(listed) > FINDINGS_SHOWN else "",
            f"{len(explained)} expected" if explained else ""])), "".join(_finding(finding) for finding in rest))
    reveal.section("home_how", "How to read this page",
                   "what is measured, how, what is left out, what comes next", _how())
    components.html(_HOW_LINKS_SCRIPT, height=0)


page()
