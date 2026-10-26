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
# The summary is cut at this many characters.
SUMMARY_CHARACTERS = 300

# News collection runs on this cadence.
NEWS_CYCLE_HOURS = 3
# News older than this is shown as late.
NEWS_LATE_HOURS = 7

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
