"""GPS, GLONASS and Galileo: which satellites are tracked, and how their orbits reach the pages. No network."""
from datetime import datetime, timedelta, timezone

import pytest

from analysis.bundled_run import load_bundled_gp_as_dataframes
from analysis.meo_run import assess_meo
from config.config import MEO_SATS
from data import celestrak
from evidence.registry_tables import constellation_names, read_table
from evidence.settings import REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_SATELLITES_FILE

# Two rows of a real reply from gp.php?GROUP=galileo&FORMAT=json, taken 17 Oct 2026: neighbours in plane B.
GSAT0101 = {"OBJECT_NAME": "GSAT0101 (GALILEO-PFM)", "OBJECT_ID": "2011-060A", "EPOCH": "2026-10-16T20:35:39.988608",
            "MEAN_MOTION": 1.70475835, "ECCENTRICITY": 0.00013107, "INCLINATION": 56.9444, "RA_OF_ASC_NODE": 338.4586,
            "ARG_OF_PERICENTER": 302.2506, "MEAN_ANOMALY": 57.7997, "EPHEMERIS_TYPE": 0, "CLASSIFICATION_TYPE": "U",
            "NORAD_CAT_ID": 37846, "ELEMENT_SET_NO": 999, "REV_AT_EPOCH": 9319, "BSTAR": 0,
            "MEAN_MOTION_DOT": -7.8e-07, "MEAN_MOTION_DDOT": 0}
GSAT0102 = {"OBJECT_NAME": "GSAT0102 (GALILEO-FM2)", "OBJECT_ID": "2011-060B", "EPOCH": "2026-10-16T04:37:16.808160",
            "MEAN_MOTION": 1.70476109, "ECCENTRICITY": 0.00032635, "INCLINATION": 56.9454, "RA_OF_ASC_NODE": 338.4772,
            "ARG_OF_PERICENTER": 304.8024, "MEAN_ANOMALY": 52.5259, "EPHEMERIS_TYPE": 0, "CLASSIFICATION_TYPE": "U",
            "NORAD_CAT_ID": 37847, "ELEMENT_SET_NO": 999, "REV_AT_EPOCH": 9318, "BSTAR": 0,
            "MEAN_MOTION_DOT": -8.1e-07, "MEAN_MOTION_DDOT": 0}
NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)


def fresh(*rows):
    return {row["NORAD_CAT_ID"]: [celestrak.as_history_row(row)] for row in rows}


@pytest.mark.parametrize("system", ["GPS", "GLONASS", "Galileo"])
def test_the_tracked_list_is_every_registry_satellite_with_a_signal_id_today(system):
    # Strict where a person approves: a registry update that gives a satellite a signal ID, or takes one away,
    # fails here until registry/dashboard_satellites.csv is changed to match.
    with_signal = {row["svn"] for row in read_table(REGISTRY_SATELLITES_FILE)
                   if row["constellation"] == system and row["signal_id_now"]}
    letters = constellation_names()
    tracked = {row["svn"] for row in read_table(REGISTRY_DASHBOARD_SATELLITES_FILE) if letters[row["svn"][0]] == system}

    assert tracked == with_signal
    assert len(MEO_SATS[system]) == len(with_signal)


def test_celestrak_rows_alone_make_a_history_when_there_is_no_bundled_file():
    frames = load_bundled_gp_as_dataframes("galileo", MEO_SATS["Galileo"], fresh(GSAT0101))

    assert [frame["satellite"].iloc[0] for frame in frames] == ["GSAT0101"]
    assert frames[0]["SEMIMAJOR_AXIS"].iloc[0] == pytest.approx(29600.108, abs=0.001)


def test_two_neighbours_are_scored_on_their_gap_and_the_rest_are_named_as_missing():
    result = assess_meo("Galileo", NOW, fresh=fresh(GSAT0101, GSAT0102))
    rows = {row["name"]: row for row in result["rows"]}

    assert list(result["health"]["Satellite"]) == ["GSAT0101", "GSAT0102"]
    assert {row["plane"] for row in rows.values()} == {"B"}
    gap = {m: (should, actual) for m, should, actual, *_ in rows["GSAT0101"]["checks"]}["spacing"]
    assert gap[0] == pytest.approx(45.0) and gap[1] == pytest.approx(45, abs=2)   # slots B05 and B06
    assert result["health"]["Overall Score"].min() >= 80
    assert result["history_note"].startswith("Orbit history: only the newest element set")
    assert result["data_time"] == "2026-10-16T20:35:39.988608"
    assert result["burns"].empty and result["set_aside"] == []


def test_more_rows_say_how_long_the_history_is():
    later = {**GSAT0101, "EPOCH": "2026-10-17T08:35:39.988608", "MEAN_ANOMALY": 0.0}
    rows = fresh(GSAT0101)
    rows[37846].append(celestrak.as_history_row(later))

    assert "12 hours, up to 2 element sets" in assess_meo("Galileo", NOW, fresh=rows)["history_note"]


def test_no_orbit_data_at_all_says_where_it_will_come_from():
    with pytest.raises(ValueError, match="next CelesTrak refresh"):
        assess_meo("GPS", NOW, fresh={})


def test_elements_much_older_than_the_rest_are_named():
    old = {**GSAT0102, "EPOCH": (datetime(2026, 10, 16) - timedelta(days=9)).isoformat(timespec="microseconds")}

    assert assess_meo("Galileo", NOW, fresh=fresh(GSAT0101, old))["warnings"] == [
        "Orbit data over 7 days older than the rest: GSAT0102"]

