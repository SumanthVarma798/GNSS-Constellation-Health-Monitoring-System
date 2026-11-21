"""A run that finds CelesTrak's element sets unchanged publishes nothing (scripts/orbit_publish_due.py, archive.yml)."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from evidence.archive import record
from evidence.settings import HOME_COUNT_EVERY, ORBIT_DATA_URL
from evidence.sources import CELESTRAK_GNSS_URL
from test_celestrak import IRNSS_1B

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import orbit_publish_due  # noqa: E402

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


class Reply:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        if self.body is None:
            raise requests.HTTPError("404")

    def json(self):
        return self.body


def served(files):
    return lambda url, timeout: Reply(files.get(url.removeprefix(ORBIT_DATA_URL)))


def archive_with(tmp_path, rows, fetched="2026-11-18T10:15:00Z"):
    record(tmp_path, CELESTRAK_GNSS_URL, fetched, 200, json.dumps(rows).encode())
    return tmp_path


def test_the_same_element_sets_are_unchanged_whatever_time_they_were_fetched(tmp_path):
    rows = [IRNSS_1B]
    archive_with(tmp_path, rows, "2026-11-18T10:15:00Z")
    files = {"latest_gnss.json": {"fetched_at": "2026-11-18T04:15:00Z", "rows": rows},
             "home_snapshot.json": {"made": (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}}

    assert orbit_publish_due.due(tmp_path, NOW, served(files)) == (False, False)


def test_new_element_sets_make_both_due(tmp_path):
    archive_with(tmp_path, [IRNSS_1B, {**IRNSS_1B, "NORAD_CAT_ID": 1}])
    files = {"latest_gnss.json": {"rows": [IRNSS_1B]}, "home_snapshot.json": {"made": "2026-11-18T11:00:00Z"}}

    assert orbit_publish_due.due(tmp_path, NOW, served(files)) == (True, True)


def test_home_alone_is_due_when_its_count_is_old(tmp_path):
    archive_with(tmp_path, [IRNSS_1B])
    made = (NOW - HOME_COUNT_EVERY).strftime("%Y-%m-%dT%H:%M:%SZ")
    files = {"latest_gnss.json": {"rows": [IRNSS_1B]}, "home_snapshot.json": {"made": made}}

    assert orbit_publish_due.due(tmp_path, NOW, served(files)) == (False, True)


def test_nothing_published_yet_or_unreadable_says_due(tmp_path):
    archive_with(tmp_path, [IRNSS_1B])

    assert orbit_publish_due.due(tmp_path, NOW, served({})) == (True, True)


def test_no_usable_copy_in_the_archive_publishes_nothing(tmp_path):
    assert orbit_publish_due.due(tmp_path, NOW, served({})) == (False, False)


def test_the_workflow_skips_both_publish_jobs_unless_the_copy_changed_or_home_is_old():
    text = (ROOT / ".github" / "workflows" / "archive.yml").read_text()
    orbits = text.split("  publish-orbits:")[1].split("  publish-home:")[0]
    home = text.split("  publish-home:")[1]

    assert "needs.archive.outputs.orbits_changed == 'true'" in orbits
    assert "needs.archive.outputs.home_due == 'true'" in home
    assert "python scripts/orbit_publish_due.py --archive archive >> \"$GITHUB_OUTPUT\"" in text
