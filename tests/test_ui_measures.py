"""Each measure as "is" next to "should be": read from the health row and the settings, never a new score."""
import pandas as pd

from config.config import DEFAULT_PARAMS
from ui import measures, surfaces

GEO = {"Satellite": "IRNSS-1C", "Type": "GEO", "Current Drift (°/day)": -0.0203, "Incl. (°)": 6.784,
       "Target Incl. (°)": 5.0, "Incl. Dev. (°)": 1.784, "Designated Lon (°)": 83.0, "Current Mean Lon (°)": 82.64,
       "Lon Slot Deviation (°)": -0.36, "Lon Deviation Score": 100.0, "Altitude (km)": 35794.8,
       "Expected Interval (days)": 48.0, "Days Since Last": 80, "_maintenance_score": 82.0,
       "EW Maneuvers": 6, "NS Maneuvers": 0}
P = measures.thresholds("NavIC", {})


def test_drift_is_judged_against_the_gear_for_geo_and_two_degrees_for_tilted_orbits():
    assert measures.drift(GEO, P) == measures.cell("-0.0203° west", "allowed ±0.05°/day", "ok")
    fast = measures.drift({**GEO, "Current Drift (°/day)": 0.08}, P)
    assert fast["status"] == "warn" and fast["should"].endswith("outside")
    assert measures.drift({**GEO, "Type": "IGSO", "Current Drift (°/day)": 0.08}, P)["should"] == "allowed ±2°/day"
    assert measures.drift(GEO, measures.thresholds("NavIC", {"drift_tolerance_gso": 0.01}))["status"] == "warn"


def test_inclination_uses_the_target_and_tolerance_or_the_band_as_the_score_does():
    off = measures.inclination(GEO, measures.requirement("IRNSS-1C"), P)
    assert (off["now"], off["should"], off["status"]) == ("6.78°", "5° ±1° · outside", "warn")
    band = {"Incl. (°)": 40.0, "Target Incl. (°)": 43.0, "Incl. Dev. (°)": 0.0}
    assert measures.inclination(band, measures.requirement("QZS-2 (Michibiki-2)"), P)["should"] == "39 to 47°"
    assert measures.inclination(band, measures.requirement("BeiDou-3 G1"), P)["should"] == "under 3°"


def test_qzss_takes_its_wider_tolerance_unless_the_gear_moves_it():
    assert measures.thresholds("QZSS", {})["inclination_tolerance"] == 4.0
    assert measures.thresholds("QZSS", {"inclination_tolerance": 2.0})["inclination_tolerance"] == 2.0
    assert measures.thresholds("NavIC", {})["inclination_tolerance"] == DEFAULT_PARAMS["inclination_tolerance"]


def test_longitude_is_in_its_slot_only_with_the_full_longitude_score():
    assert measures.longitude(GEO) == measures.cell("82.64°E", "slot 83.00°E ±0.5°", "ok", "-0.36° from its slot")
    assert measures.longitude({**GEO, "Lon Deviation Score": 42.3})["status"] == "warn"
    assert measures.longitude({**GEO, "Type": "IGSO"})["should"] == "slot 83.00°E ±5°"
    unknown = measures.longitude({**GEO, "Current Mean Lon (°)": "N/A"})
    assert (unknown["now"], unknown["note"]) == ("not known", "scored without this part")


def test_eccentricity_against_its_limit_when_one_is_set():
    assert measures.eccentricity(0.0002, {"ecc_max": 0.099})["status"] == "ok"
    assert measures.eccentricity(0.12, {"ecc_max": 0.099})["status"] == "warn"
    assert measures.eccentricity(0.0002, {})["should"] == "no limit set"


def test_upkeep_says_when_a_burn_is_late():
    assert measures.upkeep(GEO)["should"] == "every 48 d · overdue since day 72"
    assert measures.upkeep({**GEO, "Days Since Last": 50})["should"] == "every 48 d, overdue after 72"
    assert measures.upkeep({**GEO, "Expected Interval (days)": "N/A"})["should"] == "no pattern yet"


def test_orbit_types_follow_the_tilt_and_group_in_order():
    assert [measures.orbit_type(t, c) for t, c in [(2.0, "NavIC"), (29.0, "NavIC"), (40.0, "QZSS"), (None, "QZSS")]] \
        == ["GEO", "IGSO", "QZO", "Unclassified"]
    groups = measures.grouped({"a": "Other", "b": "QZO", "c": "GEO", "d": "MEO", "e": "GEO"})
    assert list(groups.items()) == [("GEO", ["c", "e"]), ("QZO", ["b"]), ("MEO", ["d"]), ("Other", ["a"])]


def test_status_counts_use_the_score_bands():
    scores = pd.DataFrame({"Overall Score": [95, 80, 79.9, 41, 39, None]})
    assert measures.status_counts(scores) == [("Healthy", 2), ("Fair", 1), ("Degraded", 1), ("Critical", 1)]


def test_the_window_runs_back_from_today_to_the_end_of_today():
    history = pd.DataFrame({"EPOCH": pd.to_datetime(["2026-07-18 00:00", "2026-07-19 00:00", "2026-10-17 23:00", "2026-10-19 00:00"]),
                            "satellite": "x"})
    kept = measures.in_window(history, 90, pd.Timestamp("2026-10-17"))
    assert list(kept["EPOCH"].dt.day) == [19, 17]


def test_burn_row_counts_each_kind_and_reads_the_pattern():
    burns = pd.DataFrame({"satellite": ["a", "a", "a", "b"], "kind": ["east-west", "east-west", "north-south", "east-west"]})
    health = {"EW Expected Interval (days)": 30.0, "EW Days Since Last": 50, "EW Pattern Confidence": "High",
              "NS Expected Interval (days)": "N/A", "NS Days Since Last": "N/A", "NS Pattern Confidence": None}
    east, north, days, ew, ns = measures.burn_row("a", burns, 89, health)
    assert (east["now"], north["now"], days["now"]) == ("2", "1", "89")
    assert ew == measures.cell("50 d ago", "every 30 d · overdue since day 45", "warn", "confidence high")
    assert ns["now"] == "no burns"
    assert [c["now"] for c in measures.burn_row("b", burns, None, None)] == ["1", "0", "–", "set aside", "set aside"]


def test_the_table_escapes_its_words_and_sets_figures_in_the_number_face():
    html = surfaces.table([("<b>", "<i>")], [("<script>", [measures.cell("1.5°", "&"), measures.cell("set aside")])])
    assert "<script>" not in html and "&lt;b&gt;" in html and "&amp;" in html
    assert '<b class="num idle">1.5°</b>' in html and '<b class="idle">set aside</b>' in html
