"""The attachment scan (scripts/contact_scan.py): it fetches what waits, runs clamscan once, reports each verdict, and
leaves what clamscan could not judge waiting. The Worker and clamscan are stand-ins."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import contact_scan

BASE = "https://feeds.example/contact"
CLEAN, BAD, BROKEN = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222", "33333333-3333-4333-8333-333333333333"


class Worker:
    def __init__(self, waiting):
        self.waiting, self.reports, self.headers = waiting, [], set()

    def get(self, url, params=None, headers=None, timeout=None):
        self.headers.add(headers["Authorization"])
        if url == f"{BASE}/attachments":
            assert params == {"scan": "pending"}
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: self.waiting)
        return SimpleNamespace(raise_for_status=lambda: None, content=f"bytes of {url.rsplit('/', 1)[1]}".encode())

    def post(self, url, json, headers, timeout):
        self.headers.add(headers["Authorization"])
        self.reports.append((url.removeprefix(f"{BASE}/attachments/"), json))
        return SimpleNamespace(raise_for_status=lambda: None)


def fake_clamscan(monkeypatch, lines, code):
    seen = {}

    def run(command, capture_output, text, check):
        folder = Path(command[-1])
        seen.update(command=command[:-1], files=sorted(p.name for p in folder.iterdir()),
                    bytes=(folder / CLEAN).read_bytes() if (folder / CLEAN).exists() else b"")
        return SimpleNamespace(returncode=code, stdout="\n".join(line.format(folder=folder) for line in lines))

    monkeypatch.setattr(contact_scan.subprocess, "run", run)
    return seen


def test_clamscan_lines_become_verdicts_and_errors_give_none():
    assert contact_scan.verdicts("/t/a: OK\n/t/b: Win.Test.EICAR_HDB-1 FOUND\n/t/c: Can't open file ERROR\nnoise") == {
        "a": ("clean", ""), "b": ("infected", "Win.Test.EICAR_HDB-1")}


def test_every_waiting_file_is_scanned_once_and_its_verdict_reported(monkeypatch):
    worker = Worker([{"id": CLEAN, "name": "plan.pdf"}, {"id": BAD, "name": "tool.docx"}, {"id": "../../etc", "name": "x"}])
    monkeypatch.setattr(contact_scan.requests, "get", worker.get)
    monkeypatch.setattr(contact_scan.requests, "post", worker.post)
    seen = fake_clamscan(monkeypatch, [f"{{folder}}/{CLEAN}: OK", f"{{folder}}/{BAD}: Eicar-Test-Signature FOUND"], 1)

    assert contact_scan.run("scan-t0ken", base=BASE) == 0

    assert seen["command"] == ["clamscan", "--no-summary", "--stdout"]
    assert seen["files"] == sorted([CLEAN, BAD]) and seen["bytes"] == f"bytes of {CLEAN}".encode()   # no odd id becomes a path
    assert worker.reports == [(f"{CLEAN}/scan", {"result": "clean", "signature": ""}),
                              (f"{BAD}/scan", {"result": "infected", "signature": "Eicar-Test-Signature"})]
    assert worker.headers == {"Bearer scan-t0ken"}


def test_a_file_clamscan_could_not_judge_waits_and_the_run_says_so(monkeypatch):
    worker = Worker([{"id": CLEAN, "name": "plan.pdf"}, {"id": BROKEN, "name": "odd.pdf"}])
    monkeypatch.setattr(contact_scan.requests, "get", worker.get)
    monkeypatch.setattr(contact_scan.requests, "post", worker.post)
    fake_clamscan(monkeypatch, [f"{{folder}}/{CLEAN}: OK", f"{{folder}}/{BROKEN}: Can't read ERROR"], 2)

    assert contact_scan.run("scan-t0ken", base=BASE) == 1
    assert [r[0] for r in worker.reports] == [f"{CLEAN}/scan"]


def test_with_nothing_waiting_clamscan_does_not_run(monkeypatch):
    worker = Worker([])
    monkeypatch.setattr(contact_scan.requests, "get", worker.get)
    monkeypatch.setattr(contact_scan.subprocess, "run", lambda *a, **k: pytest.fail("clamscan ran"))

    assert contact_scan.run("scan-t0ken", base=BASE) == 0 and worker.reports == []


def test_without_the_token_nothing_is_asked(monkeypatch, capsys):
    monkeypatch.delenv("CONTACT_SCAN_TOKEN", raising=False)
    monkeypatch.setattr(contact_scan.requests, "get", lambda *a, **k: pytest.fail("asked without a token"))

    contact_scan.main()
    assert "no CONTACT_SCAN_TOKEN" in capsys.readouterr().out
