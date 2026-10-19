"""Positions from broadcast orbits. No network: the records are copied from the IGS merged
navigation file for 17 Oct 2026 (BRDC00IGS_R_20262900000_01D_MN.rnx, from BKG), and the expected
GPS positions from IGS's rapid precise orbits for the same day (IGS0OPSRAP_20262900000_01D_15M_ORB.SP3)."""
import math
from datetime import date, datetime, timedelta, timezone

from analysis.broadcast_orbit import nearest, position, read_navigation, system_time
from scripts.orbit_record_gap import compare

FILE = """\
     3.04           N: GNSS NAV DATA    M: MIXED            RINEX VERSION / TYPE
    18    18  1929     7                                    LEAP SECONDS
                                                            END OF HEADER
G05 2026 10 17 12 00 00-2.374444156890E-04-2.273736754430E-13 0.000000000000E+00
     7.900000000000E+01-3.321875000000E+01 4.205175162420E-09 1.338709451310E+00
    -1.775100827220E-06 5.256904172710E-03 4.507601261140E-06 5.153579437260E+03
     5.616000000000E+05-5.960464477540E-08 5.470402803660E-02-6.891787052150E-08
     9.824780880420E-01 3.054062500000E+02 1.514884101050E+00-7.996404510920E-09
     3.821587755900E-11 1.000000000000E+00 2.440000000000E+03 0.000000000000E+00
     2.000000000000E+00 0.000000000000E+00-1.024454832080E-08 7.900000000000E+01
     5.544180000000E+05 4.000000000000E+00
R01 2026 10 16 23 45 00 1.896703615785E-04 9.094947017729E-13 5.166000000000E+05
    -1.045852636719E+04-2.231695175171E+00 9.313225746155E-10 0.000000000000E+00
     4.523152832031E+03-2.190664291382E+00 9.313225746155E-10 1.000000000000E+00
     2.281736767578E+04-5.881071090698E-01-9.313225746155E-10 0.000000000000E+00
C01 2026 10 17 12 00 00-7.478520274160E-07 2.930988785010E-14 0.000000000000E+00
     1.000000000000E+00-2.178593750000E+02-4.695195573740E-09 2.297144286150E+00
    -7.024966180320E-06 5.678469315170E-04-3.177672624590E-06 6.493496223450E+03
     5.616000000000E+05 1.564621925350E-07 8.432227332110E-02 8.195638656620E-08
     9.448037562400E-02 9.485937500000E+01-2.967790660940E+00 5.844529162380E-09
     3.064413359400E-10 0.000000000000E+00 1.084000000000E+03 0.000000000000E+00
     2.000000000000E+00 0.000000000000E+00 4.499999928240E-09 4.500000000000E-09
     5.616000000000E+05 1.000000000000E+00
"""
# IGS rapid precise orbit of G05, km, at GPS time 12:00 and 13:00 on 17 Oct 2026.
G05_PRECISE = {datetime(2026, 10, 17, 12): (25239.490352, -5486.387798, 6051.054474),
               datetime(2026, 10, 17, 13): (25620.641883, -4676.168310, -5413.871684)}


def test_the_file_is_read_by_signal_id_and_glonass_is_skipped():
    records = read_navigation(FILE)
    assert set(records) == {"G05", "C01"}
    g05 = records["G05"][0]
    assert g05["toc"] == datetime(2026, 10, 17, 12) and g05["toe"] == 561600 and g05["sqrt_a"] == 5153.57943726


def test_gps_lands_within_5_m_of_the_precise_orbit():
    record = read_navigation(FILE)["G05"][0]
    for when, precise in G05_PRECISE.items():
        assert math.dist(position(record, when), precise) * 1000 < 5    # broadcast orbits are good to metres


def test_a_beidou_geostationary_satellite_stays_over_one_spot():
    record = read_navigation(FILE)["C01"][0]
    longitudes = []
    for hours in (-2, 0, 2):
        x, y, z = position(record, datetime(2026, 10, 17, 12) + timedelta(hours=hours))
        radius = math.sqrt(x * x + y * y + z * z)
        assert abs(radius - 42164) < 50 and abs(math.degrees(math.asin(z / radius))) < 5
        longitudes.append(math.degrees(math.atan2(y, x)))
    assert max(longitudes) - min(longitudes) < 0.5   # without the extra rotation it would turn with the Earth


def test_system_time_and_the_nearest_record():
    utc = datetime(2026, 10, 17, 11, 59, 42)
    assert system_time(utc, "G05", 18) == datetime(2026, 10, 17, 12)
    assert system_time(utc, "C01", 18) == datetime(2026, 10, 17, 11, 59, 46)   # BeiDou time is 14 s behind GPS
    records = read_navigation(FILE)["G05"]
    assert nearest(records, datetime(2026, 10, 17, 13)) is records[0]


def test_the_gap_report_finds_a_fresh_record_within_kilometres_and_skips_uncovered_hours():
    # CelesTrak's record of BeiDou-3 G4 (C01) from 19 Oct 2026 07:32, rolled back to 17 Oct.
    record = (datetime(2026, 10, 19, 7, 32, 57, tzinfo=timezone.utc),
              "1 56564U 23066A   26292.31455302 -.00000278  00000-0  00000+0 0  9994",
              "2 56564   0.4524   8.1520 0005748 207.1566  65.7354  1.00267984 12639")
    samples, used = compare(read_navigation(FILE)["C01"], [record], "C01", 18, date(2026, 10, 17))
    assert used == record[0] and 30 <= len(samples) <= 34      # only the hours the one broadcast record covers
    gaps = sorted(sample[0] for sample in samples)
    assert gaps[len(gaps) // 2] < 15                           # orbit records are good to kilometres, not hundreds
    assert all(abs(sample[4] - 140) < 0.5 for sample in samples)
