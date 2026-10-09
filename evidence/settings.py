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

# --- The query store ---

STORE_SCHEMA_FILE = Path(__file__).resolve().parent / "store_schema.sql"  # the evidence model, in one file
STORE_FILE = Path(__file__).resolve().parent.parent / "data" / "evidence.sqlite3"  # rebuilt each run; git-ignored

# --- The identity check ---

# Satellite blocks the GEO/IGSO dashboard is meant to cover.
DASHBOARD_BLOCKS = ("IRS-", "QZS-", "BDS-3G", "BDS-3I")
