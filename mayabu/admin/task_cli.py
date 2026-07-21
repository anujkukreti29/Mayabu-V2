from __future__ import annotations

import argparse

from mayabu.monitoring.reports import list_tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Mayabu scrape tasks")
    parser.add_argument("status", nargs="?", default=None)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    for row in list_tasks(status=args.status, limit=args.limit):
        print(row)


if __name__ == "__main__":
    main()
