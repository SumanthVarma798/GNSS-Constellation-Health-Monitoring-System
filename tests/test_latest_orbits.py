"""The archive's newest copy of CelesTrak's GNSS group, written for the public dashboard (scripts/latest_orbits.py)."""
import json
import subprocess
import sys
from pathlib import Path

from evidence.archive import record
from evidence.sources import CELESTRAK_GNSS_URL
from test_celestrak import IRNSS_1B

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "latest_orbits.py"


def run(archive, out):
    return subprocess.run([sys.executable, str(SCRIPT), "--archive", str(archive), "--out", str(out)],
                          capture_output=True, text=True)


def test_the_newest_copy_is_written_with_when_it_was_fetched(tmp_path):
    record(tmp_path, CELESTRAK_GNSS_URL, "2026-10-27T06:51:33Z", 200, json.dumps([IRNSS_1B]).encode())
    newer = [IRNSS_1B, {**IRNSS_1B, "NORAD_CAT_ID": 1}]
    record(tmp_path, CELESTRAK_GNSS_URL, "2026-10-28T06:51:33Z", 200, json.dumps(newer).encode())
    out = tmp_path / "latest_gnss.json"

    assert run(tmp_path, out).returncode == 0
    copy = json.loads(out.read_text())
    assert copy == {"fetched_at": "2026-10-28T06:51:33Z", "source": CELESTRAK_GNSS_URL, "rows": newer}


def test_no_copy_or_a_body_that_is_not_orbit_records_writes_nothing(tmp_path):
    out = tmp_path / "latest_gnss.json"
    assert run(tmp_path, out).returncode != 0 and not out.exists()

    record(tmp_path, CELESTRAK_GNSS_URL, "2026-10-28T06:51:33Z", 200, b'{"error": "not a list"}')
    failed = run(tmp_path, out)
    assert failed.returncode != 0 and not out.exists() and "not a list of orbit records" in failed.stderr


def test_tracked_satellites_the_group_leaves_out_are_asked_for_one_by_one_and_kept_apart():
    from test_celestrak import Reply, ReplyText

    sys.path.insert(0, str(SCRIPT.parent))
    import latest_orbits

    qzs7 = {**IRNSS_1B, "OBJECT_NAME": "QZS-7 (MICHIBIKI-7)", "NORAD_CAT_ID": 100270}
    replies = {100270: Reply([qzs7]), 2: ReplyText("No GP data found"), 3: Reply([], status=503)}
    asked = []

    def get(url, params, timeout):
        asked.append(params["CATNR"])
        assert url == "https://celestrak.org/NORAD/elements/gp.php" and params["FORMAT"] == "json"
        if params["CATNR"] == 2:
            raise ValueError("not JSON")   # what .json() does on CelesTrak's text answer
        return replies[params["CATNR"]]

    found = latest_orbits.outside_group([IRNSS_1B], {39635, 100270, 2, 3}, get=get)

    assert asked == [2, 3, 100270]        # never the satellite the group already holds
    assert found == [qzs7]                 # a failure or an empty answer drops only that satellite


def test_qzs_7_is_tracked_by_catalogue_number():
    sys.path.insert(0, str(SCRIPT.parent))
    import latest_orbits

    assert 100270 in latest_orbits.tracked_catalogue_numbers()
