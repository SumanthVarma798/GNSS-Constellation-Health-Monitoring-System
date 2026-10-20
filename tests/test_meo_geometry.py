"""The MEO calculations by hand, on small made-up element sets: planes, spacing, the nominal values, the score."""
from datetime import datetime, timedelta

import pytest

from analysis.meo_geometry import (EXTENDED, assess, fit_planes, part_score, plane_drift, semi_major_axis_km,
                                   status_of)
from config.meo_nominal import NOMINAL

EPOCH = datetime(2026, 10, 17)
GALILEO_A = NOMINAL["Galileo"]["semi_major_axis_km"].value
GALILEO_SLOTS = NOMINAL["Galileo"]["slots"].value
PLANE_NODE = {"1": 317.632, "2": 77.632, "3": 197.632}   # A, B, C at the source's epoch


def mean_motion(a_km):
    """Revolutions a day for a semi-major axis, the inverse of semi_major_axis_km."""
    return 86400 / (2 * 3.141592653589793 * (a_km ** 3 / 398600.4418) ** 0.5)


def element(raan, u, inclination=56.0, a=GALILEO_A, e=0.0, epoch=EPOCH):
    """A circular orbit at argument of latitude u (perigee at the node, so the mean anomaly is u)."""
    return {"EPOCH": epoch, "MEAN_MOTION": mean_motion(a), "ECCENTRICITY": e, "INCLINATION": inclination,
            "RA_OF_ASC_NODE": raan, "ARG_OF_PERICENTER": 0.0, "MEAN_ANOMALY": u}


def galileo(changes=None, registry_changes=None):
    """All 24 nominal Galileo slots filled exactly, then `changes` ({slot: element keyword arguments})."""
    elements, registry = {}, {}
    for slot, u in GALILEO_SLOTS.items():
        if int(slot[1:]) > 8:
            continue
        plane = str("ABC".index(slot[0]) + 1)
        elements[slot] = element(**{"raan": PLANE_NODE[plane], "u": u, **(changes or {}).get(slot, {})})
        registry[slot] = {"plane": plane, "slot": slot, "signal_id_now": f"E{len(registry) + 1:02d}",
                          **(registry_changes or {}).get(slot, {})}
    return {row["name"]: row for row in assess("Galileo", elements, registry)}


def checks(row):
    return {measure: (should, actual, error, score) for measure, should, actual, error, score in row["checks"]}


def test_a_part_scores_full_within_its_tolerance_and_nothing_at_three_times_it():
    assert [part_score(e, 2.0) for e in (0, -2.0, 3.0, 4.0, -5.0, 6.0, 9.0)] == [100, 100, 75, 50, 25, 0, 0]


def test_the_bands_are_the_other_scores_bands():
    assert [status_of(s) for s in (100, 80, 79.9, 60, 40, 39.9)] == [
        "🟢 Healthy", "🟢 Healthy", "🟡 Fair", "🟡 Fair", "🟠 Degraded", "🔴 Critical"]


def test_planes_are_found_from_the_nodes_even_across_zero():
    turn, index, offsets = fit_planes([359.0, 119.0, 239.5, 1.0], 120.0)

    assert index[0] == index[3] and len({index[0], index[1], index[2]}) == 3
    assert turn % 120 == pytest.approx(119.625, abs=1e-3)   # the mean of -1, -1, -0.5 and +1 from 0, 120 and 240
    assert offsets == pytest.approx([-0.625, -0.625, -0.125, 1.375], abs=1e-3)


def test_a_full_constellation_on_its_slots_is_healthy_everywhere():
    rows = galileo()

    assert {row["score"] for row in rows.values()} == {100}
    a01 = checks(rows["A01"])
    assert a01["spacing"][:2] == pytest.approx((45.0, 45.0))
    assert a01["plane"][2] == pytest.approx(0.0, abs=1e-9)
    assert a01["height"][1] == pytest.approx(GALILEO_A, abs=1e-3)
    assert {row["plane"] for row in rows.values()} == {"A", "B", "C"}
    assert rows["B05"]["slot_at"] == pytest.approx(GALILEO_SLOTS["B05"], abs=1e-6)


def test_a_satellite_out_of_step_marks_its_gaps_and_its_neighbours():
    rows = galileo({"A03": {"u": GALILEO_SLOTS["A03"] + 10}})

    # 10 degrees against a gap allowance of 2 x 4 degrees: 100 - 50 * 2 / 8
    assert checks(rows["A03"])["spacing"][2:] == pytest.approx((10.0, 87.5))
    assert checks(rows["A02"])["spacing"][3] == checks(rows["A04"])["spacing"][3] == pytest.approx(87.5)
    assert checks(rows["A05"])["spacing"][3] == 100
    assert rows["A03"]["score"] == pytest.approx((0.2 + 0.3 * 0.875 + 0.2 + 0.15 + 0.15) * 100)


def test_a_satellite_off_its_plane_and_one_the_registry_puts_elsewhere():
    rows = galileo({"C02": {"raan": PLANE_NODE["3"] + 3.0}},
                   {"A04": {"plane": "2"}})

    assert checks(rows["C02"])["plane"][2] == pytest.approx(3.0 - 3.0 / 24, abs=0.01)   # the fit moves a 24th of it
    assert rows["A04"]["plane"] == "A" and not rows["A04"]["plane_agrees"] and rows["A04"]["registry_plane"] == "B"
    assert all(row["plane_agrees"] for name, row in rows.items() if name != "A04")


def test_a_satellite_away_from_its_height_is_scored_on_it_and_left_out_of_the_gaps():
    rows = galileo({"B02": {"u": GALILEO_SLOTS["B02"] + 20, "a": GALILEO_A + 25}})

    assert checks(rows["B02"])["height"][2:] == pytest.approx((25.0, 25.0), abs=1e-3)   # 15 km over a 10 km tolerance
    assert "spacing" not in checks(rows["B02"])
    # B01 to B03 is 90 degrees, as their slots are; counted with B02 20 degrees on, B01's gap ahead would be 65
    assert checks(rows["B01"])["spacing"][3] == checks(rows["B03"])["spacing"][3] == 100


def test_older_elements_are_moved_to_the_newest_epoch():
    day = mean_motion(GALILEO_A) * 360   # degrees along the orbit in a day
    rows = galileo({"C05": {"u": GALILEO_SLOTS["C05"] - day, "epoch": EPOCH - timedelta(days=1)}})

    assert checks(rows["C05"])["spacing"][2] == pytest.approx(0.0, abs=1e-6)
    assert abs(checks(rows["C05"])["plane"][2]) < 0.05   # the node drifts a few hundredths of a degree a day


def test_the_eccentric_pair_is_judged_against_its_own_orbit():
    ext = NOMINAL["Galileo"]["extended"].value
    elements = {"E18": element(52.521, 100.0, ext["inclination_deg"], ext["semi_major_axis_km"], ext["eccentricity"]),
                "A01": element(317.632, 0.0)}
    registry = {"E18": {"plane": "X", "slot": "Ext01", "signal_id_now": "E18"},
                "A01": {"plane": "1", "slot": "A01", "signal_id_now": "E31"}}
    row = assess("Galileo", elements, registry)[0]

    assert row["plane"] == EXTENDED and set(checks(row)) == {"inclination", "height", "eccentricity"}
    assert row["score"] == 100


def test_the_nominal_values_have_a_source_and_a_label():
    for system, values in NOMINAL.items():
        for key, value in values.items():
            assert value.source and value.label in ("checked", "source summary", "our choice"), (system, key)


def test_the_slot_tables_read_as_their_sources_write_them():
    glonass, gps = NOMINAL["GLONASS"]["slots"].value, NOMINAL["GPS"]["slots"].value
    assert (glonass["2"] - glonass["1"]) % 360 == pytest.approx(315)    # slot numbers run against the motion
    assert (glonass["9"] - glonass["1"]) % 360 == pytest.approx(15)     # the next plane is 15 degrees on
    assert glonass["1"] == pytest.approx(145 + 26 / 60 + 37 / 3600)
    assert len(gps) == 30 and gps["A1"] == 268.126 and gps["F2F"] == 0.456
    assert GALILEO_SLOTS["B05"] == pytest.approx(15.153) and GALILEO_SLOTS["C04"] == pytest.approx(345.153)
    # GLONASS's period, 11 h 15 min 44 s, as a semi-major axis
    assert NOMINAL["GLONASS"]["semi_major_axis_km"].value == pytest.approx(semi_major_axis_km(86400 / 40544), abs=0.1)


def test_a_glonass_slot_written_with_a_leading_zero_is_found():
    slots = NOMINAL["GLONASS"]["slots"].value
    elements = {name: element(251.25, slots[str(int(name))], 64.8, NOMINAL["GLONASS"]["semi_major_axis_km"].value)
                for name in ("01", "02", "03")}
    registry = {name: {"plane": "1", "slot": name, "signal_id_now": f"R{name}"} for name in elements}

    assert all("spacing" in checks(row) for row in assess("GLONASS", elements, registry))


def drift_row(plane, offset, node_rate, spacing_error=None):
    checks = [("plane", 0.0, offset, offset, 100)] + ([("spacing", 45.0, 45.0 + spacing_error, spacing_error, 100)]
                                                     if spacing_error is not None else [])
    return {"plane": plane, "checks": checks, "node_rate": node_rate}


def test_a_planes_drift_is_its_mean_node_offset_its_node_rate_against_the_patterns_and_its_worst_gap():
    rows = [drift_row("A", 1.0, -0.040, 0.5), drift_row("A", 2.0, -0.040, -1.5), drift_row("B", -1.5, -0.042),
            {"plane": EXTENDED, "checks": [], "node_rate": -0.1}]   # the eccentric orbit counts for nothing

    drift = plane_drift("GPS", rows)

    assert set(drift) == {"A", "B"}
    pattern = (-0.040 - 0.040 - 0.042) / 3
    assert drift["A"] == pytest.approx({"offset": 1.5, "offset_limit": 5.0, "rate": (-0.040 - pattern) * 365.25,
                                        "gap": 1.5, "gap_limit": 8.0})
    assert drift["B"]["rate"] == pytest.approx((-0.042 - pattern) * 365.25)   # -0.49 a year: B's node falls behind
    assert drift["B"]["gap"] is None


def test_a_plane_tilted_one_degree_more_drifts_against_the_pattern_and_the_rest_do_not_drift_apart():
    level = galileo()
    assert all(d["rate"] == pytest.approx(0, abs=1e-9) for d in plane_drift("Galileo", level.values()).values())

    # Plane A one degree steeper: its node turns back more slowly, by hand about 0.25 degrees a year against
    # the others, and the pattern (a third of it plane A) moves a third of that: 0.25 x 2/3 = 0.165.
    tilted = galileo({slot: {"inclination": 57.0} for slot in GALILEO_SLOTS if slot[0] == "A"})
    drift = plane_drift("Galileo", tilted.values())
    assert drift["A"]["rate"] == pytest.approx(0.165, abs=0.005)
    assert drift["B"]["rate"] == drift["C"]["rate"] == pytest.approx(-0.0823, abs=0.003)
