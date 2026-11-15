"""Orbit kept, station held, clock steady: the three measures on one constellation's own page, one step deeper than
Home. A strip at the top declares the counts; a section lists every satellite with what each measure read and the
figure behind it. What counts for each measure is in ui/limits.py (MEASURES, CLOCK_STEADY_NS).
"""
from config.config import MEO_SATS
from ui import limits, meo_overview, palette, reveal, surfaces

# (key in ui.system_summary's counts, the words on the page), in the order shown everywhere.
MEASURES = [("orbit", "Orbit kept"), ("station", "Station held"), ("clock", "Clock steady")]
# The table's columns: (heading, one plain line), by how the constellation is judged.
STATION_LINE = {"slot": "in its slot and not drifting", "plane": "in step with its plane"}
FLAG = {"ok": ("healthy", "ok"), "bad": ("unhealthy", "bad"), "silent": ("not in the IGS daily broadcast file", "idle"),
        None: ("not read", "idle")}


def _chip(words, count, of):
    if not of:
        return surfaces.chip(f"{words}: not read", "idle")
    return surfaces.chip(f"{words} {count} of {of}", surfaces.band(100 * count / of))


def strip(summary):
    """The three counts and the constellation's own flag, as chips: declared before anything else on the page."""
    chips = [_chip(words, *summary[key]) for key, words in MEASURES]
    chips.append(_chip("Says healthy", summary["flagged_healthy"], summary["checked"]))
    return f'<div class="measures" role="group" aria-label="Orbit, station-keeping and clock">{"".join(chips)}</div>'


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


def _clock(sat):
    clock = sat.get("clock")
    if not clock or sat["clock_steady"] is None:
        return _cell("not heard" if sat["broadcast"] in (None, "silent") else "too few messages", "idle")
    return _cell("steady" if sat["clock_steady"] else "stepped", "ok" if sat["clock_steady"] else "bad",
                 should=f"under {limits.CLOCK_STEADY_NS:g} ns",
                 note=f"largest step {clock['largest_step_ns']:,.1f} ns · typical {clock['typical_step_ns']:.2f} ns · "
                      f"drift {clock['drift_ns_per_day']:,.0f} ns a day")


def table(summary):
    """Every satellite against the three measures and its own flag, with the figure behind each."""
    kind = "plane" if summary["name"] in MEO_SATS else "slot"
    labels = meo_overview.LABELS if kind == "plane" else {"Inclination": "tilt", "Drift": "drift"}
    columns = [("Satellite", ""), ("Orbit kept", "on the orbit it should be on"),
               ("Station held", STATION_LINE[kind]),
               ("Clock steady", f"no step past {limits.CLOCK_STEADY_NS:g} ns in the day"),
               ("Says healthy", "its own broadcast flag")]
    rows = [(sat["name"], [_judged(sat, "orbit", kind, "kept", "not kept", labels), _station(sat, kind, labels),
                           _clock(sat), _cell(*FLAG[sat["broadcast"]])]) for sat in summary["sats"]]
    return surfaces.table(columns, rows)


def section(summary):
    """The section under the page: every satellite, measure by measure."""
    said = " · ".join(f"{words.lower()} {count} of {of}" if of else f"{words.lower()} not read"
                      for (key, words) in MEASURES for count, of in [summary[key]])
    reveal.section(f"three_measures_{summary['name']}", "Orbit, station-keeping and clock, satellite by satellite",
                   said, table(summary))
