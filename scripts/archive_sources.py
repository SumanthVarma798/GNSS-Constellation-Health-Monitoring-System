"""Fetch every archived source and keep a raw copy of whatever changed.

    python scripts/archive_sources.py --archive PATH_TO_ARCHIVE_FOLDER

Writes only when a source's content or availability changed. Tries every
source even if one fails, then exits with an error so the failure is noticed.
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.archive import FetchFailed, fetch, record
from evidence.sources import ARCHIVED_ADDRESSES


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="folder holding objects/ and versions.csv")
    args = parser.parse_args()

    failures = 0
    for address in ARCHIVED_ADDRESSES:
        fetched_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            row = record(args.archive, address, fetched_at, *fetch(address))
        except FetchFailed as error:
            failures += 1
            print(f"FAILED     {error}")
            continue
        print(f"{'changed  ' if row else 'unchanged'}  {address}")
    if failures:
        sys.exit(f"{failures} of {len(ARCHIVED_ADDRESSES)} sources could not be fetched.")


if __name__ == "__main__":
    main()
