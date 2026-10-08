"""The IGS metadata parser must keep signal-ID history, with dates."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_satellite_ids import current_prn, parse_metadata
from evidence.igs_metadata import sinex_date

SAMPLE = """\
+SATELLITE/IDENTIFIER
*SVN_ COSPAR ID SatCat Block__________ Comment__________________________________
 C006 2010-057A  37210 BDS-2G          Launched 2010-10-31; BEIDOU 6
 C217 2018-085A  43683 BDS-3G          Launched 2018-11-01; BEIDOU 3G1
-SATELLITE/IDENTIFIER
+SATELLITE/PLANE
*SVN_ Valid_From____ Valid_To______ P Slot__ Comment____________________________
 C006 2010:304:00000 2026:111:28800 G 160E   [PL04]
 C217 2018:305:00000 0000:000:00000 G 140E   [PL04]
 C231 2023:137:00000 0000:000:00000 G        [PL04]
-SATELLITE/PLANE
+SATELLITE/PRN
*SVN_ Valid_From____ Valid_To______ PRN Comment_________________________________
 C006 2010:304:00000 2026:111:28800 C04 NABU 20260022
 C217 2018:305:00000 2026:090:46920 C59 NABU 20260005 + obs. data
 C217 2026:090:48000 2026:111:28800 C62 [PR04], NABU 20260022
 C217 2026:111:43200 0000:000:00000 C04 [PR04], NABU 20260022
-SATELLITE/PRN
"""


def test_signal_id_passes_from_one_satellite_to_another():
    by_norad, prn_history, slot = parse_metadata(SAMPLE)

    assert by_norad[43683]["svn"] == "C217"
    assert current_prn(prn_history["C217"]) == "C04"
    assert current_prn(prn_history["C006"]) is None  # the older holder of C04 gave it up
    assert prn_history["C217"][0] == ("2018-11-01", "2026-03-31", "C59")
    assert slot == {"C217": "140E"}  # closed periods and blank slots are skipped


def test_sinex_date():
    assert sinex_date("2026:111:43200") == "2026-04-21"
    assert sinex_date("0000:000:00000") is None
