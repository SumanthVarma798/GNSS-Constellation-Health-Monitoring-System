"""The Library page's parts: a scoreboard per navigation system, the same by design generation, and the cost figures.

Counts come from registry/library_counts.csv (built from GCAT by scripts/build_library_table.py); cost figures
from registry/library_figures.csv (kept by hand, each with its public source). Every builder returns an HTML string.
Ratios are shown plainly, each with its definition in a footnote; nothing here ranks one system above another.
Each footnote opens from its column heading as a tooltip, and all of them are listed by notes().
"""
from collections import Counter
from html import escape

from evidence.library_settings import OTHER_PROGRAMME, SYSTEMS
from evidence.settings import GCAT_CITATION
from ui import palette, surfaces, tooltip

COUNTS = ("launched", "failed_at_launch", "failed_in_orbit", "retired", "operating", "status_not_recorded")
NOT_KNOWN = "not known"

CSS = """<style>
.lib { overflow-x: auto; }
.lib table { border-collapse: collapse; width: 100%; font-size: 14px; min-width: 800px; }
.lib caption { text-align: left; color: var(--muted); font-size: 13px; padding-bottom: 10px; }
.lib th { color: var(--muted); font-size: 12px; font-weight: 600; text-align: right; padding: 6px 7px; vertical-align: bottom; }
.lib td { padding: 11px 7px; text-align: right; border-top: 1px solid var(--edge); vertical-align: top; }
.lib th:first-child, .lib td:first-child { text-align: left; position: sticky; left: 0; z-index: 1; background: var(--platform); }
.lib td.who { min-width: 150px; }
.lib td.who b { display: block; } .lib td.who .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }
.lib td.who span.small { display: block; margin-left: 18px; }
.lib td.words { text-align: left; white-space: normal; min-width: 170px; }
.lib td.bad-count { color: var(--bad); font-weight: 700; }
.lib .zero { color: var(--muted); }
.lib .rate { display: block; font-weight: 700; }
.lib .bar { display: block; height: 5px; border-radius: 999px; background: var(--well); box-shadow: var(--pressed); margin-top: 5px; min-width: 70px; }
.lib .bar i { display: block; height: 100%; border-radius: 999px; background: var(--accent); opacity: .7; }
.lib sup { color: var(--accent); font-size: 12px; margin-left: 2px; }
.lib-notes { font-size: 13px; color: var(--muted); }
.lib-notes ol { margin: 6px 0 0; padding-left: 20px; } .lib-notes li { margin: 4px 0; }
.lib-notes a, .lib a { color: var(--accent); overflow-wrap: anywhere; }
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


def launch_success(row):
    """Reached orbit ÷ launched, or None if nothing was launched."""
    return (row["launched"] - row["failed_at_launch"]) / row["launched"] if row["launched"] else None


def orbit_success(row):
    """(Reached orbit − failed in orbit) ÷ reached orbit, or None if nothing reached orbit."""
    reached = row["launched"] - row["failed_at_launch"]
    return (reached - row["failed_in_orbit"]) / reached if reached else None


def average_retired_years(row):
    """Years from launch to end of regular operations, averaged over the retired satellites; None if none retired."""
    return row["years_retired"] / row["retired"] if row["retired"] else None


def _rate(value):
    if value is None:
        return '<span class="muted">&ndash;</span>'
    return f'<span class="rate num">{100 * value:.1f}%</span><span class="bar"><i style="width:{100 * value:.1f}%"></i></span>'


def _count(value, bad=False):
    cls = ' class="bad-count"' if bad and value else ""
    return f'<td{cls}><span class="num{" zero" if not value else ""}">{value}</span></td>'


def _years(value):
    return '<span class="muted">&ndash;</span>' if value is None else f'<span class="num">{value:,.1f}</span>'


def _heads(updated, *titles):
    """Column headings: a plain title, or (title, footnote number) for one that opens its footnote as a tooltip."""
    notes = _notes(updated)
    return "".join(f"<th scope='col'>{title}</th>" if isinstance(title, str) else
                   f"<th scope='col'>{tooltip.tip_html(f'{title[0]}<sup>{title[1]}</sup>', notes[title[1] - 1])}</th>"
                   for title in titles)


def _notes(updated):
    """The footnotes, in number order, as markup."""
    return [
        f"Launched: spacecraft launched, as GCAT lists them: those that reached orbit (payload catalogue, grouped by programme name, the list of names being in our settings) plus launches that never reached orbit (GCAT's failed-launch catalogue, found by name). GCAT as of {escape(updated)}.",
        "Failed at launch: the launch never put the spacecraft in orbit (GCAT failed-launch catalogue).",
        "Failed in orbit: reached orbit, then GCAT's result flag says it failed early in its mission.",
        "Retired: not failed early, and GCAT gives a date when regular operations ended. That includes a full working life and an early end alike.",
        "Operating: GCAT marks it as believed still operating. Its author says he updates this patchily, so read it as his latest word, not a live status.",
        "Launch success rate = (launched &minus; failed at launch) &divide; launched.",
        "Orbit success rate = (reached orbit &minus; failed in orbit) &divide; reached orbit.",
        "Satellite-years: for each retired satellite, launch to the end of regular operations; for each operating one, launch to GCAT's update date; added up. A date given only to the month or year is taken at mid-month or mid-year (count of such satellites in the generation table).",
        "Average service, retired: years in service of retired satellites &divide; number retired. Design life is not in GCAT, so service is not compared with it here.",
        "Money: only figures a public source states, listed with their source. They cover different things in different years and currencies and cannot be put side by side.",
    ]


def notes(counts):
    """Every footnote, numbered, and where the counts come from."""
    rows = system_rows(counts)
    return ('<div class="lib-notes"><ol>' + "".join(f"<li>{n}</li>" for n in _notes(rows[0]["updated"] if rows else ""))
            + f"</ol><p>Counts: {escape(GCAT_CITATION)}, files satcat, psatcat and ftocat.</p></div>")


def scoreboard(counts, figures):
    """The scoreboard: one line per system."""
    rows = system_rows(counts)
    stated = {}
    for figure in figures:
        if figure["value"] != NOT_KNOWN:
            stated[figure["system"]] = stated.get(figure["system"], 0) + 1
    lines = ""
    for row in rows:
        system = escape(row["system"])
        money = (surfaces.chip(f"{stated[row['system']]} stated", "accent") if row["system"] in stated
                 else surfaces.chip("not known", "idle"))
        service = row["years_retired"] + row["years_operating"]
        lines += (
            f'<tr><td class="who"><b><span class="dot" style="background:{palette.CONSTELLATION_COLOURS[row["system"]]}"></span>{system}</b>'
            f'<span class="small">{escape(SYSTEMS[row["system"]]["country"])}, launches {_span(row["first"], row["last"])}</span></td>'
            + _count(row["launched"]) + _count(row["failed_at_launch"], bad=True) + _count(row["failed_in_orbit"], bad=True)
            + _count(row["retired"]) + _count(row["operating"])
            + f'<td>{_rate(launch_success(row))}</td><td>{_rate(orbit_success(row))}</td>'
            f'<td>{_years(service)}</td><td>{_years(average_retired_years(row))}</td><td>{money}</td></tr>')
    table = (
        '<table><caption>Navigation satellites per system, counted from GCAT. Counts are not like for like: the systems began in '
        'different decades and early generations were tests.</caption><thead><tr>'
        + _heads(rows[0]["updated"] if rows else "", "System, country", ("Launched", 1), ("Failed at launch", 2),
                 ("Failed in orbit", 3), ("Retired", 4), ("Operating", 5), ("Launch success rate", 6),
                 ("Orbit success rate", 7), ("Satellite-years in service", 8), ("Average service, retired (years)", 9),
                 ("Money", 10))
        + f"</tr></thead><tbody>{lines}</tbody></table>")
    return f'<div class="lib">{table}</div>'


def generations(counts):
    """The same counts by design generation, with the number of satellites whose service dates are approximate."""
    lines, rows = "", programme_rows(counts)
    for row in rows:
        label = row["programme"] if row["programme"] != OTHER_PROGRAMME else row["programme"] + " (not in the programme list)"
        lines += (f'<tr><td class="who"><b>{escape(row["system"])}</b><span class="small">{escape(label)}, launched {_span(row["first_launch"], row["last_launch"])}</span></td>'
                  + _count(row["launched"]) + _count(row["failed_at_launch"], bad=True) + _count(row["failed_in_orbit"], bad=True)
                  + _count(row["retired"]) + _count(row["operating"])
                  + f'<td>{_years(average_retired_years(row))}</td><td>{_years(row["years_retired"] + row["years_operating"])}</td>'
                    f'<td>{_count_plain(row["approximate_dates"])}</td></tr>')
    table = ('<table><caption>By design generation, as GCAT groups them.</caption><thead><tr>'
             + _heads(rows[0]["gcat_updated"] if rows else "", "System, generation", ("Launched", 1),
                      ("Failed at launch", 2), ("Failed in orbit", 3), ("Retired", 4), ("Operating", 5),
                      ("Average service, retired (years)", 9), ("Satellite-years in service", 8),
                      ("Dates approximate", 8))
             + f"</tr></thead><tbody>{lines}</tbody></table>")
    return f'<div class="lib">{table}</div>'


def _span(first, last):
    return first if first == last else f"{first} to {last}"


def _number(text):
    """A stated number with thousands separators; text that is not a number is left as it is."""
    try:
        return f"{float(text):,.10g}"
    except ValueError:
        return text


def _count_plain(value):
    return f'<span class="num{" zero" if not value else ""}">{value}</span>'


def costs(figures):
    """Every public figure for money, with what it covers and where it comes from."""
    lines = ""
    for figure in figures:
        link = (f'<a href="{escape(figure["source_link"], quote=True)}" target="_blank" rel="noopener noreferrer">{escape(figure["source_name"])}</a>'
                if figure["source_link"] else escape(figure["source_name"]))
        value = (f'<span class="num"><b>{escape(_number(figure["value"]))}</b> {escape(figure["unit"])}</span>' if figure["value"] != NOT_KNOWN
                 else surfaces.chip(NOT_KNOWN, "idle"))
        lines += (f'<tr><td class="who"><b>{escape(figure["system"])}</b><span class="small">{escape(figure["programme"])}</span></td>'
                  f'<td>{value}</td><td>{escape(figure["year_of_figure"]) or "&ndash;"}</td>'
                  f'<td class="words">{escape(figure["covers"])}</td><td class="words">{link}</td>'
                  f'<td class="words">{surfaces.chip(figure["status"], "idle")}</td></tr>')
    table = ('<table><caption>Figures a public source states, in the currency and year it states them. Nothing here is converted, '
             'averaged or estimated by us. Awaiting review by the owner.</caption><thead><tr>'
             + _heads("", "System", ("Figure", 10), "Year", "What it covers", "Source", "Status")
             + f"</tr></thead><tbody>{lines}</tbody></table>")
    return f'<div class="lib">{table}</div>'


def matching(rows):
    """How satellites were put in a system, in words, from registry/library_matching.csv."""
    n = {name: sum(int(row[name]) for row in rows) for name in rows[0] if name != "system"}
    gone = [f'{row["system"]} {row["registry_not_in_gcat"]}' for row in rows if int(row["registry_not_in_gcat"])]
    return (f'A satellite is put in a system by our registry when the registry lists it (by catalogue number); otherwise by its '
            f'GCAT programme. Of {n["registry_satellites"]} registry satellites, {n["registry_found_in_gcat"]} are in GCAT '
            f'and {n["registry_not_in_gcat"]} are not ({", ".join(gone) or "none"}: GCAT does not list them yet, so they are not counted). '
            f'GCAT lists {n["found_by_programme_only"]} more by programme only, mostly early GLONASS and BeiDou-1 satellites that '
            f'the registry (built from the IGS file) does not hold. Where both say, the registry and the GCAT programme '
            + (f'disagree for {n["registry_and_programme_disagree"]}.' if n["registry_and_programme_disagree"]
               else 'agree on every satellite.'))


def registry_lag_note(matching_rows, registry_rows):
    """A short note when library_matching.csv was counted against an older registry."""
    listed = Counter(row["constellation"] for row in registry_rows)
    lagging = [(row["system"], int(row["registry_satellites"]), listed[row["system"]])
               for row in matching_rows if int(row["registry_satellites"]) < listed[row["system"]]]
    if not lagging:
        return ""
    return " ".join(f"The library was counted when the registry listed {counted} {system} satellites; it now lists {now}."
                    for system, counted, now in lagging)
