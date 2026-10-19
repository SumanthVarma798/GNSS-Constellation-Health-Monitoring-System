"""The major-changes strip: the list's shape, which changes show for which constellation, and dismissing one."""
from datetime import datetime

from test_dashboard_shell import celestrak_answers_with_nothing_new, htmls, run, segmented_controls_rerun  # noqa: F401  (autouse fixtures)
from ui import changes, shell


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


def _strip(at):
    return [b for b in htmls(at) if 'class="notice accent change"' in b]


def test_beidou_shows_both_notes_and_navic_none():
    both = _strip(run(lambda at: at.session_state.__setitem__("scope", "BeiDou-3")))
    assert len(both) == 2 and "G1 and G4 swapped" in both[1] and "C01 to C04" in both[0]
    assert "What this means for you" in both[0] and "IGS satellite metadata file" in both[0]
    assert _strip(run()) == []   # NavIC is the default scope


def test_dismissing_a_note_hides_only_that_note_for_the_session():
    def dismiss(at):
        at.session_state["scope"] = "BeiDou-3"
        at.run()
        at.button(key="dismiss_beidou3-slot-swap").click()

    at = run(dismiss)

    assert len(_strip(at)) == 1 and "C01 to C04" in _strip(at)[0]
    assert [b.key for b in at.button if b.key and b.key.startswith("dismiss_")] == ["dismiss_beidou3-signal-ids"]
