"""Settings for the Alerts page: Healthchecks.io checks and streak goals."""

from evidence.decision_settings import READ_EVERY_SECONDS

HEALTHCHECKS_API = "https://healthchecks.io/api/v3"
SECRETS_SECTION = "alerts"

# Add a slug here when a new scheduled job starts pinging Healthchecks.io.
CHECKS = [
    ("archive-documents", "Archive: documents"),
    ("archive-catalogues", "Archive: catalogues"),
    ("archive-orbital", "Archive: orbit records"),
    ("archive-news", "Archive: news"),
    ("archive-social", "Archive: social"),
    ("registry-update", "Registry update"),
    ("update-tle-data", "Update orbit data"),
    ("orbit-ages", "Orbit ages"),
    ("orbit-fresh", "Orbit ages: every satellite under 2 days"),   # fails when any orbit record passes 2 days (D3)
    ("rinex-check", "RINEX check"),
]

FLIPS_DAYS = 14
STREAK_GOAL_HOURS = 48
STREAK_FULL_HOURS = 7 * 24

# 48 h green before the demo is shared; 7 days for the full bar (~14 Nov).
DEMO_SHARE = "Thu 29 Oct"
