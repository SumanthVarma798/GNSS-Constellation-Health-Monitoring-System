import re
import sys
from pathlib import Path

from evidence import archive

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import drill  # noqa: E402


def run(name, tmp_path, monkeypatch):
    monkeypatch.setattr(archive.time, "sleep", lambda *_: None)
    return drill.run_drill(name, tmp_path / name)


def test_in_process_drills_pass_with_expected_person_needed(monkeypatch, tmp_path):
    source_down = run("source-down", tmp_path, monkeypatch)
    news_source_down = run("news-source-down", tmp_path, monkeypatch)
    site_refusing = run("site-refusing", tmp_path, monkeypatch)

    assert source_down.passed and source_down.person_needed is True
    assert news_source_down.passed and news_source_down.person_needed is False
    assert site_refusing.passed and site_refusing.person_needed is True


def test_workflow_choices_match_known_drills_plus_push_conflict():
    workflow = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "drills.yml").read_text()
    block = re.search(r"options:\s*\n((?:\s*-\s*[a-z-]+\s*\n)+)", workflow)
    assert block, "drills.yml must have a choice options block"
    options = [line.split("-", 1)[1].strip() for line in block.group(1).splitlines() if "-" in line]
    assert options == [*drill.DRILLS, "push-conflict"]


def test_archive_workflow_has_the_save_line_push_conflict_uses():
    archive_workflow = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "archive.yml").read_text()
    assert "git push --quiet || { git pull --rebase --quiet && git push --quiet; }" in archive_workflow
