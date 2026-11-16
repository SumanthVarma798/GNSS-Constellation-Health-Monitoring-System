"""A registry change read row by row (evidence/table_changes.py), as the Approvals page and the weekly job say it.

The diff is shaped like pull request 231's (15 Nov 2026): one blank catalogue row, routine Library counts, one
matching row, two payloads not identified.
"""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from evidence import table_changes
from evidence.registry_changes import change_report

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import describe_table_changes  # noqa: E402

DIFF = """diff --git a/registry/catalogue.csv b/registry/catalogue.csv
index 8d608b3..17dab03 100644
--- a/registry/catalogue.csv
+++ b/registry/catalogue.csv
@@ -281,6 +281,7 @@ R805,2020-075A
 R808,2025-206B,Uragan-K1 No. 18L,VVKOV/IACG,RU,O,MEO,2023 Feb,*,S
+R809,,,,,,,,,
 R813,,,,,,,,,
diff --git a/registry/library_counts.csv b/registry/library_counts.csv
--- a/registry/library_counts.csv
+++ b/registry/library_counts.csv
@@ -1,3 +1,3 @@
 system,programme,launched,failed_at_launch,failed_in_orbit,retired,operating,status_not_recorded,years_retired,years_operating,approximate_dates,first_launch,last_launch,gcat_updated
-GPS,GPS IIR,13,1,0,6,6,0,115.10,147.44,0,1997,2004,2026-10-16
-GPS,GPS III,10,0,0,0,10,0,0.00,40.69,0,2018,2026,2026-10-16
+GPS,GPS IIR,13,1,0,6,6,0,115.10,147.90,0,1997,2004,2026-11-13
+GPS,GPS III,11,0,0,0,11,0,0.00,41.45,0,2018,2026,2026-11-13
diff --git a/registry/library_matching.csv b/registry/library_matching.csv
--- a/registry/library_matching.csv
+++ b/registry/library_matching.csv
@@ -2,1 +2,1 @@
-GLONASS,101,100,1,100,47,0
+GLONASS,102,100,2,100,47,0
diff --git a/registry/unidentified.csv b/registry/unidentified.csv
--- a/registry/unidentified.csv
+++ b/registry/unidentified.csv
@@ -1 +1,3 @@
 catalogue_no,name,cospar_id,launched,orbit,period_minutes,inclination_degrees
+101318,OBJECT A,2026-252A,2026-11-07,medium Earth orbit,676.05,64.77
+101319,OBJECT B,2026-252B,2026-11-07,medium Earth orbit,681.01,64.85
diff --git a/registry/satellites.csv b/registry/satellites.csv
--- a/registry/satellites.csv
+++ b/registry/satellites.csv
@@ -5,1 +5,0 @@
-G044,GPS,IIR,2000-025A,26407,G22,,,Launched 2000-05-11
"""


def changes():
    return [table_changes.table_change(path, patch) for path, patch in table_changes.split_diff(DIFF).items()]


def test_rows_are_sorted_into_added_changed_routine_and_removed():
    catalogue, counts, matching, unidentified, satellites = changes()

    assert [row["svn"] for row in catalogue["added"]] == ["R809"] and not catalogue["changed"]
    assert [row["row"]["programme"] for row in counts["routine"]] == ["GPS IIR"]   # years and date only
    assert counts["changed"][0]["differs"] == [("launched", "10", "11"), ("operating", "10", "11"),
                                               ("years_operating", "40.69", "41.45"),
                                               ("gcat_updated", "2026-10-16", "2026-11-13")]
    assert table_changes.differs_text(matching["changed"][0]["differs"]) == ("registry satellites 101 → 102; "
                                                                             "not found in GCAT 1 → 2")
    assert table_changes.named(unidentified["added"], unidentified["settings"]) == "OBJECT A (2026-252A) and OBJECT B (2026-252B)"
    assert [row["svn"] for row in satellites["removed"]] == ["G044"]


def test_the_ask_says_counts_and_what_the_dashboard_shows():
    found = changes()

    assert table_changes.asked("the weekly job", found) == ("The weekly job asks to change 5 registry tables: "
                                                            "3 rows added, 3 changed, 1 removed.")
    shown = table_changes.shown_text(found)
    assert shown.startswith("On the dashboard: Master map (") and "Library (" in shown
    assert "No page shows payloads not identified yet." in shown


def test_what_needs_a_look_names_removals_blank_rows_and_payloads_not_identified():
    titles = [title for _, title, _ in table_changes.needs_a_look(changes())]

    assert titles == ["R809 added with every detail blank", "2 payloads not identified", "1 row removed from Satellites"]


def test_a_file_github_gives_no_diff_for_is_said_and_flagged():
    big = table_changes.table_change("registry/satellites.csv", None, 300, 290)
    other = table_changes.table_change("console/approvals.py", "+x", 1, 0)

    assert not big["readable"] and not other["readable"]
    assert table_changes.needs_a_look([big, other])[0][1] == "Satellites: GitHub gave no row-by-row change"
    assert table_changes.asked("A Member", [other]) == "A Member asks to change 1 other file."


def test_the_markdown_for_github_names_each_source_in_full_with_a_link():
    text = table_changes.markdown(changes())

    assert "### Payloads not identified yet: 2 rows added, none changed, none removed" in text
    assert "From [GCAT, J. McDowell's catalogue of space objects](https://planet4589.org/space/gcat/)." in text
    assert "- GLONASS: registry satellites 101 → 102; not found in GCAT 1 → 2." in text
    assert "- 1 routine: years in service and GCAT's date only (GPS IIR)." in text
    assert "## Needs a look" in text


def test_a_report_without_findings_says_it_is_decided_as_one_change():
    assert "decided as one change" in change_report("%=SNX 2.02", [], [], findings=[])
    assert "Each finding is decided on its own" in change_report("%=SNX 2.02", [], [], findings=[{"id": "R809"}])


def test_the_weekly_job_opens_its_description_with_the_ask_and_the_tables(monkeypatch, tmp_path):
    report = tmp_path / "changes.md"
    report.write_text("This is a proposed update.\n\n## Where this came from\n\nThe IGS file.\n\n<!-- findings\n{}\n-->\n")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=DIFF))
    monkeypatch.setattr(sys, "argv", ["describe_table_changes.py", "--report", str(report)])

    describe_table_changes.main()

    text = report.read_text()
    assert text.startswith("The weekly job asks to change 5 registry tables: 3 rows added, 3 changed, 1 removed. "
                           "On the dashboard:")
    assert text.index("This is a proposed update.") < text.index("## What changed, table by table") < text.index("## Where")
    assert text.rstrip().endswith("-->")   # the findings block stays where the console reads it
