"""Build the satellite registry tables from the IGS satellite metadata file.

    python scripts/build_registry.py                      # download the IGS file
    python scripts/build_registry.py --metadata FILE.snx  # use a local copy
    python scripts/build_registry.py --archive FOLDER     # use the newest archived copy
    python scripts/build_registry.py --report CHANGES.md  # also describe what changed

Writes registry/satellites.csv (one row per physical satellite) and
registry/signal_ids.csv (one row per satellite per signal-ID period).
The output has a fixed order and no build date, so `git diff registry/`
is the change report: no difference means nothing changed at the source.
"""
import argparse
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data import celestrak
from evidence.archive import latest_version, object_path
from evidence.igs_metadata import OPEN_END, block_rows, read_metadata, sinex_time
from evidence.registry_changes import change_report, describe_satellite_changes, describe_signal_id_changes
from evidence.registry_tables import constellation_names, read_table, tracked_list_in_step, write_table
from evidence.sources import IGS_SATELLITE_METADATA_URL
from evidence.settings import (REGISTRY_CONSTELLATIONS_FILE, REGISTRY_DIR, REGISTRY_SATELLITE_COLUMNS,
                               REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_DASHBOARD_TRACKED_SYSTEMS,
                               REGISTRY_SATELLITES_FILE, REGISTRY_SIGNAL_ID_COLUMNS, REGISTRY_SIGNAL_IDS_FILE)

BRACKETED = re.compile(r"\s*\[[^\]]*]\s*")


def build_tables(text):
    """Return (satellites, signal_ids): lists of rows, sorted, without headers."""
    signal_ids = []
    for line in block_rows(text, "PRN"):
        svn, start, end, signal_id, *note = line.split(None, 4)
        signal_ids.append([svn, signal_id, sinex_time(start), sinex_time(end), note[0].strip() if note else ""])
    signal_ids.sort(key=lambda row: (row[0], row[2]))
    signal_id_now = {row[0]: row[1] for row in signal_ids if not row[3]}

    # PLANE is read by column position: the slot column can be blank.
    place_now = {line[1:5]: (line[36:37].strip(), line[38:44].strip())
                 for line in block_rows(text, "PLANE") if line[21:35] == OPEN_END}

    constellations = constellation_names()
    satellites = []
    for line in block_rows(text, "IDENTIFIER"):
        svn, cospar, catalogue_no, block, *note = line.split(None, 4)
        if svn[0] not in constellations:
            # A system we have not seen before is for a person to look at, not to guess.
            raise ValueError(f"{svn}: system letter {svn[0]!r} is not in registry/{REGISTRY_CONSTELLATIONS_FILE}")
        plane, slot = place_now.get(svn, ("", ""))
        satellites.append([svn, constellations[svn[0]], block, cospar, catalogue_no,
                           signal_id_now.get(svn, ""), plane, slot, note[0].strip() if note else ""])
    satellites.sort()
    return satellites, signal_ids


def dashboard_name_for_new_satellite(satellite, catalogue_row):
    """(name, source words) for a satellite newly added to dashboard_satellites.csv."""
    if catalogue_row and catalogue_row.get("OBJECT_NAME"):
        named = BRACKETED.sub("", str(catalogue_row["OBJECT_NAME"])).strip()
        if named:
            return named, "CelesTrak's catalogue"
    if ";" in satellite["note"]:
        named = satellite["note"].split(";", 1)[1].strip()
        if named:
            return named, "the registry note"
    return satellite["svn"], "its SVN"


def dashboard_updates(before, satellites):
    """(updated rows, report lines): keep tracked satellites in step with signal IDs for the three MEO systems."""
    by_svn = {row["svn"]: row for row in satellites}
    had = {row["svn"] for row in before}
    wanted = {row["svn"] for row in satellites
              if row["constellation"] in REGISTRY_DASHBOARD_TRACKED_SYSTEMS and row["signal_id_now"]}
    new_svns = [row["svn"] for row in satellites if row["svn"] in wanted - had]
    names, source_words = {}, {}
    for svn in new_svns:
        satellite = by_svn[svn]
        entry, failed = None, False
        if satellite["catalogue_no"].isdigit():
            try:
                entry = celestrak.catalogue_entry(int(satellite["catalogue_no"]))
            except (requests.RequestException, ValueError, KeyError, TypeError):
                failed = True
        name, source = dashboard_name_for_new_satellite(satellite, entry)
        if failed and source == "the registry note":
            source = "the registry note (CelesTrak could not be read)"
        elif failed and source == "its SVN":
            source = "its SVN (CelesTrak could not be read)"
        names[svn], source_words[svn] = name, source
    updated = tracked_list_in_step(satellites, before, names)
    now = {row["svn"] for row in updated}
    lines = [f"The dashboard will track {svn} as {names.get(svn, svn)} (name from {source_words.get(svn, 'its SVN')})."
             for svn in [row["svn"] for row in updated if row["svn"] in now - had]]
    lines += [f"The dashboard will stop tracking {svn}: it has no signal ID today."
              for svn in [row["svn"] for row in before if row["svn"] in had - now]]
    return updated, lines


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--metadata", help="local copy of the IGS file (default: download it)")
    source.add_argument("--archive", help="archive folder: build from its newest copy of the IGS file")
    parser.add_argument("--report", help="write a plain-language description of what changed to this file")
    args = parser.parse_args()

    copy_used = ""
    if args.archive:
        kept = latest_version(args.archive, IGS_SATELLITE_METADATA_URL)
        if not kept or not kept["sha256"]:
            sys.exit("The archive holds no current copy of the IGS file (never fetched, or gone). Nothing written.")
        args.metadata = object_path(args.archive, kept["sha256"])
        copy_used = (f"The copy used is in the private archive: fetched {kept['fetched_at']}, "
                     f"SHA-256 `{kept['sha256']}`.")
    text = read_metadata(args.metadata)
    satellites, signal_ids = build_tables(text)
    if not satellites or not signal_ids:
        sys.exit("No satellites or no signal IDs found: the file layout may have changed. Nothing written.")
    before = (read_table(REGISTRY_SATELLITES_FILE), read_table(REGISTRY_SIGNAL_IDS_FILE),
              read_table(REGISTRY_DASHBOARD_SATELLITES_FILE))
    write_table(REGISTRY_SATELLITES_FILE, REGISTRY_SATELLITE_COLUMNS, satellites)
    write_table(REGISTRY_SIGNAL_IDS_FILE, REGISTRY_SIGNAL_ID_COLUMNS, signal_ids)
    dashboard_rows, dashboard_lines = dashboard_updates(before[2], read_table(REGISTRY_SATELLITES_FILE))
    write_table(REGISTRY_DASHBOARD_SATELLITES_FILE, ("svn", "dashboard_name"),
                [[row["svn"], row["dashboard_name"]] for row in dashboard_rows])
    print(f"{len(satellites)} satellites, {len(signal_ids)} signal-ID periods written to {REGISTRY_DIR}")
    if args.report:
        after = (read_table(REGISTRY_SATELLITES_FILE), read_table(REGISTRY_SIGNAL_IDS_FILE),
                 read_table(REGISTRY_DASHBOARD_SATELLITES_FILE))
        Path(args.report).write_text(change_report(text.splitlines()[0].strip(),
                                                   describe_satellite_changes(before[0], after[0]),
                                                   describe_signal_id_changes(before[1], after[1]),
                                                   copy_used, dashboard_lines))


if __name__ == "__main__":
    main()
