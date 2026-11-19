"""The Master map page's parts around the map: the count, one row per constellation, where each thing comes from and
how fresh it is, the spacecraft our sources disagree about, and how to read the page. Every builder returns HTML.

The rows read the same records the map draws (ui.components.master_map.master_map_records), so a dot, a card on the
map and a line under "Where our sources disagree" are always the same spacecraft.
"""
from datetime import date
from html import escape

from evidence import jobs
from evidence.console_settings import WORKFLOWS_DIR
from evidence.registry_tables import page_name, registry_name
from evidence.settings import SCHEME_SIGNAL_ID
from ui import icons, marks, palette, surfaces, tooltip
from ui.age_rule import orbit_age_status
from ui.master_map_settings import HOW, NOTES, REGISTRY_WORKFLOW, WHO
from ui.pages_data import live_feed_time



def spacecraft(n):
    return f"{n} spacecraft"


def needs_a_look(record):
    """The map's "!" mark: the two sources disagree about who it is or whether it works, or one identifier is off."""
    return bool(record["disagreement"]) or any(item["status"] == "warn" for item in record["identifiers"])


def holds_signal_id(record):
    """True when the IGS file gives the spacecraft a signal ID today."""
    return any(item["scheme"] == SCHEME_SIGNAL_ID and item["status"] == "ok" for item in record["identifiers"])


def dot_kind(record):
    """What one spacecraft counts as: "look", "seen", "now" (a signal ID today) or "past"; a disagreement wins."""
    if needs_a_look(record):
        return "look"
    if record["sighting"]:
        return "seen"
    return "now" if holds_signal_id(record) else "past"


def constellations(records, parts, tracked_counts):
    """One summary per constellation, in the order of `parts` ({name: (part, ...)}, ui/systems.py SYSTEMS): its
    spacecraft as dot kinds and the counts its row shows. tracked_counts is {part: satellites the other pages follow}."""
    rows = []
    for name, held in parts.items():
        mine = [record for record in records if record["constellation"] == registry_name(name)]
        kinds = [dot_kind(record) for record in mine]
        rows.append({"name": name, "parts": held, "kinds": kinds, "total": len(kinds),
                     "now": sum(map(holds_signal_id, mine)), "look": kinds.count("look"), "seen": kinds.count("seen"),
                     "tracked": sum(tracked_counts.get(part, 0) for part in held)})
    return rows


def head(rows):
    """The count across every constellation, and what the page is for."""
    total, now = sum(r["total"] for r in rows), sum(r["now"] for r in rows)
    tracked, look = sum(r["tracked"] for r in rows), sum(r["look"] for r in rows)
    return (f'<div class="head mm-head"><span class="big num">{total}</span>'
            f'<span class="muted">navigation spacecraft on record across {len(rows)} constellations · '
            f'{now} with a signal ID today · {tracked} followed on the other pages · {look} worth a look</span></div>')


def _figure(value, words, status=""):
    return f'<div class="sys-m"><span class="s num {status}">{value}</span><span class="small">{escape(words)}</span></div>'


def row(summary):
    """One constellation: who runs it, how many hold a signal ID, how many the other pages
    follow, and how many need a look. Its edge is the constellation's own colour, the one its cards have on the map."""
    name = summary["name"]
    who, where = WHO.get(name, ("", ""))
    colour = palette.css(palette.CONSTELLATION_COLOURS.get(registry_name(name), palette.FILL))
    notes = ([NOTES[name]] if name in NOTES else []) + (
        [f"{spacecraft(summary['seen'])} seen in CelesTrak's GNSS group, not yet in the IGS satellite metadata file"] if summary["seen"] else [])
    look = (_figure(summary["look"], "worth a look: the IGS metadata file, GCAT or CelesTrak disagree", "warn") if summary["look"]
            else _figure(0, "worth a look: the IGS metadata file, GCAT and CelesTrak agree", "ok"))
    return (f'<div class="sys mm-sys" style="border-left-color:{colour}">'
            f'<div class="sys-id"><b>{marks.mark(name)}{escape(name)}</b>'
            f'<span class="small">{escape(" · ".join(filter(None, [who, where])))}</span>'
            f'<span class="small">{spacecraft(summary["total"])} on record</span></div>'
            f'<div class="sys-mid">'
            + "".join(f'<div class="small">{escape(note)}</div>' for note in notes) + '</div>'
            f'{_figure(summary["now"], "with a signal ID today")}'
            f'{_figure(summary["tracked"], "followed on the other pages")}{look}</div>')


def _day(text):
    """'2026-10-20' -> '20 Oct 2026'; anything else as it is."""
    try:
        day = date.fromisoformat(text[:10])
    except (TypeError, ValueError):
        return text or "not known"
    return f"{day.day} {day:%b %Y}"


def _registry_schedule(now):
    """('Sundays 01:00 UTC', 'next about 22 Nov') from the registry job's workflow file; ('weekly', '') if unreadable."""
    try:
        text = (WORKFLOWS_DIR / REGISTRY_WORKFLOW).read_text(encoding="utf-8")
        crons = [cron for group in jobs.schedules(text).values() for cron in group]
        upcoming = jobs.next_run(crons, now) if crons else None
    except (OSError, ValueError, IndexError):
        return "weekly", ""
    if not crons:
        return "weekly", ""
    words = " and ".join(jobs.schedule_words(cron) for cron in crons) + " UTC"
    return words, (f"next about {upcoming.day} {upcoming:%b}" if upcoming else "")


def freshness(data, live, now):
    """Where each thing on the page comes from and how fresh it is: {what, source, when, how, status}, one per input
    the page reads. live is data.celestrak.state; now is an aware UTC datetime."""
    schedule, upcoming = _registry_schedule(now)
    approval = "A change waits for a person's approval."
    weekly = f"We update it from this file {schedule}" + (f", {upcoming}" if upcoming else "") + f". {approval}"
    changes = [row[key][:10] for row in data["signal_ids"] for key in ("valid_from", "valid_to") if row[key]]
    added = [row["added"] for row in data["tracked"] if row.get("added")]
    taken = live_feed_time(live)
    if taken:
        age = (now - taken).total_seconds() / 86400
        feed = {"when": f"copy taken {_day(taken.isoformat())} {taken:%H:%M} UTC",
                "how": "We copy CelesTrak's GNSS group every two hours and read it from that copy.",
                "status": orbit_age_status(age)}
    else:
        feed = {"when": f"weekly copy of {_day(max(data['feed_checked'].values(), default=''))}",
                "how": "The two-hourly copy of CelesTrak's orbit feed could not be read, so this dashboard's weekly copy of "
                       "CelesTrak's orbit feed stands in. It holds NavIC, QZSS and BeiDou-3's IGSO and GEO "
                       "satellites only.", "status": "warn"}
    seen = [row["note"].split(";")[-1].strip() for row in data["sightings"]]
    return [
        {"what": "Which spacecraft exist, and each one's signal ID", "source": "IGS satellite metadata file",
         "when": f"newest signal-ID change in it: {_day(max(changes, default=''))}", "how": weekly, "status": "idle"},
        {"what": "Owner, and whether it still works", "source": "GCAT, J. McDowell's catalogue of space objects",
         "when": f"GCAT dated {_day(data.get('gcat_updated', ''))}",
         "how": f"We rebuild it from GCAT in the same weekly update. {approval}", "status": "idle"},
        {"what": "The name its orbit is published under", "source": "CelesTrak's orbit feed", **feed},
        {"what": "The name the dashboard uses", "source": "this dashboard's list of the satellites it follows",
         "when": f"last satellite added {_day(max(added, default=''))}",
         "how": "Chosen by the team (registry/dashboard_satellites.csv); adding or removing one is approved by pull request.", "status": "idle"},
        {"what": "Spacecraft seen before the IGS satellite metadata file lists them", "source": "CelesTrak's GNSS group",
         "when": spacecraft(len(seen)) + (": " + ", ".join(seen) if seen else ""), "how": weekly, "status": "idle"},
    ]


def sources(facts):
    """The freshness facts as one raised card, a line each: what, from where, how fresh (words and colour), how often."""
    lines = "".join(
        f'<div class="mm-src"><div class="mm-src-what"><b>{escape(fact["what"])}</b>'
        f'<span class="small">{tooltip.link_sources(escape(fact["source"]))}</span></div>'
        f'<div class="mm-src-when">{surfaces.chip(fact["when"], fact["status"])}</div>'
        f'<div class="small mm-src-how">{escape(fact["how"])}</div></div>' for fact in facts)
    return f'<div class="raised mm-sources">{lines}</div>'


def disagreements(records):
    """The spacecraft marked on the map, in registry order, each with what is off."""
    lines = ""
    for record in records:
        if not needs_a_look(record):
            continue
        off = [record["disagreement"]] if record["disagreement"] else []
        off += [f'{item["scheme"]}: {item["remark"]}' for item in record["identifiers"] if item["status"] == "warn"]
        lines += (f'<li><b class="num">{escape(record["svn"])}</b> {escape(record["name"])} '
                  f'<span class="muted">{escape(page_name(record["constellation"]))}</span>'
                  f'<div class="small">{escape("; ".join(off))}</div></li>')
    return f'<ul class="mm-look">{lines}</ul>' if lines else ('<p class="small">The IGS satellite metadata file, GCAT and CelesTrak\'s orbit feed agree about every '
                                                                     'spacecraft.</p>')


def how():
    """Four cards, as on Home: an icon and a heading, then each point led by its term."""
    return '<div class="how-grid">' + "".join(
        f'<div class="how well"><div class="how-h">{icons.mask(icon)}<span>{escape(title)}</span></div>'
        + "".join(f"<p><b>{escape(term)}.</b> {escape(words)}</p>" for term, words in points) + "</div>"
        for icon, title, points in HOW) + "</div>"
