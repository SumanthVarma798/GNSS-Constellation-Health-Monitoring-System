"""Run one failure drill against a throwaway archive folder.

    python scripts/drill.py source-down --archive FOLDER
"""
import argparse
import contextlib
import csv
import io
import os
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import archive_sources  # noqa: E402
from evidence.archive import read_limits  # noqa: E402
from evidence.settings import DOWNLOAD_TRIES  # noqa: E402

DRILLS = ("source-down", "news-source-down", "site-refusing")
DOWN_ADDRESS = "http://127.0.0.1:9/down"
RUN_LOG = Path("runs") / "archive.csv"


@dataclass
class DrillOutcome:
    name: str
    passed: bool
    person_needed: bool
    summary: str


def _exit_code(code):
    if code is None:
        return 0
    return code if isinstance(code, int) else 1


def _run_rows(folder):
    path = Path(folder) / RUN_LOG
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _print_last_run_rows(folder, count):
    rows = _run_rows(folder)
    for row in rows[-count:]:
        print(f"RUN LOG: {row['job']} | {row['result']} | {row['changed']}")


def _append_line(path, line):
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")


def _set_output(person_needed):
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        _append_line(output, f"person_needed={'true' if person_needed else 'false'}")


def _run_archive(folder, group, addresses):
    Path(folder).mkdir(parents=True, exist_ok=True)
    old_addresses = archive_sources.archived_addresses
    old_argv = sys.argv[:]
    stream = io.StringIO()
    try:
        archive_sources.archived_addresses = lambda _group: list(addresses)
        sys.argv = ["archive_sources.py", "--archive", str(folder), "--group", group]
        with contextlib.redirect_stdout(stream):
            try:
                archive_sources.main()
                code = 0
            except SystemExit as error:
                code = _exit_code(error.code)
    finally:
        archive_sources.archived_addresses = old_addresses
        sys.argv = old_argv
    print(stream.getvalue(), end="")   # the archive run's own lines, so the GitHub log shows each try
    return code, stream.getvalue()


@contextlib.contextmanager
def standin_site():
    hits = {"ok": 0, "refuse": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/ok":
                hits["ok"] += 1
                body, status = b"ok", 200
            elif self.path == "/refuse":
                hits["refuse"] += 1
                body, status = b"refused", 403
            else:
                body, status = b"missing", 404
            self.send_response(status)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", hits
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def _source_down(folder, group, name):
    with standin_site() as (root, _):
        code, output = _run_archive(folder, group, [f"{root}/ok", DOWN_ADDRESS])
    _print_last_run_rows(folder, 1)
    row = _run_rows(folder)[-1] if _run_rows(folder) else {}
    retries_seen = f"tried {DOWNLOAD_TRIES} times" in output
    result_ok = row.get("result") == "failed: 1 of 2 sources"
    person_needed = code != 0
    passed = retries_seen and result_ok and person_needed == (group == "documents")
    if passed:
        summary = (f"DRILL {name}: PASSED — dead source was tried {DOWNLOAD_TRIES} times, the run log says "
                   f"'failed: 1 of 2 sources', and the run exited {'non-zero' if person_needed else '0'}.")
    else:
        summary = (f"DRILL {name}: FAILED — expected tries={DOWNLOAD_TRIES}, result='failed: 1 of 2 sources', "
                   f"exit {'non-zero' if group == 'documents' else '0'}; got retries_seen={retries_seen}, "
                   f"result='{row.get('result')}', exit_code={code}.")
    return DrillOutcome(name=name, passed=passed, person_needed=person_needed, summary=summary)


def _site_refusing(folder):
    with standin_site() as (root, hits):
        addresses = [f"{root}/ok", f"{root}/refuse"]
        run1_code, _ = _run_archive(folder, "documents", addresses)
        refuse_hits_after_run1, ok_hits_after_run1 = hits["refuse"], hits["ok"]
        run2_code, _ = _run_archive(folder, "documents", addresses)
        refuse_hits_after_run2, ok_hits_after_run2 = hits["refuse"], hits["ok"]
    _print_last_run_rows(folder, 2)
    row = read_limits(folder).get("127.0.0.1")
    print(f"LIMITS: {row}")
    rows = _run_rows(folder)
    result1 = rows[-2]["result"] if len(rows) >= 2 else ""
    result2 = rows[-1]["result"] if rows else ""
    waiting_logged = "waiting out a refusal" in result2
    # The back-off covers the whole site, so run 2 asks neither address on it.
    run2_skipped_refuse = refuse_hits_after_run2 == refuse_hits_after_run1 and ok_hits_after_run2 == ok_hits_after_run1
    has_backoff = bool(row and row.get("last_answer") == "403")
    person_needed = run1_code != 0   # a graded source refusing fails run 1, which alerts; run 2 waits quietly
    passed = (run1_code != 0 and refuse_hits_after_run1 == 1 and result1 == "failed: 1 of 2 sources" and has_backoff
              and waiting_logged
              and run2_skipped_refuse and run2_code == 0)
    if passed:
        summary = ("DRILL site-refusing: PASSED — run 1 asked the refusing site once (a 403 is not retried), wrote a "
                   "back-off, and failed because a graded source answered 403 (an alert: a person should look); run 2 "
                   "did not ask that site again (its back-off covers the whole site), logged 'waiting out a refusal', and passed.")
    else:
        summary = ("DRILL site-refusing: FAILED — expected run1 to ask /refuse once and end non-zero with result 'failed: 1 of 2 sources' and "
                   "back-off, then run2 to skip /refuse, log waiting out a refusal, and exit 0; got "
                   f"run1_code={run1_code}, refuse_asked={refuse_hits_after_run1}, run1_result='{result1}', has_backoff={has_backoff}, "
                   f"run2_code={run2_code}, run2_result='{result2}', skipped_refuse={run2_skipped_refuse}.")
    return DrillOutcome(name="site-refusing", passed=passed, person_needed=person_needed, summary=summary)


def run_drill(name, folder):
    folder = Path(folder)
    if name == "source-down":
        return _source_down(folder, "documents", name)
    if name == "news-source-down":
        return _source_down(folder, "news", name)
    if name == "site-refusing":
        return _site_refusing(folder)
    raise ValueError(f"Unknown drill '{name}'")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drill", choices=DRILLS)
    parser.add_argument("--archive", required=True, help="throwaway archive folder")
    args = parser.parse_args()

    outcome = run_drill(args.drill, args.archive)
    print(outcome.summary)
    print(f"PERSON NEEDED: {'yes' if outcome.person_needed else 'no'}")
    _append_line(os.getenv("GITHUB_STEP_SUMMARY"), outcome.summary)
    _set_output(outcome.person_needed)
    sys.exit(0 if outcome.passed else 1)


if __name__ == "__main__":
    main()
