"""The major changes: the list's shape, which changes are listed for which constellation, and that they go to the
notices inbox, not the page."""
from datetime import datetime

from test_dashboard_shell import celestrak_answers_with_nothing_new, htmls, run, segmented_controls_rerun  # noqa: F401  (autouse fixtures)
from ui import changes, notices, shell


def test_each_change_is_complete_and_names_known_constellations():
    ids = [c.id for c in changes.CHANGES]

    assert len(ids) == len(set(ids)) == 2
    for c in changes.CHANGES:
        assert all([c.date, c.constellations, c.headline, c.meaning, c.source])
        assert set(c.constellations) <= set(shell.CONSTELLATIONS)
        assert changes._when(c.date)   # the date reads as a day or a month


def test_only_changes_for_the_constellations_in_view_show_newest_first():
    assert [c.id for c in changes.for_constellations(["BeiDou-3"])] == ["beidou3-signal-ids", "beidou3-slot-swap"]
    assert [c.id for c in changes.for_constellations(["NavIC", "BeiDou-3"])] == ["beidou3-signal-ids", "beidou3-slot-swap"]
    assert changes.for_constellations(["NavIC"]) == changes.for_constellations(["QZSS"]) == []


def test_dates_read_as_a_day_or_a_month():
    assert changes._when("2026-04-21") == "21 Apr 2026"
    assert changes._when("2026-04") == "Apr 2026"


def _news(at):
    """The changes listed in the notices inbox, in the order the bell shows them."""
    return [text for text, status in at.session_state[notices.PAGE].values() if status == changes.STATUS]


def test_beidou_lists_both_changes_in_the_inbox_and_navic_none():
    both = _news(run(lambda at: at.session_state.__setitem__("scope", "BeiDou-3")))
    assert len(both) == 2 and "G1 and G4 swapped" in both[1] and "C01 to C04" in both[0]
    assert "What it means:" in both[0] and "IGS satellite metadata file" in both[0]
    assert not any("BeiDou-3" in text for text in _news(run()))   # NavIC is the default scope


def test_no_change_is_drawn_in_the_page_itself():
    at = run(lambda at: at.session_state.__setitem__("scope", "BeiDou-3"))

    assert not any("G1 and G4 swapped" in body and 'class="nt-row' not in body for body in htmls(at))
