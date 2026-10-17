"""The registry tables: how to read and write them.

The tables are plain text in registry/ so that every change shows up as a
line-by-line difference a person can review. See registry/README.md. Their
file names and columns are in evidence/settings.py.
"""
import csv

from evidence.settings import (REGISTRY_CONSTELLATIONS_FILE, REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_DIR,
                               REGISTRY_SATELLITES_FILE)


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


def _tracked(constellation):
    """(dashboard name, registry row or None) for each satellite the dashboard tracks in
    one constellation, in display order. The constellation is read from the SVN's letter,
    so it is known even for a satellite the registry does not list."""
    registry = {row["svn"]: row for row in read_table(REGISTRY_SATELLITES_FILE)}
    letters = constellation_names()
    return [(row["dashboard_name"], registry.get(row["svn"])) for row in read_table(REGISTRY_DASHBOARD_SATELLITES_FILE)
            if letters.get(row["svn"][:1]) == constellation]


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
