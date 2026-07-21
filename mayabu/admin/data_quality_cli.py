from __future__ import annotations

import argparse

from mayabu.monitoring.reports import list_anomalies


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Mayabu anomalies")
    parser.add_argument("--status", default="open")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    for row in list_anomalies(status=args.status, limit=args.limit):
        print(row)


if __name__ == "__main__":
    main()
