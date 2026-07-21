from __future__ import annotations

import argparse

from mayabu.monitoring.reports import list_review_items


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Mayabu review queue")
    parser.add_argument("--status", default="needs_review")
    parser.add_argument("--type", dest="review_type", choices=["listing_match", "duplicate_product"])
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    for row in list_review_items(status=args.status, review_type=args.review_type, limit=args.limit):
        print(row)


if __name__ == "__main__":
    main()
