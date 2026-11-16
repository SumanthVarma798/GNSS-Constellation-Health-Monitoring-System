"""Home: every system side by side, for a reader new to them. One card per system: its score out of 100 in a ring of its
satellites' states.

The page reads in the order the whole dashboard follows: all the satellites (the count), each system (the cards),
what stands out (Worth a look), then what is measured, how, what is left out and what comes next (the section).
A card opens in place to what makes its score, with a button on to that system's Overview.
"""
import re
from html import escape

import streamlit as st
import streamlit.components.v1 as components

from ui import data, findings, home_data, icons, marks, palette, reveal, shell, surfaces, time_range, tooltip
from config.config import MEO_SATS
from ui.home_settings import CAVEATS, FINDINGS_SHOWN, HOW, HOW_LINKS, RULES, SYSTEMS
from ui.limits import BURN_DAYS
from ui.system_summary import whole
from ui.systems import SYSTEMS as SYSTEMS_PARTS, part_name

# The states a satellite can be in: (class, what it means), in the order a row lists them. Each has its own mark
# (ui/theme.css: round, diamond, square, ring), so the colour only backs it up.
STATES = [("ok", "healthy and in place"), ("warn", "needs a look"), ("bad", "set aside"), ("accent", "new, not scored yet")]


def _dot(sat):
    return "ok" if sat["ok"] else "bad" if sat["state"] == palette.SLOT_LEFT else "warn"


ARC, GAP = 270, 3   # the gauge's ring: degrees it spans (open at the bottom, like a speedometer), and between parts


def _split(system):
    """[(state, what it means, how many)] for the states that have any satellite, in STATES' order."""
    counts = {kind: 0 for kind, _ in STATES}
    for sat in system["sats"]:
        counts[_dot(sat)] += 1
    counts["accent"] = len(system["settling"])
    return [(kind, meaning, counts[kind]) for kind, meaning in STATES if counts[kind]]


def _gauge(system, split):
    """The score in the middle of a ring, the ring cut into the states in proportion to their counts, like the
    markings round a speedometer. The ring is a conic gradient: st.html keeps styles but drops SVG."""
    total, at, stops = sum(count for _, _, count in split), 0.0, []
    gaps = GAP * (len(split) > 1)
    for kind, _, count in split:
        end = at + (ARC - gaps * len(split)) * count / total
        stops += [f"var(--{kind}) {at:.1f}deg {end:.1f}deg", f"transparent {end:.1f}deg {end + gaps:.1f}deg"]
        at = end + gaps
    ring = f"conic-gradient(from {-ARC / 2:g}deg, {', '.join(stops)}, transparent {at:.1f}deg)" if split else "none"
    score = system["score"]
    band = surfaces.band(score) if score is not None else "idle"
    words = (f"Score {score} out of 100" if score is not None else "No score") + (
        f"; {system['healthy']} of {system['total']} satellites healthy and in place")
    return (f'<div class="gauge" style="--ring: {ring}" role="img" aria-label="{words}">'
            f'<b class="num {band}">{score if score is not None else "–"}</b><small>/ 100</small></div>')


def _how_scored(system, index):
    """'how this is scored', dotted, with a card that says it in a few lines."""
    used = len(system["score_parts"])
    return tooltip.tip_html('how this is scored', tooltip.glance(
        "The average of three measures, each the share of satellites that pass", [
            ("", "Orbit kept", "on the orbit it should be on"),
            ("", "Station held", "held in its slot, or in step with its plane"),
            ("", "Clock steady", "no clock step past 30 ns in the day")],
        note=("Counted the same: our choice. " if used == 3 else "None could be read today, so there is no score. "
              if not used else f"From {used} of 3 today: {reveal.count(3 - used, 'measure')} could not be read. ")
        + "Open the card for each one."), key=f"score_{index}")


def _anchor(heading):
    """The id of one "How to read this page" card or point, from its heading: 'What is measured' ->
    'how-what-is-measured'."""
    return "how-" + re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


TERMS = {point[0].lower() for _, _, points in HOW for point in points if not isinstance(point, str)}


def _explained(words):
    """Words on a row that "How to read this page" explains, as a link to the card that explains them (dotted under,
    like every word that opens an explanation); other words as they are. Following the link opens that section and
    scrolls to the card (_how_links_script); without scripts it still jumps to the card."""
    if words not in HOW_LINKS:
        return escape(words)
    target = _anchor(words if words.lower() in TERMS else HOW_LINKS[words])   # the point itself, else its card
    return (f'<a class="how-link" href="#{target}" '
            f'title="What this means: opens How to read this page">{escape(words)}</a>')


def _beside(system):
    """What is shown beside the score and not counted in it: the operator's own flag, whether that flag matches our
    check, and the burns found (none for most medium orbits: too little history to find them)."""
    burns = system["burns"]
    burn_words = (f"{burns[0]} by {reveal.count(burns[1], 'satellite')}" if burns
                  else "none found: too little history" if system["name"] in MEO_SATS else "none found")
    return ('<div class="ms">'
            + _measure_line("says healthy", system["flagged_healthy"], system["checked"])
            + _measure_line("flag matches our check", *system["flag_agrees"])
            + f'<span class="small">{_explained("burns")} in {BURN_DAYS} days</span><i></i>'
              f'<b class="{"num" if burns else "idle"}">{escape(burn_words)}</b></div>')


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


def _row(system, unread=None, index=0):
    """One constellation as a card. Closed: its score in a ring of its satellites' states, its name, who runs it,
    the states counted in words, and how the score is made. Opened (a click anywhere on it, no page reload): the
    three measures in the score, what is shown beside it, notes, and under it the button to its own pages (page()).
    For a system of several parts each part's count is a note, and a part in `unread` ({part's name: the error})
    says why it is missing."""
    name = system["name"]
    who, where = SYSTEMS.get(name, ("", ""))
    split = _split(system)
    notes = [f"{escape(new)} is new ({escape(stage)}) and is {_explained('not scored yet')}"   # each note is markup
             for new, stage in system["settling"].items()]
    notes += [escape(CAVEATS[name])] if name in CAVEATS else []
    notes = ([escape(" · ".join(f"{label} {count} of {of}" for label, count, of in system["parts"]))] * bool(system["parts"])
             + [escape(f"{label} could not be read just now: {_why(error)}") for label, error in (unread or {}).items()]
             + notes)
    # in the card's head nothing is a link, so a click there always opens the card; the words link once it is open
    counted = "".join(f'<span><i class="{kind}"></i>{count} {escape(meaning)}</span>' for kind, meaning, count in split)
    key = "".join(f'<span><i class="{kind}"></i>{_explained(meaning)}</span>' for kind, meaning, _ in split)
    in_score = '<div class="ms">' + "".join(_measure_line(*line) for line in [
        ("orbit kept", *system["orbit"]), ("station held", *system["station"]), ("clock steady", *system["clock"])]) + "</div>"
    return (f'<details class="sys card {surfaces.band(system["score"]) if system["score"] is not None else "idle"}">'
            f'<summary>{_gauge(system, split)}<div class="sys-id"><b>{marks.mark(name)}{escape(name)}</b>'
            f'<span class="small">{escape(" · ".join(filter(None, [who, where])))}</span>'
            f'<div class="dots mixw small">{counted}</div>'
            f'<span class="small">{_how_scored(system, index)}</span></div>'
            '<span class="sys-go" aria-hidden="true">&rsaquo;</span></summary>'
            f'<div class="card-more"><div class="card-g"><h4>In the score</h4>{in_score}</div>'
            f'<div class="card-g"><h4>Shown beside, not in the score</h4>{_beside(system)}</div>'
            + (f'<div class="card-g card-notes">' + "".join(f'<div class="small">{note}</div>' for note in notes)
               + "</div>" if notes else "")
            + (f'<div class="dots mixw small card-key">{key}</div>' if key else "")
            + "</div></details>")


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
            '<p class="lede small">One card per constellation, scored out of 100. Click a card to see what makes its '
            'score, and to explore that constellation further.</p>')


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


def _open(key, part):
    """The button laid over a finding (ui/theme.css): the whole finding opens the Overview of `part`."""
    st.button(f"Open {part}'s overview", key=key, on_click=shell.open_system, args=(part,))


def _how():
    """Four cards, in the order every page follows: an icon and a heading, then each point, its term on a line of its
    own. A card with groups (HOW's plain strings) takes the full width and sets them side by side."""
    cards = []
    for icon, title, points in HOW:
        groups = []
        for point in points:
            if isinstance(point, str) or not groups:
                groups.append((point if isinstance(point, str) else "", []))
            if not isinstance(point, str):
                groups[-1][1].append(point)
        body = "".join('<div class="how-g">' + (f"<h4>{escape(name)}</h4>" if name else "")
                       + "".join(f'<p class="how-p" id="{_anchor(term)}"><b>{escape(term)}</b> {escape(words)}</p>'
                                 for term, words in group) + "</div>" for name, group in groups)
        cards.append(f'<div class="how well{" wide" if len(groups) > 1 else ""}" id="{_anchor(title)}">'
                     f'<div class="how-h">{icons.mask(icon)}<span>{escape(title)}</span></div>'
                     f'<div class="how-groups">{body}</div></div>')
    return '<div class="how-grid">' + "".join(cards) + "</div>"


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
    kept = home_data.keys(data.orbit_gap()) if home_data.PARTS - set(ready) else None
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
            with slots[index].container(key=f"home_card_{index}"):
                unread = {part_name(name) or name: failed[name] for name in names if name in failed}
                st.html(_row(wholes[system], unread, index) if system in wholes else _failed(system, failed[names[0]]))
                # shown only while the card is open (ui/theme.css), as the way on to the constellation's own pages
                st.button(f"Explore {system} further", key=f"home_explore_{index}", type="primary",
                          icon=":material/arrow_forward:", on_click=shell.open_system,
                          args=(next((name for name in names if name in parts), names[0]),))
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
