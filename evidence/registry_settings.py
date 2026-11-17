"""The registry tables' file names and column lists, in one place.

The tables are plain text in registry/ so that every change shows up as a
line-by-line difference a person can review. Their readers import these
names from here; see registry/README.md.
"""
from pathlib import Path

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "registry"

REGISTRY_SATELLITES_FILE = "satellites.csv"
REGISTRY_SATELLITE_COLUMNS = ["svn", "constellation", "block", "cospar_id", "catalogue_no",
                              "signal_id_now", "plane", "slot", "note"]

REGISTRY_SIGNAL_IDS_FILE = "signal_ids.csv"
REGISTRY_SIGNAL_ID_COLUMNS = ["svn", "signal_id", "valid_from", "valid_to", "note"]

# Built by scripts/build_registry.py: satellites CelesTrak's GNSS group lists before the IGS file does, in
# satellites.csv's columns, each under a stand-in SVN (system letter, "-", catalogue number). A row leaves when the
# IGS file lists its catalogue number.
REGISTRY_SIGHTINGS_FILE = "sightings.csv"
# CelesTrak names that make a sighting, by system: how its GNSS group names each system's satellites today (GPS
# "GPS BIII-9 (PRN 01)", GLONASS "COSMOS 2620 (709K)", Galileo "GSAT0234 (GALILEO 34)", BeiDou "BEIDOU-3 M23 (C45)", QZSS
# "QZS-6 (QZSS/PRN 200)", NavIC "NVS-03 (IRNSS-1L)"). The augmentation satellites in the group (EGNOS, WAAS, GAGAN, SDCM)
# belong to none of these and match none. The IGS file took weeks to list NVS-03; it can be as slow for any system.
SIGHTING_NAMES = {"GPS": r"^GPS ", "GLONASS": r"^COSMOS \d+ \(", "Galileo": r"^GSAT0\d+", "BeiDou": r"^BEIDOU-",
                  "QZSS": r"^QZS-", "NavIC": r"^(IRNSS|NVS)-"}

REGISTRY_UNIDENTIFIED_FILE = "unidentified.csv"   # payloads in a navigation orbit that no other registry table lists
REGISTRY_UNIDENTIFIED_COLUMNS = ["catalogue_no", "name", "cospar_id", "launched", "orbit", "period_minutes",
                                 "inclination_degrees"]

REGISTRY_CONSTELLATIONS_FILE = "constellations.csv"  # kept by hand: system letter -> constellation
# Kept by hand: which satellites the dashboard tracks, in display order, and its name for each.
REGISTRY_DASHBOARD_SATELLITES_FILE = "dashboard_satellites.csv"
REGISTRY_DASHBOARD_SATELLITE_COLUMNS = ["svn", "dashboard_name", "added"]
REGISTRY_DASHBOARD_SYSTEMS_FILE = "dashboard_systems.csv"  # kept by hand: one row per dashboard page system
# The tracked list that must stay in step with today's signal IDs when the registry is rebuilt.
REGISTRY_DASHBOARD_TRACKED_SYSTEMS = ("GPS", "GLONASS", "Galileo")
# Kept by hand: satellites with a signal ID today that the dashboard leaves out on purpose, each with why and a source.
# Every satellite with a signal ID is either tracked or listed here (tests/test_registry_coverage.py).
REGISTRY_LEFT_OUT_FILE = "left_out.csv"
REGISTRY_LEFT_OUT_COLUMNS = ["svn", "name", "reason", "source"]
NEW_ON_DASHBOARD_DAYS = 30  # a tracked satellite is shown as "new" on the dashboard for this many days

# Built from the General Catalog of Artificial Space Objects (GCAT): owner and status per satellite.
REGISTRY_CATALOGUE_FILE = "catalogue.csv"
# Our column name -> the catalogue's own column name. Values are kept exactly as the catalogue writes them.
GCAT_OBJECT_COLUMNS = {"cospar_id": "Piece", "name": "PLName", "owner": "Owner", "state": "State",
                       "status": "Status", "orbit_class": "OpOrbit"}                               # satcat.tsv
GCAT_PAYLOAD_COLUMNS = {"last_known_active": "TLast", "operations_ended": "TOp", "mission_result": "Result"}  # psatcat.tsv
REGISTRY_CATALOGUE_COLUMNS = ["svn", *GCAT_OBJECT_COLUMNS, *GCAT_PAYLOAD_COLUMNS]

# Column name -> how to say it to a reader who does not write software.
REGISTRY_COLUMN_PLAIN_NAMES = {
    "constellation": "constellation",
    "block": "design generation",
    "cospar_id": "launch designator",
    "catalogue_no": "catalogue number",
    "signal_id_now": "signal ID",
    "plane": "plane",
    "slot": "slot",
    "note": "note",
}
