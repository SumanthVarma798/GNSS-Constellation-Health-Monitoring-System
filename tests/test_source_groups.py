"""Every archived source sits in exactly one group, and every schedule line names a real group."""
import re
from collections import Counter
from datetime import timedelta
from pathlib import Path

from evidence.archive import min_gap, site
from evidence.settings import NEVER_FETCH, RUN_WAIT_BUDGET
from evidence.sources import (ARCHIVED_SOURCES, CELESTRAK_GNSS_URL, GALMON_SATELLITES_URL, GCAT_FAILED_LAUNCHES_URL, GCAT_OBJECTS_URL,
                              GCAT_PAYLOADS_URL, IGS_SATELLITE_METADATA_URL, archived_addresses, working_candidates)

JOB = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "archive.yml").read_text()


def test_addresses_by_group():
    assert archived_addresses("documents") == [IGS_SATELLITE_METADATA_URL]
    assert archived_addresses("catalogues") == [GCAT_OBJECTS_URL, GCAT_PAYLOADS_URL, GCAT_FAILED_LAUNCHES_URL]
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


def test_orbits_are_kept_every_two_hours():
    # CelesTrak updates its GP data only every 2 hours and allows one download per update.
    assert re.search(r"- cron: '15 \*/2 \* \* \*'\s+# orbital: every 2 hours", JOB)


# Scheduled workflows that still ask celestrak.org themselves, with the reason (the weekly registry job needs CelesTrak's
# SATCAT catalogue, which the orbit copy on orbit-data does not hold).
STILL_ASKS_CELESTRAK = {"registry-update.yml": "weekly: SATCAT and one GP request per changed satellite"}
ROOT = Path(__file__).resolve().parent.parent


def downloads_from_celestrak(script):
    """Whether a script calls CelesTrak itself: celestrak.fetch/_get/catalogue_entry, or refresh without direct=False."""
    text = (ROOT / "scripts" / f"{script}.py").read_text()
    return bool(re.search(r"celestrak\.(fetch\(|_get\(|catalogue_entry\()", text)
                or any("direct=False" not in line for line in text.splitlines() if "celestrak.refresh(" in line))


def test_only_the_archive_orbital_group_downloads_gnss_orbits_from_celestrak():
    # orbit-ages and rinex-check read the copy the orbital group publishes on orbit-data; the archive runs every 2 hours.
    asking = {path.name for path in (ROOT / ".github" / "workflows").glob("*.yml")
              if "schedule:" in path.read_text()
              and any(downloads_from_celestrak(name) for name in re.findall(r"scripts/(\w+)\.py", path.read_text()))}
    assert asking - {"archive.yml"} == set(STILL_ASKS_CELESTRAK)
    assert not downloads_from_celestrak("orbit_ages") and not downloads_from_celestrak("orbit_record_gap")
    assert "fetch_copy" in (ROOT / "scripts" / "orbit_ages.py").read_text()
    orbital = re.search(r"- cron: '([^']+)'\s+# orbital:", JOB).group(1)
    assert timedelta(hours=hours_between_runs(orbital)) >= min_gap(CELESTRAK_GNSS_URL)


def test_the_job_can_be_started_by_hand_for_any_group():
    options = re.search(r"options: \[([^\]]+)\]", JOB).group(1).replace(" ", "").split(",")
    assert options == ["all", *ARCHIVED_SOURCES]


def test_news_social_and_x_are_the_candidates_whose_check_worked():
    worked = {row["address"] for row in working_candidates()}
    assert set(archived_addresses("news")) | set(archived_addresses("social")) | set(archived_addresses("x")) == worked
    assert not any(address.startswith("https://pib.gov.in/") for address in worked)   # refused (403): via Google News
    assert not any("ssc.spaceforce.mil" in address for address in worked)   # answered with an empty body


def test_no_tracker_site_is_ever_archived():
    assert not any(name in address.lower() for address in archived_addresses() for name in NEVER_FETCH)


def hours_between_runs(cron):
    """The shortest gap between a schedule line's runs, for the three forms the job uses: */n, a list, one hour."""
    minute, hour, *rest = cron.split()
    assert minute.isdigit() and rest == ["*", "*", "*"], f"teach this test the schedule '{cron}'"
    if hour.startswith("*/"):
        return int(hour[2:])
    hours = sorted(int(h) for h in hour.split(","))
    return min(b - a for a, b in zip(hours, hours[1:] + [hours[0] + 24]))   # across midnight too


def test_the_shortest_gap_counts_a_list_and_midnight():
    assert hours_between_runs("15 1,8,14,20 * * *") == 5
    assert hours_between_runs("15 */2 * * *") == 2
    assert hours_between_runs("15 1,2 * * *") == 1
    assert hours_between_runs("15 0,23 * * *") == 1
    assert hours_between_runs("50 */3 * * *") == 3 and hours_between_runs("30 0 * * *") == 24


def test_each_group_runs_no_more_often_than_its_slowest_site_allows():
    for cron, group in re.findall(r"- cron: '([^']+)'\s+# (\w+):", JOB):
        slowest = max(min_gap(address) for address in ARCHIVED_SOURCES[group])
        assert timedelta(hours=hours_between_runs(cron)) >= slowest, f"'{group}' runs more often than one of its sites allows"


def test_no_run_spends_longer_than_its_budget_waiting_out_gaps():
    for group, addresses in ARCHIVED_SOURCES.items():
        sites = Counter(site(address) for address in addresses)
        waits = sum((min_gap(f"https://{name}/") * (count - 1) for name, count in sites.items()), timedelta(0))
        assert waits <= RUN_WAIT_BUDGET, f"'{group}' would wait {waits} between requests in one run"
