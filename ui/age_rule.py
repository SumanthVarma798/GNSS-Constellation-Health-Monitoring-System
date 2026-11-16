"""The orbit-record age bands shared by the shell, data rows and the master map."""

from evidence.settings import ORBIT_ALERT_DAYS, ORBIT_STALE_DAYS


def orbit_age_status(age_days):
    """'ok', 'warn', 'bad' or 'idle' for an orbit record's age in days."""
    if age_days is None:
        return "idle"
    if age_days >= ORBIT_STALE_DAYS:
        return "bad"
    if age_days >= ORBIT_ALERT_DAYS:
        return "warn"
    return "ok"
