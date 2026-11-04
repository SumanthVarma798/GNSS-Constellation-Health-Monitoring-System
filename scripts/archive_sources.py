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

from evidence.archive import (FetchFailed, log_run, note_answer, pacer, read_limits, record, thin, waiting_until,
                              write_limits)
from evidence import x_reader
from evidence.settings import ARCHIVE_THIN_GROUPS
from evidence.sources import ARCHIVED_SOURCES, PROVISIONAL_GROUPS, archived_addresses

RUN_LOG = "archive"  # runs/archive.csv in the archive folder


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="folder holding objects/ and versions.csv")
    parser.add_argument("--group", choices=sorted(ARCHIVED_SOURCES), help="fetch only this group (default: all)")
    args = parser.parse_args()

    started, changed, thinned, failures, graded_failures, waiting = utc_now(), [], [], 0, 0, 0
    addresses = archived_addresses(args.group)
    result = "stopped early"  # replaced below unless something unexpected ends the run
    paced_fetch, limits = pacer(), read_limits(args.archive)
    x_addresses = set(ARCHIVED_SOURCES["x"])   # read through the X reader, not fetched from x.com
    if args.group:
        # A named group is either all graded or all provisional, so one flag covers every address in it.
        provisional_addresses, graded_group = set(), args.group not in PROVISIONAL_GROUPS
    else:
        # An "all" run can hold both: classify each address against the provisional news and social groups.
        provisional_addresses = {address for name in PROVISIONAL_GROUPS for address in ARCHIVED_SOURCES[name]}
        graded_group = None
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
            graded = graded_group if graded_group is not None else address not in provisional_addresses
            try:
                reply = x_reader.fetch(address) if address in x_addresses else paced_fetch(address)
            except FetchFailed as error:
                note_answer(limits, address, "no answer", now)
                failures += 1
                graded_failures += graded
                print(f"FAILED     {error}")
                continue
            note_answer(limits, address, reply[0], now)
            try:
                row = record(args.archive, address, utc_now(), *reply)
            except FetchFailed as error:
                failures += 1
                graded_failures += graded
                print(f"FAILED     {error}")
                continue
            print(f"{'changed  ' if row else 'unchanged'}  {address}")
            if row:
                changed.append(address)
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            thinned = thin(args.archive, [address for group in ARCHIVE_THIN_GROUPS if args.group in (None, group)
                                          for address in archived_addresses(group)], now)
        except Exception as error:  # thinning must not fail a run
            print(f"WARNING    thinning failed: {error}")
        for row in thinned:
            print(f"thinned    {row['sha256']}  {row['address']}")
        result = f"failed: {failures} of {len(addresses)} sources" if failures else "ok"
        result += f"; {waiting} waiting out a refusal" if waiting else ""
    finally:
        write_limits(args.archive, limits)
        log_run(args.archive, RUN_LOG, f"archive {args.group or 'all'}", started, utc_now(), result,
                " ".join(changed + ([f"thinned {len(thinned)} old {'copy' if len(thinned) == 1 else 'copies'}"]
                                    if thinned else [])) or "nothing")
    attempted = len(addresses) - waiting
    if failures and (graded_failures or (attempted and failures == attempted)):
        sys.exit(f"{failures} of {len(addresses)} sources could not be fetched.")


if __name__ == "__main__":
    main()
