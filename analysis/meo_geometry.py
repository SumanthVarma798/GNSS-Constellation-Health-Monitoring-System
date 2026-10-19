"""Where each medium Earth orbit (MEO) satellite is against where its system says it should be.

GPS, GLONASS and Galileo are judged by orbital plane, not by longitude slot. From each satellite's
newest mean elements, all moved to one common time (the newest epoch among them):

  plane         Which plane its orbit is in, from its node (right ascension of the ascending node, RAAN).
                The planes sit an equal step apart (config/meo_nominal.py), so the whole pattern's turn
                is fitted to every satellite at once; each satellite is in the nearest plane of that
                pattern and its offset is how far its node is from that plane's. The plane is named by
                the registry plane most of its satellites have; a satellite the registry puts in
                another plane is named in `plane_agrees`.
  spacing       The gap in argument of latitude to the next satellite ahead in the same plane, against
                the gap between their two slots in the source's slot table. Both neighbours count:
                the worse of the gap ahead and the gap behind is scored. The sources give how far one
                satellite may be from its slot, so a gap, set by two satellites, is allowed twice that.
                A satellite away from its working height (outside the height tolerance) is passing
                through the plane, not holding a slot: it is left out of its neighbours' gaps.
  inclination   Tilt against the nominal.     height   Semi-major axis against the nominal.
  eccentricity  Against the most the system allows.

Galileo's two satellites in the eccentric orbit (registry plane X) are judged against that orbit:
inclination, height and eccentricity only.

Health score (0 to 100, bands as the other scores: 80 healthy, 60 fair, 40 degraded, below critical):
each part scores 100 while its error is within its tolerance and falls in a straight line to 0 at three
times the tolerance. The overall score is the weighted mean of the parts that could be worked out,
with WEIGHTS (spacing counts most: it is what keeps coverage even). Manoeuvres are not part of the
score: they need history, which these systems mostly lack (see analysis/meo_run.py).

Two-body motion only, with the Earth's flattening (J2) for the node's drift. Over the day or two
between epochs that is well inside the tolerances. The argument of latitude from mean elements uses
the first-order correction for eccentricity.
"""
import math

import numpy as np

from config.meo_nominal import NOMINAL

MU = 398600.4418      # km^3/s^2
EARTH_KM = 6378.137
J2 = 1.08262668e-3
WEIGHTS = {"plane": 0.20, "spacing": 0.30, "inclination": 0.20, "height": 0.15, "eccentricity": 0.15}
BANDS = ((80, "🟢 Healthy"), (60, "🟡 Fair"), (40, "🟠 Degraded"), (-math.inf, "🔴 Critical"))
EXTENDED = "Extended"   # the plane name for Galileo's eccentric-orbit pair


def wrap(deg):
    """An angle in degrees, to -180..180."""
    return (deg + 180) % 360 - 180


def part_score(error, tolerance):
    """100 within the tolerance, then a straight line to 0 at three times it."""
    over = abs(error) - tolerance
    return 100.0 if over <= 0 else max(0.0, 100.0 - 50.0 * over / tolerance)


def status_of(score):
    return next(words for floor, words in BANDS if score >= floor)


def semi_major_axis_km(mean_motion_rev_day):
    n = mean_motion_rev_day * 2 * math.pi / 86400
    return (MU / n ** 2) ** (1 / 3)


def _node_rate_deg_day(a, e, i_deg, n_rev_day):
    """The node's drift from the Earth's flattening (J2), degrees a day."""
    return -1.5 * n_rev_day * 360 * J2 * (EARTH_KM / a) ** 2 * math.cos(math.radians(i_deg)) / (1 - e * e) ** 2


def at_common_time(elements):
    """{name: {raan, u, i, a, e}} for {name: newest element row}, all moved to the newest epoch among them."""
    when = max(row["EPOCH"] for row in elements.values())
    moved = {}
    for name, row in elements.items():
        n, e, i = float(row["MEAN_MOTION"]), float(row["ECCENTRICITY"]), float(row["INCLINATION"])
        a = semi_major_axis_km(n)
        days = (when - row["EPOCH"]).total_seconds() / 86400
        m = float(row["MEAN_ANOMALY"])
        u = float(row["ARG_OF_PERICENTER"]) + m + math.degrees(2 * e * math.sin(math.radians(m))) + n * 360 * days
        moved[name] = {"raan": (float(row["RA_OF_ASC_NODE"]) + _node_rate_deg_day(a, e, i, n) * days) % 360,
                       "u": u % 360, "i": i, "a": a, "e": e}
    return moved


def fit_planes(raans, spacing):
    """(turn, [plane index per satellite], [offset per satellite]) for planes `spacing` degrees apart.

    Multiplying every node by the number of planes puts all the planes on one angle, so its circular
    mean gives the pattern's turn."""
    count = round(360 / spacing)
    turn = math.degrees(np.angle(np.mean(np.exp(1j * count * np.radians(raans))))) / count
    index = [round((r - turn) / spacing) % count for r in raans]
    return turn, index, [wrap(r - turn - k * spacing) for r, k in zip(raans, index)]


def _name_planes(index, registry_planes):
    """{plane index: name}: the registry plane most of its satellites have."""
    names = {}
    for k in set(index):
        given = [p for j, p in zip(index, registry_planes) if j == k and p]
        names[k] = max(set(given), key=given.count) if given else f"unnamed {k + 1}"
    return names


def _slot_key(slot):
    """The registry's slot name as the slot tables write it: GLONASS's "07" is slot "7"."""
    return str(int(slot)) if slot.isdigit() else slot


def _spacing(members, now, slots):
    """{name: [(gap is, gap should be, error), ahead then behind]} for one plane's satellites with a known slot.

    members: [(name, registry slot)], only satellites at their working height."""
    known = sorted((now[name]["u"], name, slots[_slot_key(slot)]) for name, slot in members if _slot_key(slot) in slots)
    gaps = {name: [] for _, name, _ in known}
    if len(known) < 2:
        return gaps
    for (u, name, nominal), (u_next, name_next, nominal_next) in zip(known, known[1:] + known[:1]):
        actual, should = (u_next - u) % 360, (nominal_next - nominal) % 360
        gap = (actual, should, wrap(actual - should))
        gaps[name].append(gap)
        gaps[name_next].append(gap)
    return gaps


def _slot_positions(rows, working, now, slot_of, slots):
    """Set each row's "slot_at": where its own slot is now, in argument of latitude, or None without one.

    All slots move together, so one turn, fitted to the satellites at their working height, places them all."""
    held = [name for name in working if _slot_key(slot_of[name]) in slots]
    if not held:
        return
    turn = math.degrees(np.angle(np.mean([np.exp(1j * math.radians(now[name]["u"] - slots[_slot_key(slot_of[name])]))
                                          for name in held])))
    for name, slot in slot_of.items():
        rows[name]["slot_at"] = (slots[_slot_key(slot)] + turn) % 360 if _slot_key(slot) in slots else None


def assess(system, elements, registry):
    """One row per satellite of `system` ("GPS", "GLONASS" or "Galileo"), in the order of `elements`.

    elements: {name: newest element row, with EPOCH a datetime}. registry: {name: registry row (plane,
    slot, signal_id_now)}. Each row: name, signal_id, plane (from the orbit), registry_plane, plane_agrees,
    slot (the registry's), u (argument of latitude now), slot_at (where its slot is now, or None),
    node_rate (its node's drift from J2, degrees a day), checks ([(measure, should be, is, error, score)]),
    parts ({measure: score}), score, status.
    """
    nominal = {key: value.value for key, value in NOMINAL[system].items()}
    now = at_common_time(elements)
    names = list(elements)
    plane_of = {name: nominal["registry_planes"].get(registry[name]["plane"]) for name in names}
    in_planes = [name for name in names if plane_of[name]]
    rows = {name: {"name": name, "signal_id": registry[name]["signal_id_now"], "u": now[name]["u"],
                   "registry_plane": plane_of[name], "slot": registry[name]["slot"], "slot_at": None,
                   "checks": [], "plane": EXTENDED, "plane_agrees": True,
                   "node_rate": _node_rate_deg_day(now[name]["a"], now[name]["e"], now[name]["i"],
                                                   float(elements[name]["MEAN_MOTION"]))} for name in names}

    if in_planes:
        _, index, offsets = fit_planes([now[name]["raan"] for name in in_planes], nominal["plane_spacing_deg"])
        plane_names = _name_planes(index, [plane_of[name] for name in in_planes])
        for name, k, offset in zip(in_planes, index, offsets):
            rows[name]["plane"], rows[name]["plane_agrees"] = plane_names[k], plane_names[k] == plane_of[name]
            rows[name]["checks"].append(("plane", 0.0, offset, offset,
                                         part_score(offset, nominal["plane_tolerance_deg"])))
        working = [name for name in in_planes
                   if abs(now[name]["a"] - nominal["semi_major_axis_km"]) <= nominal["semi_major_axis_tolerance_km"]]
        _slot_positions(rows, working, now, {name: registry[name]["slot"] for name in in_planes}, nominal["slots"])
        for plane in set(plane_names.values()):
            members = [(name, registry[name]["slot"]) for name in working if rows[name]["plane"] == plane]
            for name, gaps in _spacing(members, now, nominal["slots"]).items():
                if gaps:
                    actual, should, error = max(gaps, key=lambda gap: abs(gap[2]))
                    rows[name]["checks"].append(("spacing", should, actual, error,
                                                 part_score(error, 2 * nominal["spacing_tolerance_deg"])))

    for name in names:
        orbit, row = now[name], rows[name]
        if plane_of[name]:
            targets = [("inclination", nominal["inclination_deg"], orbit["i"], nominal["inclination_tolerance_deg"]),
                       ("height", nominal["semi_major_axis_km"], orbit["a"], nominal["semi_major_axis_tolerance_km"])]
            row["checks"].append(("eccentricity", nominal["eccentricity_max"], orbit["e"],
                                  max(0.0, orbit["e"] - nominal["eccentricity_max"]),
                                  part_score(orbit["e"], nominal["eccentricity_max"])))
        elif "extended" in nominal:
            ext = nominal["extended"]
            targets = [("inclination", ext["inclination_deg"], orbit["i"], nominal["inclination_tolerance_deg"]),
                       ("height", ext["semi_major_axis_km"], orbit["a"], nominal["semi_major_axis_tolerance_km"]),
                       ("eccentricity", ext["eccentricity"], orbit["e"], nominal["extended_eccentricity_tolerance"])]
        else:
            targets = []
        for measure, should, actual, tolerance in targets:
            row["checks"].append((measure, should, actual, actual - should, part_score(actual - should, tolerance)))
        row["checks"].sort(key=lambda check: list(WEIGHTS).index(check[0]))
        row["parts"] = {measure: score for measure, *_, score in row["checks"]}
        weight = sum(WEIGHTS[m] for m in row["parts"])
        row["score"] = sum(WEIGHTS[m] * s for m, s in row["parts"].items()) / weight if weight else None
        row["status"] = status_of(row["score"]) if row["score"] is not None else ""
    return [rows[name] for name in names]


def plane_drift(system, rows):
    """{plane: {offset, offset_limit, rate, gap, gap_limit}} for each plane of slots in `rows` (assess's), not the
    eccentric orbit.

      offset  How far the plane's node sits from the fitted pattern of equally spaced planes: the mean of its
              satellites' plane offsets, degrees.
      rate    How fast that offset is changing, degrees a year: the plane's node drift from the Earth's flattening
              (J2), worked out from its satellites' tilt and height, less the whole pattern's (every satellite in a
              plane, as fit_planes weighs them). From the newest elements, so it needs no history. The same sign
              as offset means moving away from the pattern.
      gap     The spacing spread inside the plane: the worst gap error against the slot table, degrees, or None
              when no gap could be measured.
    The limits are those the satellites' own plane and spacing checks use.
    """
    nominal = NOMINAL[system]
    in_planes = [row for row in rows if row["plane"] != EXTENDED]
    if not in_planes:
        return {}
    pattern_rate = np.mean([row["node_rate"] for row in in_planes])
    out = {}
    for plane in {row["plane"] for row in in_planes}:
        members = [row for row in in_planes if row["plane"] == plane]
        checks = [{check[0]: check for check in row["checks"]} for row in members]
        gaps = [abs(check["spacing"][3]) for check in checks if "spacing" in check]
        out[plane] = {"offset": float(np.mean([check["plane"][3] for check in checks])),
                      "offset_limit": nominal["plane_tolerance_deg"].value,
                      "rate": float(np.mean([row["node_rate"] for row in members]) - pattern_rate) * 365.25,
                      "gap": max(gaps) if gaps else None,
                      "gap_limit": 2 * nominal["spacing_tolerance_deg"].value}
    return out
