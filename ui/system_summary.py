"""One system in a few numbers, for the Home page: how many of its satellites are healthy and in place, and how many
broadcast themselves as healthy. The counts are the ones the system's own Overview shows as its headline, made by
the same rules (in_slot_and_healthy here, meo_overview.healthy for the systems judged by plane).
"""
from analysis.meo_geometry import plane_drift
from config.config import MEO_SATS
from ui import meo_overview, orbit_age, orbit_section, palette
from ui.figures.slot_rows import as_number

HEALTHY_FROM = meo_overview.HEALTHY_FROM   # one top band for both kinds of system


def in_slot_and_healthy(score, state):
    """A satellite judged by longitude slot counts when its score is in the top band and it is in its slot."""
    return score is not None and score >= HEALTHY_FROM and state == palette.SLOT_IN


def _slot_satellites(result):
    """One row per satellite of a system judged by longitude slot: those scored, then those set aside."""
    positions_rows = orbit_section.positions_and_rows(result["health"], result["set_aside"],
                                                      orbit_section.designated_longitude, result["history"])
    slots = {row["name"]: row for row in positions_rows[1]}
    sats = []
    for health in result["health"].to_dict("records"):
        name, score = str(health["Satellite"]), as_number(health.get("Overall Score"))
        state = slots[name]["state"] if name in slots else palette.SLOT_UNKNOWN
        sats.append({"name": name, "group": str(health.get("Type", "")), "score": score, "state": state,
                     "ok": in_slot_and_healthy(score, state)})
    return sats + [{"name": name, "group": "set aside", "score": None, "state": palette.SLOT_LEFT, "ok": False}
                   for name in result["set_aside"]]


def _plane_satellites(result):
    """One row per satellite of a system judged by orbital plane, plane by plane."""
    return [{"name": row["name"], "group": str(row["plane"]), "score": row["score"],
             "state": meo_overview.state_of(row)[0], "ok": meo_overview.healthy(row)}
            for members in meo_overview.by_plane(result["rows"]).values() for row in members]


def summary(name, result, gap=None):
    """{name, sats, healthy, total, settling, planes, in_file, flagged_healthy, broadcast_day} for one system.

    sats: {name, group, score, state, ok, broadcast} per satellite counted, where broadcast is "ok" (flagged
    healthy), "bad" (flagged unhealthy), "silent" (not in the day's file) or None (no broadcast check to read).
    settling: the satellites still moving to their slot, which are not counted. planes: plane_drift's rows for a
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
    checked = [sat for sat in sats if sat["broadcast"] is not None]
    return {"name": name, "sats": sats, "healthy": sum(sat["ok"] for sat in sats), "total": len(sats),
            "settling": list(result.get("moving") or {}),
            "planes": plane_drift(name, result["rows"]) if by_plane else {},
            "in_file": sum(sat["broadcast"] != "silent" for sat in checked) if checked else None,
            "flagged_healthy": sum(sat["broadcast"] == "ok" for sat in checked) if checked else None,
            "checked": len(checked), "broadcast_day": (gap or {}).get("day") if checked else None}
