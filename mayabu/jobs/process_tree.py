"""Parent-shell and child-process helpers for worker shutdown.

On Windows, stopping the launching shell does not deliver SIGTERM to the
worker. The worker watches that shell and, after a graceful stop window,
kills Playwright and other child processes.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Callable


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _windows_alive(pid)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def process_parent_map() -> dict[int, tuple[int, str]]:
    if os.name == "nt":
        return _windows_process_map()
    return {}


def console_ancestor_pid(pid: int | None = None, *, processes: dict[int, tuple[int, str]] | None = None) -> int | None:
    """First ancestor that is not another Python launcher."""
    current = os.getpid() if pid is None else pid
    mapping = processes if processes is not None else process_parent_map()
    seen: set[int] = set()
    while current and current not in seen:
        seen.add(current)
        entry = mapping.get(current)
        if entry is None:
            return None
        parent, name = entry
        if "python" not in name.lower():
            return current
        current = parent
    return None


def direct_child_pids(root_pid: int, processes: dict[int, tuple[int, str]]) -> list[int]:
    return [pid for pid, (parent, _name) in processes.items() if parent == root_pid and pid != root_pid]


def terminate_children(root_pid: int | None = None) -> list[int]:
    """Force-stop child processes after the graceful shutdown window."""
    root = os.getpid() if root_pid is None else root_pid
    mapping = process_parent_map()
    children = direct_child_pids(root, mapping)
    killed: list[int] = []
    for child in children:
        if _force_kill(child):
            killed.append(child)
    return killed


def _force_kill(pid: int) -> bool:
    if os.name == "nt":
        completed = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode == 0
    try:
        os.kill(pid, 15)
    except OSError:
        return False
    return True


def _windows_alive(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return int(code.value) == 259
    finally:
        kernel.CloseHandle(handle)


def _windows_process_map() -> dict[int, tuple[int, str]]:
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return {}

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    found: dict[int, tuple[int, str]] = {}
    try:
        if not kernel.Process32FirstW(snapshot, ctypes.byref(entry)):
            return {}
        while True:
            found[int(entry.th32ProcessID)] = (int(entry.th32ParentProcessID), str(entry.szExeFile))
            if not kernel.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel.CloseHandle(snapshot)
    return found


def parent_watch_should_stop(ancestor_alive: bool, already_stopping: bool) -> bool:
    return not ancestor_alive and not already_stopping


def install_shutdown_signals(stop: Callable[[], None]) -> None:
    """Register SIGINT/SIGTERM, including the Windows signal.signal fallback."""
    import signal
    import threading

    names = ["SIGINT", "SIGTERM"]
    if sys.platform == "win32":
        names.append("SIGBREAK")
    for name in names:
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, lambda *_args: stop())
        except (ValueError, OSError):
            continue
    # signal handlers must run on the main thread; this helper is called there.
    if threading.current_thread() is not threading.main_thread():
        return
