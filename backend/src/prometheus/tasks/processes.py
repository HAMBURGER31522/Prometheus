"""End every child process of the backend (PLAN 15.2-1, cancellation).

The queue runs one item at a time, so while a task is running every child of the
backend (Pi, the whisper worker, ffmpeg) belongs to that task. Killing the
children's trees therefore cancels the stage without any vendor hooks.
"""

import os
import subprocess
import sys
from pathlib import Path

# Started without a window by the Tauri shell, the backend owns a console host; killing it with the task's
# processes left the next taskkill stuck and the backend unanswering (installed run, 2026-09-30).
_NEVER_KILLED = frozenset({"conhost.exe"})
CREATE_NO_WINDOW = 0x08000000


def _children_windows(parent: int) -> list[tuple[int, str]]:
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if snapshot in (None, wintypes.HANDLE(-1).value):
        return []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    children = []
    try:
        more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.th32ParentProcessID == parent and entry.th32ProcessID != parent:
                children.append((int(entry.th32ProcessID), entry.szExeFile))
            more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return children


def _children_posix(parent: int) -> list[tuple[int, str]]:
    children = []
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            text = stat.read_text(encoding="utf-8")
        except OSError:
            continue
        name, fields = text.split("(", 1)[1].rsplit(")", 1)[0], text.rsplit(")", 1)[1].split()
        if int(fields[1]) == parent:
            children.append((int(stat.parent.name), name))
    return children


def child_processes(parent: int | None = None) -> list[tuple[int, str]]:
    """(pid, executable name) of every direct child."""
    parent = os.getpid() if parent is None else parent
    return _children_windows(parent) if sys.platform == "win32" else _children_posix(parent)


def child_pids(parent: int | None = None) -> list[int]:
    return [pid for pid, _name in child_processes(parent)]


def kill_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            creationflags=CREATE_NO_WINDOW,  # not attached to the backend's console
        )
        return
    import signal

    for child in child_pids(pid):
        kill_tree(child)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def kill_children() -> list[int]:
    """Kill the process tree of every direct child of this process, except its own console host."""
    killed = [pid for pid, name in child_processes() if name.lower() not in _NEVER_KILLED]
    for pid in killed:
        kill_tree(pid)
    return killed
