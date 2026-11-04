"""The console's assistant (its Ask page): answers questions about the project in simple words, only from the project's
own material (evidence/assistant_settings.py says what that is), naming the source of each fact.

The whole material goes with every question, so the model has nothing else to draw on and the instructions can tell it
to refuse what the material does not say. It asks DeepSeek's hosted model or an Ollama, as the console's secrets say. A
model can still slip, so the page also lists any source an answer names that is not in the material (unknown_sources).
"""
import ast
import csv
import json
import re
import time

import requests

from evidence.assistant_settings import (ANSWER_SECONDS, ANSWER_TOKENS, CODE_FOLDERS, CONTEXT_TOKENS, DEEPSEEK,
                                         DEEPSEEK_MODEL, DOCUMENTS, HISTORY_TOKENS, HISTORY_TURNS, ISSUE_CHARACTERS,
                                         MODEL, OLLAMA, OLLAMA_URL, REMINDER, ROOT, RULES, SOURCE_FILES, SYSTEMS, TRACKED,
                                         WORKFLOWS)

PAGE_LABEL = "System design page"


class Unavailable(Exception):
    """The model cannot answer; the message says why in plain words."""


def _headers(key):
    return {"Authorization": f"Bearer {key}"} if key else {}


def model_name(provider=OLLAMA):
    return DEEPSEEK_MODEL if provider == DEEPSEEK else MODEL


def available(url=OLLAMA_URL, key="", provider=OLLAMA):
    """Whether the model can be asked: for DeepSeek, a key is set (a refused one is said when asking); for Ollama, it
    or the gate in front of it answers at `url` (with `key`)."""
    if provider == DEEPSEEK:
        return bool(key)
    try:
        return requests.get(f"{url}/api/version", headers=_headers(key), timeout=5).ok
    except requests.RequestException:
        return False


def material(issues, parts, pulls=()):
    """Everything the assistant may answer from, each piece under its [label]. `issues` are GitHub's open issues,
    `parts` the System design page's words (ui/components/system_design.PARTS), `pulls` GitHub's latest closed pull
    requests (only the merged ones are used). What changes from day to day comes last."""
    pieces = [f"=== [{path}] ===\n{(ROOT / path).read_text(encoding='utf-8')}" for path in DOCUMENTS]
    pieces.extend(f"=== [{path.relative_to(ROOT).as_posix()}] ===\n{_job_lines(path)}"
                  for path in sorted((ROOT / WORKFLOWS).glob("*.yml")))
    pieces.append(f"=== [{TRACKED}] ===\n{_tracked()}")
    pieces.extend(f"=== [{path}] ===\n{_source_lines(path)}" for path in SOURCE_FILES)
    pieces.append(f"=== [{PAGE_LABEL}] ===\n" + "\n".join(
        f"{name} ({kind}): {simple} Details: {'; '.join(tech)}. Limits: {'; '.join(limits)}. Lives in: {where}."
        for name, kind, simple, tech, limits, where in parts.values()))
    pieces.append("=== The description at the top of each code file; cite the file named at the start of its line ===\n"
                  + "\n".join(f"[{path}] {doc}" for path, doc in _descriptions()))
    merged = sorted((p for p in pulls if p.get("merged_at")), key=lambda p: p["merged_at"], reverse=True)
    pieces.append("=== Merged pull requests, newest first: changes that are built; cite each by its PR number ===\n"
                  + "\n".join(f"[PR #{p['number']}] {p['title']} (merged {p['merged_at'][:10]})" for p in merged))
    pieces.append("=== Open issues: planned work, not built; cite each by its issue number ===\n"
                  + "\n".join(f"[issue #{i['number']}] {i['title']}: {_short(i.get('body') or '')}" for i in issues))
    return "\n\n".join(pieces)


def tokens(text):
    """About how many tokens `text` is: 3 characters a token, on the high side for English and code."""
    return len(text) // 3 + 1   # ponytail: a rough count; use the model's own tokenizer if a budget must be exact


def _job_lines(path):
    """A job file's opening comment, its name, and each schedule line with the comment just above it: what the job
    does, when, and what it reports to."""
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = set(range(next((n for n, line in enumerate(lines) if not line.startswith("#")), len(lines))))
    for n, line in enumerate(lines):
        if line.startswith("name:") or "cron:" in line:
            kept.add(n)
            above = n - 1
            while above >= 0 and lines[above].strip().startswith("#"):
                kept.add(above)
                above -= 1
    return "\n".join(lines[n].strip().lstrip("# ").rstrip() for n in sorted(kept))


def _tracked():
    """How many satellites the dashboard tracks, in all and per system, each listed by its id and dashboard name."""
    with (ROOT / TRACKED).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with (ROOT / SYSTEMS).open(newline="", encoding="utf-8") as handle:
        names = {row["svn_letter"]: row["constellation"] for row in csv.DictReader(handle)}
    systems = {}
    for row in rows:
        systems.setdefault(names.get(row["svn"][0], row["svn"][0]), []).append(f"{row['svn']} {row['dashboard_name']}")
    return f"{len(rows)} satellites tracked in all. Per system (satellite id, then its name on the dashboard):\n" + "\n".join(
        f"{system}: {len(listed)} satellites: {'; '.join(listed)}" for system, listed in systems.items())


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


def answer(question, history, material_text, url=OLLAMA_URL, key="", provider=OLLAMA):
    """The answer, piece by piece as the model writes it. `history` is the earlier [{role, content}] turns."""
    system = f"{RULES}\n\nMATERIAL:\n{material_text}"
    hosted = provider == DEEPSEEK
    room = HISTORY_TOKENS if hosted else min(  # Ollama shares one context among all of it
        HISTORY_TOKENS, CONTEXT_TOKENS - tokens(system) - tokens(REMINDER) - tokens(question) - ANSWER_TOKENS)
    messages = ([{"role": "system", "content": system}] + recent(history, room)
                + [{"role": "system", "content": REMINDER}, {"role": "user", "content": question}])
    if hosted:   # OpenAI-style chat completions, streamed as server-sent events
        address = f"{url}/chat/completions"
        body = {"model": DEEPSEEK_MODEL, "messages": messages, "stream": True, "thinking": {"type": "disabled"},
                "temperature": 0}
    else:
        address = f"{url}/api/chat"
        body = {"model": MODEL, "messages": messages, "stream": True, "think": False,
                "options": {"num_ctx": CONTEXT_TOKENS, "num_predict": ANSWER_TOKENS, "temperature": 0}}
    deadline = time.monotonic() + ANSWER_SECONDS
    try:
        reply = requests.post(address, stream=True, timeout=ANSWER_SECONDS, headers=_headers(key), json=body)
    except requests.ConnectionError as error:
        raise Unavailable("DeepSeek's service is not reachable from the console. Try again in a few minutes." if hosted
                          else "The model is not reachable. On the computer that runs it, start `ollama serve` (and, "
                               "for the shared console, the gate and the tunnel).") from error
    except requests.RequestException as error:
        raise Unavailable(f"The model did not answer ({error.__class__.__name__}). Try again.") from error
    with reply:
        if trouble := _refused(reply.status_code, hosted):
            raise Unavailable(trouble)
        try:
            reply.raise_for_status()
            for line in reply.iter_lines():
                if time.monotonic() > deadline:
                    raise Unavailable(f"The answer took longer than {ANSWER_SECONDS} seconds, so it was stopped. Try again.")
                if hosted:
                    if not line.startswith(b"data:"):   # a blank line between events, or a ": keep-alive" comment
                        continue
                    line = line[5:].strip()
                    if line == b"[DONE]":
                        return
                if not line:
                    continue
                piece = json.loads(line)
                if error := piece.get("error"):
                    raise Unavailable(f"The model stopped: {error.get('message', error) if isinstance(error, dict) else error}")
                if hosted:
                    yield "".join((choice.get("delta") or {}).get("content") or "" for choice in piece.get("choices", []))
                else:
                    yield piece.get("message", {}).get("content", "")
        except requests.RequestException as error:
            raise Unavailable(f"The model did not answer ({error.__class__.__name__}). Try again.") from error
        except (ValueError, AttributeError, TypeError) as error:   # a line that is not JSON, or JSON of another shape
            raise Unavailable("The model's reply was not in the expected shape. Try again.") from error
        if hosted:   # DeepSeek ends a whole answer with [DONE]; Ollama's stream simply ends
            raise Unavailable("The answer stopped part way, so it may be incomplete. Try again.")


def recent(history, room=HISTORY_TOKENS):
    """The newest question-and-answer pairs of `history` that fit in `room` tokens, at most HISTORY_TURNS of them, each
    pair whole and in order. Older ones are left out, never cut in the middle."""
    kept = []
    for at in range(len(history) - 2, -1, -2):
        pair = history[at:at + 2]
        cost = sum(tokens(turn["content"]) for turn in pair)
        if len(kept) // 2 >= HISTORY_TURNS or cost > room:
            break
        kept[:0], room = pair, room - cost
    return kept


def _refused(status, hosted):
    """Plain words for a status that means the model will not answer this question, or None."""
    if status in (401, 403):
        return ("DeepSeek does not accept the console's key. Check [assistant] key in the console's secrets." if hosted
                else "The console's key for the model is not accepted. Check [assistant] key in its secrets.")
    if status == 429:
        return ("DeepSeek is getting too many questions just now. Try again in a minute." if hosted
                else "The model is answering someone else's question. Try again in a minute.")
    if hosted and status == 402:
        return "The DeepSeek account has run out of credit. Its owner can top it up at platform.deepseek.com."
    if not hosted and status == 404:
        return f"The model {MODEL} is not on the computer that runs it. There, get it once with `ollama pull {MODEL}`."
    return None


def unknown_sources(answer_text, material_text):
    """Sources the answer names in [brackets] that the material has no label for: a sign the model made one up."""
    known = set(re.findall(r"\[([^\]\n]+)\]", material_text))
    named = {s.strip() for cited in re.findall(r"\[([^\]\n]+)\]", answer_text) for s in re.split(r"[;,]", cited)}
    return sorted(named - known - {""})
