A one-off frozen copy of the bundled orbit data (data/*_tles.json, data/*_gp_history.json, 4 Oct 2026),
read only by the tests, through BUNDLED_DATA_DIR set in tests/conftest.py. It is not the norm: the app, the
dashboard and every job read the live data/ folder, and new tests should check behaviour without pinning this
snapshot's dates or values. The weekly "Update TLE Data" job never rewrites these files; refresh them only on
purpose, then re-record the golden scores (RECORD_GOLDEN=1, see tests/test_golden_scores.py).
