import subprocess
import sys

from mayabu.jobs.process_tree import (
    _force_kill,
    console_ancestor_pid,
    direct_child_pids,
    parent_watch_should_stop,
    process_alive,
)


def test_console_ancestor_skips_python_launchers() -> None:
    processes = {
        10: (9, "python.exe"),
        9: (8, "python.exe"),
        8: (1, "powershell.exe"),
    }
    assert console_ancestor_pid(10, processes=processes) == 8


def test_parent_watch_stops_only_when_the_shell_is_gone() -> None:
    assert parent_watch_should_stop(False, False) is True
    assert parent_watch_should_stop(True, False) is False
    assert parent_watch_should_stop(False, True) is False


def test_current_process_is_alive_and_missing_pid_is_not() -> None:
    assert process_alive(0) is False
    assert process_alive(2**31 - 1) is False


def test_direct_children_follow_the_parent_pid() -> None:
    processes = {2: (1, "python.exe"), 3: (2, "chrome.exe"), 4: (1, "node.exe")}
    assert direct_child_pids(1, processes) == [2, 4]


def test_force_kill_stops_a_spawned_process() -> None:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert _force_kill(child.pid) is True
        child.wait(timeout=10)
        assert child.poll() is not None
    finally:
        if child.poll() is None:
            child.kill()
