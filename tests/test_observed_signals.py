"""Which signals a receiver recorded, from a hand-written RINEX 3 observation file. No network."""
import json

from test_dashboard_shell import (celestrak_answers_with_nothing_new, run,  # noqa: F401 (fixtures)
                                  segmented_controls_rerun)
from analysis.observed_signals import combine, read_observations
from scripts import signals_heard
from ui import shell, signal_settings, signals_view
from ui.signal_settings import signal_name


def _header():
    rows = [("     3.04           OBSERVATION DATA    M: Mixed            ", "RINEX VERSION / TYPE"),
            ("G    6 C1C L1C C2W L2W C5Q L5Q                              ", "SYS / # / OBS TYPES"),
            ("I    3 C5A L5A S5A                                          ", "SYS / # / OBS TYPES"),
            ("E    4 C1C C7Q L7Q D1C                                      ", "SYS / # / OBS TYPES"),
            ("", "END OF HEADER")]
    return "\n".join(text.ljust(60) + label for text, label in rows) + "\n"


def _satellite(name, *values):
    """One satellite line: 14-character values (blank for none), each followed by its two flag characters."""
    return name + "".join((f"{v:14.3f}" if v is not None else " " * 14) + "  " for v in values)


def _epoch(second, flag, *lines):
    return f"> 2026 11 16 00 00 {second:02d}.0000000  {flag}{len(lines):3d}\n" + "\n".join(lines) + "\n"


FILE = (_header()
        + _epoch(0, 0, _satellite("G05", 2.1e7, 1.1e8, 2.1e7, 8.0e7, None, None),   # L1 C/A and L2 P(Y), no L5
                 _satellite("G09", 2.2e7, 1.1e8, None, None, 2.2e7, 8.8e7),         # L1 C/A and L5
                 _satellite("I06", 3.6e7, None, 40.0),                              # NavIC: a code range on L5
                 _satellite("I07", None, None, 40.0),                               # signal strength alone is not a signal
                 _satellite("E11", 2.5e7, None, None, 1234.0))                      # Doppler alone is not a signal
        + _epoch(30, 0, _satellite("E11", 2.5e7, 1.0e8, None, 1234.0), _satellite("G05", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        + _epoch(60, 4, "event text line one", "event text line two")
        + _epoch(90, 0, _satellite("C99", 2.0e7)))                                  # constellation not in the header


def test_signal_names_are_plain_and_unknown_codes_are_kept():
    assert signal_name("G", "1C") == "L1 C/A" and signal_name("G", "1L") == "L1C" and signal_name("G", "5Q") == "L5"
    assert signal_name("E", "7Q") == "E5b" and signal_name("C", "2I") == "B1I" and signal_name("I", "9A") == "S"
    assert signal_name("J", "6E") == "L6E" and signal_name("J", "6L") == "L6" and signal_name("R", "3Q") == "G3"
    assert signal_name("C", "7I") == "B2I" and signal_name("C", "7D") == "B2b"
    assert signal_name("G", "1M") == "L1 M" and signal_name("G", "2W") == "L2 P(Y)" and signal_name("G", "2D") == "L2 P(Y)"
    assert signal_name("G", "9X") == "band 9"   # not dropped


def test_a_signal_counts_when_a_code_range_or_phase_was_recorded():
    heard = read_observations(FILE, every=1)
    assert heard["G05"] == {"L1 C/A", "L2 P(Y)"}      # the zero row of epoch 2 adds nothing
    assert heard["G09"] == {"L1 C/A", "L5"}
    assert heard["I06"] == {"L5"} and "I07" not in heard
    assert heard["E11"] == {"E1", "E5b"}               # E5b only appears in epoch 2; Doppler alone adds nothing
    assert "C99" not in heard                          # a constellation the header did not declare is skipped


def test_event_epochs_are_skipped_not_read_as_satellites():
    assert "event" not in "".join(read_observations(FILE, every=1))


def test_sampling_reads_one_epoch_in_every_n_and_skips_the_rest_unread():
    sampled = read_observations(FILE, every=2)         # epochs 0 and 2 (the event does not count): epoch 1 is skipped
    assert sampled["E11"] == {"E1"} and sampled["G05"] == {"L1 C/A", "L2 P(Y)"} and "I06" in sampled


def test_combine_lists_stations_per_signal_in_a_fixed_order():
    rows = combine({"WTZR": {"G05": {"L1 C/A", "L5"}}, "IISC": {"G05": {"L1 C/A"}}},
                   [("GPS BIIF-3", "G05"), ("GPS no ID", None), ("GPS BIII-1", "G04")])
    assert rows[0] == {"satellite": "GPS BIIF-3", "signal_id": "G05",
                       "signals": {"L1 C/A": ["IISC", "WTZR"], "L5": ["WTZR"]}}
    assert rows[1]["signals"] == {} and rows[2]["signals"] == {}


def test_every_station_has_its_why_and_a_bkg_address():
    for code, (short, place, why) in signal_settings.STATIONS.items():
        assert code.startswith(short) and place and why
    assert signal_settings.FILES.format(year=2026, doy=320, code="IISC00IND").endswith("IISC00IND_R_20263200000_01D_30S_MO.crx.gz")


def test_measure_leaves_out_a_station_it_cannot_read_and_fails_when_none_can_be_read(monkeypatch):
    from datetime import date

    def text(code, day):
        if code.startswith("WTZR"):
            raise OSError("no file")
        return FILE, 1_000_000

    monkeypatch.setattr(signals_heard, "observation_text", text)
    monkeypatch.setattr(signals_heard, "tracked", lambda day: [("x", "GPS BIIF-3", 1, "G05"), ("y", "NVS-03", 2, None)])
    payload = signals_heard.measure(date(2026, 11, 16))
    assert [s["read"] for s in payload["stations"]].count(False) == 1
    assert payload["satellites"][0]["signals"]["L1 C/A"] == sorted(s[0] for c, s in signal_settings.STATIONS.items() if not c.startswith("WTZR"))
    assert signals_heard.summary(payload) == "1 of 2 satellites heard by 5 of 6 stations"
    json.dumps(payload)
    monkeypatch.setattr(signals_heard, "observation_text", lambda code, day: (_ for _ in ()).throw(OSError("down")))
    try:
        signals_heard.measure(date(2026, 11, 16))
    except RuntimeError as error:
        assert "no station" in str(error)
    else:
        raise AssertionError("expected a RuntimeError")


def test_the_section_says_heard_silent_and_missing_in_words():
    payload = {"day": "2026-11-16", "folder": "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/320/", "sample_every": 20,
               "stations": [{"code": "IISC00IND", "name": "IISC", "place": "Bengaluru, India", "read": True},
                            {"code": "WTZR00DEU", "name": "WTZR", "place": "Wettzell, Germany", "read": True}],
               "satellites": [{"satellite": "A", "signal_id": "G05", "signals": {"L1 C/A": ["IISC"], "L5": ["IISC", "WTZR"]}},
                              {"satellite": "B", "signal_id": "G06", "signals": {}},
                              {"satellite": "C", "signal_id": None, "signals": {}}]}
    summary, body = signals_view.section_markup(payload, ["A", "B", "C", "D"])
    assert summary == "1 of 4 satellites heard · 1 not heard by any of 2 stations · 16 Nov"
    assert "L1 C/A" in body and "L5" in body and "IISC, WTZR" in body
    assert "not heard by any of the 2 stations that day" in body and "no signal ID that day" in body
    assert "not in the signals check" in body and "16 Nov" in body and "https://igs.bkg.bund.de" in body
    assert "#" not in body.replace("&#x27;", "")   # no colour written into the markup


def test_show_draws_the_open_section_or_says_the_result_is_missing(monkeypatch):
    drawn, said = [], []
    monkeypatch.setattr(signals_view.reveal, "section", lambda *args, **kwargs: drawn.append((args, kwargs)))
    monkeypatch.setattr(signals_view.surfaces, "notice", lambda text, status: said.append(text) or "")
    monkeypatch.setattr(signals_view.surfaces, "show", lambda html: None)
    signals_view.show("NavIC")
    assert not drawn and said == ["Signals heard: the daily result is not available right now."]
    monkeypatch.setattr(signals_view.dashboard_data, "signals_heard",
                        lambda: {"day": "2026-11-16", "stations": [], "satellites": [{"satellite": "NVS-01", "signal_id": "I10",
                                                                                      "signals": {"L5": ["IISC"]}}]})
    signals_view.show("NavIC")
    assert drawn[0][0][0] == "signals_NavIC" and drawn[0][1] == {"open": True}
    assert drawn[0][0][1] == f"Signals heard on {signals_view._day_words('2026-11-16')}"   # its day, never "today"


def test_the_regional_overview_carries_the_section(monkeypatch):
    """The medium-orbit page calls the same signals_view.show; it has no data in AppTest, so only this one renders."""
    from ui import data

    monkeypatch.setattr(shell, "DEFAULT_PAGE", "Overview")
    payload = {"day": "2026-11-16", "stations": [{"code": "IISC00IND", "name": "IISC", "place": "Bengaluru, India", "read": True}],
               "satellites": [{"satellite": next(iter(data.SATELLITES["NavIC"])), "signal_id": "I02", "signals": {"L5": ["IISC"]}}]}
    monkeypatch.setattr(data, "signals_heard", lambda: payload)
    at = run(lambda at: at.session_state.__setitem__("scope", "NavIC"))
    assert any("Signals heard on" in box.proto.label for box in at.get("checkbox"))
    assert "IISC" in "".join(part.proto.body for part in at.get("html"))
