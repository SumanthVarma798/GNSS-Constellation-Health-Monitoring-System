"""Fetch archived sources and keep a raw copy of whatever changed.

    python scripts/archive_sources.py --archive FOLDER                    # every group
    python scripts/archive_sources.py --archive FOLDER --group documents  # one group

Writes only when a source's content or availability changed. Tries every
source even if one fails, then exits with an error so the failure is noticed.
Every run, whatever happens, adds one line to the archive's run log, runs/archive.csv.
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.archive import FetchFailed, fetch, log_run, record
from evidence.sources import ARCHIVED_SOURCES, archived_addresses

RUN_LOG = "archive"  # runs/archive.csv in the archive folder


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="folder holding objects/ and versions.csv")
    parser.add_argument("--group", choices=sorted(ARCHIVED_SOURCES), help="fetch only this group (default: all)")
    args = parser.parse_args()

    started, changed, failures = utc_now(), [], 0
    addresses = archived_addresses(args.group)
    result = "stopped early"  # replaced below unless something unexpected ends the run
    try:
        if not addresses:
            print(f"The group '{args.group}' has no sources yet. Nothing to fetch.")
        for address in addresses:
            try:
                row = record(args.archive, address, utc_now(), *fetch(address))
            except FetchFailed as error:
                failures += 1
                print(f"FAILED     {error}")
                continue
            print(f"{'changed  ' if row else 'unchanged'}  {address}")
            if row:
                changed.append(address)
        result = f"failed: {failures} of {len(addresses)} sources" if failures else "ok"
    finally:
        log_run(args.archive, RUN_LOG, f"archive {args.group or 'all'}", started, utc_now(), result,
                " ".join(changed) or "nothing")
    if failures:
        sys.exit(f"{failures} of {len(addresses)} sources could not be fetched.")


if __name__ == "__main__":
    main()
