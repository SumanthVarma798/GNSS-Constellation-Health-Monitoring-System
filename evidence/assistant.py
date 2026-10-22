"""The System design page's assistant: answers questions about the project in simple words, only from the project's
own material (evidence/assistant_settings.py says what that is), naming the source of each fact.

The whole material goes with every question, so the model has nothing else to draw on and the instructions can tell it
to refuse what the material does not say. A local model can still slip, so the page also lists any source an answer
names that is not in the material (unknown_sources).
"""
import ast
import csv
import json
import re
import time

import requests

from evidence.assistant_settings import (ANSWER_SECONDS, CODE_FOLDERS, CONTEXT_TOKENS, DOCUMENTS, HISTORY_TURNS,
                                         ISSUE_CHARACTERS, MODEL, OLLAMA_URL, ROOT, RULES, SOURCE_FILES)

PAGE_LABEL = "System design page"


class Unavailable(Exception):
    """The model cannot answer; the message says why in plain words."""


def _headers(key):
    return {"Authorization": f"Bearer {key}"} if key else {}


def available(url=OLLAMA_URL, key=""):
    """Whether the model can be asked: Ollama, or the gate in front of it, answers at `url` (with `key`)."""
    try:
        return requests.get(f"{url}/api/version", headers=_headers(key), timeout=5).ok
    except requests.RequestException:
        return False


def material(issues, parts):
    """Everything the assistant may answer from, each piece under its [label]. `issues` are GitHub's open issues,
    `parts` the System design page's words (ui/components/system_design.PARTS)."""
    pieces = [f"=== [{path}] ===\n{(ROOT / path).read_text(encoding='utf-8')}" for path in DOCUMENTS]
    pieces.extend(f"=== [{path}] ===\n{_source_lines(path)}" for path in SOURCE_FILES)
    pieces.append(f"=== [{PAGE_LABEL}] ===\n" + "\n".join(
        f"{name} ({kind}): {simple} Details: {'; '.join(tech)}. Limits: {'; '.join(limits)}. Lives in: {where}."
        for name, kind, simple, tech, limits, where in parts.values()))
    pieces.append("=== Code: the description at the top of each file ===\n" + "\n".join(
        f"[{path}] {doc}" for path, doc in _descriptions()))
    pieces.append("=== Open issues: planned work, not built ===\n" + "\n".join(
        f"[issue #{i['number']}] {i['title']}: {_short(i.get('body') or '')}" for i in issues))
    return "\n\n".join(pieces)


def _source_lines(path):
    """One compact line per source in a source list, with the fields an answer about news sources needs."""
    with (ROOT / path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if path.endswith("source_candidates.csv"):
        return "\n".join(
            f"{row['source_id']} | {row['name']} | {row['kind']} | {row['address']} | check status {row['check_status']}"
            f" | proposed grade {row['proposed_grade'] or 'none'} | {row['standing']}"
            for row in rows)
    return "\n".join(
        f"{row['source_id']} | {row['name']} | given grade {row['reliability']} | {row['graded_by']} | "
        f"graded {row['graded_on']} | {row['reason']}"
        for row in rows)


def _descriptions():
    files = sorted(ROOT.glob("*.py")) + sorted(p for folder in CODE_FOLDERS for p in (ROOT / folder).rglob("*.py"))
    for path in files:
        try:
            doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
        except SyntaxError:
            continue
        if doc:
            yield path.relative_to(ROOT).as_posix(), " ".join(doc.split("\n\n")[0].split())


def _short(text):
    text = " ".join(text.split())
    return text if len(text) <= ISSUE_CHARACTERS else text[:ISSUE_CHARACTERS].rsplit(" ", 1)[0] + " …"


def answer(question, history, material_text, url=OLLAMA_URL, key=""):
    """The answer, piece by piece as the model writes it. `history` is the earlier [{role, content}] turns."""
    messages = ([{"role": "system", "content": f"{RULES}\n\nMATERIAL:\n{material_text}"}]
                + history[-2 * HISTORY_TURNS:] + [{"role": "user", "content": question}])
    deadline = time.monotonic() + ANSWER_SECONDS
    try:
        reply = requests.post(f"{url}/api/chat", stream=True, timeout=ANSWER_SECONDS, headers=_headers(key),
                              json={"model": MODEL, "messages": messages, "stream": True, "think": False,
                                    "options": {"num_ctx": CONTEXT_TOKENS, "temperature": 0}})
    except requests.ConnectionError as error:
        raise Unavailable("The model is not reachable. On the computer that runs it, start `ollama serve` (and, for the "
                          "shared console, the gate and the tunnel).") from error
    except requests.RequestException as error:
        raise Unavailable(f"The model did not answer ({error.__class__.__name__}). Try again.") from error
    with reply:
        if reply.status_code == 404:
            raise Unavailable(f"The model {MODEL} is not on this computer. Get it once with `ollama pull {MODEL}`.")
        if reply.status_code == 429:
            raise Unavailable("The model is answering someone else's question. Try again in a minute.")
        if reply.status_code in (401, 403):
            raise Unavailable("The console's key for the model is not accepted. Check [assistant] key in its secrets.")
        try:
            reply.raise_for_status()
            for line in reply.iter_lines():
                if time.monotonic() > deadline:
                    raise Unavailable(f"The answer took longer than {ANSWER_SECONDS} seconds, so it was stopped. Try again.")
                if not line:
                    continue
                piece = json.loads(line)
                if piece.get("error"):
                    raise Unavailable(f"The model stopped: {piece['error']}")
                yield piece.get("message", {}).get("content", "")
        except requests.RequestException as error:
            raise Unavailable(f"The model did not answer ({error.__class__.__name__}). Try again.") from error
        except ValueError as error:   # a line that is not JSON
            raise Unavailable("The model's reply was not in the expected shape. Try again.") from error

def unknown_sources(answer_text, material_text):
    """Sources the answer names in [brackets] that the material has no label for: a sign the model made one up."""
    known = set(re.findall(r"\[([^\]\n]+)\]", material_text))
    named = {s.strip() for cited in re.findall(r"\[([^\]\n]+)\]", answer_text) for s in re.split(r"[;,]", cited)}
    return sorted(named - known - {""})
