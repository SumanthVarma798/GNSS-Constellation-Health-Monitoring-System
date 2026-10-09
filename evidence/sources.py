"""Addresses of the outside sources the pipeline reads.

Kept in one place so that a moved address is fixed once. Reliability grades
for each source belong in the source table, not here.
"""

# International GNSS Service: which physical satellite is which, with history.
IGS_SATELLITE_METADATA_URL = "https://files.igs.org/pub/station/general/igs_satellite_metadata.snx"

# CelesTrak: current orbits of every catalogued BeiDou object.
CELESTRAK_BEIDOU_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=beidou&FORMAT=json"

# Galmon: signals heard live by a volunteer-run receiver network.
# On hold: do not read it until its maintainer has been told.
GALMON_SATELLITES_URL = "https://galmon.eu/svs.json"

# Addresses the archive job keeps a raw copy of. Adding one here is a decision
# for a person: it starts scheduled requests to someone else's server.
ARCHIVED_ADDRESSES = [
    IGS_SATELLITE_METADATA_URL,
]
