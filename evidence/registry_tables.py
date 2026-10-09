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


def dashboard_satellites(constellation):
    """{'IRNSS-1B': 39635, ...}: the dashboard's name for each satellite it tracks in one
    constellation, to its catalogue number, in display order.

    A person chooses which satellites are tracked and what they are called. The
    catalogue number is looked up in the registry by physical-satellite number.
    """
    registry = {row["svn"]: row for row in read_table(REGISTRY_SATELLITES_FILE)}
    tracked = {}
    for row in read_table(REGISTRY_DASHBOARD_SATELLITES_FILE):
        if row["svn"] not in registry:
            # Dropping a tracked satellite silently would be worse than stopping.
            raise ValueError(f"{row['dashboard_name']}: {row['svn']} is in registry/"
                             f"{REGISTRY_DASHBOARD_SATELLITES_FILE} but not in registry/{REGISTRY_SATELLITES_FILE}")
        if registry[row["svn"]]["constellation"] == constellation:
            tracked[row["dashboard_name"]] = int(registry[row["svn"]]["catalogue_no"])
    return tracked
