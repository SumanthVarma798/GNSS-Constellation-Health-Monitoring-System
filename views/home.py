"""Home: every system side by side, for a reader new to them. One row per system, one dot per satellite.

The page reads in the order the whole dashboard follows: all the satellites (the count), each system (the rows),
what stands out (Worth a look), then what is measured, how, what is left out and what comes next (the section).
A row opens that system's Overview, where the same count is the headline.
"""
from html import escape

import streamlit as st
import streamlit.components.v1 as components

from ui import data, findings, icons, marks, palette, reveal, shell, surfaces, time_range, tooltip
from ui.home_settings import CAVEATS, FINDINGS_SHOWN, HOW, HOW_LINKS, RULES, SYSTEMS
from ui.system_summary import summary, whole
from ui.systems import SYSTEMS as SYSTEMS_PARTS, part_name

# One dot per satellite: (class, what it means, its shape), in the order the legend lists them. Each has its own
# shape (ui/theme.css), so the colour only backs it up.
DOTS = [("ok", "healthy and in place", "round"), ("warn", "needs a look", "diamond"), ("bad", "set aside", "square"),
        ("accent", "new, not scored yet", "ring")]
DOT_COLOURS = {"ok": palette.OK, "warn": palette.WARN, "bad": palette.BAD, "accent": palette.ACCENT}


def _dot(sat):
    return "ok" if sat["ok"] else "bad" if sat["state"] == palette.SLOT_LEFT else "warn"


def _dots(system):
    """The system's satellites as dots, a small gap between its planes or orbit types, the new ones not scored yet last."""
    groups = {}
    for sat in system["sats"]:
        groups.setdefault(sat["group"], []).append(_dot(sat))
    if system["settling"]:
        groups["settling"] = ["accent"] * len(system["settling"])
    if not groups:
        return ""   # nothing to draw, so no picture without a name
    counts = {kind: sum(dot == kind for dots in groups.values() for dot in dots) for kind, _, _ in DOTS}
    words = ", ".join(f"{counts[kind]} {meaning}" for kind, meaning, _ in DOTS if counts[kind])
    spans = "".join(f'<span class="dg">{"".join(f"<i class={kind}></i>" for kind in dots)}</span>'
                    for dots in groups.values())
    return f'<div class="dots" role="img" aria-label="{escape(words)}">{spans}</div>'


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


def _row(system, unread=None):
    """One system: who runs it, its satellites as dots, the two counts, and what the page leaves out for it.
    For a system of several parts, each part's count is a line under the dots, and a part in `unread`
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
            f'<div class="sys-mid">{_dots(system)}'
            + "".join(f'<div class="small">{note}</div>' for note in notes) + '</div>'
            f'{_measure(system["healthy"], system["total"], "healthy and in place")}'
            f'{_measure(system["flagged_healthy"], system["checked"], "broadcasting healthy")}'
            '<span class="sys-go" aria-hidden="true">&rsaquo;</span></div>')


def _failed(name, error):
    return (f'<div class="sys idle"><div class="sys-id"><b>{marks.mark(name)}{escape(name)}</b></div>'
            f'<div class="sys-mid small">Could not be read just now: {escape(_why(error))}. '
            'The other constellations are not affected.</div></div>')


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
    window_days = st.session_state.get("window_days", time_range.DEFAULT_DAYS)
    gap = data.orbit_gap()
    parts, failed = {}, {}
    for name in shell.CONSTELLATIONS:   # one that fails says why in its row; the others still show (issue 39)
        try:
            parts[name] = summary(name, data.load(name, window_days), gap)
        except Exception as error:
            failed[name] = error
    wholes = {system: whole(system, [parts[name] for name in names if name in parts])
              for system, names in SYSTEMS_PARTS.items() if any(name in parts for name in names)}
    healthy, total = sum(s["healthy"] for s in wholes.values()), sum(s["total"] for s in wholes.values())
    surfaces.show(f'<div class="head"><span class="big num">{healthy} of {total}</span>'
                  f'<span class="muted">navigation satellites healthy and in place, across '
                  f'{reveal.count(len(wholes), "constellation")}</span>'
                  f'<span class="right">{tooltip.legend([(DOT_COLOURS[kind], meaning, shape) for kind, meaning, shape in DOTS], "What a dot means")}</span></div>'
                  '<p class="lede small">One row per constellation, one dot per satellite. A row opens that constellation, where every '
                  'satellite and every number behind these counts is shown.</p>')
    with st.container(key="home_systems"):
        for index, (system, names) in enumerate(SYSTEMS_PARTS.items()):
            with st.container(key=f"home_row_{index}"):
                unread = {part_name(name) or name: failed[name] for name in names if name in failed}
                st.html(_row(wholes[system], unread) if system in wholes else _failed(system, failed[names[0]]))
                _open(f"home_open_{index}", next((name for name in names if name in parts), names[0]), system)

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
