"""The archive keeps a copy only when a source changes, and never mistakes a failure for a change."""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from evidence.archive import FetchFailed, latest_version, object_path, read_versions, record, thin
from evidence import archive
from evidence.settings import MAX_COPY_BYTES

ADDRESS = "https://example.org/notice"
OTHER_ADDRESS = "https://example.org/other"
NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)


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
        record(tmp_path, ADDRESS, "2026-10-08T10:00:00Z", 200, b"x" * (MAX_COPY_BYTES + 1))
    assert read_versions(tmp_path) == []


def test_sources_are_tracked_separately(tmp_path):
    record(tmp_path, ADDRESS, "2026-10-08T10:00:00Z", 200, b"same")

    assert record(tmp_path, "https://example.org/other", "2026-10-08T10:00:00Z", 200, b"same") is not None
    assert len(list((tmp_path / "objects").rglob("*"))) == 2  # one folder, one copy: stored once


def test_latest_version_is_the_newest_row_even_when_the_page_is_gone(tmp_path):
    assert latest_version(tmp_path, ADDRESS) is None

    record(tmp_path, ADDRESS, "2026-10-08T10:00:00Z", 200, b"here")
    assert latest_version(tmp_path, ADDRESS)["fetched_at"] == "2026-10-08T10:00:00Z"

    record(tmp_path, ADDRESS, "2026-10-09T10:00:00Z", 404)
    assert (latest_version(tmp_path, ADDRESS)["status"], latest_version(tmp_path, ADDRESS)["sha256"]) == ("404", "")


def test_thin_removes_an_old_big_non_newest_copy_and_keeps_versions_csv_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "ARCHIVE_THIN_FROM_BYTES", 4)
    old = record(tmp_path, ADDRESS, "2026-10-01T10:00:00Z", 200, b"old-big")
    newest = record(tmp_path, ADDRESS, "2026-10-29T10:00:00Z", 200, b"new-big")
    before = read_versions(tmp_path)

    thinned = thin(tmp_path, [ADDRESS], NOW)

    assert thinned == [old]
    assert not object_path(tmp_path, old["sha256"]).exists()
    assert object_path(tmp_path, newest["sha256"]).read_bytes() == b"new-big"
    assert read_versions(tmp_path) == before


def test_thin_keeps_the_newest_copy_of_an_address_even_when_old_and_big(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "ARCHIVE_THIN_FROM_BYTES", 4)
    row = record(tmp_path, ADDRESS, "2026-10-01T10:00:00Z", 200, b"only-big")

    assert thin(tmp_path, [ADDRESS], NOW) == []
    assert object_path(tmp_path, row["sha256"]).read_bytes() == b"only-big"


def test_thin_keeps_small_old_copies(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "ARCHIVE_THIN_FROM_BYTES", 4)
    row = record(tmp_path, ADDRESS, "2026-10-01T10:00:00Z", 200, b"abc")

    assert thin(tmp_path, [ADDRESS], NOW) == []
    assert object_path(tmp_path, row["sha256"]).read_bytes() == b"abc"


def test_thin_keeps_big_copies_younger_than_the_window(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "ARCHIVE_THIN_FROM_BYTES", 4)
    row = record(tmp_path, ADDRESS, "2026-10-20T10:00:00Z", 200, b"young-big")

    assert thin(tmp_path, [ADDRESS], NOW) == []
    assert object_path(tmp_path, row["sha256"]).read_bytes() == b"young-big"


def test_thin_keeps_a_hash_that_is_the_newest_of_another_address(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "ARCHIVE_THIN_FROM_BYTES", 4)
    old = record(tmp_path, ADDRESS, "2026-10-01T10:00:00Z", 200, b"shared")
    record(tmp_path, OTHER_ADDRESS, "2026-10-20T10:00:00Z", 200, b"shared")

    assert thin(tmp_path, [ADDRESS], NOW) == []
    assert object_path(tmp_path, old["sha256"]).read_bytes() == b"shared"


def test_thin_only_touches_the_addresses_passed_in(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "ARCHIVE_THIN_FROM_BYTES", 4)
    old = record(tmp_path, ADDRESS, "2026-10-01T10:00:00Z", 200, b"old-big")
    record(tmp_path, ADDRESS, "2026-10-20T10:00:00Z", 200, b"new-big")
    other_old = record(tmp_path, OTHER_ADDRESS, "2026-10-01T10:00:00Z", 200, b"other-old")
    record(tmp_path, OTHER_ADDRESS, "2026-10-20T10:00:00Z", 200, b"other-new")

    thin(tmp_path, [ADDRESS], NOW)

    assert not object_path(tmp_path, old["sha256"]).exists()
    assert object_path(tmp_path, other_old["sha256"]).read_bytes() == b"other-old"


def test_the_archive_workflow_counts_only_added_object_files():
    workflow = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "archive.yml").read_text()

    assert "git diff --cached --name-only --diff-filter=A -- objects | wc -l" in workflow


def test_thin_keeps_the_last_real_copy_when_the_page_is_now_gone(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "ARCHIVE_THIN_FROM_BYTES", 4)
    last = record(tmp_path, ADDRESS, "2026-10-01T10:00:00Z", 200, b"last-big")
    record(tmp_path, ADDRESS, "2026-10-29T10:00:00Z", 404)

    assert thin(tmp_path, [ADDRESS], NOW) == []
    assert object_path(tmp_path, last["sha256"]).read_bytes() == b"last-big"


def test_only_groups_read_newest_first_are_thinned_never_the_feeds_news_rereads():
    from evidence.settings import ARCHIVE_THIN_GROUPS
    from evidence.sources import ARCHIVED_SOURCES

    assert set(ARCHIVE_THIN_GROUPS) <= set(ARCHIVED_SOURCES)
    assert not {"news", "social", "x"} & set(ARCHIVE_THIN_GROUPS)
