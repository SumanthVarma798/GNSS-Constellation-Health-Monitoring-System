"""The system design page must say what the code says."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from update_design_doc import END, PAGE, START, constants_table, refreshed


def test_the_constants_on_the_page_match_the_code():
    page = PAGE.read_text()

    assert START in page and END in page
    assert refreshed(page) == page, "run: python scripts/update_design_doc.py"


def test_the_table_reads_the_real_schedules_and_the_real_bar():
    table = constants_table()

    assert "`30 0 * * *` (documents: once a day, 00:30 UTC = 06:00 India time)" in table
    assert "`45 0 * * 0` (catalogues: Sundays 00:45 UTC = 06:15 India time" in table
    assert "`0 1 * * 0` (Sundays 01:00 UTC = 06:30 India time" in table
    assert "| Grades that clear the bar alone | A |" in table
    assert "| The three labels | confirmed, probable, unconfirmed |" in table
