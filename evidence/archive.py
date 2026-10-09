"""The raw-copy archive: every version of every source page or file, kept by its hash.

Layout of an archive folder:

    objects/<first two characters of the hash>/<hash>   one raw copy, never overwritten
    versions.csv                                        one row per change, oldest first

A row is written only when a source's content or availability changes. The
newest row for an address is its current state. Databases keep the hash from
that row, never the copy itself.

Everything fetched is untrusted data: it is stored and hashed, never run, and
never used to name a file.
"""
import csv
import hashlib
from http import HTTPStatus
from pathlib import Path

import requests

from evidence.settings import (ARCHIVE_OBJECTS_DIR, ARCHIVE_VERSION_COLUMNS, ARCHIVE_VERSIONS_FILE, GONE_STATUSES,
                               MAX_COPY_BYTES, REQUEST_TIMEOUT_SECONDS, USER_AGENT)


class FetchFailed(Exception):
    """The source could not be read this time. Not a change; nothing is recorded."""


def fetch(address):
    """Return (status, body, content_type) for one address."""
    try:
        response = requests.get(address, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
    except requests.RequestException as error:
        raise FetchFailed(f"{address}: {error}") from error
    return response.status_code, response.content, response.headers.get("Content-Type", "")


def object_path(archive, sha256):
    return Path(archive) / ARCHIVE_OBJECTS_DIR / sha256[:2] / sha256


def read_versions(archive):
    """Every change row, oldest first. An archive with no rows yet gives an empty list."""
    path = Path(archive) / ARCHIVE_VERSIONS_FILE
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def latest_version(archive, address):
    """The newest row for an address, or None if it was never kept. It may be a "gone" row."""
    return next((row for row in reversed(read_versions(archive)) if row["address"] == address), None)


def record(archive, address, fetched_at, status, body=b"", content_type=""):
    """Keep this fetch if it differs from the last one kept for the address.

    Returns the new row, or None when nothing changed. Raises FetchFailed for
    anything that is neither a good copy nor a clear "gone".
    """
    if status == HTTPStatus.OK:
        if len(body) > MAX_COPY_BYTES:
            raise FetchFailed(f"{address}: {len(body)} bytes is over the {MAX_COPY_BYTES}-byte limit")
        sha256 = hashlib.sha256(body).hexdigest()
    elif status in GONE_STATUSES:
        sha256, body, content_type = "", b"", ""
    else:
        raise FetchFailed(f"{address}: status {status}")

    row = dict(zip(ARCHIVE_VERSION_COLUMNS,
                   [address, fetched_at, str(status), sha256, str(len(body)), content_type, ""]))
    last = latest_version(archive, address)
    if last and (last["status"], last["sha256"]) == (row["status"], row["sha256"]):
        return None

    if sha256:
        path = object_path(archive, sha256)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)  # same hash means same bytes, so rewriting is harmless
    versions = Path(archive) / ARCHIVE_VERSIONS_FILE
    is_new = not versions.exists()
    with open(versions, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, ARCHIVE_VERSION_COLUMNS, lineterminator="\n")
        if is_new:
            writer.writeheader()
        writer.writerow(row)
    return row
