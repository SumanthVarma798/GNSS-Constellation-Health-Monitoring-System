"""Addresses of the outside sources the pipeline reads.

Kept in one place so that a moved address is fixed once. Reliability grades
for each source belong in the source table, not here.
"""

# International GNSS Service: which physical satellite is which, with history.
IGS_SATELLITE_METADATA_URL = "https://files.igs.org/pub/station/general/igs_satellite_metadata.snx"

# General Catalog of Artificial Space Objects (GCAT), Jonathan McDowell: owner, state and
# status of every catalogued object, and when each payload stopped regular operations.
# Released under CC-BY; cite it (see GCAT_CITATION in evidence/settings.py).
GCAT_OBJECTS_URL = "https://planet4589.org/space/gcat/tsv/cat/satcat.tsv"     # about 19 MB
GCAT_PAYLOADS_URL = "https://planet4589.org/space/gcat/tsv/cat/psatcat.tsv"   # about 5 MB

# CelesTrak: current orbits of every catalogued BeiDou object.
CELESTRAK_BEIDOU_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=beidou&FORMAT=json"
# CelesTrak: current orbits of the navigation satellites in service, all six systems. The dashboard
# reads the same group live (data/celestrak.py); a daily copy kept here builds the history that GPS,
# GLONASS and Galileo have nowhere else without a Space-Track login.
CELESTRAK_GNSS_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=gnss&FORMAT=json"

# Galmon: signals heard live by a volunteer-run receiver network.
# On hold: do not read it until its maintainer has been told.
GALMON_SATELLITES_URL = "https://galmon.eu/svs.json"

# What the archive job keeps a raw copy of, by group. Each group is fetched on
# its own schedule, set in .github/workflows/archive.yml. Adding an address is
# a decision for a person: it starts scheduled requests to someone else's server.
ARCHIVED_SOURCES = {
    # Official documents and files. They change rarely.
    "documents": [
        IGS_SATELLITE_METADATA_URL,
    ],
    # Whole catalogues. Large, and regenerated daily with a new date line, so every
    # fetch is a new copy: about 24 MB a day. Fetched daily for now, by decision;
    # make it less often in archive.yml when the archive's size starts to matter.
    "catalogues": [
        GCAT_OBJECTS_URL,
        GCAT_PAYLOADS_URL,
    ],
    # Orbital elements. They change several times a day; kept once a day, by decision (issue 69).
    "orbital": [
        CELESTRAK_GNSS_URL,
    ],
    # News feeds and pages. They change all the time. No source yet.
    "news": [],
}


def archived_addresses(group=None):
    """The addresses of one group, or of every group when none is named."""
    groups = [group] if group else ARCHIVED_SOURCES
    return [address for name in groups for address in ARCHIVED_SOURCES[name]]
