"""Open the weekly registry proposal with what changed, table by table.

    python scripts/describe_table_changes.py --report CHANGES.md   # after the tables are rebuilt

Reads `git diff` of registry/ and puts, at the top of the report: one sentence saying what is asked, then each table's
rows added, changed (old -> new) and removed with their source, then what needs a person's look. The rest of the report
follows unchanged. The console's Approvals page reads the same change the same way (evidence/table_changes.py).
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence import table_changes
from evidence.decision_settings import RAISED_BY


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", required=True, help="the pull request text to open with the change")
    args = parser.parse_args()
    diff = subprocess.run(["git", "diff", "--no-color", "--", "registry/"], check=True, capture_output=True, text=True).stdout
    changes = [table_changes.table_change(path, patch) for path, patch in table_changes.split_diff(diff).items()]
    report = Path(args.report)
    first, _, rest = report.read_text(encoding="utf-8").partition("\n\n")
    asked = table_changes.asked(RAISED_BY["github-actions[bot]"], changes)
    report.write_text(f"{asked} {table_changes.shown_text(changes)}\n\n{first}\n\n{table_changes.markdown(changes)}\n{rest}",
                      encoding="utf-8")


if __name__ == "__main__":
    main()
