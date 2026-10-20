"""One way to call GitHub's API, for everything the admin console reads or writes. Never logs the token."""
import base64

import requests

from evidence.decision_settings import REPOSITORY

API = "https://api.github.com"
TIMEOUT_SECONDS = 20


def ask(method, path, token, repository=REPOSITORY, **request):
    """One call about `repository`; its JSON answer. Raises requests' errors when GitHub refuses or does not answer."""
    answer = requests.request(method, f"{API}/repos/{repository}{path}", timeout=TIMEOUT_SECONDS,
                              headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                              **request)
    answer.raise_for_status()
    return answer.json() if answer.content else None


def file_text(token, repository, path):
    """A text file from a repository's default branch."""
    return base64.b64decode(ask("GET", f"/contents/{path}", token, repository)["content"]).decode("utf-8")
