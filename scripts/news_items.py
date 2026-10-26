"""List the news items in the archive's feed copies, or make the labelling sheet from them (issues 13, 15).

    python scripts/news_items.py --archive FOLDER                 # every item, as CSV, to the screen
    python scripts/news_items.py --archive FOLDER --sheet         # write the labelling sheet
    python scripts/news_items.py --archive FOLDER --report        # per feed: change rate, share naming a system

The sheet (evidence/labelling_sheet.csv) holds about 30 recent items spread across the six
systems, with two empty columns for a person: the claims in each item, or "none".
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.news import collected_items, feed_report, labelling_sample, latest_news
from evidence.settings import FEED_REPORT_COLUMNS, LABELLING_SHEET_COLUMNS, LABELLING_SHEET_FILE, NEWS_ITEM_COLUMNS


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="folder holding objects/ and versions.csv")
    parser.add_argument("--sheet", action="store_true", help=f"write {LABELLING_SHEET_FILE.name} instead")
    parser.add_argument("--report", action="store_true", help="one row per feed: how often it changed, how on-topic")
    parser.add_argument("--latest", help="write latest news as JSON to this file")
    args = parser.parse_args()

    if args.report:
        writer = csv.DictWriter(sys.stdout, FEED_REPORT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(feed_report(args.archive))
        return

    items, unreadable = collected_items(args.archive)
    for address, fetched_at, reason in unreadable:
        print(f"UNREADABLE {address} as fetched {fetched_at}: {reason}", file=sys.stderr)
    if args.latest:
        latest = latest_news(items)
        path = Path(args.latest)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(latest, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{len(latest['items'])} items written to {path}", file=sys.stderr)
        return
    if args.sheet:
        sample = labelling_sample(items)
        with open(LABELLING_SHEET_FILE, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, LABELLING_SHEET_COLUMNS, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(sample)
        print(f"{len(sample)} of {len(items)} items written to {LABELLING_SHEET_FILE}", file=sys.stderr)
        return
    writer = csv.DictWriter(sys.stdout, NEWS_ITEM_COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(items)


if __name__ == "__main__":
    main()
