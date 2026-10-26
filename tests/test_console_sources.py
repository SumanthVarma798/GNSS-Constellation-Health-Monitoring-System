"""The console's Sources page (console/sources.py): every source with its grade, filters, and the grades waiting."""
from test_console import GitHub, run, signed_in, text  # noqa: F401
from test_dashboard_shell import segmented_controls_rerun  # noqa: F401  (AppTest 1.45's segmented controls)
from test_decisions import pr

GRADE_PR = pr(116, ["decision: source grade"], title="Sources: confirm proposed grade A for 13 candidate sources")


def test_every_source_is_listed_with_its_grade_and_whether_it_answered(monkeypatch):
    signed_in(monkeypatch, "member@example.com")

    page = text(run(monkeypatch, GitHub([GRADE_PR]), page="console/sources.py"))

    for words in ("ISRO press releases", "International GNSS Service (IGS)", "proposed", "answered", "refused (403)",
                  "1 decision waiting"):
        assert words in page, words
    assert "var(--g-a)" in page and "var(--c-ok)" not in page.split("Grades")[1].split("</div>")[0]   # grades in the ramp


def test_a_filter_and_find_narrow_the_list(monkeypatch):
    signed_in(monkeypatch, "member@example.com")
    at = run(monkeypatch, page="console/sources.py")

    at.session_state["sources_show"] = "not answering"
    at.run()
    page = text(at)
    assert "refused (403)" in page and "ISRO press releases" not in page

    at.session_state["sources_show"] = "all"
    at.text_input(key="sources_find").set_value("isro.gov").run()   # an address finds the site's own pages only
    assert "ISRO press releases" in text(at) and "Reddit" not in text(at)
