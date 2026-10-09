"""A registry change must be described in words a reviewer can check."""
from evidence.registry_changes import change_report, describe_satellite_changes, describe_signal_id_changes

G1 = {"svn": "C217", "constellation": "BeiDou", "block": "BDS-3G", "cospar_id": "2018-085A",
      "catalogue_no": "43683", "signal_id_now": "C62", "plane": "G", "slot": "140E", "note": "BEIDOU 3G1"}
OLD = {"svn": "C006", "constellation": "BeiDou", "block": "BDS-2G", "cospar_id": "2010-057A",
       "catalogue_no": "37210", "signal_id_now": "C04", "plane": "", "slot": "", "note": "BEIDOU 6"}
NEW = {"svn": "J008", "constellation": "QZSS", "block": "QZS-3G", "cospar_id": "2026-182A",
       "catalogue_no": "100270", "signal_id_now": "J09", "plane": "G", "slot": "175W", "note": "QZS-7"}


def test_satellite_changes_in_plain_words():
    after = [{**G1, "signal_id_now": "C04", "slot": ""}, NEW]

    assert describe_satellite_changes([G1, OLD], after) == [
        "New satellite J008 (QZSS, catalogue number 100270): QZS-7",
        "Satellite C006 (BeiDou) is no longer in the IGS file.",
        "C217 (BeiDou): signal ID was C62, now C04.",
        "C217 (BeiDou): slot was 140E, now blank.",
    ]
    assert describe_satellite_changes([G1], [G1]) == []


def test_signal_id_changes_in_plain_words():
    def period(signal_id, start, end):
        return {"svn": "C217", "signal_id": signal_id, "valid_from": start, "valid_to": end, "note": ""}
    before = [period("C62", "2026-03-31T13:20:00Z", "")]
    after = [period("C62", "2026-03-31T13:20:00Z", "2026-04-21T08:00:00Z"), period("C04", "2026-04-21T12:00:00Z", "")]

    assert describe_signal_id_changes(before, after) == [
        "C217: signal ID C04 from 2026-04-21T12:00:00Z to now.",
        "C217: signal ID C62 from 2026-03-31T13:20:00Z to 2026-04-21T08:00:00Z.",
        "1 earlier signal-ID period(s) were removed or replaced by the lines above.",
    ]


def test_report_says_nothing_changed_rather_than_leaving_a_gap():
    report = change_report("%=SNX 2.02", ["C217 (BeiDou): signal ID was C62, now C04."], [])

    assert "- C217 (BeiDou): signal ID was C62, now C04." in report
    assert "- Nothing." in report
    assert "Nothing changes until a person approves it" in report


def test_report_names_the_copy_it_was_built_from():
    assert "Read straight from the IGS website" in change_report("%=SNX 2.02", [], [])
    assert "SHA-256 `abc`" in change_report("%=SNX 2.02", [], [], "The copy used is in the private archive: SHA-256 `abc`.")
