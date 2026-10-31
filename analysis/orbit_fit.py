"""Fit an SGP4 orbit record to Earth-fixed positions, without scipy.

The input samples are [(utc (aware datetime), Earth-fixed (x, y, z) km), ...] oldest first.
Each position is turned into TEME (SGP4's frame), and a Gauss-Newton fit recovers the six
elements SGP4 needs (as equinoctial elements, see _classical). The result is an OMM-shaped history row, so it can be
used wherever CelesTrak and Space-Track rows are used.
"""
import math

import numpy as np
from skyfield.api import load
from skyfield.framelib import itrs
from skyfield.sgp4lib import TEME
from sgp4.api import Satrec, WGS72, jday

from data.celestrak import as_history_row
from evidence.settings import ORBIT_FIT_MAX_KM, ORBIT_FIT_MIN_SAMPLES

MU = 398600.8        # km^3/s^2, WGS-72 as used by the SGP4 fit
_ts = load.timescale()


def _julian_arrays(times):
    """(jd, fr) numpy arrays for SGP4's vector propagator."""
    parts = [jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)
             for t in times]
    return np.array([pair[0] for pair in parts]), np.array([pair[1] for pair in parts])


def _classical(parameters):
    """(n, e, i, node, perigee, mean anomaly) from the fitted (n, h, k, p, q, λ).

    Equinoctial elements: h, k = e sin/cos(ϖ), p, q = tan(i/2) sin/cos(node), λ = M + ϖ, with ϖ = perigee + node.
    They stay smooth where e or i is near 0, where perigee and node are not defined (QZS-6 is near both).
    """
    n, h, k, p, q, longitude = parameters
    node = math.atan2(p, q)
    wide = math.atan2(h, k)                       # ϖ
    return (n, math.hypot(h, k), 2 * math.atan(math.hypot(p, q)), node % (2 * math.pi),
            (wide - node) % (2 * math.pi), (longitude - wide) % (2 * math.pi))


def _satellite(parameters, epoch):
    n, eccentricity, inclination, node, perigee, mean_anomaly = _classical(parameters)
    satellite = Satrec()
    jd, fr = jday(epoch.year, epoch.month, epoch.day, epoch.hour, epoch.minute,
                  epoch.second + epoch.microsecond / 1e6)
    satellite.sgp4init(WGS72, "i", 99999, (jd + fr) - 2433281.5, 0.0, 0.0, 0.0,
                       eccentricity, perigee, inclination, mean_anomaly, n, node)
    return satellite


def _predict(satellite, times):
    """TEME positions in km for the fitted satellite, and SGP4's per-time error codes."""
    jd, fr = _julian_arrays(times)
    error, positions, _ = satellite.sgp4_array(jd, fr)
    return positions, error


def _rms(parameters, epoch, times, observed):
    """Root-mean-square distance in km from the observed positions, or infinity when SGP4 fails."""
    positions, error = _predict(_satellite(parameters, epoch), times)
    if np.any(error) or not np.all(np.isfinite(positions)):
        return math.inf
    return float(np.sqrt(np.mean(np.sum((observed - positions) ** 2, axis=1))))


def _initial(samples):
    """A first guess from the osculating elements at the second-last sample, rolled on to the last one.

    The velocity is the chord between its two neighbours, which belongs to the middle sample; paired with an end
    sample instead, a geostationary orbit looked 0.03 eccentric and the fit ran away (QZS-6, 24 Oct 2026)."""
    (t0, r0), (tm, rm), (t1, _) = samples[-3], samples[-2], samples[-1]
    position = np.asarray(rm, dtype=float)
    velocity = (np.asarray(samples[-1][1], dtype=float) - np.asarray(r0, dtype=float)) / (t1 - t0).total_seconds()
    angular = np.cross(position, velocity)
    radius, speed = np.linalg.norm(position), np.linalg.norm(velocity)
    semi_major = 1 / (2 / radius - speed * speed / MU)
    eccentric = np.cross(velocity, angular) / MU - position / radius
    inclination = math.acos(max(-1.0, min(1.0, angular[2] / np.linalg.norm(angular))))
    node_vector = np.cross([0.0, 0.0, 1.0], angular)
    node = math.atan2(node_vector[1], node_vector[0])
    e = float(np.linalg.norm(eccentric))
    if e > 1e-8:
        perigee = math.atan2(np.dot(np.cross(node_vector, eccentric), angular) / np.linalg.norm(angular),
                             np.dot(node_vector, eccentric))
        reference = eccentric
    else:
        perigee = 0.0
        reference = node_vector
    true = math.atan2(np.dot(np.cross(reference, position), angular) / np.linalg.norm(angular),
                      np.dot(reference, position))
    eccentric_anomaly = 2 * math.atan(math.sqrt((1 - e) / (1 + e)) * math.tan(true / 2))
    mean_anomaly = eccentric_anomaly - e * math.sin(eccentric_anomaly)
    n = math.sqrt(MU / semi_major ** 3) * 60
    wide, tilt = perigee + node, math.tan(inclination / 2)
    return np.array([n, e * math.sin(wide), e * math.cos(wide), tilt * math.sin(node), tilt * math.cos(node),
                     mean_anomaly + wide + n * (t1 - tm).total_seconds() / 60]), t1


def fit(samples, norad, object_id, object_name=None):
    """(history_row, rms_km), or None when there are too few samples or the fit does not hold.

    A burn inside the day breaks a single-arc fit; such a satellite is left out rather than
    published as a bad record.
    """
    if len(samples) < ORBIT_FIT_MIN_SAMPLES:
        return None
    times = [sample[0] for sample in samples]
    inertial = [(sample[0], _to_teme(sample[0], sample[1])) for sample in samples]
    observed = np.array([position for _, position in inertial], dtype=float)
    parameters, epoch = _initial(inertial)
    steps = np.array([1e-9, 1e-7, 1e-7, 1e-7, 1e-7, 1e-7])
    rms_km = _rms(parameters, epoch, times, observed)
    for _ in range(30):
        if not math.isfinite(rms_km):
            return None
        positions, _ = _predict(_satellite(parameters, epoch), times)
        residual = (observed - positions).ravel()
        jacobian = np.empty((residual.size, parameters.size))
        for column in range(parameters.size):
            moved = parameters.copy()
            moved[column] += steps[column]
            predicted, predicted_error = _predict(_satellite(moved, epoch), times)
            if np.any(predicted_error) or not np.all(np.isfinite(predicted)):
                return None
            jacobian[:, column] = ((predicted - positions).ravel()) / steps[column]
        delta = np.linalg.lstsq(jacobian, residual, rcond=None)[0]
        # Take a step only if it lowers the gap, halving it until it does: near i = 0 SGP4's deep-space model has
        # a kink (the Lyddane change), and full steps there swing back and forth without settling.
        for _ in range(8):
            tried = _rms(parameters + delta, epoch, times, observed)
            if tried < rms_km:
                break
            delta = delta / 2
        else:
            break                                   # no step helps: as good as it gets
        parameters, rms_km = parameters + delta, tried
        if np.all(np.abs(delta) < steps):
            break
    if not math.isfinite(rms_km) or rms_km > ORBIT_FIT_MAX_KM:
        return None

    n, eccentricity, inclination, node, perigee, mean_anomaly = _classical(parameters)
    row = {
        "CLASSIFICATION_TYPE": "U",
        "OBJECT_ID": object_id,
        "OBJECT_NAME": object_name or object_id,
        "EPHEMERIS_TYPE": 0,
        "ELEMENT_SET_NO": 999,
        "REV_AT_EPOCH": 0,
        "EPOCH": epoch.strftime("%Y-%m-%dT%H:%M:%S.%f"),
        "MEAN_MOTION": n * 1440 / (2 * math.pi),
        "ECCENTRICITY": eccentricity,
        "INCLINATION": math.degrees(inclination),
        "RA_OF_ASC_NODE": math.degrees(node),
        "ARG_OF_PERICENTER": math.degrees(perigee),
        "MEAN_ANOMALY": math.degrees(mean_anomaly),
        "BSTAR": 0.0,
        "MEAN_MOTION_DOT": 0.0,
        "MEAN_MOTION_DDOT": 0.0,
        "NORAD_CAT_ID": int(norad),
    }
    return as_history_row(row), rms_km


def _to_teme(utc, fixed):
    """Earth-fixed km -> TEME km, the frame SGP4's output uses."""
    at = _ts.from_datetime(utc)
    return TEME.rotation_at(at) @ itrs.rotation_at(at).T @ np.asarray(fixed, dtype=float)
