"""Every archived source sits in exactly one group, and every schedule line names a real group."""
import re
from collections import Counter
from datetime import timedelta
from pathlib import Path

from evidence.archive import min_gap, site
from evidence.settings import NEVER_FETCH, RUN_WAIT_BUDGET
from evidence.sources import (ARCHIVED_SOURCES, CELESTRAK_GNSS_URL, GALMON_SATELLITES_URL, GCAT_OBJECTS_URL,
                              GCAT_PAYLOADS_URL, IGS_SATELLITE_METADATA_URL, archived_addresses, working_candidates)

JOB = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "archive.yml").read_text()


def test_addresses_by_group():
    assert archived_addresses("documents") == [IGS_SATELLITE_METADATA_URL]
    assert archived_addresses("catalogues") == [GCAT_OBJECTS_URL, GCAT_PAYLOADS_URL]
    assert archived_addresses("orbital") == [CELESTRAK_GNSS_URL]
    assert archived_addresses("news") and archived_addresses("social") == [
        f"https://www.reddit.com/r/{name}/.rss" for name in ("ISRO", "gnss", "nasa", "ESA", "roscosmos", "JAXA")]
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
    labelled = dict(re.findall(r"- cron: '([^']+)'\s+# (\w+):", JOB))

    assert schedules and sorted(schedules) == sorted(assigned)   # same lines in both places
    assert len(schedules) == len(set(schedules))                 # two groups cannot share a line
    assert labelled == assigned       # each line's comment, and so the design page, names the group it fetches
    for group in assigned.values():
        assert ARCHIVED_SOURCES[group], f"'{group}' has a schedule but no sources: its runs would do nothing"


def test_orbits_are_kept_once_a_day():
    # CelesTrak asks that unchanged data is not fetched more than every 2 hours; once a day is well inside.
    assert re.search(r"- cron: '15 1 \* \* \*'\s+# orbital: once a day", JOB)


def test_the_job_can_be_started_by_hand_for_any_group():
    options = re.search(r"options: \[([^\]]+)\]", JOB).group(1).replace(" ", "").split(",")
    assert options == ["all", *ARCHIVED_SOURCES]


def test_news_and_social_are_the_candidates_whose_check_worked():
    worked = {row["address"] for row in working_candidates()}
    assert set(archived_addresses("news")) | set(archived_addresses("social")) == worked
    assert not any(address.startswith("https://pib.gov.in/") for address in worked)   # refused (403): via Google News
    assert not any("ssc.spaceforce.mil" in address for address in worked)   # answered with an empty body


def test_no_tracker_site_is_ever_archived():
    assert not any(name in address.lower() for address in archived_addresses() for name in NEVER_FETCH)


def hours_between_runs(cron):
    """How far apart a schedule line's runs are, for the two forms the job uses."""
    minute, hour, *rest = cron.split()
    assert minute.isdigit() and rest == ["*", "*", "*"], f"teach this test the schedule '{cron}'"
    return int(hour[2:]) if hour.startswith("*/") else 24


def test_each_group_runs_no_more_often_than_its_slowest_site_allows():
    for cron, group in re.findall(r"- cron: '([^']+)'\s+# (\w+):", JOB):
        slowest = max(min_gap(address) for address in ARCHIVED_SOURCES[group])
        assert timedelta(hours=hours_between_runs(cron)) >= slowest, f"'{group}' runs more often than one of its sites allows"


def test_no_run_spends_longer_than_its_budget_waiting_out_gaps():
    for group, addresses in ARCHIVED_SOURCES.items():
        sites = Counter(site(address) for address in addresses)
        waits = sum((min_gap(f"https://{name}/") * (count - 1) for name, count in sites.items()), timedelta(0))
        assert waits <= RUN_WAIT_BUDGET, f"'{group}' would wait {waits} between requests in one run"
