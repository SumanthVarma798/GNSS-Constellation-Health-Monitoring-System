"""Scan the contact inbox's waiting attachments for viruses with ClamAV, and tell the inbox what was found.

    CONTACT_SCAN_TOKEN=... python scripts/contact_scan.py

Run by .github/workflows/contact-scan.yml every 30 minutes. Lists the attachments still waiting
(GET /contact/attachments?scan=pending on the newsletters Worker), downloads each into a temporary folder, runs
clamscan once over them all, and posts each verdict (POST /contact/attachments/<id>/scan). The Worker deletes an
infected file's bytes and keeps its record with the signature; a clean one can then be downloaded in the console.
A file clamscan could not judge stays waiting for the next run, and the run exits non-zero so it shows as failed.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.console_settings import CONTACT_INBOX_URL
from evidence.contact_settings import SCAN_TOKEN_ENV

TIMEOUT = 60   # seconds per request
ID = re.compile(r"[0-9a-f-]{36}")   # as the Worker makes them; nothing else becomes a path or an address


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def waiting(token, base=CONTACT_INBOX_URL):
    """The attachments not yet scanned: [{id, name, size, ...}]."""
    answer = requests.get(f"{base}/attachments", params={"scan": "pending"}, headers=_bearer(token), timeout=TIMEOUT)
    answer.raise_for_status()
    return answer.json()


def download(token, attachment_id, base=CONTACT_INBOX_URL):
    answer = requests.get(f"{base}/attachments/{attachment_id}", headers=_bearer(token), timeout=TIMEOUT)
    answer.raise_for_status()
    return answer.content


def report(token, attachment_id, result, signature="", base=CONTACT_INBOX_URL):
    answer = requests.post(f"{base}/attachments/{attachment_id}/scan", json={"result": result, "signature": signature},
                           headers=_bearer(token), timeout=TIMEOUT)
    answer.raise_for_status()


def verdicts(output):
    """{file name: (result, signature)} from clamscan's lines: "<path>: OK" or "<path>: <signature> FOUND". A line
    of any other kind (an error) gives no verdict, so that file waits for the next run."""
    found = {}
    for line in output.splitlines():
        path, _, said = line.rpartition(": ")
        if not path:
            continue
        if said == "OK":
            found[Path(path).name] = ("clean", "")
        elif said.endswith(" FOUND"):
            found[Path(path).name] = ("infected", said[:-len(" FOUND")].strip())
    return found


def scan(folder, clamscan="clamscan"):
    """clamscan over every file in `folder`: its exit code (0 none found, 1 some found, 2 an error) and its lines."""
    done = subprocess.run([clamscan, "--no-summary", "--stdout", str(folder)], capture_output=True, text=True, check=False)
    return done.returncode, done.stdout


def run(token, clamscan="clamscan", base=CONTACT_INBOX_URL):
    """Scan everything waiting and report it. Returns how many files are still unjudged."""
    files = [f for f in waiting(token, base) if ID.fullmatch(str(f.get("id", "")))]
    if not files:
        print("No attachment is waiting to be scanned.")
        return 0
    with tempfile.TemporaryDirectory() as folder:
        for f in files:   # each saved under its id, never its sender's name
            (Path(folder) / f["id"]).write_bytes(download(token, f["id"], base))
        code, output = scan(folder, clamscan)
        found = verdicts(output)
    unjudged = 0
    for f in files:
        if f["id"] not in found:
            unjudged += 1
            print(f"{f['id']} ({f.get('name', '')}): not judged (clamscan exit {code}); it waits for the next run.")
            continue
        result, signature = found[f["id"]]
        report(token, f["id"], result, signature, base)
        print(f"{f['id']} ({f.get('name', '')}): {result}{f' ({signature})' if signature else ''}")
    return unjudged


def main():
    token = os.environ.get(SCAN_TOKEN_ENV, "").strip()
    if not token:
        print(f"::warning::Not scanned: no {SCAN_TOKEN_ENV}. Attachments stay 'being scanned' until it is set.")
        return
    sys.exit(1 if run(token) else 0)


if __name__ == "__main__":
    main()
