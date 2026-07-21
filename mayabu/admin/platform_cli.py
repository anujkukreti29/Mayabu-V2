from __future__ import annotations

import argparse

from mayabu.monitoring.reports import pause_platform, resume_platform


def main() -> None:
    parser = argparse.ArgumentParser(description="Pause or resume a Mayabu platform")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("pause", "resume"):
        p = sub.add_parser(name)
        p.add_argument("platform")
    args = parser.parse_args()
    if args.command == "pause":
        pause_platform(args.platform)
        print(f"Paused {args.platform}")
    else:
        resume_platform(args.platform)
        print(f"Resumed {args.platform}")


if __name__ == "__main__":
    main()
