"""Addresses of the outside sources the pipeline reads.

Kept in one place so that a moved address is fixed once. Reliability grades
for each source belong in the source table, not here.
"""
import csv

from evidence.settings import CANDIDATE_SOCIAL_KIND, CANDIDATE_WORKED, SOURCE_CANDIDATES_FILE

# International GNSS Service: which physical satellite is which, with history.
IGS_SATELLITE_METADATA_URL = "https://files.igs.org/pub/station/general/igs_satellite_metadata.snx"

# General Catalog of Artificial Space Objects (GCAT), Jonathan McDowell: owner, state and
# status of every catalogued object, and when each payload stopped regular operations.
# Released under CC-BY; cite it (see GCAT_CITATION in evidence/settings.py).
GCAT_OBJECTS_URL = "https://planet4589.org/space/gcat/tsv/cat/satcat.tsv"     # about 19 MB
GCAT_PAYLOADS_URL = "https://planet4589.org/space/gcat/tsv/cat/psatcat.tsv"   # about 5 MB

# CelesTrak: current orbits of every catalogued BeiDou object.
CELESTRAK_BEIDOU_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=beidou&FORMAT=json"
# CelesTrak: current orbit record (OMM, as JSON) of every satellite in its GNSS group, about
# 170 objects. Never TLE: CelesTrak ran out of 5-digit catalogue numbers on 11 Jul 2026, and
# newer objects cannot be written as TLE. CelesTrak asks for one download per 2 hours at most.
CELESTRAK_GNSS_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=gnss&FORMAT=json"

# Galmon: signals heard live by a volunteer-run receiver network.
# On hold: do not read it until its maintainer has been told.
GALMON_SATELLITES_URL = "https://galmon.eu/svs.json"


def working_candidates():
    """The candidate rows (issue 13) whose feed or page answered with something when checked.

    Each is provisional: collected, never deciding anything, until the team grades it.
    """
    with open(SOURCE_CANDIDATES_FILE, newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle)
                if row["check_status"] == CANDIDATE_WORKED and int(row["check_bytes"] or 0) > 0]


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
    # Orbit records. They change several times a day, so nearly every fetch is a new
    # copy: about 130 KB a day (guess, from 170 objects). Kept so the age of each
    # satellite's record can be measured over time, without a Space-Track login.
    "orbital": [
        CELESTRAK_GNSS_URL,
    ],
    # News feeds and pages: every candidate whose check worked (evidence/source_candidates.csv), except
    # social media. Feeds change several times a day; the cadence is being measured (issue 13).
    "news": [row["address"] for row in working_candidates() if row["kind"] != CANDIDATE_SOCIAL_KIND],
    # Social media feeds, read rarely: Reddit refuses a second request in quick succession. A post counts
    # only for the link it holds (decision 5).
    "social": [row["address"] for row in working_candidates() if row["kind"] == CANDIDATE_SOCIAL_KIND],
}
# Groups read from the candidate list: provisional sources, archived before the team grades them.
PROVISIONAL_GROUPS = ("news", "social")


def archived_addresses(group=None):
    """The addresses of one group, or of every group when none is named."""
    groups = [group] if group else ARCHIVED_SOURCES
    return [address for name in groups for address in ARCHIVED_SOURCES[name]]
