"""One system in a few numbers, for the Home page: how many of its satellites are healthy and in place, and how many
broadcast themselves as healthy. The counts are the ones the system's own Overview shows as its headline, made by
the same rules (in_slot_and_healthy here, meo_overview.healthy for the systems judged by plane).
"""
from analysis import commissioning
from analysis.meo_geometry import plane_drift
from statistics import median

from evidence.registry_tables import judged_by_plane
from ui import burn_record, limits, meo_overview, orbit_age, orbit_section, palette, systems
from ui.figures.slot_rows import as_number

HEALTHY_FROM = meo_overview.HEALTHY_FROM   # one top band for both kinds of system


def in_slot_and_healthy(score, state):
    """A satellite judged by longitude slot counts when its score is in the top band and it is in its slot."""
    return score is not None and score >= HEALTHY_FROM and state == palette.SLOT_IN


def _passes(scores):
    """Whether every part that has a score is in the top band; None when none has a score, so nothing is judged."""
    known = [score for score in scores if score is not None]
    return all(score >= HEALTHY_FROM for score in known) if known else None


def _measured(parts, kind, state_ok):
    """(orbit kept, station held) for one satellite from its parts' scores: each True, False, or None when the
    parts that show it have no score. kind is "slot" or "plane"; state_ok is whether it is where it should be."""
    orbit = _passes(parts.get(part) for part in limits.MEASURES["orbit"][kind])
    held = _passes(parts.get(part) for part in limits.MEASURES["station"][kind])
    return orbit, None if held is None else held and state_ok


def _slot_satellites(result):
    """One row per satellite of a system judged by longitude slot: those scored, then those set aside."""
    positions_rows = orbit_section.positions_and_rows(result["health"], result["set_aside"],
                                                      orbit_section.designated_longitude, result["history"])
    slots = {row["name"]: row for row in positions_rows[1]}
    sats = []
    for health in result["health"].to_dict("records"):
        name, score = str(health["Satellite"]), as_number(health.get("Overall Score"))
        state = slots[name]["state"] if name in slots else palette.SLOT_UNKNOWN
        parts = {label: as_number(health.get(column)) for label, column in orbit_section.PARTS}
        orbit, station = _measured(parts, "slot", state == palette.SLOT_IN)
        sats.append({"name": name, "group": str(health.get("Type", "")), "score": score, "state": state,
                     "ok": in_slot_and_healthy(score, state), "parts": parts, "orbit": orbit, "station": station})
    return sats + [{"name": name, "group": "set aside", "score": None, "state": palette.SLOT_LEFT, "ok": False,
                    "parts": {}, "orbit": None, "station": None} for name in result["set_aside"]]


def _plane_satellites(result):
    """One row per satellite of a system judged by orbital plane, plane by plane."""
    sats = []
    for members in meo_overview.by_plane(result["rows"]).values():
        for row in members:
            state = meo_overview.state_of(row)[0]
            orbit, station = _measured(row["parts"], "plane", state != palette.SLOT_OFF)
            sats.append({"name": row["name"], "group": str(row["plane"]), "score": row["score"], "state": state,
                         "ok": meo_overview.healthy(row), "parts": dict(row["parts"]), "orbit": orbit, "station": station})
    return sats


def score_of(counts, system):
    """(the constellation's score out of 100, [(measure, its pass rate in %, its weight)]): the weighted average of
    the pass rates of orbit kept, station held, clock steady and the burn record that could be read, weighed by the constellation's
    mission (ui.limits MISSION, MEASURE_WEIGHTS), heaviest first. A measure not read is left out and the others'
    weights are scaled up to add to 1. (None, []) when none could be read."""
    owner = next((name for name, parts in systems.SYSTEMS.items() if system in parts), system)   # a part's system
    weights = limits.MEASURE_WEIGHTS[limits.MISSION.get(owner, "global")]
    read = [(key, 100 * passed / judged) for key, weight in sorted(weights.items(), key=lambda item: -item[1])
            for passed, judged in [counts.get(key, (0, 0))] if judged]
    total = sum(weights[key] for key, _ in read)
    parts = [(key, rate, weights[key] / total) for key, rate in read]
    return (round(sum(rate * weight for _, rate, weight in parts)) if parts else None), parts


def _measures(sats, system):
    """{"orbit", "station", "clock", "care": (how many pass, how many were judged), "clock_typical_ns", "score",
    "score_parts"} over `sats`: the four measures counted ("care" is the burn record), the middle of the satellites' typical clock steps (None
    when no clock was heard), and the score made from them (score_of())."""
    def count(key):
        judged = [sat[key] for sat in sats if sat.get(key) is not None]
        return sum(judged), len(judged)

    typical = [sat["clock"]["typical_step_ns"] for sat in sats
               if sat.get("clock") and sat["clock"].get("typical_step_ns") is not None]
    counts = {"orbit": count("orbit"), "station": count("station"), "clock": count("clock_steady"),
              "care": count("care"), "clock_typical_ns": median(typical) if typical else None}
    counts["score"], counts["score_parts"] = score_of(counts, system)
    return counts


def _stage(result, name):
    """A new satellite's stage in words (analysis/commissioning.py), or "new" when its records cannot say."""
    try:
        return commissioning.stage(result["history"], name)
    except (KeyError, TypeError, ValueError):
        return "new"


def _when_scored(result, name, first):
    """Its stage and the day it will be scored from (analysis/commissioning.py), or its stage alone when its records
    cannot say."""
    try:
        return commissioning.when_scored(result["history"], name, first)
    except (KeyError, TypeError, ValueError):
        return _stage(result, name)


def _burn_record(name, result, sats):
    """The constellation's burn record (ui/burn_record.py record_of), with each satellite's pass of the burn record
    set in `sats` as "care" (True, False, or None: not judged, set aside, or no burns found). None when no burns were
    found: the systems judged by plane mostly have too little history to find any (analysis/meo_run.py)."""
    table = burn_record.classified(name, result)
    care = burn_record.care_of(table) if table is not None else {}
    for sat in sats:
        sat["care"] = None if sat["group"] == "set aside" else care.get(sat["name"])
    return burn_record.record_of(table)


def summary(name, result, gap=None):
    """{name, sats, healthy, total, settling, planes, in_file, flagged_healthy, broadcast_day} for one system.

    Also the four measures counted (_measures) and burn_record (the burns by kind over 365 days, or None). sats:
    {name, group, score, state, ok, parts, orbit, station, broadcast, clock, clock_steady, care} per satellite counted,
    where orbit, station, clock_steady and care are True, False or None (not judged: ui/limits.py MEASURES), clock is the day's clock figures, and broadcast is "ok" (flagged
    healthy), "bad" (flagged unhealthy), "silent" (not in the day's file) or None (no broadcast check to read).
    settling: {satellite: which stage it is at} for the new satellites not scored yet, which are not counted. planes: plane_drift's rows for a
    system judged by plane, else {}. `gap` is ui.data.orbit_gap()'s payload.
    """
    by_plane = judged_by_plane(name)
    sats = _plane_satellites(result) if by_plane else _slot_satellites(result)
    statuses = orbit_age._status_by_satellite(gap)
    for sat in sats:
        status = statuses.get(sat["name"])
        if status is None:
            sat["broadcast"] = None
        elif status.get("health") is None:
            sat["broadcast"] = "silent"
        else:
            sat["broadcast"] = "ok" if orbit_age.health_words(status)[1] == "ok" else "bad"
        sat["clock"] = clock = (status or {}).get("clock") or None   # analysis/broadcast_clock.py's figures for the day
        step = (clock or {}).get("largest_step_ns")
        sat["clock_steady"] = None if step is None else step <= limits.CLOCK_STEADY_NS
    checked = [sat for sat in sats if sat["broadcast"] is not None]
    flagged = [sat for sat in checked if sat["broadcast"] in ("ok", "bad")]
    return {"name": name, "sats": sats, "healthy": sum(sat["ok"] for sat in sats), "total": len(sats),
            # the operator's own word against our check: its flag says healthy exactly where we count it healthy
            "flag_agrees": (sum((sat["broadcast"] == "ok") == sat["ok"] for sat in flagged), len(flagged)),
            "burn_record": _burn_record(name, result, sats),
            "settling": {new: _when_scored(result, new, first) for new, first in (result.get("moving") or {}).items()},
            "planes": plane_drift(name, result["rows"]) if by_plane else {},
            "in_file": sum(sat["broadcast"] != "silent" for sat in checked) if checked else None,
            "flagged_healthy": sum(sat["broadcast"] == "ok" for sat in checked) if checked else None,
            "checked": len(checked), "broadcast_day": (gap or {}).get("day") if checked else None,
            **_measures(sats, name)}


def whole(system, parts):
    """A system's parts as one: each part's satellites in turn, and the counts added up. `parts` are summary()'s
    rows for the parts that could be read, in the system's order. "parts" holds (the part's name beside the
    system's, healthy, total) for a system with several parts, so a reader can go one step deeper, and "part_scores"
    (the part's name, its own score) beside them. The system's score counts every satellite of every part once,
    so it lies between its parts' scores and is the same number on Home and on each part's page."""
    checked = sum(part["checked"] for part in parts)
    return {"name": system, "sats": [sat for part in parts for sat in part["sats"]],
            "flag_agrees": tuple(map(sum, zip(*(part["flag_agrees"] for part in parts)))) if parts else (0, 0),
            "burn_record": burn_record.combine(part["burn_record"] for part in parts),
            "healthy": sum(part["healthy"] for part in parts), "total": sum(part["total"] for part in parts),
            "settling": {name: stage for part in parts for name, stage in part["settling"].items()}, "checked": checked,
            "flagged_healthy": sum(part["flagged_healthy"] or 0 for part in parts) if checked else None,
            "parts": [(systems.part_name(part["name"]), part["healthy"], part["total"]) for part in parts]
            if len(systems.SYSTEMS[system]) > 1 else [],
            "part_scores": [(systems.part_name(part["name"]), part.get("score")) for part in parts]
            if len(systems.SYSTEMS[system]) > 1 else [],
            **_measures([sat for part in parts for sat in part["sats"]], system)}
