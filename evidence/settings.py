"""Values a person may want to adjust, in one place.

Addresses of outside sources live in evidence/sources.py. The system-letter
mapping lives in registry/constellations.csv.
"""
from pathlib import Path

# --- Requests to outside servers ---

REQUEST_TIMEOUT_SECONDS = 60  # how long to wait for any outside server
USER_AGENT = "gnss-evidence-archive/0.1 (scheduled research fetch)"  # how we name ourselves to them

# --- The raw-copy archive ---

MAX_COPY_BYTES = 50 * 1024 * 1024  # GitHub refuses files over 100 MB; stop well short of that
GONE_STATUSES = (404, 410)         # the page no longer exists: a change worth recording

ARCHIVE_OBJECTS_DIR = "objects"          # folder of raw copies, inside an archive folder
ARCHIVE_VERSIONS_FILE = "versions.csv"   # one row per change, inside an archive folder
ARCHIVE_VERSION_COLUMNS = ["address", "fetched_at", "status", "sha256", "bytes", "content_type", "wayback_url"]

# --- The registry tables ---

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "registry"

REGISTRY_SATELLITES_FILE = "satellites.csv"
REGISTRY_SATELLITE_COLUMNS = ["svn", "constellation", "block", "cospar_id", "catalogue_no",
                              "signal_id_now", "plane", "slot", "note"]

REGISTRY_SIGNAL_IDS_FILE = "signal_ids.csv"
REGISTRY_SIGNAL_ID_COLUMNS = ["svn", "signal_id", "valid_from", "valid_to", "note"]

REGISTRY_CONSTELLATIONS_FILE = "constellations.csv"  # kept by hand: system letter -> constellation
# Kept by hand: which satellites the dashboard tracks, in display order, and its name for each.
REGISTRY_DASHBOARD_SATELLITES_FILE = "dashboard_satellites.csv"

# Built from the General Catalog of Artificial Space Objects (GCAT): owner and status per satellite.
REGISTRY_CATALOGUE_FILE = "catalogue.csv"
# Our column name -> the catalogue's own column name. Values are kept exactly as the catalogue writes them.
GCAT_OBJECT_COLUMNS = {"cospar_id": "Piece", "name": "PLName", "owner": "Owner", "state": "State",
                       "status": "Status", "orbit_class": "OpOrbit"}                               # satcat.tsv
GCAT_PAYLOAD_COLUMNS = {"last_known_active": "TLast", "operations_ended": "TOp", "mission_result": "Result"}  # psatcat.tsv
REGISTRY_CATALOGUE_COLUMNS = ["svn", *GCAT_OBJECT_COLUMNS, *GCAT_PAYLOAD_COLUMNS]
GCAT_STILL_OPERATING = "*"  # in operations_ended: "believed to be still operating"
GCAT_MISSION_FAILED = "F"   # in mission_result: failed early in its mission
# The catalogue is released under CC-BY. This citation goes wherever its data is shown.
GCAT_CITATION = "data from GCAT (J. McDowell, planet4589.org/space/gcat)"

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

# --- Confidence: the grades, the bar and the labels ---

# The source table: one row per source, graded by a person. Changed only through review.
SOURCE_GRADES_FILE = Path(__file__).resolve().parent / "source_grades.csv"
SOURCE_GRADE_COLUMNS = ["source_id", "name", "reliability", "graded_by", "graded_on", "reason"]

# Source reliability, from the Admiralty code. The grade belongs to the source.
RELIABILITY_GRADES = {
    "A": "operator advisories and official documents",
    "B": "intergovernmental and scientific bodies",
    "C": "specialist press",
    "D": "general news",
    "E": "social media",
    "F": "unattributed posts",
}

# THE BAR an item must clear to reach the dashboard. A starting proposal, set by
# Sumanth on 8 Oct 2026, to be confirmed with Adithya. Each line is one rule.
GRADES_THAT_CLEAR_ALONE = ("A",)                 # the operator's own word is enough
GRADES_LIFTED_BY_A_SECOND_SOURCE = ("B",)        # clears when a second independent source agrees
GRADES_LIFTED_BY_OBSERVATION = ("B",)            # clears when our own orbit or signal data agrees
GRADES_THAT_COUNT_AS_A_SECOND_SOURCE = ("A", "B", "C", "D")  # social media and unattributed posts do not corroborate

# What a reader sees. Three levels, in words.
LABEL_CONFIRMED = "confirmed"
LABEL_PROBABLE = "probable"
LABEL_UNCONFIRMED = "unconfirmed"

# --- The query store ---

STORE_SCHEMA_FILE = Path(__file__).resolve().parent / "store_schema.sql"  # the evidence model, in one file
STORE_FILE = Path(__file__).resolve().parent.parent / "data" / "evidence.sqlite3"  # rebuilt each run; git-ignored

# --- The identity check ---

# Satellite blocks the GEO/IGSO dashboard is meant to cover.
DASHBOARD_BLOCKS = ("IRS-", "QZS-", "BDS-3G", "BDS-3I")

# --- The master map: which spacecraft is which, under every identifier ---

# How each identifier scheme is named to a reader.
SCHEME_NORAD = "US catalogue number (NORAD)"
SCHEME_COSPAR = "Launch designator (COSPAR)"
SCHEME_GCAT = "Catalogue of space objects (GCAT)"
SCHEME_SIGNAL_ID = "Signal ID today (PRN)"
SCHEME_ORBIT_FEED = "Orbit feed name (CelesTrak)"
SCHEME_DASHBOARD = "Dashboard name"

# The state of one identifier, as the page colours it.
MAP_OK = "ok"          # fine, or agrees with the other source
MAP_WARN = "warn"      # worth a person's look
MAP_IDLE = "idle"      # nothing to say yet
MAP_ACCENT = "accent"  # this dashboard's own choice

# Whether the two sources agree about who a spacecraft is.
IDENTITY_AGREE = "two sources agree"
IDENTITY_ONE_SOURCE = "one source only"
IDENTITY_DIFFER = "sources differ"

# Whether the two sources agree about it being in service.
SERVICE_AGREE_OPERATING = "agree: operating"
SERVICE_AGREE_NOT_IN_SERVICE = "agree: not in service"
SERVICE_DISAGREE = "disagree"
SERVICE_NOT_IN_CATALOGUE = "not in the catalogue yet"

ORBIT_FEED_FILES = "*_tles.json"  # in the bundled data folder: one file of element sets per system

# --- Burns: how often a satellite's orbit is corrected ---

# A FIRST PROPOSAL for the team to tune: how the cadence picture names a burn pattern.
BURN_MIN_FOR_PATTERN = 3           # fewer burns of one kind than this: "too few" to call a pattern
BURN_REGULAR_MAX_IQR_SHARE = 0.25  # "regular" when the spread (IQR) is at most this share of the median interval
BURN_TIMELINE_RECENT_DAYS = 90     # the burn timeline opens on this many days; the rest is a scroll away

# --- The master map canvas ---

# One letter on each leaf of a tree, per identifier scheme.
SCHEME_TAGS = {SCHEME_NORAD: "N", SCHEME_COSPAR: "C", SCHEME_SIGNAL_ID: "P", SCHEME_GCAT: "G",
               SCHEME_ORBIT_FEED: "F", SCHEME_DASHBOARD: "D"}

# How the Sources filter words the two sources' readings of one spacecraft.
SOURCES_AGREE = "agree"
SOURCES_DISAGREE = "disagree"
SOURCES_NOT_IN_CATALOGUE = "not in catalogue"

# The catalogue's state codes (who owns the spacecraft), said in full.
COUNTRY_NAMES = {"IN": "India", "CN": "China", "US": "United States", "J": "Japan", "RU": "Russia",
                 "SU": "Soviet Union", "I-EU": "European Union", "I-ESA": "European Space Agency"}
COUNTRY_NOT_GIVEN = "not given"
