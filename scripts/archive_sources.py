"""Fetch archived sources and keep a raw copy of whatever changed.

    python scripts/archive_sources.py --archive FOLDER                    # every group
    python scripts/archive_sources.py --archive FOLDER --group documents  # one group

Writes only when a source's content or availability changed. Tries every
source even if one fails, then exits with an error so the failure is noticed.
Every run, whatever happens, adds one line to the archive's run log, runs/archive.csv.
Waits between two requests to the same site, as long as MIN_GAP_BETWEEN_DOWNLOADS
in evidence/settings.py says. A site that refused us, or did not answer, is left
alone until its back-off has passed (limits.csv in the archive): that is shown,
but is not a new failure.
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.archive import (FetchFailed, log_run, note_answer, pacer, read_limits, record, waiting_until,
                              write_limits)
from evidence.sources import ARCHIVED_SOURCES, archived_addresses

RUN_LOG = "archive"  # runs/archive.csv in the archive folder


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="folder holding objects/ and versions.csv")
    parser.add_argument("--group", choices=sorted(ARCHIVED_SOURCES), help="fetch only this group (default: all)")
    args = parser.parse_args()

    started, changed, failures, waiting = utc_now(), [], 0, 0
    addresses = archived_addresses(args.group)
    result = "stopped early"  # replaced below unless something unexpected ends the run
    paced_fetch, limits = pacer(), read_limits(args.archive)
    try:
        if not addresses:
            print(f"The group '{args.group}' has no sources yet. Nothing to fetch.")
        for address in addresses:
            now = datetime.datetime.now(datetime.timezone.utc)
            until = waiting_until(limits, address, now)
            if until:  # it refused us lately: not a new failure, and not asked again yet
                waiting += 1
                print(f"waiting    {address} (refused lately; asked again after {until:%Y-%m-%d %H:%M} UTC)")
                continue
            try:
                reply = paced_fetch(address)
            except FetchFailed as error:
                note_answer(limits, address, "no answer", now)
                failures += 1
                print(f"FAILED     {error}")
                continue
            note_answer(limits, address, reply[0], now)
            try:
                row = record(args.archive, address, utc_now(), *reply)
            except FetchFailed as error:
                failures += 1
                print(f"FAILED     {error}")
                continue
            print(f"{'changed  ' if row else 'unchanged'}  {address}")
            if row:
                changed.append(address)
        result = f"failed: {failures} of {len(addresses)} sources" if failures else "ok"
        result += f"; {waiting} waiting out a refusal" if waiting else ""
    finally:
        write_limits(args.archive, limits)
        log_run(args.archive, RUN_LOG, f"archive {args.group or 'all'}", started, utc_now(), result,
                " ".join(changed) or "nothing")
    if failures:
        sys.exit(f"{failures} of {len(addresses)} sources could not be fetched.")


if __name__ == "__main__":
    main()
