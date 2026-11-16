"""One system in a few numbers, for the Home page: how many of its satellites are healthy and in place, and how many
broadcast themselves as healthy. The counts are the ones the system's own Overview shows as its headline, made by
the same rules (in_slot_and_healthy here, meo_overview.healthy for the systems judged by plane).
"""
from datetime import datetime, timedelta, timezone

from analysis import commissioning
from analysis.meo_geometry import plane_drift
from config.config import MEO_SATS
from statistics import median

from ui import limits, meo_overview, orbit_age, orbit_section, palette, systems
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


def score_of(counts):
    """(the constellation's score out of 100, [(measure, its pass rate in %)]): the average of the pass rates of orbit
    kept, station held and clock steady that could be read, each weighted the same (our choice: ui/home_settings.py
    HOW names it). (None, []) when none could be read."""
    rates = [(key, 100 * passed / judged) for key in ("orbit", "station", "clock") for passed, judged in [counts[key]]
             if judged]
    return (round(sum(rate for _, rate in rates) / len(rates)) if rates else None), rates


def _measures(sats):
    """{"orbit", "station", "clock": (how many pass, how many were judged), "clock_typical_ns", "score",
    "score_parts"} over `sats`: the three measures counted, the middle of the satellites' typical clock steps (None
    when no clock was heard), and the score made from them (score_of())."""
    def count(key):
        judged = [sat[key] for sat in sats if sat.get(key) is not None]
        return sum(judged), len(judged)

    typical = [sat["clock"]["typical_step_ns"] for sat in sats
               if sat.get("clock") and sat["clock"].get("typical_step_ns") is not None]
    counts = {"orbit": count("orbit"), "station": count("station"), "clock": count("clock_steady"),
              "clock_typical_ns": median(typical) if typical else None}
    counts["score"], counts["score_parts"] = score_of(counts)
    return counts


def _stage(result, name):
    """A new satellite's stage in words (analysis/commissioning.py), or "new" when its records cannot say."""
    try:
        return commissioning.stage(result["history"], name)
    except (KeyError, TypeError, ValueError):
        return "new"


def _recent_burns(burns, now=None):
    """(burns, satellites that made them) found in the last BURN_DAYS of orbit records, or None when none were found:
    the systems judged by plane mostly have too little history to find any (analysis/meo_run.py)."""
    if burns is None or not len(burns):
        return None
    since = (now or datetime.now(timezone.utc)).replace(tzinfo=None) - timedelta(days=limits.BURN_DAYS)
    recent = burns[burns["window_end"] >= since]
    return len(recent), int(recent["satellite"].nunique())


def summary(name, result, gap=None):
    """{name, sats, healthy, total, settling, planes, in_file, flagged_healthy, broadcast_day} for one system.

    Also the three measures counted (_measures). sats: {name, group, score, state, ok, parts, orbit, station,
    broadcast, clock, clock_steady} per satellite counted, where orbit, station and clock_steady are True, False or
    None (not judged: ui/limits.py MEASURES), clock is the day's clock figures, and broadcast is "ok" (flagged
    healthy), "bad" (flagged unhealthy), "silent" (not in the day's file) or None (no broadcast check to read).
    settling: {satellite: which stage it is at} for the new satellites not scored yet, which are not counted. planes: plane_drift's rows for a
    system judged by plane, else {}. `gap` is ui.data.orbit_gap()'s payload.
    """
    by_plane = name in MEO_SATS
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
            "burns": _recent_burns(result.get("burns")),
            "settling": {new: _stage(result, new) for new in result.get("moving") or {}},
            "planes": plane_drift(name, result["rows"]) if by_plane else {},
            "in_file": sum(sat["broadcast"] != "silent" for sat in checked) if checked else None,
            "flagged_healthy": sum(sat["broadcast"] == "ok" for sat in checked) if checked else None,
            "checked": len(checked), "broadcast_day": (gap or {}).get("day") if checked else None,
            **_measures(sats)}


def whole(system, parts):
    """A system's parts as one: each part's satellites in turn, and the counts added up. `parts` are summary()'s
    rows for the parts that could be read, in the system's order. "parts" holds (the part's name beside the
    system's, healthy, total) for a system with several parts, so a reader can go one step deeper."""
    checked = sum(part["checked"] for part in parts)
    burns = [part["burns"] for part in parts if part["burns"]]
    return {"name": system, "sats": [sat for part in parts for sat in part["sats"]],
            "flag_agrees": tuple(map(sum, zip(*(part["flag_agrees"] for part in parts)))) if parts else (0, 0),
            "burns": tuple(map(sum, zip(*burns))) if burns else None,
            "healthy": sum(part["healthy"] for part in parts), "total": sum(part["total"] for part in parts),
            "settling": {name: stage for part in parts for name, stage in part["settling"].items()}, "checked": checked,
            "flagged_healthy": sum(part["flagged_healthy"] or 0 for part in parts) if checked else None,
            "parts": [(systems.part_name(part["name"]), part["healthy"], part["total"]) for part in parts]
            if len(systems.SYSTEMS[system]) > 1 else [],
            **_measures([sat for part in parts for sat in part["sats"]])}
