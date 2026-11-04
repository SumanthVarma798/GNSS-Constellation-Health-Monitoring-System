"""A registry change must be described in words a reviewer can check."""
from datetime import date

from evidence import decisions
from evidence.registry_changes import change_report, describe_satellite_changes, describe_signal_id_changes, registry_findings

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
    assert "## What changes on the dashboard" in report
    assert "Nothing changes until a person approves it" in report


def test_report_names_the_copy_it_was_built_from():
    assert "Read straight from the IGS website" in change_report("%=SNX 2.02", [], [])
    assert "SHA-256 `abc`" in change_report("%=SNX 2.02", [], [], "The copy used is in the private archive: SHA-256 `abc`.")


def test_registry_findings_for_a_new_satellite_uses_igs_celestrak_and_news_in_window():
    before_satellites = [{"svn": "R801", "constellation": "GLONASS", "block": "GLO-M", "cospar_id": "2011-009A",
                          "catalogue_no": "37372", "signal_id_now": "R01", "plane": "1", "slot": "1",
                          "note": "Launched 2011-02-26; COSMOS 2471"}]
    after_satellites = [*before_satellites, {"svn": "R809", "constellation": "GLONASS", "block": "GLO-K1",
                                              "cospar_id": "2026-216A", "catalogue_no": "100744", "signal_id_now": "R30",
                                              "plane": "8", "slot": "24", "note": "Launched 2026-09-17; COSMOS 2620"}]
    before_signal_ids = [{"svn": "R801", "signal_id": "R01", "valid_from": "2011-02-26T00:00:00Z", "valid_to": "",
                          "note": ""}]
    after_signal_ids = [*before_signal_ids, {"svn": "R809", "signal_id": "R30", "valid_from": "2026-09-17T00:00:00Z",
                                             "valid_to": "", "note": ""}]
    grades = [{"source_id": "files.igs.org", "name": "International GNSS Service (IGS) satellite metadata file",
               "reliability": "B", "graded_by": "Sumanth Varma (awaiting the team's review)"},
              {"source_id": "celestrak.org", "name": "CelesTrak satellite catalogue", "reliability": "B",
               "graded_by": "Proposed with issue 31 (awaiting the team's review)"},
              {"source_id": "spacenews.com", "name": "SpaceNews", "reliability": "C", "graded_by": "A Person"}]
    candidates = []
    news_items = [
        {"source_id": "spacenews.com", "address": "https://spacenews.com/glonass-2620", "title": "GLONASS satellite COSMOS 2620 launched",
         "published_at": "2026-09-18T05:00:00Z", "fetched_at": "2026-09-18T06:00:00Z"},
        {"source_id": "spacenews.com", "address": "https://spacenews.com/glonass-old", "title": "GLONASS mission from last year",
         "published_at": "2026-08-01T05:00:00Z", "fetched_at": "2026-08-01T06:00:00Z"},
        {"source_id": "spacenews.com", "address": "https://spacenews.com/gps", "title": "GPS mission this week",
         "published_at": "2026-09-18T05:00:00Z", "fetched_at": "2026-09-18T06:00:00Z"},
        # Names the system in the window, but is not about this satellite: matched for R809 on 26 Oct 2026.
        {"source_id": "bgr.com", "address": "https://bgr.com/watch", "published_at": "2026-09-20T05:00:00Z",
         "title": "What Is GLONASS And Why Is It Missing From The Apple Watch Ultra 4?", "fetched_at": "2026-09-20T06:00:00Z"},
    ]
    celestrak_reads = {"R809": {"checked": True, "catalogue_status": "ok",
                                "catalogue_entry": {"OBJECT_NAME": "COSMOS 2620 [GLONASS-K1]", "OBJECT_ID": "2026-216A",
                                                    "OBJECT_TYPE": "PAYLOAD", "LAUNCH_DATE": "2026-09-17",
                                                    "PERIOD": "676.39", "INCLINATION": "64.78", "APOGEE": "19153",
                                                    "PERIGEE": "19140"},
                                "orbit_status": "none", "orbit_row": None}}

    findings = registry_findings(before_satellites, after_satellites, before_signal_ids, after_signal_ids,
                                 {"R809": "Approving also adds it to the dashboard as COSMOS 2620."},
                                 {"R809": "R809 2026-216A 100744 GLO-K1B Launched 2026-09-17; COSMOS 2620"},
                                 {}, celestrak_reads, date(2026, 10, 26), news_items, grades, candidates)

    assert len(findings) == 1
    assert findings[0]["id"] == "R809" and findings[0]["category"] == "New satellite"
    assert findings[0]["detail"] == "Approving also adds it to the dashboard as COSMOS 2620."
    assert len(findings[0]["sources"]) == 3
    assert findings[0]["sources"][0]["source"] == "International GNSS Service (IGS) satellite metadata file"
    assert findings[0]["sources"][1]["source"] == "CelesTrak satellite catalogue"
    assert findings[0]["sources"][2]["line"] == "GLONASS satellite COSMOS 2620 launched"
    assert findings[0]["measured"] == [
        {"what": "CelesTrak catalogue entry",
         "value": "period 676.39 minutes, inclination 64.78 degrees, apogee 19,153 km, perigee 19,140 km",
         "link": "https://celestrak.org/satcat/records.php?CATNR=100744"},
        {"what": "CelesTrak orbit record", "value": "none published yet (checked 26 Oct 2026)"},
    ]


def test_registry_findings_keep_new_satellite_when_celestrak_is_down():
    findings = registry_findings(
        [], [{"svn": "R809", "constellation": "GLONASS", "block": "GLO-K1", "cospar_id": "2026-216A",
              "catalogue_no": "100744", "signal_id_now": "R30", "plane": "8", "slot": "24",
              "note": "Launched 2026-09-17; COSMOS 2620"}], [], [],
        {}, {"R809": "R809 2026-216A 100744 GLO-K1B Launched 2026-09-17; COSMOS 2620"}, {},
        {"R809": {"checked": True, "catalogue_status": "error", "catalogue_entry": None,
                  "orbit_status": "error", "orbit_row": None}},
        date(2026, 10, 26), [], [{"source_id": "files.igs.org", "name": "International GNSS Service (IGS) satellite metadata file",
                                  "reliability": "B", "graded_by": "Sumanth Varma"}], [])

    assert findings[0]["category"] == "New satellite"
    assert findings[0]["measured"] == [
        {"what": "CelesTrak catalogue entry", "value": "CelesTrak could not be read (checked 26 Oct 2026)"},
        {"what": "CelesTrak orbit record", "value": "CelesTrak could not be read"},
    ]


def test_registry_findings_say_signal_id_change_with_the_closing_date_and_new_prn_lines():
    before_satellites = [{"svn": "R723", "constellation": "GLONASS", "block": "GLO-M", "cospar_id": "2007-065C",
                          "catalogue_no": "32395", "signal_id_now": "R10", "plane": "2", "slot": "10",
                          "note": "Launched 2007-12-25; COSMOS 2436"}]
    after_satellites = [{**before_satellites[0], "signal_id_now": "R28"}]
    before_signal_ids = [{"svn": "R723", "signal_id": "R10", "valid_from": "2019-09-30T00:00:00Z", "valid_to": "", "note": ""}]
    after_signal_ids = [{"svn": "R723", "signal_id": "R10", "valid_from": "2019-09-30T00:00:00Z",
                         "valid_to": "2026-10-20T00:00:00Z", "note": ""},
                        {"svn": "R723", "signal_id": "R28", "valid_from": "2026-10-20T00:00:00Z", "valid_to": "",
                         "note": ""}]

    findings = registry_findings(before_satellites, after_satellites, before_signal_ids, after_signal_ids, {},
                                 {"R723": "R723 2007-065C 32395 GLO-M Launched 2007-12-25; COSMOS 2436"},
                                 {"R723": ["R723 2019:273:00000 2026:294:00000 R10",
                                           "R723 2026:294:00000 0000:000:00000 R28"]},
                                 {}, date(2026, 10, 26), [],
                                 [{"source_id": "files.igs.org",
                                   "name": "International GNSS Service (IGS) satellite metadata file",
                                   "reliability": "B", "graded_by": "Sumanth Varma"}], [])

    assert findings == [{
        "id": "R723",
        "category": "Signal ID change",
        "statement": "R723 (GLONASS, COSMOS 2436) now uses signal ID R28; it used R10 until 20 Oct 2026.",
        "sources": [
            {"source": "International GNSS Service (IGS) satellite metadata file",
             "line": "R723 2007-065C 32395 GLO-M Launched 2007-12-25; COSMOS 2436",
             "grade": "B", "link": "https://files.igs.org/pub/station/general/igs_satellite_metadata.snx"},
            {"source": "International GNSS Service (IGS) satellite metadata file",
             "line": "R723 2019:273:00000 2026:294:00000 R10",
             "grade": "B", "link": "https://files.igs.org/pub/station/general/igs_satellite_metadata.snx"},
            {"source": "International GNSS Service (IGS) satellite metadata file",
             "line": "R723 2026:294:00000 0000:000:00000 R28",
             "grade": "B", "link": "https://files.igs.org/pub/station/general/igs_satellite_metadata.snx"},
        ],
        "measured": [],
    }]


def test_report_appends_findings_block_and_round_trips_a_title_with_arrow():
    findings = [{
        "id": "R809", "category": "New satellite",
        "statement": "Saw title with --> and kept it as plain text.",
        "sources": [{"source": "A source", "line": "COSMOS 2620 --> launch note", "grade": "B"}],
        "measured": [{"what": "CelesTrak orbit record", "value": "none published yet (checked 26 Oct 2026)"}],
    }]

    report = change_report("%=SNX 2.02", [], [], findings=findings)

    assert report.strip().endswith(decisions.findings_block(findings))
    assert decisions.findings(report) == findings


def test_registry_findings_for_removed_satellite_has_igs_source_line():
    before_satellites = [{"svn": "C006", "constellation": "BeiDou", "block": "BDS-2G", "cospar_id": "2010-057A",
                          "catalogue_no": "37210", "signal_id_now": "C04", "plane": "", "slot": "",
                          "note": "Launched 2010-10-31; BEIDOU 6"}]
    grades = [{"source_id": "files.igs.org",
               "name": "International GNSS Service (IGS) satellite metadata file",
               "reliability": "B", "graded_by": "Sumanth Varma"}]

    findings = registry_findings(
        before_satellites, [], [{"svn": "C006", "signal_id": "C04", "valid_from": "2010-10-31T00:00:00Z", "valid_to": "", "note": ""}], [],
        {}, {}, {}, {}, date(2026, 10, 26), [], grades, [])

    assert findings[0]["category"] == "Satellite removed"
    assert findings[0]["sources"] == [{
        "source": "International GNSS Service (IGS) satellite metadata file",
        "line": "No longer listed in the IGS satellite metadata file",
        "grade": "B",
        "link": "https://files.igs.org/pub/station/general/igs_satellite_metadata.snx",
    }]


def test_registry_findings_marks_celestrak_as_not_checked_without_catalogue_number():
    findings = registry_findings(
        [], [{"svn": "R900", "constellation": "GLONASS", "block": "GLO-K1", "cospar_id": "2026-250A",
              "catalogue_no": "", "signal_id_now": "R99", "plane": "8", "slot": "24",
              "note": "Launched 2026-09-17; COSMOS 2999"}], [], [],
        {}, {"R900": "R900 2026-250A  GLO-K1B Launched 2026-09-17; COSMOS 2999"}, {},
        {"R900": {"checked": False, "catalogue_status": "none", "catalogue_entry": None,
                  "orbit_status": "none", "orbit_row": None}},
        date(2026, 10, 26), [], [{"source_id": "files.igs.org",
                                  "name": "International GNSS Service (IGS) satellite metadata file",
                                  "reliability": "B", "graded_by": "Sumanth Varma"}], [])

    assert findings[0]["measured"] == [
        {"what": "CelesTrak catalogue entry", "value": "not checked: no catalogue number in the IGS file"},
        {"what": "CelesTrak orbit record", "value": "not checked: no catalogue number in the IGS file"},
    ]
