"""Reading the General Catalog of Artificial Space Objects (GCAT), and joining it to the registry.

GCAT is kept by Jonathan McDowell and released under the Creative Commons
CC-BY licence. Anything shown from it must carry the citation in
evidence/settings.py (GCAT_CITATION).

Two of its files are used. The object catalogue has one row per catalogued
object: owner, state, orbit. The payload catalogue has one row per payload:
when regular operations ended, and whether the mission failed early.
"""
from evidence.settings import GCAT_OBJECT_COLUMNS, GCAT_PAYLOAD_COLUMNS


def read_rows(text, needed):
    """Each data line as a dict keyed by column name. The file is tab-separated;
    its first line names the columns and every other line starting with '#' is a comment."""
    lines = text.split("\n")
    columns = lines[0].lstrip("#").split("\t")
    missing = [column for column in needed if column not in columns]
    if missing:
        # A changed layout is for a person to look at, not to guess around.
        raise ValueError(f"The catalogue file has no column named {', '.join(missing)}: its layout may have changed.")
    return [dict(zip(columns, (field.strip() for field in line.split("\t"))))
            for line in lines[1:] if line and not line.startswith("#")]


def catalogue_rows(satellites, objects_text, payloads_text):
    """One row per registry satellite, in registry order: what the catalogue says about it.

    Satellites are matched by catalogue number. One the catalogue does not list
    yet still gets a row, with blanks: the two sources are updated by different
    people at different times, so a gap is normal and is shown, not hidden.
    """
    objects = {int(row["Satcat"]): row for row in read_rows(objects_text, ["JCAT", "Satcat", *GCAT_OBJECT_COLUMNS.values()])
               if row["Satcat"].isdigit()}
    payloads = {row["JCAT"]: row for row in read_rows(payloads_text, ["JCAT", *GCAT_PAYLOAD_COLUMNS.values()])}
    rows = []
    for satellite in satellites:
        found = objects.get(int(satellite["catalogue_no"]), {})
        payload = payloads.get(found.get("JCAT"), {})
        rows.append([satellite["svn"],
                     *(found.get(column, "") for column in GCAT_OBJECT_COLUMNS.values()),
                     *(payload.get(column, "") for column in GCAT_PAYLOAD_COLUMNS.values())])
    return rows
