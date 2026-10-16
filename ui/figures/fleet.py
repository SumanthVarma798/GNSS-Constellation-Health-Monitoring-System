"""Every satellite of a constellation's generation, tracked or not: its name, its plane group and its orbit in words.

The rows come from the registry (config.config.GENERATIONS says which). Plane and slot are as
the registry gives them; a numbered plane is a MEO plane, named after its slots' letter.
"""
from config.config import MEO_KIND, PLANE_KINDS
from evidence.master_map import display_name

OTHER_GROUP = "Other"


def plane_letters(registry_rows):
    """{'1': 'A', ...}: each numbered plane to the letter its slots carry (slot 'A-4' is in plane A)."""
    return {row["plane"]: row["slot"][0] for row in registry_rows if row["plane"].isdigit() and "-" in row["slot"]}


def orbit_words(row, letters):
    """'MEO · plane A, slot A-4', 'GEO · slot 140E', ... from the registry; '' when it gives neither."""
    plane, slot = row["plane"], row["slot"]
    kind = MEO_KIND if plane.isdigit() else PLANE_KINDS.get(plane, "")
    where = [f"plane {letters.get(plane, plane)}"] if plane.isdigit() else []
    where += [f"slot {slot}"] if slot else []
    return " · ".join(part for part in (kind, ", ".join(where)) if part)


def group_of(row, letters):
    """The chip group: 'GEO', 'IGSO', 'Plane A', or OTHER_GROUP when the registry gives no plane we name."""
    plane = row["plane"]
    return f"Plane {letters.get(plane, plane)}" if plane.isdigit() else PLANE_KINDS.get(plane, OTHER_GROUP)


def fleet_rows(registry_rows, tables):
    """One entry per registry row, in registry order: norad, name (the dashboard's own for a tracked one), group, orbit.

    tables is ui.pages_data.load_master_map_data(), for the names.
    """
    letters = plane_letters(registry_rows)
    return [{"norad": int(row["catalogue_no"]),
             "name": display_name(row["svn"], tables["satellites"], tables["catalogue"], tables["tracked"]),
             "group": group_of(row, letters), "orbit": orbit_words(row, letters)} for row in registry_rows]
