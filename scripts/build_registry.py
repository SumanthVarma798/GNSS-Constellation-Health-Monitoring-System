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
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data import celestrak
from evidence.confidence import read_source_grades
from evidence.archive import latest_version, object_path
from evidence.igs_metadata import OPEN_END, block_rows, read_metadata, sinex_time
from evidence import news
from evidence.registry_changes import (change_report, describe_satellite_changes, describe_signal_id_changes,
                                      registry_findings, BRACKETED, signal_row_tuple)
from evidence.registry_tables import constellation_names, read_table, tracked_list_in_step, write_table
from evidence.sources import IGS_SATELLITE_METADATA_URL
from evidence.settings import (REGISTRY_CONSTELLATIONS_FILE, REGISTRY_DIR, REGISTRY_SATELLITE_COLUMNS,
                               REGISTRY_DASHBOARD_SATELLITE_COLUMNS,
                               REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_DASHBOARD_TRACKED_SYSTEMS,
                               REGISTRY_SATELLITES_FILE, REGISTRY_SIGNAL_ID_COLUMNS, REGISTRY_SIGNAL_IDS_FILE,
                               SOURCE_CANDIDATES_FILE)


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


def dashboard_updates(before, satellites, today, celestrak_reads=None):
    """(updated rows, report lines, detail-by-svn, reads): keep dashboard tracking in step; new rows are added `today`."""
    by_svn = {row["svn"]: row for row in satellites}
    had = {row["svn"] for row in before}
    wanted = {row["svn"] for row in satellites
              if row["constellation"] in REGISTRY_DASHBOARD_TRACKED_SYSTEMS and row["signal_id_now"]}
    new_svns = [row["svn"] for row in satellites if row["svn"] in wanted - had]
    reads = dict(celestrak_reads or {})
    names, source_words = {}, {}
    for svn in new_svns:
        satellite = by_svn[svn]
        read = reads.get(svn)
        if read is None:
            read = celestrak_read(satellite.get("catalogue_no", ""))
            reads[svn] = read
        entry = read.get("catalogue_entry")
        failed = read.get("checked") and read.get("catalogue_status") == "error"
        name, source = dashboard_name_for_new_satellite(satellite, entry)
        if failed and source == "the registry note":
            source = "the registry note (CelesTrak could not be read)"
        elif failed and source == "its SVN":
            source = "its SVN (CelesTrak could not be read)"
        names[svn], source_words[svn] = name, source
    updated = tracked_list_in_step(satellites, before, names, today)
    now = {row["svn"] for row in updated}
    lines = [f"The dashboard will track {svn} as {names.get(svn, svn)} (name from {source_words.get(svn, 'its SVN')})."
             for svn in [row["svn"] for row in updated if row["svn"] in now - had]]
    lines += [f"The dashboard will stop tracking {svn}: it has no signal ID today."
              for svn in [row["svn"] for row in before if row["svn"] in had - now]]
    details = {svn: f"Approving also adds it to the dashboard as {names.get(svn, svn)}."
               for svn in [row["svn"] for row in updated if row["svn"] in now - had]}
    details.update({svn: "Approving also stops the dashboard tracking it: it has no signal ID today."
                    for svn in [row["svn"] for row in before if row["svn"] in had - now]})
    return updated, lines, details, reads


def metadata_lines(text):
    """({svn: raw IDENTIFIER line}, {(svn, signal row): raw PRN line}) from the IGS text."""
    identifiers, prn_lines = {}, {}
    for line in block_rows(text, "IDENTIFIER"):
        identifiers[line.split(None, 1)[0]] = line.strip()
    for line in block_rows(text, "PRN"):
        svn, start, end, signal_id, *note = line.split(None, 4)
        row = signal_row_tuple({"svn": svn, "signal_id": signal_id, "valid_from": sinex_time(start),
                                "valid_to": sinex_time(end), "note": note[0].strip() if note else ""})
        prn_lines[row] = line.strip()
    return identifiers, prn_lines


def new_prn_lines(before_signal_ids, after_signal_ids, prn_lines):
    """{svn: [raw PRN line, ...]} for signal-ID rows that are new in after_signal_ids."""
    old, new = ({signal_row_tuple(row) for row in rows} for rows in (before_signal_ids, after_signal_ids))
    by_svn = {}
    for row in sorted(new - old):
        if row in prn_lines:
            by_svn.setdefault(row[0], []).append(prn_lines[row])
    return by_svn


def celestrak_read(catalogue_no):
    """One satellite's CelesTrak catalogue and orbit read, with non-fatal read status."""
    read = {"checked": False, "catalogue_status": "none", "catalogue_entry": None,
            "orbit_status": "none", "orbit_row": None}
    if not str(catalogue_no).isdigit():
        return read
    read["checked"] = True
    catnr = int(catalogue_no)
    try:
        read["catalogue_entry"] = celestrak.catalogue_entry(catnr)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        read["catalogue_status"] = "error"
    else:
        read["catalogue_status"] = "ok" if read["catalogue_entry"] else "none"
    try:
        rows = celestrak._get(CATNR=catnr, empty_text="No GP data found")
    except (requests.RequestException, ValueError, KeyError, TypeError):
        read["orbit_status"] = "error"
    else:
        read["orbit_status"] = "ok" if rows else "none"
        read["orbit_row"] = rows[0] if rows else None
    return read


def read_source_candidates():
    """Candidate-source rows from evidence/source_candidates.csv."""
    with open(SOURCE_CANDIDATES_FILE, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def findings_news(archive):
    """(news items, error words) for findings; reading errors are reported, never fatal."""
    if not archive:
        return [], ""
    try:
        items, unreadable = news.collected_items(archive)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [], f"News could not be read from the archive: {error}"
    if unreadable:
        return items, f"News: {len(unreadable)} archived feed copies could not be read, so their items are left out."
    return items, ""


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
    after_satellites, after_signal_ids = read_table(REGISTRY_SATELLITES_FILE), read_table(REGISTRY_SIGNAL_IDS_FILE)
    today = datetime.now(timezone.utc).date()
    dashboard_rows, dashboard_lines, dashboard_details, celestrak_reads = dashboard_updates(before[2], after_satellites,
                                                                                            today.isoformat())
    write_table(REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_DASHBOARD_SATELLITE_COLUMNS,
                [[row["svn"], row["dashboard_name"], row.get("added", "")] for row in dashboard_rows])
    print(f"{len(satellites)} satellites, {len(signal_ids)} signal-ID periods written to {REGISTRY_DIR}")
    if args.report:
        identifier_lines, prn_lines = metadata_lines(text)
        news_items, news_error = findings_news(args.archive)
        findings = registry_findings(before[0], after_satellites, before[1], after_signal_ids, dashboard_details,
                                     identifier_lines, new_prn_lines(before[1], after_signal_ids, prn_lines),
                                     celestrak_reads, today, news_items, read_source_grades(), read_source_candidates())
        if news_error:
            copy_used = f"{copy_used}\n\n{news_error}".strip() if copy_used else news_error
        Path(args.report).write_text(change_report(text.splitlines()[0].strip(),
                                                   describe_satellite_changes(before[0], after_satellites),
                                                   describe_signal_id_changes(before[1], after_signal_ids),
                                                   copy_used, dashboard_lines, findings=findings))


if __name__ == "__main__":
    main()
