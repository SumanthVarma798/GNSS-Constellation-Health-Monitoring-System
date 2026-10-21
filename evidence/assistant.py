"""The System design page's assistant: answers questions about the project in simple words, only from the project's
own material (evidence/assistant_settings.py says what that is), naming the source of each fact.

The whole material goes with every question, so the model has nothing else to draw on and the instructions can tell it
to refuse what the material does not say. A local model can still slip, so the page also lists any source an answer
names that is not in the material (unknown_sources).
"""
import ast
import json
import re
import time

import requests

from evidence.assistant_settings import (ANSWER_SECONDS, CODE_FOLDERS, CONTEXT_TOKENS, DOCUMENTS, HISTORY_TURNS,
                                         ISSUE_CHARACTERS, MODEL, OLLAMA_URL, ROOT, RULES)

PAGE_LABEL = "System design page"


class Unavailable(Exception):
    """The model cannot answer; the message says why in plain words."""


def available():
    """Whether the model can be asked here: Ollama answers at OLLAMA_URL. False on the shared console, which has none."""
    try:
        return requests.get(f"{OLLAMA_URL}/api/version", timeout=2).ok
    except requests.RequestException:
        return False


def material(issues, parts):
    """Everything the assistant may answer from, each piece under its [label]. `issues` are GitHub's open issues,
    `parts` the System design page's words (ui/components/system_design.PARTS)."""
    pieces = [f"=== [{path}] ===\n{(ROOT / path).read_text(encoding='utf-8')}" for path in DOCUMENTS]
    pieces.append(f"=== [{PAGE_LABEL}] ===\n" + "\n".join(
        f"{name} ({kind}): {simple} Details: {'; '.join(tech)}. Limits: {'; '.join(limits)}. Lives in: {where}."
        for name, kind, simple, tech, limits, where in parts.values()))
    pieces.append("=== Code: the description at the top of each file ===\n" + "\n".join(
        f"[{path}] {doc}" for path, doc in _descriptions()))
    pieces.append("=== Open issues: planned work, not built ===\n" + "\n".join(
        f"[issue #{i['number']}] {i['title']}: {_short(i.get('body') or '')}" for i in issues))
    return "\n\n".join(pieces)


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


def answer(question, history, material_text):
    """The answer, piece by piece as the model writes it. `history` is the earlier [{role, content}] turns."""
    messages = ([{"role": "system", "content": f"{RULES}\n\nMATERIAL:\n{material_text}"}]
                + history[-2 * HISTORY_TURNS:] + [{"role": "user", "content": question}])
    deadline = time.monotonic() + ANSWER_SECONDS
    try:
        reply = requests.post(f"{OLLAMA_URL}/api/chat", stream=True, timeout=ANSWER_SECONDS,
                              json={"model": MODEL, "messages": messages, "stream": True, "think": False,
                                    "options": {"num_ctx": CONTEXT_TOKENS, "temperature": 0}})
    except requests.ConnectionError as error:
        raise Unavailable(f"The local model is not running. Start it with `ollama serve` (at {OLLAMA_URL}).") from error
    except requests.RequestException as error:
        raise Unavailable(f"The model did not answer ({error.__class__.__name__}). Try again.") from error
    with reply:
        if reply.status_code == 404:
            raise Unavailable(f"The model {MODEL} is not on this computer. Get it once with `ollama pull {MODEL}`.")
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
