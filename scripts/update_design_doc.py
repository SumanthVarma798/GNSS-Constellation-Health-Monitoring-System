"""Keep the constants in docs/system-design.md in step with the code.

    python scripts/update_design_doc.py          # rewrite the table in the page
    python scripts/update_design_doc.py --check  # exit with an error if the page is out of date

The table between the two markers in the page is produced here, from
evidence/settings.py, evidence/sources.py and the two job files. A test runs
the check, so the page cannot quietly disagree with the code.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evidence import settings
from evidence.sources import ARCHIVED_SOURCES

PAGE = ROOT / "docs" / "system-design.md"
START = "<!-- constants: produced by scripts/update_design_doc.py, do not edit by hand -->"
END = "<!-- constants: end -->"
JOBS = ROOT / ".github" / "workflows"


def schedule(job_file, which=0):
    """One schedule line of a job file (the first unless told otherwise), and the comment that explains it."""
    lines = (JOBS / job_file).read_text().splitlines()
    index = [number for number, line in enumerate(lines) if "- cron:" in line][which]
    cron, _, same_line = lines[index].partition("#")
    above = []
    while index > 0 and lines[index - 1].strip().startswith("#"):
        index -= 1
        above.insert(0, lines[index].strip().lstrip("# "))
    note = same_line.strip() or " ".join(above)
    schedule = re.search(r"'([^']+)'", cron).group(1)
    return f"`{schedule}` ({note.rstrip('.')})"


def duration(gap):
    seconds = int(gap.total_seconds())
    return f"{seconds // 3600} hours" if seconds >= 3600 else f"{seconds} seconds"


def constants_table():
    megabytes = settings.MAX_COPY_BYTES // (1024 * 1024)
    rows = [
        ("Documents are fetched", schedule("archive.yml"), "`.github/workflows/archive.yml`"),
        ("Catalogues are fetched", schedule("archive.yml", 1), "`.github/workflows/archive.yml`"),
        ("Orbit records are fetched", schedule("archive.yml", 2), "`.github/workflows/archive.yml`"),
        ("News feeds and pages are fetched", schedule("archive.yml", 3), "`.github/workflows/archive.yml`"),
        ("Social media feeds are fetched", schedule("archive.yml", 4), "`.github/workflows/archive.yml`"),
        ("The registry is rebuilt", schedule("registry-update.yml"), "`.github/workflows/registry-update.yml`"),
        ("Sources archived, by group", ", ".join(f"{group}: {len(found)}" for group, found in ARCHIVED_SOURCES.items()),
         "`evidence/sources.py`"),
        ("Grades that clear the bar alone", ", ".join(settings.GRADES_THAT_CLEAR_ALONE), "`evidence/settings.py`"),
        ("Grades lifted by a second source", ", ".join(settings.GRADES_LIFTED_BY_A_SECOND_SOURCE), "`evidence/settings.py`"),
        ("Grades lifted by our own data", ", ".join(settings.GRADES_LIFTED_BY_OBSERVATION), "`evidence/settings.py`"),
        ("Grades that count as a second source", ", ".join(settings.GRADES_THAT_COUNT_AS_A_SECOND_SOURCE),
         "`evidence/settings.py`"),
        ("The three labels", ", ".join((settings.LABEL_CONFIRMED, settings.LABEL_PROBABLE, settings.LABEL_UNCONFIRMED)),
         "`evidence/settings.py`"),
        ("Longest wait for an outside server", f"{settings.REQUEST_TIMEOUT_SECONDS} seconds", "`evidence/settings.py`"),
        ("A failed download is tried", f"{settings.DOWNLOAD_TRIES} times, {settings.WAIT_BETWEEN_TRIES_SECONDS} seconds "
         "apart; once a run where that is sooner than the source's gap", "`evidence/settings.py`"),
        ("Shortest gap between two requests to one site",
         ", ".join([*(f"{site}: {duration(gap)}" for site, gap in settings.MIN_GAP_BETWEEN_DOWNLOADS.items()),
                    f"any other site: {duration(settings.DEFAULT_MIN_GAP)}"]), "`evidence/settings.py`"),
        ("Largest copy the archive keeps", f"{megabytes} MB", "`evidence/settings.py`"),
        ("Statuses that mean a page is gone", ", ".join(map(str, settings.GONE_STATUSES)), "`evidence/settings.py`"),
        ("How our requests name themselves", f"`{settings.USER_AGENT}`", "`evidence/settings.py`"),
    ]
    table = ["| Constant | Value today | Set in |", "|---|---|---|", *(f"| {name} | {value} | {where} |" for name, value, where in rows)]
    return "\n".join(table)


def refreshed(page_text):
    """The page with its constants table replaced by today's."""
    before, _, rest = page_text.partition(START)
    _, _, after = rest.partition(END)
    return f"{before}{START}\n{constants_table()}\n{END}{after}"


def main():
    current = PAGE.read_text()
    if "--check" in sys.argv:
        if refreshed(current) != current:
            sys.exit("docs/system-design.md is out of date. Run: python scripts/update_design_doc.py")
        return
    PAGE.write_text(refreshed(current))
    print(f"constants written to {PAGE}")


if __name__ == "__main__":
    main()
