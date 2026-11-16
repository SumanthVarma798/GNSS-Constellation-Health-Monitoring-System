"""Settings for the Alerts page: Healthchecks.io checks and streak goals."""

from evidence.console_settings import JOBS
from evidence.decision_settings import READ_EVERY_SECONDS

HEALTHCHECKS_API = "https://healthchecks.io/api/v3"
SECRETS_SECTION = "alerts"

# Each job's Healthchecks.io checks, in JOBS order (evidence/console_settings.py); add a slug there.
CHECKS = list({slug: (slug, label) for job in JOBS for slug, label in job.checks}.values())

FLIPS_DAYS = 14
STREAK_GOAL_HOURS = 48
STREAK_FULL_HOURS = 7 * 24
