"""The raw-copy archive: every version of every source page or file, kept by its hash.

Layout of an archive folder:

    objects/<first two characters of the hash>/<hash>   one raw copy, never overwritten
    versions.csv                                        one row per change, oldest first
    runs/<job file>.csv                                 one row per run of a scheduled job, oldest first

A row is written only when a source's content or availability changes. The
newest row for an address is its current state. Databases keep the hash from
that row, never the copy itself.

Everything fetched is untrusted data: it is stored and hashed, never run, and
never used to name a file.
"""
import csv
import hashlib
import time
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

from evidence.settings import (ARCHIVE_OBJECTS_DIR, ARCHIVE_RUN_COLUMNS, ARCHIVE_RUNS_DIR, ARCHIVE_VERSION_COLUMNS,
                               ARCHIVE_VERSIONS_FILE, DEFAULT_MIN_GAP, DOWNLOAD_TRIES, GONE_STATUSES, MAX_COPY_BYTES,
                               MIN_GAP_BETWEEN_DOWNLOADS, NEVER_FETCH, REQUEST_TIMEOUT_SECONDS, RETRY_STATUSES,
                               USER_AGENT, WAIT_BETWEEN_TRIES_SECONDS)


class FetchFailed(Exception):
    """The source could not be read this time. Not a change; nothing is recorded."""


def site(address):
    """The site an address belongs to: a site named in MIN_GAP_BETWEEN_DOWNLOADS that holds its host, or else the host."""
    host = (urlsplit(address).hostname or "").lower()
    return next((name for name in MIN_GAP_BETWEEN_DOWNLOADS if host == name or host.endswith("." + name)), host)


def min_gap(address):
    """The shortest time allowed between two of our requests to this address's site (see MIN_GAP_BETWEEN_DOWNLOADS)."""
    return MIN_GAP_BETWEEN_DOWNLOADS.get(site(address), DEFAULT_MIN_GAP)


def pacer(fetch_one=None, clock=None, sleep=None):
    """A `paced_fetch(address)` for one run: fetch, after waiting out the site's minimum gap since our last request
    to that site ended. Counting from the end means the retries inside one fetch never eat into the gap."""
    fetch_one, clock, sleep = fetch_one or fetch, clock or time.monotonic, sleep or time.sleep
    ended = {}

    def paced_fetch(address):
        name = site(address)
        if name in ended:
            sleep(max(0.0, ended[name] + min_gap(address).total_seconds() - clock()))
        try:
            return fetch_one(address)
        finally:
            ended[name] = clock()

    return paced_fetch


def refuse_if_never_fetched(address):
    """Raise FetchFailed for a site in NEVER_FETCH, before any request is made to it."""
    host = (urlsplit(address).hostname or "").lower()
    if any(name in host for name in NEVER_FETCH):
        raise FetchFailed(f"{address}: never fetched (a tracker site, read only through journalists)")


def _no_redirect_to_never_fetched(response, **_):
    if response.is_redirect:
        refuse_if_never_fetched(urljoin(response.url, response.headers["Location"]))


def fetch(address):
    """Return (status, body, content_type) for one address.

    A network error or a RETRY_STATUSES reply is tried again, DOWNLOAD_TRIES times in all with
    WAIT_BETWEEN_TRIES_SECONDS between, unless that wait is shorter than the source's minimum gap:
    such a source is tried once per run. The last reply is returned whatever its status.
    A site in NEVER_FETCH is refused, and so is a redirect to one.
    """
    refuse_if_never_fetched(address)
    tries = 1 if min_gap(address) > timedelta(seconds=WAIT_BETWEEN_TRIES_SECONDS) else DOWNLOAD_TRIES
    for attempt in range(1, tries + 1):
        if attempt > 1:
            time.sleep(WAIT_BETWEEN_TRIES_SECONDS)
        try:
            response = requests.get(address, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT},
                                    hooks={"response": _no_redirect_to_never_fetched})
        except requests.RequestException as error:
            if attempt == tries:
                raise FetchFailed(f"{address}: {error} (tried {tries} times)") from error
            continue
        if response.status_code not in RETRY_STATUSES or attempt == tries:
            return response.status_code, response.content, response.headers.get("Content-Type", "")


def object_path(archive, sha256):
    return Path(archive) / ARCHIVE_OBJECTS_DIR / sha256[:2] / sha256


def _rows(path):
    """Every row of one CSV file, oldest first; a file not written yet gives an empty list."""
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_versions(archive):
    """Every change row, oldest first. An archive with no rows yet gives an empty list."""
    return _rows(Path(archive) / ARCHIVE_VERSIONS_FILE)


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


def log_run(archive, log, job, started, ended, result, changed):
    """Add one line to the run log `runs/<log>.csv`: which job, when it started and ended, how it went, what changed."""
    path = Path(archive) / ARCHIVE_RUNS_DIR / f"{log}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, ARCHIVE_RUN_COLUMNS, lineterminator="\n")
        if is_new:
            writer.writeheader()
        writer.writerow(dict(zip(ARCHIVE_RUN_COLUMNS, [job, started, ended, result, changed])))


def read_runs(archive, log):
    """Every line of one run log, oldest first; empty before its first run."""
    return _rows(Path(archive) / ARCHIVE_RUNS_DIR / f"{log}.csv")
