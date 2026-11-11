"""The MEO systems: which satellites are tracked, and how their orbits reach the pages. No network."""
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from analysis.bundled_run import load_bundled_gp_as_dataframes
from analysis.meo_geometry import NO_PLANE
from analysis.meo_run import assess_meo
from config.config import BEIDOU3_SATS, MEO_SATS
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


@pytest.mark.coverage_gate   # a new BeiDou MEO signal ID must open a registry proposal, then block only its merge
def test_beidou_3_meo_tracks_every_bds_3_meo_satellite_with_a_signal_id_and_beidou_3_keeps_the_rest():
    # BeiDou's rows are kept by a person, not in step with the registry: this fails when a MEO satellite gains or
    # loses a signal ID, until registry/dashboard_satellites.csv is changed to match.
    registry = read_table(REGISTRY_SATELLITES_FILE)
    with_signal = {row["catalogue_no"] for row in registry
                   if row["block"].startswith(("BDS-3M", "BDS-3SM")) and row["signal_id_now"]}
    geo_igso = {row["catalogue_no"] for row in registry
                if row["block"].startswith(("BDS-3G", "BDS-3I", "BDS-2I", "BDS-3SI"))}

    assert {str(n) for n in MEO_SATS["BeiDou-3 MEO"].values()} == with_signal   # 28 BDS-3M and the two test MEOs
    assert {str(n) for n in BEIDOU3_SATS.values()} <= geo_igso   # the split leaves no MEO satellite in BeiDou-3
    assert len(BEIDOU3_SATS) == 10   # 4 GEO and 3 IGSO of BeiDou-3, BeiDou-2 IGSO-6 and -7, the test IGSO-2S


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


def test_a_satellite_with_no_part_worked_out_has_no_score_and_the_page_still_draws(monkeypatch):
    # COSMOS 2620 on 4 Nov 2026: its None score stopped GLONASS's Overview and the World map.
    from analysis import meo_run
    from ui import meo_overview
    real = meo_run.assess

    def unscored(*args):
        rows = real(*args)
        next(row for row in rows if row["name"] == "GSAT0101").update(score=None, status="", parts={})
        return rows
    monkeypatch.setattr(meo_run, "assess", unscored)
    result = assess_meo("Galileo", NOW, fresh=fresh(GSAT0101, GSAT0102))

    assert result["health"].set_index("Satellite")["Overall Score"].isna().to_dict() == {"GSAT0101": True,
                                                                                        "GSAT0102": False}
    assert meo_overview.tiles(result)["GSAT0101"][1] is False   # not counted as healthy


def test_elements_much_older_than_the_rest_are_named():
    old = {**GSAT0102, "EPOCH": (datetime(2026, 10, 16) - timedelta(days=9)).isoformat(timespec="microseconds")}

    assert assess_meo("Galileo", NOW, fresh=fresh(GSAT0101, old))["warnings"] == [
        "Orbit data over 7 days older than the rest: GSAT0102"]


# COSMOS 2620 (R809, launched Sep 2026): the registry gives it no plane or slot yet, so no part can be scored.
# Its round(None) once stopped every page that loads GLONASS, the World map among them.
COSMOS_2620 = {**GSAT0101, "OBJECT_NAME": "COSMOS 2620", "NORAD_CAT_ID": 100744, "MEAN_MOTION": 2.13102,
               "INCLINATION": 64.8}


def test_a_satellite_the_registry_gives_no_plane_is_kept_with_no_score():
    result = assess_meo("GLONASS", NOW, fresh=fresh(COSMOS_2620))
    row = result["rows"][0]

    assert row["score"] is None and row["plane"] == NO_PLANE and row["checks"] == []
    assert list(result["health"]["Satellite"]) == ["COSMOS 2620"]
    assert pd.isna(result["health"]["Overall Score"].iloc[0])



def test_a_new_beidou_satellite_is_announced_on_its_own_page_only(monkeypatch):
    from datetime import date

    from evidence import registry_tables

    real = registry_tables.read_table
    added = {"C215": "2026-11-07", "C217": "2026-11-07"}   # BeiDou-3 M16 (MEO) and BeiDou-3 G1 (GEO)

    def read_table(name):
        rows = real(name)
        if name == REGISTRY_DASHBOARD_SATELLITES_FILE:
            rows = [{**row, "added": added.get(row["svn"], row["added"])} for row in rows]
        return rows

    monkeypatch.setattr(registry_tables, "read_table", read_table)
    meo = registry_tables.new_on_dashboard("BeiDou-3 MEO", date(2026, 11, 8))
    geo_igso = registry_tables.new_on_dashboard("BeiDou-3", date(2026, 11, 8))

    assert "BeiDou-3 M16" in meo and "BeiDou-3 G1" not in meo
    assert "BeiDou-3 G1" in geo_igso and "BeiDou-3 M16" not in geo_igso


def test_along_track_and_tilt_follow_from_the_elements():
    """2 pi a0 (n - n0): a satellite at the nominal mean motion has none; two satellites in one plane tilt alike."""
    import math

    from analysis.meo_geometry import MU, assess
    from config.meo_nominal import NOMINAL
    from evidence.registry_tables import dashboard_registry_rows

    a0 = NOMINAL["Galileo"]["semi_major_axis_km"].value
    n0 = math.sqrt(MU / a0 ** 3) * 86400 / (2 * math.pi)
    registry = dashboard_registry_rows("Galileo")
    elements = {name: {**celestrak.as_history_row(row), "EPOCH": NOW} for name, row in
                (("GSAT0101", {**GSAT0101, "MEAN_MOTION": n0}), ("GSAT0102", GSAT0102))}
    rows = {row["name"]: row for row in assess("Galileo", elements, {n: registry[n] for n in elements})}

    assert abs(rows["GSAT0101"]["along_track_km_day"]) < 1e-6
    expected = 2 * math.pi * a0 * (float(GSAT0102["MEAN_MOTION"]) - n0)
    assert rows["GSAT0102"]["along_track_km_day"] == pytest.approx(expected)
    assert rows["GSAT0101"]["tilt_vs_peers_deg"] == pytest.approx(rows["GSAT0102"]["tilt_vs_peers_deg"])
