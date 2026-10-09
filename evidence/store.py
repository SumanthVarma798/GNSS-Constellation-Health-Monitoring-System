"""The query store: a SQLite file built from the archive and the registry.

It is thrown away and rebuilt on every run, so it can never drift from what
it was built from. The model is in evidence/store_schema.sql.

The store holds references to documents, never the documents: a document row
carries the hash that names its raw copy in the archive.
"""
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from evidence.archive import read_versions
from evidence.confidence import read_source_grades
from evidence.registry_tables import read_table
from evidence.settings import (REGISTRY_CONSTELLATIONS_FILE, REGISTRY_SATELLITES_FILE, REGISTRY_SIGNAL_IDS_FILE,
                               STORE_SCHEMA_FILE)


def new_store(path=":memory:"):
    """An empty store with every table of the model, and its rules switched on."""
    store = sqlite3.connect(path)
    store.execute("PRAGMA foreign_keys = ON")  # SQLite leaves these off unless asked
    store.executescript(Path(STORE_SCHEMA_FILE).read_text())
    return store


def _blank_to_null(row):
    return [value if value != "" else None for value in row.values()]


def load_registry(store):
    """Constellations, satellites and their signal-ID periods, from the registry tables."""
    for table, name in (("constellation", REGISTRY_CONSTELLATIONS_FILE), ("satellite", REGISTRY_SATELLITES_FILE),
                        ("signal_id_period", REGISTRY_SIGNAL_IDS_FILE)):
        rows = [_blank_to_null(row) for row in read_table(name)]
        store.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' * len(rows[0]))})", rows)


def load_sources(store):
    """Every source a person has graded, from the source table."""
    store.executemany("INSERT INTO source (id, name, reliability) VALUES (?, ?, ?)",
                      [(row["source_id"], row["name"], row["reliability"]) for row in read_source_grades()])


def load_documents(store, archive):
    """One document row per row of the archive's change log.

    A source that is not in the source table yet is added under its host
    name, with no grade.

    A document's id is its row number in that log. The log is only ever added
    to, so the id is the same on every rebuild.
    """
    for number, row in enumerate(read_versions(archive), start=1):
        host = urlsplit(row["address"]).hostname
        store.execute("INSERT OR IGNORE INTO source (id, name) VALUES (?, ?)", (host, host))
        store.execute("INSERT INTO document VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (number, host, row["address"], row["fetched_at"], int(row["status"]), row["sha256"] or None,
                       int(row["bytes"]), row["content_type"] or None, row["wayback_url"] or None))


def build_store(path, archive):
    """Build the whole store afresh at `path`, replacing any file already there."""
    path = Path(path)
    path.unlink(missing_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    store = new_store(path)
    with store:
        load_registry(store)
        load_sources(store)
        load_documents(store, archive)
    return store
