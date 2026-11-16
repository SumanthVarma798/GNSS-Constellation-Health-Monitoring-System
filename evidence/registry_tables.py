"""The registry tables: how to read and write them.

The tables are plain text in registry/ so that every change shows up as a
line-by-line difference a person can review. See registry/README.md. Their
file names and columns are in evidence/settings.py.
"""
import csv
from datetime import date, timedelta

from evidence.settings import (REGISTRY_CONSTELLATIONS_FILE, REGISTRY_DASHBOARD_SATELLITES_FILE,
                               REGISTRY_DASHBOARD_SYSTEMS_FILE, REGISTRY_DIR, REGISTRY_DASHBOARD_TRACKED_SYSTEMS,
                               REGISTRY_SATELLITES_FILE, REGISTRY_SIGHTINGS_FILE, NEW_ON_DASHBOARD_DAYS,
                               REGISTRY_LEFT_OUT_FILE)


def read_table(name):
    """One table as a list of rows, each a dict keyed by column name."""
    with open(REGISTRY_DIR / name, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_table(name, columns, rows):
    """Write one table with Unix line endings, so the same rows give the same bytes."""
    with open(REGISTRY_DIR / name, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def constellation_names():
    """{'C': 'BeiDou', ...}: the first letter of an SVN to its constellation."""
    return {row["svn_letter"]: row["constellation"] for row in read_table(REGISTRY_CONSTELLATIONS_FILE)}


def dashboard_systems():
    """One row per dashboard page system, in the order the dashboard shows them."""
    return sorted(read_table(REGISTRY_DASHBOARD_SYSTEMS_FILE), key=lambda row: int(row["order"]))


def _system_row(page_name):
    """The dashboard_systems row for a page name, or None."""
    return next((row for row in dashboard_systems() if row["page_name"] == page_name), None)


def registry_name(page_name):
    """The registry's name for a dashboard page: BeiDou-3 and BeiDou-3 MEO are BeiDou; anything unknown is unchanged."""
    row = _system_row(page_name)
    return row["registry_name"] if row else page_name


def page_name(registry):
    """The dashboard's name for a registry constellation: BeiDou is BeiDou-3; anything unknown is unchanged."""
    row = next((r for r in dashboard_systems() if r["registry_name"] == registry), None)
    return row["page_name"] if row else registry


def blocks(page_name):
    """The block prefixes a page's satellites start with, or () when the page takes the whole constellation."""
    row = _system_row(page_name)
    return tuple(prefix for prefix in (row or {}).get("block_prefixes", "").split() if prefix)


def _tracked(constellation):
    """(dashboard name, registry row or None) for each satellite the dashboard tracks in one constellation, in display
    order; see _system_rows()."""
    return [(row["dashboard_name"], found) for row, found in _system_rows(constellation)]


def _membership(constellation):
    """(whether an SVN belongs to one dashboard system, {svn: registry row}). The constellation is read from the SVN's
    letter, so it is known even for a satellite the registry does not list. A satellite CelesTrak lists before
    the IGS file does is found in sightings.csv. A part page in dashboard_systems.csv takes its constellation's
    satellites of its blocks, which the system's other page then leaves out; a satellite the registry does not
    list has no block, so it stays with the system page."""
    registry = {row["svn"]: row for row in read_table(REGISTRY_SATELLITES_FILE) + read_table(REGISTRY_SIGHTINGS_FILE)}
    letters = constellation_names()
    rows = dashboard_systems()
    row = next((r for r in rows if r["page_name"] == constellation), None)
    if row is None:
        row = next((r for r in rows if r["registry_name"] == constellation), None)
    name = row["registry_name"] if row else constellation
    page = (row or {}).get("page_name")
    split_off = tuple(prefix for other in rows if other["registry_name"] == name and other["page_name"] != page
                      for prefix in blocks(other["page_name"]))
    own = blocks(page) if row and row["orbit_kind"] == "global" else ()

    def member(svn):
        found = registry.get(svn)
        held = (found or {}).get("block", "")
        if letters.get(svn[:1]) != name:
            return False
        return bool(found) and held.startswith(own) if own else not (held and held.startswith(split_off))

    return member, registry


def _system_rows(constellation):
    """(dashboard_satellites.csv row, registry row or None) for each satellite the dashboard tracks in
    one constellation, in display order; see _membership()."""
    member, registry = _membership(constellation)
    return [(row, registry.get(row["svn"])) for row in read_table(REGISTRY_DASHBOARD_SATELLITES_FILE)
            if member(row["svn"])]


def left_out(constellation):
    """[(name, reason, source)] for the satellites with a signal ID today that one system's page leaves out on purpose."""
    member, _ = _membership(constellation)
    return [(row["name"], row["reason"], row["source"]) for row in read_table(REGISTRY_LEFT_OUT_FILE)
            if member(row["svn"])]


def left_out_notice(constellation):
    """The page's line on satellites left out on purpose, or ""."""
    named = "; ".join(f"{name}: {reason}" for name, reason, _ in left_out(constellation))
    return f"Broadcasting but not shown, on purpose: {named}." if named else ""


def dashboard_satellites(constellation):
    """{'IRNSS-1B': 39635, ...}: the dashboard's name for each satellite it tracks in one
    constellation, to its catalogue number, in display order.

    A person chooses which satellites are tracked and what they are called. The
    catalogue number is looked up in the registry by physical-satellite number.
    A tracked satellite the registry does not list is left out here and named by
    dashboard_satellites_not_in_registry(): the two tables are approved by a person
    at different times, so the dashboard must run while one is behind the other.
    """
    return {name: int(found["catalogue_no"]) for name, found in _tracked(constellation) if found}


def dashboard_registry_rows(constellation):
    """{dashboard name: registry row} for the tracked satellites of one constellation the registry lists."""
    return {name: found for name, found in _tracked(constellation) if found}


def dashboard_satellites_not_in_registry(constellation):
    """Names of tracked satellites the registry does not list. Normally none; a test
    keeps it so at the point of approval. The dashboard shows these in a notice."""
    return [name for name, found in _tracked(constellation) if not found]


def generation_satellites(constellation, block_start):
    """Registry rows of one constellation whose block starts with block_start, in registry order."""
    return [row for row in read_table(REGISTRY_SATELLITES_FILE)
            if row["constellation"] == constellation and row["block"].startswith(block_start)]


def tracked_list_in_step(satellites, tracked, names, today):
    """dashboard_satellites.csv rows with GPS/GLONASS/Galileo kept in step with today's signal IDs.

    `satellites` and `tracked` are table rows as read_table() returns; `names` maps SVN to a dashboard
    name for new rows. Systems outside REGISTRY_DASHBOARD_TRACKED_SYSTEMS are left exactly as they are.
    """
    target = set(REGISTRY_DASHBOARD_TRACKED_SYSTEMS)
    by_svn = {row["svn"]: row for row in satellites}
    letters = {row["svn"][0]: row["constellation"] for row in satellites if row["constellation"] in target and row["svn"]}
    wanted = {system: [row["svn"] for row in satellites if row["constellation"] == system and row["signal_id_now"]]
              for system in REGISTRY_DASHBOARD_TRACKED_SYSTEMS}
    wanted_sets = {system: set(svns) for system, svns in wanted.items()}
    kept, seen = [], set()
    for row in tracked:
        system = by_svn.get(row["svn"], {}).get("constellation") or letters.get(row["svn"][:1], "")
        if system in target:
            if row["svn"] in wanted_sets[system]:
                kept.append(row)
                seen.add(row["svn"])
            continue
        kept.append(row)
    updated = list(kept)
    for system in REGISTRY_DASHBOARD_TRACKED_SYSTEMS:
        missing = [svn for svn in wanted[system] if svn not in seen]
        if not missing:
            continue
        insert_at = max((i for i, row in enumerate(updated)
                         if (by_svn.get(row["svn"], {}).get("constellation") or letters.get(row["svn"][:1], "")) == system),
                        default=len(updated) - 1)   # a system with no rows yet goes last
        added = [{"svn": svn, "dashboard_name": names.get(svn) or svn, "added": today} for svn in missing]
        updated[insert_at + 1:insert_at + 1] = added
    return updated


def recently_added(constellation, today, days=NEW_ON_DASHBOARD_DAYS):
    """[(dashboard name, added date)] for tracked satellites recently added in one constellation.

    Rows with a blank or unreadable date are not counted as recently added. A part page counts only its own
    satellites, as _tracked() does.
    """
    window_start = today - timedelta(days=days)
    fresh = []
    for row, _ in _system_rows(constellation):
        try:
            added = date.fromisoformat((row.get("added") or "").strip())
        except ValueError:
            continue
        if window_start <= added <= today:
            fresh.append((row["dashboard_name"], added.isoformat()))
    return fresh


def new_on_dashboard(constellation, today):
    """The page's notice for satellites recently added to the tracked list, or ""."""
    fresh = recently_added(constellation, today)
    named = "; ".join(f"{name} (added {(day := date.fromisoformat(added)).day} {day:%b %Y} after an approved registry proposal)"
                      for name, added in fresh)
    return f"New on the dashboard: {named}." if fresh else ""
