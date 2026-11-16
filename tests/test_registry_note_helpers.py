from evidence.registry_tables import LAUNCH_NOTE_FORMAT, launch_date, launch_name


def test_launch_note_helpers_read_standard_note():
    note = LAUNCH_NOTE_FORMAT.format(launch_words="Launched 2026-10-30", name="NVS-03 (IRNSS-1L)")
    assert launch_date(note).isoformat() == "2026-10-30"
    assert launch_name(note) == "NVS-03 (IRNSS-1L)"


def test_launch_note_helpers_keep_name_when_date_not_read():
    note = LAUNCH_NOTE_FORMAT.format(launch_words="Launch date not read", name="NVS-03 (IRNSS-1L)")
    assert launch_date(note) is None
    assert launch_name(note) == "NVS-03 (IRNSS-1L)"
