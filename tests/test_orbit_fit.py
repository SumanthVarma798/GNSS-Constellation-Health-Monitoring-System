"""The broadcast-position orbit fit recovers a known SGP4 record and refuses bad inputs."""
from datetime import datetime, timedelta, timezone

import numpy as np
from skyfield.api import load
from skyfield.framelib import itrs
from skyfield.sgp4lib import TEME
from sgp4.api import Satrec, jday

from analysis.orbit_fit import fit

TLE = ("1 56564U 23066A   26292.31455302 -.00000278  00000-0  00000+0 0  9994",
       "2 56564   0.4524   8.1520 0005748 207.1566  65.7354  1.00267984 12639")


def _samples():
    satellite = Satrec.twoline2rv(*TLE)
    timescale = load.timescale()
    start = datetime(2026, 10, 17, tzinfo=timezone.utc)
    samples, teme = [], {}
    for step in range(96):
        at = start + timedelta(minutes=15 * step)
        jd, fr = jday(at.year, at.month, at.day, at.hour, at.minute, at.second)
        error, positions, _ = satellite.sgp4_array(np.array([jd]), np.array([fr]))
        assert error[0] == 0
        inertial = positions[0]
        fixed = itrs.rotation_at(timescale.from_datetime(at)) @ TEME.rotation_at(timescale.from_datetime(at)).T @ inertial
        samples.append((at, fixed))
        teme[at] = inertial
    return samples, teme


def test_a_known_sgp4_record_is_recovered_within_a_hundredth_of_a_km():
    samples, teme = _samples()
    fitted, rms_km = fit(samples, 56564, "2023-066A", "BeiDou-3 G4")

    assert rms_km < 0.01
    satellite = Satrec.twoline2rv(fitted["TLE_LINE1"], fitted["TLE_LINE2"])
    for at, expected in teme.items():
        jd, fr = jday(at.year, at.month, at.day, at.hour, at.minute, at.second)
        error, positions, _ = satellite.sgp4_array(np.array([jd]), np.array([fr]))
        assert error[0] == 0
        assert np.linalg.norm(positions[0] - expected) < 0.1


def test_too_few_samples_are_left_out():
    samples, _ = _samples()
    assert fit(samples[:5], 56564, "2023-066A") is None


def test_a_fifty_km_jump_is_treated_as_a_burn_and_left_out():
    samples, _ = _samples()
    for index in range(48, len(samples)):
        samples[index] = (samples[index][0], samples[index][1] + np.array([50.0, 0.0, 0.0]))

    assert fit(samples, 56564, "2023-066A") is None


def test_a_fitted_records_gap_against_its_own_positions_is_near_zero_and_glonass_keeps_only_that_day():
    from scripts import orbit_record_gap

    samples, _ = _samples()
    assert orbit_record_gap._fitted_gap(samples, {"TLE_LINE1": TLE[0], "TLE_LINE2": TLE[1]}) < 0.01
    assert orbit_record_gap._fitted_gap(samples, {"TLE_LINE1": "not a line"}) is None
    assert orbit_record_gap._fitted_gap([], {"TLE_LINE1": TLE[0], "TLE_LINE2": TLE[1]}) is None

    day = datetime(2026, 10, 17, tzinfo=timezone.utc)
    glonass = {"R08": {day: (1.0, 2.0, 3.0), day + timedelta(days=1): (4.0, 5.0, 6.0)}}
    kept = orbit_record_gap.glonass_samples(glonass, "R08", day.date())
    assert [utc for utc, _ in kept] == [day] and orbit_record_gap.glonass_samples(glonass, "R01", day.date()) == []
