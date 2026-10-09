"""The registry tables: how to read and write them.

The tables are plain text in registry/ so that every change shows up as a
line-by-line difference a person can review. See registry/README.md. Their
file names and columns are in evidence/settings.py.
"""
import csv

from evidence.settings import REGISTRY_CONSTELLATIONS_FILE, REGISTRY_DIR


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
