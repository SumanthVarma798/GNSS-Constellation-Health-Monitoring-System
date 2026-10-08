"""The archive keeps a copy only when a source changes, and never mistakes a failure for a change."""
import hashlib

import pytest

from evidence.archive import MAX_BYTES, FetchFailed, object_path, read_versions, record

ADDRESS = "https://example.org/notice"


def test_first_copy_is_kept_under_its_hash(tmp_path):
    row = record(tmp_path, ADDRESS, "2026-10-08T10:00:00Z", 200, b"first", "text/html")

    sha256 = hashlib.sha256(b"first").hexdigest()
    assert row == {"address": ADDRESS, "fetched_at": "2026-10-08T10:00:00Z", "status": "200", "sha256": sha256,
                   "bytes": "5", "content_type": "text/html", "wayback_url": ""}
    assert object_path(tmp_path, sha256).read_bytes() == b"first"
    assert read_versions(tmp_path) == [row]


def test_unchanged_page_writes_nothing(tmp_path):
    record(tmp_path, ADDRESS, "2026-10-08T10:00:00Z", 200, b"same")

    assert record(tmp_path, ADDRESS, "2026-10-08T16:00:00Z", 200, b"same") is None
    assert len(read_versions(tmp_path)) == 1


def test_changed_page_keeps_both_versions(tmp_path):
    record(tmp_path, ADDRESS, "2026-10-08T10:00:00Z", 200, b"before")
    record(tmp_path, ADDRESS, "2026-10-09T10:00:00Z", 200, b"after")

    kept = [row["sha256"] for row in read_versions(tmp_path)]
    assert [object_path(tmp_path, sha256).read_bytes() for sha256 in kept] == [b"before", b"after"]


def test_a_page_that_disappears_is_recorded_once(tmp_path):
    record(tmp_path, ADDRESS, "2026-10-08T10:00:00Z", 200, b"here")

    gone = record(tmp_path, ADDRESS, "2026-10-09T10:00:00Z", 404, b"<html>Not found</html>")
    assert (gone["status"], gone["sha256"], gone["bytes"]) == ("404", "", "0")
    assert record(tmp_path, ADDRESS, "2026-10-10T10:00:00Z", 404) is None
    # It comes back with the same text: that is a change too.
    assert record(tmp_path, ADDRESS, "2026-10-11T10:00:00Z", 200, b"here") is not None
    assert [row["status"] for row in read_versions(tmp_path)] == ["200", "404", "200"]


@pytest.mark.parametrize("status", [500, 503, 403, 429])
def test_a_failed_fetch_is_never_recorded_as_a_change(tmp_path, status):
    record(tmp_path, ADDRESS, "2026-10-08T10:00:00Z", 200, b"here")

    with pytest.raises(FetchFailed):
        record(tmp_path, ADDRESS, "2026-10-09T10:00:00Z", status, b"server trouble")
    assert len(read_versions(tmp_path)) == 1


def test_an_oversized_copy_is_refused(tmp_path):
    with pytest.raises(FetchFailed, match="over the"):
        record(tmp_path, ADDRESS, "2026-10-08T10:00:00Z", 200, b"x" * (MAX_BYTES + 1))
    assert read_versions(tmp_path) == []


def test_sources_are_tracked_separately(tmp_path):
    record(tmp_path, ADDRESS, "2026-10-08T10:00:00Z", 200, b"same")

    assert record(tmp_path, "https://example.org/other", "2026-10-08T10:00:00Z", 200, b"same") is not None
    assert len(list((tmp_path / "objects").rglob("*"))) == 2  # one folder, one copy: stored once
