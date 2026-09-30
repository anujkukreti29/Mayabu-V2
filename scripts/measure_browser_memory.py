"""Measure approximate Playwright browser/worker RSS on this host.

Usage:
  python scripts/measure_browser_memory.py

Reports process RSS for idle Python, after Chromium launch, and with N contexts.
Does not hit retailers. Safe for local capacity planning only.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import os
import sys
from ctypes import wintypes


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore

        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    if sys.platform == "win32":
        try:

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                ctypes.windll.kernel32.GetCurrentProcess(),
                ctypes.byref(counters),
                counters.cb,
            )
            if ok:
                return counters.WorkingSetSize / (1024 * 1024)
        except Exception:
            return -1.0
        return -1.0
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return usage / (1024 * 1024)
        return usage / 1024.0
    except Exception:
        return -1.0


async def main(contexts: int) -> None:
    from playwright.async_api import async_playwright

    print(f"idle_python_rss_mb={_rss_mb():.1f}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        print(f"after_chromium_launch_rss_mb={_rss_mb():.1f}")
        opened = []
        for i in range(max(1, contexts)):
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.goto("about:blank")
            opened.append(ctx)
            print(f"contexts={i + 1}_rss_mb={_rss_mb():.1f}")
        for ctx in opened:
            await ctx.close()
        await browser.close()
    print(f"after_close_rss_mb={_rss_mb():.1f}")
    print(
        "recommendation=start_with_worker_concurrency_1_to_2_and_platform_concurrency_1_to_2"
    )
    print(
        "note=python_rss_excludes_child_chromium_processes; measure host total separately in staging"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--contexts", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(main(args.contexts))
