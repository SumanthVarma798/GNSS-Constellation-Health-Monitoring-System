""" "Worth a look": comparisons the dashboard finds itself, from ui.system_summary's rows. Each finding comes from a
named rule (ui/home_settings.py RULES), never a hand pick, and carries the numbers that raised it.

A finding: {rule, system, line, numbers, pair, size, about, explained}. `pair` is the two things compared, as
((label, value), (label, value)), for the picture. `about` names the satellites or plane, for the explained list.
`explained` is why it is expected (home_settings.EXPLAINED), or "" when it is not.
"""
from statistics import median

from ui import reveal
from ui.home_settings import EXPLAINED, ODD_NEEDS, ODD_SPREAD_FLOOR, ODD_SPREADS, RULES


def _day(iso):
    """'13 Nov' for '2026-11-13'."""
    return f"{int(iso[8:10])} {'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[int(iso[5:7]) - 1]}" if iso else "that day"


def _names(names, most=4):
    return ", ".join(names[:most]) + (f" and {len(names) - most} more" if len(names) > most else "")


def _split(rule, system, names):
    """(names not explained, {name: why} for those that are)."""
    why = {name: EXPLAINED[rule, system, name] for name in names if (rule, system, name) in EXPLAINED}
    return [name for name in names if name not in why], why


def _finding(rule, system, line, numbers, pair, size, about, explained=""):
    return {"rule": rule, "system": system, "line": line, "numbers": numbers, "pair": pair, "size": size,
            "about": about, "explained": explained}


def _each(rule, system, names, make):
    """One finding for the names not explained (when any), and one per explained name, each from make(names)."""
    fresh, why = _split(rule, system, names)
    return ([make(fresh)] if fresh else []) + [{**make([name]), "explained": reason} for name, reason in why.items()]


def silent(summary):
    """Tracked and in orbit, but missing from the day's broadcast file."""
    counted = [sat for sat in summary["sats"] if sat["broadcast"] is not None and sat["group"] != "set aside"]
    missing = [sat["name"] for sat in counted if sat["broadcast"] == "silent"]
    return _each("silent", summary["name"], missing, lambda names: _finding(
        "silent", summary["name"],
        f"{reveal.count(len(names), 'tracked satellite')} not in the day's broadcast file",
        f"{_names(names)} · {len(counted) - len(missing)} of {len(counted)} tracked are in the file of "
        f"{_day(summary['broadcast_day'])}",
        (("tracked", len(counted)), ("in the file", len(counted) - len(missing))), len(names) / len(counted), names))


def disagree(summary):
    """The broadcast says healthy but the orbit check does not, or the other way round."""
    name, sats = summary["name"], [sat for sat in summary["sats"] if sat["broadcast"] in ("ok", "bad")]
    flagged_ok = [sat for sat in sats if sat["broadcast"] == "ok"]
    out_of_place = [sat["name"] for sat in flagged_ok if not sat["ok"]]
    flagged_bad = [sat for sat in sats if sat["broadcast"] == "bad"]
    in_place = [sat["name"] for sat in flagged_bad if sat["ok"]]
    found = _each("disagree", name, out_of_place, lambda names: _finding(
        "disagree", name,
        f"{len(names)} broadcast as healthy, but our orbit check finds {'it' if len(names) == 1 else 'them'} out of place",
        f"{_names(names)} · {len(flagged_ok)} flagged healthy, {len(flagged_ok) - len(out_of_place)} of them in place",
        (("flagged healthy", len(flagged_ok)), ("also in place", len(flagged_ok) - len(out_of_place))),
        len(names) / len(sats), names))
    return found + _each("disagree", name, in_place, lambda names: _finding(
        "disagree", name,
        f"{len(names)} flagged unhealthy by {'its' if len(names) == 1 else 'their'} own broadcast, though in place "
        "by our orbit check",
        f"{_names(names)} · {len(flagged_bad)} flagged unhealthy in the file of {_day(summary['broadcast_day'])}",
        (("in place", sum(sat["ok"] for sat in sats)), ("also flagged healthy", sum(sat["ok"] for sat in flagged_ok))),
        len(names) / len(sats), names))


def plane(summary):
    """A plane whose node or spacing is past its limit while a sister plane is within both."""
    def past(row):   # how many times its limit the worse of the two measures is
        return max(abs(row["offset"]) / row["offset_limit"], (row["gap"] or 0) / row["gap_limit"])

    planes = summary["planes"]
    if not any(past(row) <= 1 for row in planes.values()):
        return []   # every plane is past a limit: that is the system, not one plane out of step
    found = []
    for letter, row in planes.items():
        if past(row) <= 1:
            continue
        gap_worse = (row["gap"] or 0) / row["gap_limit"] >= abs(row["offset"]) / row["offset_limit"]
        value, limit = ((row["gap"], row["gap_limit"]) if gap_worse else (abs(row["offset"]), row["offset_limit"]))
        what = "spacing" if gap_worse else "node"
        found += _each("plane", summary["name"], [f"plane {letter}"], lambda names: _finding(
            "plane", summary["name"], f"P{names[0][1:]}'s {what} is past its limit; its sister planes are within theirs",
            f"{what} off by {value:.1f}° against a limit of {limit:g}°",
            ((f"{names[0]}, °", round(value, 1)), ("limit, °", limit)), past(row), names))
    return found


def odd(summary):
    """A satellite whose score is far under its system's median, by the system's own spread."""
    scored = [sat for sat in summary["sats"] if sat["score"] is not None]
    if len(scored) < ODD_NEEDS:
        return []
    middle = median(sat["score"] for sat in scored)
    spread = max(median(abs(sat["score"] - middle) for sat in scored), ODD_SPREAD_FLOOR)   # median absolute deviation
    floor = middle - ODD_SPREADS * spread
    low = sorted((sat for sat in scored if sat["score"] < floor), key=lambda sat: sat["score"])
    return _each("odd", summary["name"], [sat["name"] for sat in low], lambda names: _finding(
        "odd", summary["name"],
        f"{_names(names)} score{'s' if len(names) == 1 else ''} well under the rest of the system",
        f"lowest {min(sat['score'] for sat in low if sat['name'] in names):.0f} · the system's median is "
        f"{middle:.0f} · the line is {floor:.0f} ({ODD_SPREADS:g} spreads of {spread:.1f} under it)",
        (("system median", round(middle)), ("lowest", round(min(sat["score"] for sat in low if sat["name"] in names)))),
        (middle - min(sat["score"] for sat in low if sat["name"] in names)) / (ODD_SPREADS * spread), names))


FINDERS = {"silent": silent, "disagree": disagree, "plane": plane, "odd": odd}
assert list(FINDERS) == list(RULES)


def find(summaries):
    """(findings to list, findings explained). Listed: each rule's largest finding in RULES' order, then the rest by
    rule, largest first. Explained: by rule, largest first."""
    found = [finding for rule in RULES for summary in summaries for finding in FINDERS[rule](summary)]
    found.sort(key=lambda finding: (list(RULES).index(finding["rule"]), -finding["size"]))
    listed = [finding for finding in found if not finding["explained"]]
    first = {finding["rule"]: finding for finding in reversed(listed)}   # each rule's largest
    lead = [first[rule] for rule in RULES if rule in first]
    return (lead + [finding for finding in listed if finding not in lead],
            [finding for finding in found if finding["explained"]])
