"""The master map page, driven by Streamlit's own test runner against the real tables.

Expected counts are worked out here from evidence.master_map.agreement and the registry, not typed in.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from evidence.master_map import agreement
from evidence.registry_tables import read_table
from evidence.settings import (IDENTITY_DIFFER, REGISTRY_CATALOGUE_FILE, REGISTRY_DASHBOARD_SATELLITES_FILE,
                               REGISTRY_SATELLITES_FILE, SERVICE_DISAGREE)

PAGE = str(Path(__file__).resolve().parent.parent / "pages" / "master_map.py")
LINES = agreement(read_table(REGISTRY_SATELLITES_FILE), read_table(REGISTRY_CATALOGUE_FILE))
TRACKED = {row["svn"] for row in read_table(REGISTRY_DASHBOARD_SATELLITES_FILE)}
NOTICE = "No spacecraft match these filters"


def expected(constellation="All", differing=False, watched=False):
    """The SVNs the page should offer for these filters."""
    return [line["svn"] for line in LINES
            if constellation in ("All", line["constellation"])
            and (not differing or line["identity"] == IDENTITY_DIFFER or line["service"] == SERVICE_DISAGREE)
            and (not watched or line["svn"] in TRACKED)]


def run(constellation="All", differing=False, watched=False):
    """Run the page with the filters already chosen; widgets are found by key."""
    app = AppTest.from_file(PAGE, default_timeout=60)
    app.session_state["constellation"] = constellation
    app.session_state["only_disagree"] = differing
    app.session_state["only_tracked"] = watched
    return app.run()


def page_html(app):
    return " ".join(element.proto.body for element in app.get("html"))


def test_the_default_view_names_c217_and_its_stale_orbit_feed_name():
    app = run()
    assert not app.exception
    assert app.selectbox(key="spacecraft").value == "C217"
    html = page_html(app)
    assert "C217" in html
    assert "two signal IDs out of date" in html
    assert html.count("data:image/svg+xml") == 2  # both timelines are drawn


def test_choosing_navic_leaves_its_ten_spacecraft():
    app = run(constellation="NavIC")
    assert not app.exception
    assert len(app.selectbox(key="spacecraft").options) == len(expected("NavIC")) == 10


def test_only_where_the_sources_disagree_keeps_just_those():
    app = run(differing=True)
    assert not app.exception
    shown = expected(differing=True)
    assert 0 < len(shown) < len(LINES)
    assert len(app.selectbox(key="spacecraft").options) == len(shown)
    assert app.selectbox(key="spacecraft").value == shown[0]  # C217 is not among them, so the first is chosen


def test_only_tracked_keeps_the_dashboards_spacecraft():
    app = run(watched=True)
    assert len(app.selectbox(key="spacecraft").options) == len(expected(watched=True))


def test_filters_narrow_together():
    app = run("NavIC", differing=True, watched=True)
    assert len(app.selectbox(key="spacecraft").options) == len(expected("NavIC", True, True))


def test_a_filter_that_leaves_nothing_shows_one_notice_and_nothing_below():
    assert not expected("Galileo", watched=True)  # the dashboard tracks no Galileo spacecraft
    app = run("Galileo", watched=True)
    assert not app.exception
    assert NOTICE in page_html(app)
    assert not app.selectbox
    assert not app.dataframe


@pytest.mark.parametrize("constellation", ["All", "QZSS"])
def test_the_table_has_one_row_per_spacecraft_shown(constellation):
    app = run(constellation)
    assert len(app.dataframe[0].value) == len(expected(constellation))
