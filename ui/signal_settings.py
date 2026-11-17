"""Which signals each satellite sends, and how we hear it: the stations and the names of the signals, in one place.

Change a value here by pull request. Nothing else needs editing.
"""

# The IGS observation files the daily check reads (scripts/signals_heard.py), from BKG's IGS data centre, open and with
# no login. Each station is a fixed receiver that records every signal it tracks, from every constellation it can,
# every 30 seconds. {BKG's station code: (short name, place, why this one)}. Together they put every constellation,
# the regional ones too, in view of at least one receiver that can track it (checked in their file headers, 16 Nov 2026).
STATIONS = {
    "IISC00IND": ("IISC", "Bengaluru, India", "under NavIC's coverage; its receiver also tracks QZSS and the four global constellations"),
    "MIZU00JPN": ("MIZU", "Mizusawa, Japan", "under QZSS's coverage; also tracks NavIC and the four global constellations"),
    "DARW00AUS": ("DARW", "Darwin, Australia", "the southern part of QZSS's and BeiDou's orbits; also tracks NavIC and the four global constellations"),
    "WTZR00DEU": ("WTZR", "Wettzell, Germany", "Europe: GPS, GLONASS, Galileo and BeiDou (its receiver does not track QZSS)"),
    "HRAO00ZAF": ("HRAO", "Hartebeesthoek, South Africa", "Africa and the southern hemisphere; tracks all six constellations"),
    "BOGT00COL": ("BOGT", "Bogota, Colombia", "the Americas: GPS, GLONASS, Galileo and BeiDou (its receiver does not track QZSS or NavIC)"),
}
FILES = "https://igs.bkg.bund.de/root_ftp/IGS/obs/{year}/{doy:03d}/{code}_R_{year}{doy:03d}0000_01D_30S_MO.crx.gz"
FOLDER = "https://igs.bkg.bund.de/root_ftp/IGS/obs/{year}/{doy:03d}/"
SAMPLE_EVERY = 20   # read one 30-second epoch in 20 (one in ten minutes). Our choice: a satellite in view stays in view for
                    # hours, so the day's signals are the same as from every epoch, for a twentieth of the reading.

# RINEX 3 observation codes. A code is a type letter, a band digit and an attribute letter ("C1C": pseudorange, band 1,
# attribute C). A satellite sends a signal if a receiver records a pseudorange (C) or carrier phase (L) code for it.
# Source: RINEX 3.05, section 5.1 and table A2 (https://files.igs.org/pub/data/format/rinex305.pdf), and for each
# signal's name the constellation's interface document: IS-GPS-200/705/800, Galileo OS SIS ICD, BeiDou ICD (B1I, B1C,
# B2a, B2b, B3I), GLONASS ICD, IS-QZSS-PNT, IRNSS ICD. {constellation letter: [(band digit, attribute letters, name)]}
SIGNALS = {
    "G": [("1", "C", "L1 C/A"), ("1", "SLX", "L1C"), ("1", "PWYMN", "L1 P(Y)"),
          ("2", "C", "L2 C/A"), ("2", "SLX", "L2C"), ("2", "PWYMND", "L2 P(Y)"),   # 2D: semi-codeless P(Y), not L2C
          ("5", "IQX", "L5")],
    "R": [("1", "CP", "G1"), ("4", "ABX", "G1a"), ("2", "CP", "G2"), ("6", "ABX", "G2a"), ("3", "IQX", "G3")],
    "E": [("1", "ABCXZ", "E1"), ("5", "IQX", "E5a"), ("7", "IQX", "E5b"), ("8", "IQX", "E5 (AltBOC)"),
          ("6", "ABCXZ", "E6")],
    "C": [("2", "IQX", "B1I"), ("1", "DPX", "B1C"), ("1", "ANSLZ", "B1A"), ("5", "DPX", "B2a"),
          ("7", "IQXDPZ", "B2b / B2I"), ("8", "DPX", "B2 (a+b)"), ("6", "IQX", "B3I"), ("6", "DPZ", "B3A")],
    "J": [("1", "C", "L1 C/A"), ("1", "SLX", "L1C"), ("1", "B", "L1Sb"), ("1", "Z", "L1S"), ("2", "SLX", "L2C"),
          ("5", "IQX", "L5"), ("5", "DPZ", "L5S"), ("6", "SLXEZ", "L6")],
    "I": [("5", "ABCX", "L5"), ("9", "ABCX", "S"), ("1", "DPX", "L1")],
}


def signal_name(system, code):
    """The plain signal name for a satellite of `system` ("G") and the band and attribute of an observation code
    ("1C"), or "band 1" when the table above does not know it, so a new code is shown, never dropped."""
    for band, attributes, name in SIGNALS.get(system, []):
        if code[0] == band and code[1:2] in attributes:
            return name
    return f"band {code[0]}"
