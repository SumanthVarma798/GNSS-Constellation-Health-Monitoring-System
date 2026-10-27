"""Settings for the latest-news file the dashboard reads."""
from collections import OrderedDict

# The branch that holds the latest-news file for the dashboard.
NEWS_BRANCH = "news-data"
# The latest-news file name on that branch.
NEWS_FILE_NAME = "latest_news.json"
# The public URL the dashboard reads, with no key.
NEWS_URL = ("https://raw.githubusercontent.com/SumanthVarma798/GNSS-Constellation-Health-Monitoring-System/"
            f"{NEWS_BRANCH}/{NEWS_FILE_NAME}")

# The newest items kept per constellation.
NEWS_ITEMS_PER_SYSTEM = 150
# Items published longer ago than this stay in the archive but are left out of the latest-news file.
NEWS_MAX_AGE_DAYS = 365
# The summary is cut at this many characters.
SUMMARY_CHARACTERS = 300
# These feed kinds may match systems from feed text when the headline names none.
NEWS_TEXT_MATCH_KINDS = ("Substack feed", "newsletter feed")

# News collection runs on this cadence.
NEWS_CYCLE_HOURS = 3
# News older than this is shown as late.
NEWS_LATE_HOURS = 7

# Bars a source record must meet for B, C or D: (checked claims at least, score at least).
GRADE_BARS = OrderedDict([("B", (10, 0.90)), ("C", (5, 0.75)), ("D", (3, 0.50))])
# With this many checked claims, a source at least reaches E.
GRADE_E_MIN_CLAIMS = 3
# A grade drops only once score falls this far below that grade's score bar.
GRADE_DROP_MARGIN = 0.05
# Source-record scoring looks back this many days.
RECORD_WINDOW_DAYS = 365
# A launch claim may be this many days before the launch date and still hold.
LAUNCH_DAYS_BEFORE = 3
# A launch claim may be this many days after the launch date and still hold.
LAUNCH_DAYS_AFTER = 1
# If no check succeeded after this many days, the result becomes "could not check".
CHECK_GIVE_UP_DAYS = 30
# Corroboration counts only within this many days after the claim.
CORROBORATION_DAYS = 30
# A corroborated claim contributes this share of a held claim's weight.
CORROBORATION_WEIGHT = 0.5
# Only these grades may corroborate another source's claim.
CORROBORATING_GRADES = ("A", "B")
# A source on B is shortlisted for A at this bar: (claims, score, no-failed days).
SHORTLIST_FOR_A = (20, 0.95, 90)
# A disagreement finding needs at least this many steps between grades.
DISAGREEMENT_STEPS = 2
# A disagreement finding needs at least this many checked claims.
DISAGREEMENT_MIN_CLAIMS = 5
# This marks grades set by the weekly source-record job and approved on the Approvals page.
RECORD_GRADED_BY = "the source record (weekly job), approved on the Approvals page"
# A rejected move is proposed again only after this many more checked claims for that source.
REJECTED_WAIT_CLAIMS = 3
# The weekly source-record proposal branch.
SOURCE_RECORD_BRANCH = "source-record"
# The decision label on source-record proposals.
SOURCE_RECORD_LABEL = "decision: source grade"

# Rules for category names by words in the headline, then the summary (first match wins).
NEWS_CATEGORIES = OrderedDict([
    ("launch", ("launch", "launched", "launches", "launching", "lift-off", "liftoff", "lifts off", "into orbit",
                "put into orbit", "rocket", "launch vehicle", "H3", "Long March", "Falcon 9", "Soyuz", "Ariane",
                "PSLV", "GSLV", "Vulcan")),
    ("satellite status and outages", ("outage", "outages", "anomaly", "failure", "failed", "fails", "fault",
                                      "malfunction", "out of service", "unhealthy", "unusable", "decommissioned",
                                      "retired", "end of life", "lost", "clock failure", "degraded")),
    ("signal and service", ("signal", "signals", "jamming", "jammed", "spoofing", "spoofed", "interference",
                            "accuracy", "service", "services", "open service", "high accuracy", "PPP", "SBAS",
                            "augmentation", "authentication", "frequency", "L1", "L5", "E6", "timing")),
    ("programme and policy", ("contract", "contracts", "funding", "budget", "agreement", "policy", "programme",
                              "program", "regulation", "minister", "ministry", "government", "procurement",
                              "strategy", "award", "awarded", "modernisation", "modernization", "plan", "plans")),
    ("other", ()),
])

# Category rules: checked in order on the headline first; if none match there, checked in order on the summary.
CATEGORY_RULE_WORDS = ('Categories are checked in order: first the headline is checked against every category; only when '
                       'none matches, the feed text is checked in the same order; no match is "other".')
