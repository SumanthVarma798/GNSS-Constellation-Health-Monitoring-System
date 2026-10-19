"""Values a person may want to adjust, in one place.

Addresses of outside sources live in evidence/sources.py. The system-letter
mapping lives in registry/constellations.csv.
"""
from datetime import timedelta
from pathlib import Path

# --- Requests to outside servers ---

REQUEST_TIMEOUT_SECONDS = 60  # how long to wait for any outside server
USER_AGENT = "gnss-evidence-archive/0.1 (scheduled research fetch)"  # how we name ourselves to them

# Each site's minimum gap between two of our requests to it. Every fetcher reads it here: the archive job and
# the dashboard. A site is a host name and every host under it ("reddit.com" covers www.reddit.com).
# Within one run the archive job waits out the gap, counted from the end of the last request; between runs,
# each group's schedule in .github/workflows/archive.yml must be at least as far apart as its longest gap (a test checks).
MIN_GAP_BETWEEN_DOWNLOADS = {
    # CelesTrak asks for one download per 2 hours at most, and blocked this machine on 17 Oct 2026 for more (issue 76).
    "celestrak.org": timedelta(hours=2),
    # Refused a second request three seconds after the first (8 and 19 Oct 2026); five subreddits read 150 s apart
    # all answered (19 Oct). Read once a day (issue 13). The real limit is not published for feeds (guess).
    "reddit.com": timedelta(minutes=2),
    # Seven search feeds in a row; how often Google allows them is not stated (guess).
    "news.google.com": timedelta(seconds=10),
}
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

ARCHIVE_OBJECTS_DIR = "objects"          # folder of raw copies, inside an archive folder
ARCHIVE_VERSIONS_FILE = "versions.csv"   # one row per change, inside an archive folder
ARCHIVE_VERSION_COLUMNS = ["address", "fetched_at", "status", "sha256", "bytes", "content_type", "wayback_url"]
# The run log: one line per run of a scheduled job, inside an archive folder. One file per job file
# (runs/archive.csv, runs/registry-update.csv), so two jobs saving at once never edit the same file.
ARCHIVE_RUNS_DIR = "runs"
# Each site in its back-off, one row per site, rewritten whole every run, inside an archive folder.
ARCHIVE_LIMITS_FILE = "limits.csv"
ARCHIVE_LIMIT_COLUMNS = ["site", "refusals", "last_answer", "refused_at", "wait_until"]
ARCHIVE_RUN_COLUMNS = ["job", "started", "ended", "result", "changed"]

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
CANDIDATE_SOCIAL_KIND = "social feed"  # kind of a social media feed: its posts count only for the link they hold
# A social post's own platform. A link to one of these is not a link to the post's source.
SOCIAL_PLATFORM_HOSTS = ("reddit.com", "redd.it", "redditmedia.com", "redditstatic.com")
# Links in a post that are not an article to check: countdown clocks, image hosts, videos. Skipped when
# looking for the post's source (an r/ISRO launch thread's first link was a countdown clock, 19 Oct 2026).
NOT_AN_ARTICLE_HOSTS = ("timeanddate.com", "imgur.com", "youtube.com", "youtu.be", "twitch.tv",
                        # another social post is a pointer too, never the source (r/roscosmos, 19 Oct 2026)
                        "x.com", "twitter.com", "facebook.com", "instagram.com", "linkedin.com", "t.me")

# One collected news item (issue 13): a pointer to an article, read from a feed. Not a claim; nothing here decides.
# source_id: who published the article (for a discovery or social feed, the linked page's host, decision 5);
# via: the feed it was read from; fetched_at: when our archive first held it.
NEWS_ITEM_COLUMNS = ["source_id", "address", "title", "published_at", "fetched_at", "via"]

# One row per archived feed, measured from the archive (issue 13): how often a copy changed per run of its group
# (to set cadence), and the share of its items that name a navigation system (a first signal-to-noise measure,
# until the hand-labelled set gives a better one). Measurements only: no grade or cadence changes by itself.
FEED_REPORT_COLUMNS = ["via", "group", "runs", "copies", "copies_per_run", "items", "items_naming_a_system",
                       "share_naming_a_system"]

# The hand-labelled set for choosing a claim-extraction model (issue 15, week 1). Kept here, beside the
# source lists, until the extraction step decides where its test data lives.
LABELLING_SHEET_FILE = Path(__file__).resolve().parent / "labelling_sheet.csv"
LABELLING_SHEET_COLUMNS = ["system", "title", "source_id", "published_at", "address", "claims_in_this_item", "none"]
LABELLING_SHEET_SIZE = 30
# Words that put an item under a system, for spreading the sheet across all six. Matched as whole words,
# any case. A cheap pointer, not the relevance filter: an item may name several systems or none.
SYSTEM_WORDS = {
    "GPS": ("GPS", "Navstar"),
    "GLONASS": ("GLONASS",),
    "Galileo": ("Galileo",),
    "BeiDou": ("BeiDou", "Compass navigation"),
    "QZSS": ("QZSS", "Michibiki", "QZS"),
    "NavIC": ("NavIC", "IRNSS", "NVS-01", "NVS-02", "NVS-03"),
}

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

# The catalogue's state codes (who owns the spacecraft), said in full.
COUNTRY_NAMES = {"IN": "India", "CN": "China", "US": "United States", "J": "Japan", "RU": "Russia",
                 "SU": "Soviet Union", "I-EU": "European Union", "I-ESA": "European Space Agency"}
COUNTRY_NOT_GIVEN = "not given"
