"""The evidence model holds: who said what, about which satellite, and what we saw ourselves."""
import sqlite3

import pytest

from evidence.archive import record
from evidence.registry_tables import read_table
from evidence.settings import REGISTRY_SATELLITES_FILE
from evidence.store import build_store, new_store

ADDRESS = "https://operator.example/notices"


@pytest.fixture
def store():
    """An empty store with one satellite, and one document from each of two sources."""
    store = new_store()
    store.execute("INSERT INTO constellation VALUES ('C', 'BeiDou')")
    store.execute("INSERT INTO satellite VALUES ('C217', 'BeiDou', 'BDS-3G', '2018-085A', 43683, 'C04', 'G', '140E', NULL)")
    store.executemany("INSERT INTO source (id, name) VALUES (?, ?)",
                      [("operator.example", "The operator"), ("press.example", "A newspaper")])
    store.executemany("INSERT INTO document VALUES (?, ?, ?, ?, 200, ?, 10, NULL, NULL)",
                      [(1, "operator.example", ADDRESS, "2026-04-22T06:00:00Z", "a" * 64),
                       (2, "press.example", "https://press.example/story", "2026-05-01T06:00:00Z", "b" * 64)])
    return store


def test_two_sources_that_disagree_both_stay_attached_to_one_event(store):
    store.execute("INSERT INTO event VALUES (1, 'C217', '2026-04-21', 'Changed signal ID from C62 to C04')")
    store.execute("INSERT INTO claim VALUES (1, 1, 'C217', 'C217 broadcasts C04 from 21 Apr 2026', NULL)")
    store.execute("INSERT INTO claim VALUES (2, 2, 'C217', 'The change happened on 19 Apr 2026', NULL)")
    store.execute("INSERT INTO event_claim VALUES (1, 1, 'supports'), (1, 2, 'contests')")

    stances = store.execute("""SELECT source.name, event_claim.stance FROM event_claim
                               JOIN claim ON claim.id = event_claim.claim_id
                               JOIN document ON document.id = claim.document_id
                               JOIN source ON source.id = document.source_id ORDER BY claim.id""").fetchall()
    assert stances == [("The operator", "supports"), ("A newspaper", "contests")]


def test_an_event_can_stand_on_observation_alone(store):
    store.execute("INSERT INTO event VALUES (1, 'C217', '2026-06-02', 'Moved 0.4 degrees east; no notice found')")
    store.execute("INSERT INTO observation VALUES (1, 1, 'orbit', '2026-06-02T00:00:00Z', 'Longitude drifted 0.4 degrees')")

    assert store.execute("SELECT COUNT(*) FROM event_claim WHERE event_id = 1").fetchone() == (0,)
    assert store.execute("SELECT kind FROM observation WHERE event_id = 1").fetchall() == [("orbit",)]


@pytest.mark.parametrize("statement", [
    "INSERT INTO claim VALUES (1, 99, 'C217', 'No such document', NULL)",       # a claim needs its document
    "INSERT INTO claim VALUES (1, NULL, 'C217', 'No document at all', NULL)",
    "INSERT INTO claim VALUES (1, 1, 'X999', 'No such satellite', NULL)",
    "INSERT INTO claim VALUES (1, 1, 'C217', 'Credibility is 1 to 6', 7)",
    "INSERT INTO event VALUES (1, 'X999', NULL, 'No such satellite')",
    "INSERT INTO source VALUES ('x.example', 'X', 'G')",                        # reliability is A to F
    "INSERT INTO observation VALUES (1, 99, 'orbit', '2026-01-01T00:00:00Z', 'No such event')",
    "INSERT INTO event_claim VALUES (99, 99, 'supports')",
    "INSERT INTO document VALUES (9, 'operator.example', 'https://x', '2026-01-01T00:00:00Z', 200, NULL, 0, NULL, NULL)",  # a copy has a hash
    "INSERT INTO document VALUES (9, 'operator.example', 'https://x', '2026-01-01T00:00:00Z', 404, 'c', 0, NULL, NULL)",   # a gone page has none
])
def test_the_store_refuses_what_the_model_forbids(store, statement):
    with pytest.raises(sqlite3.IntegrityError):
        store.execute(statement)


def test_a_stance_is_supports_or_contests_and_nothing_else(store):
    store.execute("INSERT INTO event VALUES (1, 'C217', NULL, 'Something')")
    store.execute("INSERT INTO claim VALUES (1, 1, 'C217', 'Something', NULL)")
    with pytest.raises(sqlite3.IntegrityError):
        store.execute("INSERT INTO event_claim VALUES (1, 1, 'mentions')")


def test_last_updated_is_the_newest_document_behind_a_satellites_events(store):
    assert store.execute("SELECT * FROM satellite_last_updated").fetchall() == []

    store.execute("INSERT INTO event VALUES (1, 'C217', NULL, 'Something')")
    store.execute("INSERT INTO claim VALUES (1, 1, 'C217', 'From the operator', NULL), (2, 2, 'C217', 'From the press', NULL)")
    store.execute("INSERT INTO event_claim VALUES (1, 1, 'supports'), (1, 2, 'supports')")

    assert store.execute("SELECT * FROM satellite_last_updated").fetchall() == [("C217", "2026-05-01T06:00:00Z")]


def test_the_store_keeps_a_reference_to_a_document_never_the_document(store):
    columns = {name: kind for _, name, kind, *_ in store.execute("PRAGMA table_info(document)")}

    assert list(columns) == ["id", "source_id", "address", "fetched_at", "status", "sha256", "bytes",
                             "content_type", "wayback_url"]
    assert "BLOB" not in columns.values()
    for table, in store.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
        names = [name for _, name, *_ in store.execute(f"PRAGMA table_info({table})")]
        assert not {"body", "content", "text", "html", "raw"} & set(names), table


def test_the_store_is_built_from_the_archive_and_the_registry(tmp_path):
    archive = tmp_path / "archive"
    record(archive, ADDRESS, "2026-10-08T06:00:00Z", 200, b"first notice", "text/html")
    record(archive, ADDRESS, "2026-10-09T06:00:00Z", 200, b"edited notice", "text/html")
    record(archive, ADDRESS, "2026-10-10T06:00:00Z", 404)

    store = build_store(tmp_path / "store.sqlite3", archive)

    documents = store.execute("SELECT id, source_id, status, sha256 IS NULL, bytes FROM document ORDER BY id").fetchall()
    assert documents == [(1, "operator.example", 200, 0, 12), (2, "operator.example", 200, 0, 13), (3, "operator.example", 404, 1, 0)]
    assert store.execute("SELECT id, name, reliability FROM source").fetchall() == [("operator.example", "operator.example", None)]
    assert store.execute("SELECT COUNT(*) FROM satellite").fetchone() == (len(read_table(REGISTRY_SATELLITES_FILE)),)
    assert store.execute("SELECT signal_id_now, slot FROM satellite WHERE svn = 'C217'").fetchone() == ("C04", "140E")
    assert store.execute("PRAGMA foreign_key_check").fetchall() == []


def test_a_document_keeps_its_number_when_the_store_is_rebuilt(tmp_path):
    archive = tmp_path / "archive"
    record(archive, ADDRESS, "2026-10-08T06:00:00Z", 200, b"first notice")
    before = build_store(tmp_path / "store.sqlite3", archive).execute("SELECT id, sha256 FROM document").fetchall()

    record(archive, "https://other.example/page", "2026-10-09T06:00:00Z", 200, b"another page")
    after = build_store(tmp_path / "store.sqlite3", archive).execute("SELECT id, sha256 FROM document ORDER BY id").fetchall()

    assert after[:1] == before and [row[0] for row in after] == [1, 2]
