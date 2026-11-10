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
NEWS_TEXT_MATCH_KINDS = ("Substack feed", "newsletter feed", "X account")

# News collection runs on this cadence.
NEWS_CYCLE_HOURS = 3
# Two titles are one article when, written plainly (quotes, punctuation, case and letter styles set aside), they are the
# same or one is the start of the other and at least this long: a headline cut short ("...") or with the outlet's name
# added ("– Tech Times") is still the same article. The start must also be most of the longer title: "ISRO successfully
# launches NVS-03 satellite" is another outlet's shorter headline, not a cut-off copy of "...; India's NavIC system restored".
NEWS_SAME_TITLE_PREFIX = 40
NEWS_SAME_TITLE_SHARE = 0.7
# An item is new when it was published after the reader's last visit, less this many hours: a feed can carry an article
# a few hours after it went out. One published days earlier and found late (Google News re-lists old articles) is not new.
NEWS_NEW_GRACE_HOURS = 2 * NEWS_CYCLE_HOURS
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

# Stories on the News page: items that say the same thing are shown once, with every source that said it
# (evidence/news_stories.py). Two headlines tell one story when they share a mission or satellite ID (NVS-03,
# GSLV-F18, SV10), or share at least STORY_SHARED_WORDS words that are not common in that constellation's news,
# making up at least STORY_SHARE of the shorter headline. Items in a story share a category, and each is
# published within STORY_DAYS of one already in it.
STORY_DAYS = 10
STORY_SHARE = 0.5
STORY_SHARED_WORDS = 2
# A word in more than this share of the shown items (and in more than 3) says nothing about which story it is.
STORY_COMMON_SHARE = 0.15
# Headlines sharing at least this share of all their words are the same story, even when those words are common.
STORY_NEAR_SAME = 0.8
# A story's own words, marked on the page: in at least this share of its reports (and in at least 2).
STORY_TOLD_SHARE = 0.25
# A headline longer than this (a social post, a whole first paragraph) heads a story only when every report's is.
STORY_HEADLINE_CHARACTERS = 120
STORY_STOP_WORDS = frozenset(
    "a an the and or of to in on for with by from at as is are be its it this that new into over after says say "
    "will has have how why what who more than up out about via amid".split())

# Category rules: checked in order on the headline first; if none match there, checked in order on the summary.
CATEGORY_RULE_WORDS = ('Categories are checked in order: first the headline is checked against every category; only when '
                       'none matches, the feed text is checked in the same order; no match is "other".')

# X accounts (kind "X account" in source_candidates.csv), read through twitterapi.io (key: TWITTERAPI_IO_KEY).
X_API_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"
# Only posts that name a navigation system (or an NVS satellite: "NVS-03") are read.
X_POST_WORDS = "(GPS OR BeiDou OR Galileo OR GLONASS OR NavIC OR IRNSS OR NVS OR QZSS OR Michibiki)"
# Each read covers this many days back, so a missed run loses nothing.
X_READ_DAYS = 2
# A post has no headline: its first words, cut here, stand in for one.
X_TITLE_CHARACTERS = 120
