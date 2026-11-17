"""Words for a change to the registry tables, as the console's Approvals page and the weekly job's pull request say
it: what each table is, where its rows come from, what the dashboard shows from it, and which changes are routine.
The reading is in evidence/table_changes.py. A file not listed here is shown as a file, by its lines.
"""
from evidence.library_settings import LIBRARY_COUNTS_COLUMNS, LIBRARY_MATCHING_COLUMNS
from evidence.settings import SOURCE_LINKS
from evidence.registry_settings import (
    REGISTRY_CATALOGUE_COLUMNS,
    REGISTRY_DASHBOARD_SATELLITE_COLUMNS,
    REGISTRY_COLUMN_PLAIN_NAMES,
    REGISTRY_LEFT_OUT_COLUMNS,
    REGISTRY_SATELLITE_COLUMNS,
    REGISTRY_SIGNAL_ID_COLUMNS,
    REGISTRY_UNIDENTIFIED_COLUMNS
)
from evidence.sources import IGS_SATELLITE_METADATA_URL

# Each source by its full name, never "the file" or "the catalogue", with where a reader can check it.
IGS = ("the IGS satellite metadata file", IGS_SATELLITE_METADATA_URL)
GCAT = ("GCAT, J. McDowell's catalogue of space objects", SOURCE_LINKS["GCAT"])
CELESTRAK = ("CelesTrak's list of GNSS satellites", "https://celestrak.org/NORAD/elements/gp.php?GROUP=gnss&FORMAT=tle")
SPACE_TRACK = ("Space-Track's list of payloads launched lately", SOURCE_LINKS["Space-Track"])
BY_HAND = ("the team, by hand", "")

# Per table (its path in the repository):
#   name     what it is, in a few words
#   columns  its columns, in order (the diff GitHub gives often has no heading line)
#   key      the columns that pick out one row; label: the columns that name a row to a reader (default: key)
#   source   where its rows come from
#   shows    {dashboard page: what that page shows from it}; empty when no page reads it
#   routine  columns whose change is expected every week (years add up, a source's date moves on): a row changed only
#            in these is counted as routine and kept out of the way
#   flag_added  a row added here always needs a person's look: (what one is called, what many are called, why)
TABLES = {
    "registry/satellites.csv": {
        "name": "Satellites", "columns": REGISTRY_SATELLITE_COLUMNS, "key": ("svn",), "source": IGS,
        "shows": {"Master map": "the satellites", "Library": "the satellites", "Overview": "the 3D view"}},
    "registry/signal_ids.csv": {
        "name": "Signal-ID history", "columns": REGISTRY_SIGNAL_ID_COLUMNS, "key": ("svn", "signal_id", "valid_from"),
        "label": ("svn", "signal_id"), "source": IGS,
        "shows": {"Master map": "signal IDs", "Library": "each satellite's timeline"}},
    "registry/dashboard_satellites.csv": {
        "name": "Satellites the dashboard tracks", "columns": REGISTRY_DASHBOARD_SATELLITE_COLUMNS, "key": ("svn",),
        "label": ("svn", "dashboard_name"), "source": IGS,
        "shows": {"Overview, Station-keeping and Geometry": "which satellites are tracked",
                  "Master map": "which satellites are tracked"}},
    "registry/sightings.csv": {
        "name": "Satellites seen before the IGS file lists them", "columns": REGISTRY_SATELLITE_COLUMNS, "key": ("svn",),
        "source": CELESTRAK, "shows": {"Master map": "the satellites", "Overview": "the 3D view"}},
    "registry/catalogue.csv": {
        "name": "Owner and status of each satellite", "columns": REGISTRY_CATALOGUE_COLUMNS, "key": ("svn",),
        "source": GCAT, "shows": {"Master map": "owner and status", "Library": "owner and status"}},
    "registry/library_counts.csv": {
        "name": "Library counts", "columns": LIBRARY_COUNTS_COLUMNS, "key": ("system", "programme"), "label": ("programme",),
        "source": GCAT, "shows": {"Library": "the counts", "Master map": "GCAT's date"},
        "routine": ("years_retired", "years_operating", "gcat_updated")},
    "registry/library_matching.csv": {
        "name": "How registry satellites were found in GCAT", "columns": LIBRARY_MATCHING_COLUMNS, "key": ("system",),
        "source": GCAT, "shows": {"Library": "the note on how satellites were matched"}},
    "registry/unidentified.csv": {
        "name": "Payloads not identified yet", "columns": REGISTRY_UNIDENTIFIED_COLUMNS, "key": ("catalogue_no",),
        "label": ("name", "cospar_id"), "source": SPACE_TRACK, "shows": {},
        "flag_added": ("payload not identified", "payloads not identified",
                       "Nothing is tracked from them until a person says what they are.")},
    "registry/left_out.csv": {
        "name": "Satellites the dashboard leaves out on purpose", "columns": REGISTRY_LEFT_OUT_COLUMNS, "key": ("svn",),
        "label": ("svn", "name"), "source": BY_HAND, "shows": {"Overview": "which satellites are left out"}},
}

# What a routine change is, in words, for the tables that have routine columns.
ROUTINE_WORDS = {"registry/library_counts.csv": "years in service and GCAT's date only"}

# Column name -> words, for the columns the registry's own plain names do not cover.
COLUMN_WORDS = {
    **REGISTRY_COLUMN_PLAIN_NAMES,
    "svn": "SVN", "signal_id": "signal ID", "valid_from": "from", "valid_to": "until", "dashboard_name": "name on the dashboard",
    "added": "added on", "cospar_id": "launch designator", "catalogue_no": "catalogue number", "name": "name",
    "owner": "owner", "state": "country", "status": "status", "orbit_class": "orbit", "last_known_active": "last known active",
    "operations_ended": "operations ended", "mission_result": "mission result",
    "programme": "programme", "failed_at_launch": "failed at launch", "failed_in_orbit": "failed in orbit",
    "status_not_recorded": "status not recorded", "years_retired": "years in service, retired",
    "years_operating": "years in service, operating", "approximate_dates": "approximate dates",
    "first_launch": "first launch", "last_launch": "last launch", "gcat_updated": "GCAT's date",
    "registry_satellites": "registry satellites", "registry_found_in_gcat": "found in GCAT",
    "registry_not_in_gcat": "not found in GCAT", "also_found_by_programme": "also found by programme",
    "found_by_programme_only": "found by programme only", "registry_and_programme_disagree": "registry and programme disagree",
    "period_minutes": "period (minutes)", "inclination_degrees": "inclination (degrees)", "reason": "why", "source": "source",
}

NAMED_AT_MOST = 3   # rows named in a one-line summary; the rest are counted
