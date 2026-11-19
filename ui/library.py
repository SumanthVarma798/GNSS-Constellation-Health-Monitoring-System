"""The Library's comparisons, each answering one question with a picture: who maintains their constellation best,
who has done this longest and how well, did one design generation keep failing, and what public sources say each
cost. Each builder returns an HTML string; each *_answer returns the one line that answers its question.

Counts come from registry/library_counts.csv (built from GCAT by scripts/build_library_table.py); cost figures
from registry/library_figures.csv (kept by hand, each with its public source). What each count means opens from its
key as a tooltip (LIBRARY_COLUMN_HELP).
"""
from collections import Counter
from html import escape
from urllib.parse import urlparse

from evidence.library_settings import AMOUNT_SCALES, GRADE_STATUS, LIBRARY_COLUMN_HELP, OTHER_PROGRAMME, SYSTEMS
from evidence.settings import GCAT_CITATION, RELIABILITY_GRADES
from ui import palette, surfaces, tooltip

COUNTS = ("launched", "failed_at_launch", "failed_in_orbit", "retired", "operating", "status_not_recorded")
NOT_KNOWN = "not known"

CSS = """<style>
.lib { padding-top: 2px; }
.gen-caption { color: var(--fc-small); font-size: var(--fs-small); margin: 0 0 8px; }
.gen-key { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: var(--fs-small); color: var(--fc-small); margin-bottom: 6px; }
.gen-key span { display: inline-flex; align-items: center; gap: 6px; }
.gen-key i { width: 14px; height: 8px; border-radius: 3px; }
.gen-sys { margin: 18px 0 4px; font-size: var(--fs-side); font-weight: var(--fw-side); color: var(--fc-side); letter-spacing: .02em; }
.gen-row { display: grid; grid-template-columns: minmax(150px, 300px) 1fr auto; align-items: center; gap: 4px 14px; padding: 8px 0;
  border-top: 1px solid var(--edge); }
.gen-name { min-width: 0; } .gen-name > b { display: block; font-weight: 600; } .gen-name .small { display: block; }
:is(.gen-name, .gen-sys) .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }
.gen-name .chip { margin: 4px 6px 0 0; }
.gen-name a { color: var(--accent); font-size: var(--fs-small); overflow-wrap: anywhere; }
.gen-row.worst { box-shadow: inset 3px 0 0 var(--bad); } .gen-row.worst .gen-name { padding-left: 12px; }
.gen-track { height: 22px; display: flex; align-items: center; min-width: 0; }
.gen-bar { display: flex; gap: 2px; height: 12px; min-width: 6px; border-radius: 3px; outline-offset: 3px; cursor: default; }
.gen-bar i { display: grid; place-items: center; height: 100%; border-radius: 3px; min-width: 3px; overflow: hidden; }
.gen-bar i b { font-size: var(--fs-small); font-weight: 700; font-style: normal; font-variant-numeric: tabular-nums; color: var(--sink); opacity: 0; }
/* hovered or focused, the bar grows to hold each part's count; a part too thin for its number widens to fit it */
.gen-bar:is(:hover, :focus-visible) { height: 22px; }
.gen-bar:is(:hover, :focus-visible) i { min-width: 1.9em; }
.gen-bar:is(:hover, :focus-visible) i b { opacity: 1; }
.gen-bar i[style*="gradient"] b { color: var(--ink); text-shadow: 0 0 3px var(--sink); }
@media (prefers-reduced-motion: no-preference) { .gen-bar { transition: height 150ms ease; } .gen-bar i b { transition: opacity 150ms ease; } }
.gen-n { text-align: right; white-space: nowrap; } .gen-n b { font-size: var(--fs-body); margin-right: 4px; }
.gen-n .block { display: block; }
.gen-n .bad-count { color: var(--bad); }
/* two measures per row, one bar each: a pressed rail with the measure's colour in it, its number beside it */
.lib-pair { display: grid; gap: 6px; min-width: 0; }
.lib-pair > span { display: grid; grid-template-columns: minmax(0, 1fr) 12.5em; align-items: center; gap: 10px; }
.rail { display: block; height: 10px; border-radius: 999px; background: var(--well); box-shadow: var(--pressed); overflow: hidden; }
.rail i { display: block; height: 100%; border-radius: 999px; }
.lib-pair b { font-weight: 700; } .lib-pair .small { margin-left: 4px; }
@media (max-width: 640px) {
  .gen-row { grid-template-columns: 1fr auto; }
  .gen-name { grid-column: 1 / -1; }
  .gen-row.pairs .lib-pair { grid-column: 1 / -1; }
}
</style>"""


def _int(row, name):
    return int(row[name])


def system_rows(counts):
    """One summed row per system, in the order of SYSTEMS: counts, years, first and last launch year, GCAT's update date."""
    sums = {}
    for row in counts:
        one = sums.setdefault(row["system"], dict.fromkeys(COUNTS, 0) | {"years_retired": 0.0, "years_operating": 0.0,
                                                                     "approximate_dates": 0, "first": row["first_launch"],
                                                                     "last": row["last_launch"], "updated": row["gcat_updated"]})
        for name in COUNTS + ("approximate_dates",):
            one[name] += _int(row, name)
        one["years_retired"] += float(row["years_retired"])
        one["years_operating"] += float(row["years_operating"])
        one["first"], one["last"] = min(one["first"], row["first_launch"]), max(one["last"], row["last_launch"])
    return [{"system": system, **sums[system]} for system in SYSTEMS if system in sums]


def programme_rows(counts):
    """The programme rows as numbers, in file order."""
    return [{**row, **{name: _int(row, name) for name in COUNTS + ("approximate_dates",)},
             "years_retired": float(row["years_retired"]), "years_operating": float(row["years_operating"])} for row in counts]


def failures(row):
    """Failed at launch plus failed in orbit."""
    return row["failed_at_launch"] + row["failed_in_orbit"]


def failure_share(row):
    """Failures per satellite launched; 0 when nothing was launched."""
    return failures(row) / row["launched"] if row["launched"] else 0


def satellite_years(row):
    return row["years_retired"] + row["years_operating"]


def average_retired_years(row):
    """Years from launch to end of regular operations, averaged over the retired satellites; None if none retired."""
    return row["years_retired"] / row["retired"] if row["retired"] else None


def _and(names):
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _help(key, updated=""):
    """The card a key opens: what the count is, read at a glance (LIBRARY_COLUMN_HELP)."""
    lead, items, note = LIBRARY_COLUMN_HELP[key]
    return tooltip.glance(lead, items, note.format(updated=updated))


def _cited(updated):
    """GCAT's citation, which its licence (CC-BY) asks for wherever its data is shown."""
    return f"{escape(GCAT_CITATION)}, as of {escape(updated)}." if updated else f"{escape(GCAT_CITATION)}."


def _who(system, line=""):
    """A constellation's name with its colour dot, and a small line under it."""
    dot = palette.css(palette.CONSTELLATION_COLOURS.get(system, palette.FILL))
    return (f'<b><span class="dot" style="background:{dot}"></span>{escape(system)}</b>'
            + (f'<span class="small">{line}</span>' if line else ""))


# What became of a constellation's or generation's satellites, in bar order: the part, its words, its colour (the
# same meanings as the lifecycles: working green, after service grey, failure red) and the help its key opens.
GENERATION_PARTS = (("operating", "operating", "var(--ok)", "operating"), ("retired", "retired", "var(--idle)", "retired"),
                    ("failed_in_orbit", "failed in orbit", "var(--bad)", "failed_in_orbit"),
                    ("failed_at_launch", "failed at launch", "repeating-linear-gradient(135deg, var(--bad) 0 3px, var(--well) 3px 6px)",
                     "failed_at_launch"),
                    ("status_not_recorded", "status not recorded", "var(--track)", None))


def _parts_key(rows, updated, length_help=True):
    """The key over a set of outcome bars: what the length means, then the colour of each part some row has, each
    opening its help."""
    length = f'<span>bar length: {tooltip.tip_html("launched", _help("launched", updated))}</span>' if length_help else ""
    return '<div class="gen-key">' + length + "".join(
        f'<span><i style="background: {colour}"></i>' + (tooltip.tip_html(words, _help(help)) if help else words) + "</span>"
        for name, words, colour, help in GENERATION_PARTS if any(row[name] for row in rows)) + "</div>"


def _outcome_bar(row, width):
    """One bar of what became of a row's satellites, split by part; a part that is zero is not drawn. Each part
    carries its count, shown when the bar is hovered or focused (the bar grows to hold it)."""
    parts = [(row[name], words, colour) for name, words, colour, _ in GENERATION_PARTS if row[name]]
    said = ", ".join(f"{n} {words}" for n, words, _ in parts)
    segments = "".join(f'<i style="flex: {n} 1 0; background: {colour}" title="{n} {words}"><b>{n}</b></i>'
                       for n, words, colour in parts)
    return (f'<div class="gen-track"><div class="gen-bar" tabindex="0" role="img" '
            f'aria-label="{row["launched"]} launched: {escape(said, quote=True)}" style="width: {width:.1f}%">{segments}</div></div>')


def _origin(row):
    return escape(SYSTEMS[row["system"]]["country"]) + " · launches " + _span(row["first"], row["last"])


def _failed_cell(row):
    lost = failures(row)
    return (f'<div class="gen-n"><b class="num{" bad-count" if lost else ""}">{lost}</b>'
            f'<span class="small">failed of {row["launched"]}</span></div>')


# ---- Who maintains their constellation best? ----

def upkeep_order(counts):
    """The constellations, fewest failures per launch first; a tie goes to the one that launched more."""
    return sorted((row for row in system_rows(counts) if row["launched"]), key=lambda row: (failure_share(row), -row["launched"]))


def upkeep_answer(counts):
    rows = upkeep_order(counts)
    if not rows:
        return "nothing counted"
    clean = [row["system"] for row in rows if not failures(row)]
    worst = rows[-1]
    first = f"none failed: {_and(clean)}" if clean else f"fewest failures per launch: {rows[0]['system']}"
    return first + (f" · most: {worst['system']}, {failures(worst)} of {worst['launched']}" if failures(worst) else "")


def upkeep(counts):
    """Every satellite each constellation launched, as one full-width bar split by what became of it, ranked by
    failures per launch."""
    rows = upkeep_order(counts)
    if not rows:
        return '<div class="lib"><p class="small">Nothing counted.</p></div>'
    updated = rows[0]["updated"]
    body = "".join(f'<div class="gen-row"><div class="gen-name">{_who(row["system"], _origin(row))}</div>'
                   f'{_outcome_bar(row, 100)}{_failed_cell(row)}</div>' for row in rows)
    return (f'<div class="lib">{_parts_key(rows, updated, length_help=False)}{body}'
            f'<p class="gen-caption">Each bar is every satellite the constellation launched; hover it for the counts. '
            f'{_cited(updated)}</p></div>')


# ---- Who has done this longest, and how well? ----

def experience_answer(counts):
    rows = [row for row in system_rows(counts) if satellite_years(row)]
    if not rows:
        return "nothing counted"
    top = max(rows, key=satellite_years)
    lasting = max((row for row in rows if row["retired"]), key=average_retired_years, default=None)
    words = f"longest: {top['system']}, {satellite_years(top):,.0f} satellite-years"
    if lasting:
        words += (f" · longest-serving retired satellites: {lasting['system']}, {average_retired_years(lasting):.1f} years "
                  f"each ({lasting['retired']} retired)")
    return words


def experience(counts):
    """Per constellation, two bars: satellite-years in service, and the years a retired satellite served on average."""
    rows = sorted(system_rows(counts), key=satellite_years, reverse=True)
    if not rows:
        return '<div class="lib"><p class="small">Nothing counted.</p></div>'
    updated = rows[0]["updated"]
    most = max(satellite_years(row) for row in rows) or 1
    longest = max((average_retired_years(row) or 0) for row in rows) or 1
    key = '<div class="gen-key">' + "".join(
        f'<span><i style="background: var(--{colour})"></i>{tooltip.tip_html(words, _help(help))}</span>'
        for colour, words, help in (("accent", "satellite-years in service", "satellite_years"),
                                    ("ok", "years a retired satellite served, on average", "average_retired"))) + "</div>"
    body = ""
    for row in rows:
        years, average = satellite_years(row), average_retired_years(row)
        served = (f'<span><span class="rail"><i style="width: {average / longest * 100:.1f}%; background: var(--ok)"></i></span>'
                  f'<span><b class="num">{average:,.1f}</b><span class="small">years · {row["retired"]} retired</span></span></span>'
                  if average is not None else
                  '<span><span class="rail"></span><span class="small">none retired yet</span></span>')
        body += (f'<div class="gen-row pairs"><div class="gen-name">{_who(row["system"], "since " + escape(row["first"]))}</div>'
                 f'<div class="lib-pair" role="img" aria-label="{row["system"]}: {years:,.0f} satellite-years'
                 + (f', retired satellites served {average:.1f} years on average' if average is not None else "") + '">'
                 f'<span><span class="rail"><i style="width: {years / most * 100:.1f}%; background: var(--accent)"></i></span>'
                 f'<span><b class="num">{years:,.0f}</b><span class="small">satellite-years</span></span></span>{served}</div></div>')
    return f'<div class="lib">{key}{body}<p class="gen-caption">{_cited(updated)}</p></div>'


# ---- Did one design generation keep failing? ----

def generations_answer(counts):
    rows = programme_rows(counts)
    failing = [row for row in rows if failures(row)]
    if not failing:
        return "no: no generation has a failure"
    worst = max(failing, key=failures)
    rest = sum(map(failures, failing)) - failures(worst)
    if failures(worst) > rest:
        return (f"yes: {worst['programme']}, {failures(worst)} of {worst['launched']} failed, more than every other "
                f"generation together ({rest})")
    return f"no: failures are spread over {len(failing)} generations, at most {failures(worst)} in one ({worst['programme']})"


def generations(counts):
    """One bar per design generation, as long as the satellites it launched, split by what became of them; the
    generation with the most failures is marked."""
    rows = programme_rows(counts)
    if not rows:
        return '<div class="lib"><p class="small">No generations counted.</p></div>'
    updated, longest = rows[0]["gcat_updated"], max(row["launched"] for row in rows) or 1
    worst = max(rows, key=failures)
    body, system = "", None
    for row in rows:
        if row["system"] != system:
            system = row["system"]
            body += f'<h4 class="gen-sys">{_who(system)}</h4>'
        label = row["programme"] if row["programme"] != OTHER_PROGRAMME else row["programme"] + " (not in the programme list)"
        marked = row is worst and failures(row)
        body += (f'<div class="gen-row{" worst" if marked else ""}"><div class="gen-name"><b>{escape(label)}</b>'
                 f'<span class="small">launched {_span(row["first_launch"], row["last_launch"])}</span>'
                 + (surfaces.chip("most failures", "bad") if marked else "") + "</div>"
                 + _outcome_bar(row, row["launched"] / longest * 100)
                 + f'<div class="gen-n"><b class="num">{row["launched"]}</b><span class="small">launched</span>'
                 + (f'<span class="small bad-count block">{failures(row)} failed</span>' if failures(row) else "") + "</div></div>")
    return (f'<div class="lib gen">{_parts_key(rows, updated)}{body}'
            f'<p class="gen-caption">Design generations as GCAT groups them. {_cited(updated)}</p></div>')


def _span(first, last):
    return first if first == last else f"{first} to {last}"


# ---- What do public sources say each cost? ----

def _number(text):
    """A stated number with thousands separators; text that is not a number is left as it is."""
    try:
        return f"{float(text):,.10g}"
    except ValueError:
        return text


def amount(figure):
    """(the stated amount with its scale word applied, its currency): ("1.6", "billion US dollars") gives
    (1.6e9, "US dollars"). The currency is never converted."""
    scale, _, currency = figure["unit"].partition(" ")
    if scale in AMOUNT_SCALES:
        return float(figure["value"]) * AMOUNT_SCALES[scale], currency
    return float(figure["value"]), figure["unit"]


def grade_of(figure, grades):
    """The figure's publisher's reliability grade (A to F) from grades {domain: grade}, or "" when not graded."""
    return grades.get(urlparse(figure["source_link"]).netloc.removeprefix("www."), "")


def costs_answer(figures):
    stated = [figure for figure in figures if figure["value"] != NOT_KNOWN]
    currencies = {amount(figure)[1] for figure in stated}
    missing = [figure["system"] for figure in figures if figure["value"] == NOT_KNOWN]
    return (f"{len(stated)} figures in {len(currencies)} currencies, each as its source states it"
            + (f" · {_and(missing)}: none found" if missing else ""))


def costs(figures, grades):
    """A bar per stated figure, grouped by currency (a bar compares only with bars in its own currency), coloured by
    how sure it is: its publisher's grade. A figure no source states is listed with "not known"."""
    groups, source = {}, ""
    for figure in figures:
        # "Same as the line above" names the previous row's publisher
        source = source if figure["source_name"].startswith("Same as") else figure["source_name"].split(",")[0]
        if figure["value"] == NOT_KNOWN:
            groups.setdefault(None, []).append((figure, None, source))
        else:
            value, currency = amount(figure)
            groups.setdefault(currency, []).append((figure, value, source))
    shown = sorted({grade_of(figure, grades) for figure, value, _ in sum(groups.values(), []) if value is not None},
                   key=lambda grade: (not grade, grade))   # graded first
    key = '<div class="gen-key">' + "".join(
        f'<span><i style="background: var(--{GRADE_STATUS[grade] if grade else "idle"})"></i>'
        + (f"grade {grade}: {escape(RELIABILITY_GRADES[grade])}" if grade else "publisher not graded") + "</span>"
        for grade in shown) + "</div>"
    body = ""
    for currency, rows in sorted(groups.items(), key=lambda item: item[0] is None):
        body += f'<h4 class="gen-sys">{escape(currency[:1].upper() + currency[1:]) if currency else "No public figure found"}</h4>'
        top = max((value for _, value, _ in rows if value), default=1)
        for figure, value, source in rows:
            grade = grade_of(figure, grades)
            card = tooltip.glance(figure["covers"], [("database", "Source", figure["source_name"])],
                                  f"Status: {figure['status']}")
            link = (f'<a href="{escape(figure["source_link"], quote=True)}" target="_blank" rel="noopener noreferrer">'
                    f'{escape(source)}</a>' if figure["source_link"] else escape(figure["source_name"]))
            chip = surfaces.chip(f"grade {grade}" if grade else "not graded", GRADE_STATUS.get(grade, "idle"))
            name = (f'<div class="gen-name">{_who(figure["system"], tooltip.tip_html(escape(figure["programme"]), card))}'
                    f'{chip if value is not None else ""}{link}</div>')
            if value is None:
                body += f'<div class="gen-row">{name}<div></div><div class="gen-n">{surfaces.chip(NOT_KNOWN, "idle")}</div></div>'
                continue
            scale = figure["unit"].removesuffix(currency).strip()
            body += (f'<div class="gen-row">{name}<div class="gen-track"><span class="rail" style="width: {value / top * 100:.1f}%; '
                     f'min-width: 10px; flex: none" role="img" aria-label="{escape(_number(figure["value"]))} {escape(figure["unit"])}">'
                     f'<i style="width: 100%; background: var(--{GRADE_STATUS.get(grade, "idle")})"></i></span></div>'
                     f'<div class="gen-n"><b class="num">{escape(_number(figure["value"]))}</b>{escape(scale)}'
                     f'<span class="small block">{escape(figure["year_of_figure"])}</span></div></div>')
    return (f'<div class="lib">{key}{body}<p class="gen-caption">Each figure in the currency and year its source states; '
            f'nothing converted, averaged or estimated by us. Hover a programme for what the figure covers.</p></div>')


def matching(rows):
    """How satellites were put in a system, in words, from registry/library_matching.csv."""
    n = {name: sum(int(row[name]) for row in rows) for name in rows[0] if name != "system"}
    gone = [f'{row["system"]} {row["registry_not_in_gcat"]}' for row in rows if int(row["registry_not_in_gcat"])]
    return (f'A satellite is put in a constellation by the IGS satellite metadata file when that file lists it (by catalogue '
            f'number); otherwise by its programme in GCAT, J. McDowell\'s catalogue of space objects. Of '
            f'{n["registry_satellites"]} satellites in the IGS satellite metadata file, {n["registry_found_in_gcat"]} are in GCAT '
            f'and {n["registry_not_in_gcat"]} are not ({", ".join(gone) or "none"}: GCAT does not list them yet, so they are not counted). '
            f'GCAT lists {n["found_by_programme_only"]} more by programme only, mostly early GLONASS and BeiDou-1 satellites that '
            f'the IGS satellite metadata file does not list. Where both say, the IGS satellite metadata file and the GCAT programme '
            + (f'disagree for {n["registry_and_programme_disagree"]}.' if n["registry_and_programme_disagree"]
               else 'agree on every satellite.'))


def registry_lag_note(matching_rows, registry_rows):
    """A short note when library_matching.csv was counted against an older registry."""
    listed = Counter(row["constellation"] for row in registry_rows)
    lagging = [(row["system"], int(row["registry_satellites"]), listed[row["system"]])
               for row in matching_rows if int(row["registry_satellites"]) < listed[row["system"]]]
    if not lagging:
        return ""
    return " ".join(f"These counts were made when the IGS satellite metadata file listed {counted} {system} satellites; "
                    f"it now lists {now}."
                    for system, counted, now in lagging)
