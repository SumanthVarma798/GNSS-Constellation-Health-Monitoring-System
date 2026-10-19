"""Every archived source sits in exactly one group, and every schedule line names a real group."""
import re
from pathlib import Path

from evidence.sources import (ARCHIVED_SOURCES, CELESTRAK_GNSS_URL, GALMON_SATELLITES_URL, GCAT_OBJECTS_URL,
                              GCAT_PAYLOADS_URL, IGS_SATELLITE_METADATA_URL, archived_addresses)

JOB = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "archive.yml").read_text()


def test_addresses_by_group():
    assert archived_addresses("documents") == [IGS_SATELLITE_METADATA_URL]
    assert archived_addresses("catalogues") == [GCAT_OBJECTS_URL, GCAT_PAYLOADS_URL]
    assert archived_addresses("orbital") == [CELESTRAK_GNSS_URL]
    assert archived_addresses("news") == []
    assert archived_addresses() == [address for group in ARCHIVED_SOURCES.values() for address in group]


def test_no_address_is_in_two_groups():
    everything = archived_addresses()
    assert len(everything) == len(set(everything))


def test_orbit_records_are_kept_as_json_never_tle():
    # TLE cannot hold catalogue numbers past 99999, which CelesTrak ran out of on 11 Jul 2026.
    assert all("FORMAT=json" in address for address in archived_addresses("orbital"))


def test_galmon_is_not_fetched_on_a_schedule():
    # On hold until Adithya has been consulted and its maintainer emailed.
    assert GALMON_SATELLITES_URL not in archived_addresses()


def test_every_schedule_line_is_assigned_to_a_group():
    schedules = re.findall(r"- cron: '([^']+)'", JOB)
    assigned = dict(re.findall(r"^\s+'([^']+)'\) group=(\w+) ;;", JOB, re.M))

    assert schedules and sorted(schedules) == sorted(assigned)   # same lines in both places
    assert len(schedules) == len(set(schedules))                 # two groups cannot share a line
    for group in assigned.values():
        assert ARCHIVED_SOURCES[group], f"'{group}' has a schedule but no sources: its runs would do nothing"


def test_the_job_can_be_started_by_hand_for_any_group():
    options = re.search(r"options: \[([^\]]+)\]", JOB).group(1).replace(" ", "").split(",")
    assert options == ["all", *ARCHIVED_SOURCES]
