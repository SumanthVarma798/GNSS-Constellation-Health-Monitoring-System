"""Values a person may want to adjust, in one place.

Registry table names and columns live in evidence/registry_settings.py.
News-only settings live in evidence/news_settings.py. Words only one dashboard
page reads live beside that page (ui/orbit_age_settings.py,
ui/official_status_settings.py, ui/figures/burns_settings.py, and
ui/master_map_settings.py). Addresses of outside sources live in
evidence/sources.py. The system-letter mapping lives in registry/constellations.csv.
"""
from datetime import timedelta
from pathlib import Path

# --- Requests to outside servers ---

REQUEST_TIMEOUT_SECONDS = 60  # how long to wait for any outside server
USER_AGENT = "gnss-evidence-archive/0.1 (scheduled research fetch)"  # how we name ourselves to them
ORBIT_ALERT_DAYS = 2  # an orbit record this many days old raises an alert (the team's limit is 3; a day of buffer)
ORBIT_STALE_DAYS = 3  # this old, the dashboard shows it as stale (the team's limit)
ORBIT_FIT_MIN_SAMPLES = 12  # fewer broadcast positions than this is not enough to fit an orbit record
ORBIT_FIT_MAX_KM = 5  # a fit this far off its broadcast positions is a burn, so the satellite is left out

# Each site's minimum gap between two of our requests to it. Every fetcher reads it here: the archive job and
# the dashboard. A site is a host name and every host under it ("reddit.com" covers www.reddit.com).
# Within one run the archive job waits out the gap, counted from the end of the last request; between runs,
# each group's schedule in .github/workflows/archive.yml must be at least as far apart as its longest gap (a test checks).
MIN_GAP_BETWEEN_DOWNLOADS = {
    # CelesTrak asks for one download per 2 hours at most, and blocked this machine on 17 Oct 2026 for more (issue 76).
    "celestrak.org": timedelta(hours=2),
    # Space-Track asks that class gp is read no more than once an hour, and says each login is capped at 30 requests
    # a minute and 300 an hour (its API documentation; to confirm).
    "space-track.org": timedelta(hours=1),
    # Refused a second request three seconds after the first (8 and 19 Oct 2026); five subreddits read 150 s apart
    # all answered (19 Oct). Read once a day (issue 13). The real limit is not published for feeds (guess).
    "reddit.com": timedelta(minutes=2),
    # Seven search feeds in a row; how often Google allows them is not stated (guess).
    "news.google.com": timedelta(seconds=10),
}
# How often the dashboard looks for a newer copy of CelesTrak's GNSS group on GitHub (latest_gnss.json on branch
# orbit-data). Reading a raw GitHub file is cheap and CelesTrak is not asked, so this is not bound by the 2-hour gap
# above. The archive job publishes a new copy every 2 hours, a few minutes after its run starts (archive.yml), so a
# look every 20 minutes shows a published copy within about 20 minutes of its publication.
COPY_LOOK_GAP = timedelta(minutes=20)
# Where the archive job publishes what the dashboard reads (branch orbit-data), and how often Home's counts are made
# anyway when the orbit copy has not changed (the orbit-checks files and the clock still move them).
ORBIT_DATA_URL = "https://raw.githubusercontent.com/SumanthVarma798/GNSS-Constellation-Health-Monitoring-System/orbit-data/"
HOME_COUNT_EVERY = timedelta(hours=8)
# A scheduled or manual run does not download from these sites when the archive's run log shows a run asked them less
# than the site's FULL minimum gap ago (no slack: CelesTrak's rule is strict, and it blocked us on 17 Oct). A scheduled run
# that GitHub starts a few minutes early is skipped, and the next one, 2 hours later, fetches. This also keeps a manual
# run of the orbital group from asking CelesTrak again right after a scheduled one.
RUN_GATED_SITES = ("celestrak.org",)
RUN_GATE_SLACK = timedelta(0)
DEFAULT_MIN_GAP = timedelta(seconds=5)  # any other site: no stated limit, so a polite pause
# The most one run of a group may spend waiting out gaps, so it ends well inside archive.yml's 30-minute fetch step.
RUN_WAIT_BUDGET = timedelta(minutes=15)

DOWNLOAD_TRIES = 3                # a failed download is tried this many times in one run...
WAIT_BETWEEN_TRIES_SECONDS = 60   # ...with this wait between, unless that is shorter than the source's gap: then once
RETRY_STATUSES = (429, 500, 502, 503, 504)  # replies worth another try; any other reply is the source's answer

# A site that refuses us, or does not answer at all, is not asked again until its back-off has passed:
# BACKOFF_FIRST after the first refusal, doubling with each refusal in a row, never longer than BACKOFF_LONGEST.
# One good answer clears it. Kept across runs in the archive's ARCHIVE_LIMITS_FILE.
REFUSAL_STATUSES = (403, 429)
BACKOFF_FIRST = timedelta(hours=1)
BACKOFF_LONGEST = timedelta(days=7)

# Never fetched, by any job or any person's script: the Russian and Chinese satellite-tracker sites named on
# the 17 Oct 2026 call. They may be malicious; what they show reaches us only through independent journalists.
NEVER_FETCH = ("vimpel", "spacemapper")  # matched anywhere in a host name

# --- The raw-copy archive ---

MAX_COPY_BYTES = 50 * 1024 * 1024  # GitHub refuses files over 100 MB; stop well short of that
GONE_STATUSES = (404, 410)         # the page no longer exists: a change worth recording
ARCHIVE_THIN_FROM_BYTES = 5 * 1024 * 1024  # copies this size or larger may leave the checkout; today only the GCAT tables
ARCHIVE_THIN_AFTER_DAYS = 14              # an old copy this many days after it was fetched may be thinned
# Only groups whose readers need just the newest copy are thinned: evidence/news.py re-reads every copy of
# every news, social and X feed, so those groups keep all of theirs.
ARCHIVE_THIN_GROUPS = ("documents", "catalogues", "orbital")

ARCHIVE_OBJECTS_DIR = "objects"          # folder of raw copies, inside an archive folder
ARCHIVE_VERSIONS_FILE = "versions.csv"   # one row per change, inside an archive folder
ARCHIVE_VERSION_COLUMNS = ["address", "fetched_at", "status", "sha256", "bytes", "content_type", "wayback_url"]
# The run log: one line per run of a scheduled job, inside an archive folder. One file per job file
# (runs/archive.csv, runs/registry-update.csv, runs/orbit-ages.csv), so two jobs saving at once never edit the same file.
# The orbit-age table (runs/orbit-age-by-satellite.csv) is also in this folder: one line per tracked satellite per run.
ARCHIVE_RUNS_DIR = "runs"
# Each site in its back-off, one row per site, rewritten whole every run, inside an archive folder.
ARCHIVE_LIMITS_FILE = "limits.csv"
ARCHIVE_LIMIT_COLUMNS = ["site", "refusals", "last_answer", "refused_at", "wait_until"]
ARCHIVE_RUN_COLUMNS = ["job", "started", "ended", "result", "changed"]
ORBIT_AGE_COLUMNS = ["day", "checked", "constellation", "satellite", "norad", "epoch", "source", "age_days", "status"]
# --- The registry tables ---

# Space-Track lists a new payload as soon as it is tracked, weeks before the IGS file does. It says the object exists,
# not that it is a navigation satellite or whose, so a payload launched in the last RECENT_LAUNCH_DAYS days is only
# picked out by its orbit (the geosynchronous band starts at 1380 because NVS-03 sat at 1407 minutes while still being raised): (name, period in minutes, inclination in degrees). A person decides what it is.
# ponytail: geostationary navigation satellites (inclination near 0) look like every communications satellite, so this
# cannot find them; add a way to name one by hand if that matters.
RECENT_LAUNCH_DAYS = 60
NAVIGATION_ORBITS = (("medium Earth orbit", (670, 860), (50, 66)),
                     ("inclined geosynchronous orbit", (1380, 1450), (25, 60)))
# Built from the General Catalog of Artificial Space Objects (GCAT): owner and status per satellite.
GCAT_STILL_OPERATING = "*"  # in operations_ended: "believed to be still operating"
GCAT_MISSION_FAILED = "F"   # in mission_result: failed early in its mission
# The catalogue is released under CC-BY. This citation goes wherever its data is shown.
GCAT_CITATION = "data from GCAT (J. McDowell, planet4589.org/space/gcat)"

# Where each source named in a tooltip leads: its own page (ui/tooltip.py makes the name a link). Add a source here and
# every tooltip that names it links to it.
SOURCE_LINKS = {"GCAT": "https://planet4589.org/space/gcat/", "CelesTrak": "https://celestrak.org/",
                "Space-Track": "https://www.space-track.org/", "IGS": "https://igs.org/",
                "BKG": "https://igs.bkg.bund.de/", "Natural Earth": "https://www.naturalearthdata.com/"}

# --- Confidence: the grades, the bar and the labels ---

# The source table: one row per source, graded by a person. Changed only through review.
SOURCE_GRADES_FILE = Path(__file__).resolve().parent / "source_grades.csv"
SOURCE_GRADE_COLUMNS = ["source_id", "name", "reliability", "graded_by", "graded_on", "reason"]
# Checked claims per source, appended as checks complete.
SOURCE_RECORD_FILE = Path(__file__).resolve().parent / "source_record.csv"
# Rejected source-grade findings: source, finding id, claim count then, and decision day.
SOURCE_RECORD_REJECTED_FILE = Path(__file__).resolve().parent / "source_record_rejected.csv"
SOURCE_RECORD_REJECTED_COLUMNS = ["source_id", "finding_id", "claims_at_rejection", "decided_on"]

# Candidate sources for the news pipeline (issue 13), one row per feed or page. Each address was fetched once;
# where it failed, up to two other addresses were tried, and the row records the last one.
# Proposals only: a grade counts once the team moves it into the source table. The rows whose check worked
# are archived on a schedule (evidence/sources.py), and decide nothing.
SOURCE_CANDIDATES_FILE = Path(__file__).resolve().parent / "source_candidates.csv"
SOURCE_CANDIDATE_COLUMNS = ["source_id", "name", "kind", "address", "checked_on", "check_status", "check_type",
                            "check_bytes", "check_items", "proposed_grade", "grade_reason", "standing", "note"]
CANDIDATE_GRADED = "graded"  # already in the source table; the proposed grade must match it
CANDIDATE_STANDINGS = ("provisional", CANDIDATE_GRADED, "no grade: discovery or pointer", "held: not fetched")
CANDIDATE_WORKED = "200"         # check_status of a row whose feed or page answered
CANDIDATE_FEED_TYPE = "feed"     # check_type starts with this when the answer was a feed a program can read
CANDIDATE_X_KIND = "X account"  # an X account read through twitterapi.io (evidence/x_reader.py): its posts are its own
CANDIDATE_SOCIAL_KIND = "social feed"  # kind of a social media feed: its posts count only for the link they hold
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

# --- The master map canvas ---

# Who issues each kind of identifier, as a card says it when zoomed close.
SCHEME_ISSUERS = {SCHEME_NORAD: "the US Space Force space catalogue, via Space-Track",
                  SCHEME_COSPAR: "COSPAR",
                  SCHEME_GCAT: "GCAT, Jonathan McDowell",
                  SCHEME_ORBIT_FEED: "CelesTrak",
                  SCHEME_DASHBOARD: "this project's registry"}
# A signal ID is issued by the operator of its system. Keyed by constellation name, as in constellations.csv.
SIGNAL_ID_ISSUERS = {"NavIC": "ISRO", "QZSS": "Cabinet Office of Japan", "BeiDou": "China Satellite Navigation Office",
                     "GPS": "US Space Force", "Galileo": "European Union (EUSPA)", "GLONASS": "Roscosmos"}
# Said instead of a date when the repository keeps no record of when a value was last checked.
NOT_RECORDED = "not recorded"

# Our sources, as the hover card names them, and what one says when it does not hold an identifier.
SOURCE_IGS = "IGS satellite file"
SOURCE_GCAT = "GCAT"
SOURCE_ORBIT_FEED = "CelesTrak orbit feed"
SOURCE_DASHBOARD = "our dashboard registry"
SOURCE_SILENT = "does not carry it"
SOURCE_SIGHTING = "CelesTrak GNSS group"  # where a sighting's (registry/sightings.csv) numbers come from
# What a card says for a field only the IGS file gives.
NOT_YET_KNOWN = "not yet known"
