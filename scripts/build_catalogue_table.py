"""Build registry/catalogue.csv: owner and status of each registry satellite, as the
General Catalog of Artificial Space Objects (GCAT) states them.

    python scripts/build_catalogue_table.py --archive FOLDER                # newest archived copies
    python scripts/build_catalogue_table.py --objects A.tsv --payloads B.tsv  # local copies
    python scripts/build_catalogue_table.py ... --report DISAGREEMENTS.md   # also say where it and the IGS file disagree

Like the other registry tables, the output has a fixed order and no build
date, so `git diff registry/` shows exactly what the catalogue changed.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.archive import latest_version, object_path
from evidence.catalogue_check import disagreement_report, disagreements
from evidence.gcat import catalogue_rows
from evidence.registry_tables import read_table, write_table
from evidence.settings import REGISTRY_CATALOGUE_COLUMNS, REGISTRY_CATALOGUE_FILE, REGISTRY_SATELLITES_FILE
from evidence.sources import GCAT_OBJECTS_URL, GCAT_PAYLOADS_URL


def archived_copy(archive, address):
    """(path, sentence saying which copy) for the newest archived copy of one address."""
    kept = latest_version(archive, address)
    if not kept or not kept["sha256"]:
        # The fetch job and this build run separately. Until the first fetch lands, there is nothing to build from.
        sys.exit(f"The archive holds no current copy of {address} (never fetched, or gone). Nothing written.")
    return object_path(archive, kept["sha256"]), f"- {address}, fetched {kept['fetched_at']}, SHA-256 `{kept['sha256']}`"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", help="archive folder: build from its newest copies of the two catalogue files")
    parser.add_argument("--objects", help="local copy of the object catalogue (satcat.tsv)")
    parser.add_argument("--payloads", help="local copy of the payload catalogue (psatcat.tsv)")
    parser.add_argument("--report", help="write the disagreements with the IGS file to this file")
    args = parser.parse_args()

    copies_used = ""
    if args.archive:
        (args.objects, first), (args.payloads, second) = (archived_copy(args.archive, address)
                                                          for address in (GCAT_OBJECTS_URL, GCAT_PAYLOADS_URL))
        copies_used = f"Copies in the private archive:\n\n{first}\n{second}"
    if not (args.objects and args.payloads):
        parser.error("give --archive, or both --objects and --payloads")

    satellites = read_table(REGISTRY_SATELLITES_FILE)
    rows = catalogue_rows(satellites, *(Path(path).read_text(encoding="utf-8") for path in (args.objects, args.payloads)))
    matched = sum(1 for row in rows if any(row[1:]))
    if not matched:
        sys.exit("No registry satellite was found in the catalogue: its layout may have changed. Nothing written.")
    write_table(REGISTRY_CATALOGUE_FILE, REGISTRY_CATALOGUE_COLUMNS, rows)
    print(f"{matched} of {len(rows)} registry satellites found in the catalogue; written to registry/{REGISTRY_CATALOGUE_FILE}")
    if args.report:
        found = disagreements(satellites, read_table(REGISTRY_CATALOGUE_FILE))
        Path(args.report).write_text(disagreement_report(found, copies_used))


if __name__ == "__main__":
    main()
