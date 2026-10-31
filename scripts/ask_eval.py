"""Ask the Ask page's eval questions (tests/assistant_eval.py) live on DeepSeek, each on its own, and say how many pass.

    python scripts/ask_eval.py [--out answers.json]

Run by hand, never in CI: it spends a few cents of DeepSeek credit. The key comes from DEEPSEEK_API_KEY in the
environment, and GITHUB_TOKEN (optional) reads the open issues and merged pull requests the console's material holds;
neither is written anywhere. An answer passes when it holds every fact, names at least one source (a question to refuse
excepted), and names no source the material does not have.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from assistant_eval import QUESTIONS, missing_facts  # noqa: E402
from evidence import assistant, decisions, work  # noqa: E402
from evidence.assistant_settings import DEEPSEEK, DEEPSEEK_URL  # noqa: E402
from ui.components.system_design import PARTS  # noqa: E402


def material():
    token = os.environ.get("GITHUB_TOKEN")
    issues = work.fetch_open_issues(token) if token else []
    merged = decisions.fetch_recent_closed(token) if token else []
    return assistant.material(issues, PARTS, merged)


def grade(item, said, text):
    trouble = [f"lacks {fact!r}" for fact in missing_facts(said, item)]
    trouble += [f"names unknown source [{s}]" for s in assistant.unknown_sources(said, text)]
    if not item.get("refuse") and "[" not in said:
        trouble.append("names no source")
    return trouble


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="also write each question, answer and verdict to this JSON file")
    args = parser.parse_args()
    key = os.environ.get("DEEPSEEK_API_KEY") or sys.exit("Set DEEPSEEK_API_KEY first.")
    text = material()
    print(f"Material: {len(text):,} characters, about {assistant.tokens(text):,} tokens.")
    results = []
    for item in QUESTIONS:
        try:
            said = "".join(assistant.answer(item["question"], [], text, DEEPSEEK_URL, key, DEEPSEEK))
        except assistant.Unavailable as error:
            said = f"(no answer: {error})"
        trouble = grade(item, said, text)
        results.append({"question": item["question"], "answer": said, "trouble": trouble})
        print(f"{'PASS' if not trouble else 'FAIL'}  {item['question']}" + "".join(f"\n      {t}" for t in trouble))
    passed = sum(not r["trouble"] for r in results)
    print(f"\n{passed} of {len(results)} passed.")
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
