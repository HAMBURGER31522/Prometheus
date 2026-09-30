"""File protection for every Agent run (PLAN 15.4.13, user 2026-09-29).

    python -m prometheus.agents.contain --writable DIR [--writable DIR ...] --temp DIR -- COMMAND ...

labels the folders so that a low-integrity process may write there, then starts COMMAND at Windows'
low integrity level with this process's stdin, stdout and stderr, and exits with its exit code. A
low-integrity process reads as usual, but Windows refuses its writes and deletes everywhere else,
and everything it starts inherits that (browsers keep web pages away from files the same way). The
command runs in a kill-on-close job: stopping this launcher (a timeout, a cancelled task) ends it
too. No administrator rights are needed; where the drive does not give the user full control (a
second disk often grants only 「修改」), the user grants it to themselves on these folders first.
"""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

LOW_INTEGRITY = "S-1-16-4096"
_ICACLS = str(Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "icacls.exe")


class ContainError(RuntimeError):
    code = "ENVIRONMENT_FAILURE"


def prefix(writable, *, temp) -> list:
    """What to put before a command so that it runs contained, writable only in `writable` and `temp`."""
    parts = [sys.executable, "-m", "prometheus.agents.contain"]
    for folder in writable:
        parts += ["--writable", str(folder)]
    return [*parts, "--temp", str(temp), "--"]


# ---- Win32 ----

_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True) if os.name == "nt" else None
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None

TOKEN_QUERY, TOKEN_DUPLICATE, TOKEN_ASSIGN_PRIMARY, TOKEN_ADJUST_DEFAULT = 0x8, 0x2, 0x1, 0x80
SECURITY_IMPERSONATION, TOKEN_PRIMARY, TOKEN_USER, TOKEN_INTEGRITY_LEVEL = 2, 1, 1, 25
SE_GROUP_INTEGRITY = 0x20
STARTF_USESTDHANDLES = 0x100
HANDLE_FLAG_INHERIT = 0x1
CREATE_SUSPENDED, CREATE_UNICODE_ENVIRONMENT = 0x4, 0x400
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
INFINITE = 0xFFFFFFFF


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _StartupInfo(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD),
                ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.c_void_p),
                ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]


class _ProcessInformation(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE), ("dwProcessId", wintypes.DWORD),
                ("dwThreadId", wintypes.DWORD)]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ("ReadOperationCount", "WriteOperationCount",
                "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _BasicLimits(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _BasicLimits), ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


def _declare() -> None:
    k, a = _kernel32, _advapi32
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.GetStdHandle.restype = wintypes.HANDLE
    k.GetStdHandle.argtypes = [wintypes.DWORD]
    k.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k.ResumeThread.argtypes = [wintypes.HANDLE]
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.LocalFree.argtypes = [ctypes.c_void_p]
    a.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    a.DuplicateTokenEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                   ctypes.POINTER(wintypes.HANDLE)]
    a.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    a.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    a.GetLengthSid.argtypes = [ctypes.c_void_p]
    a.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                      ctypes.POINTER(wintypes.DWORD)]
    a.SetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    a.CreateProcessAsUserW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
                                       ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p]


def _check(ok, what: str):
    if not ok:
        raise ContainError(f"{what} 失败（Windows 错误 {ctypes.get_last_error()}）")
    return ok


def _own_token():
    token = wintypes.HANDLE()
    _check(_advapi32.OpenProcessToken(_kernel32.GetCurrentProcess(), TOKEN_QUERY | TOKEN_DUPLICATE |
                                      TOKEN_ASSIGN_PRIMARY | TOKEN_ADJUST_DEFAULT, ctypes.byref(token)), "读取进程令牌")
    return token


def _user_sid() -> str:
    """The current user's SID as text, for granting them full control on the writable folders."""
    token, size = _own_token(), wintypes.DWORD()
    _advapi32.GetTokenInformation(token, TOKEN_USER, None, 0, ctypes.byref(size))
    buffer = ctypes.create_string_buffer(size.value)
    _check(_advapi32.GetTokenInformation(token, TOKEN_USER, buffer, size, ctypes.byref(size)), "读取当前用户")
    text = wintypes.LPWSTR()
    _check(_advapi32.ConvertSidToStringSidW(_SidAndAttributes.from_buffer(buffer).Sid, ctypes.byref(text)),
           "转换用户 SID")
    try:
        return text.value
    finally:
        _kernel32.LocalFree(text)


def _low_token():
    duplicate = wintypes.HANDLE()
    _check(_advapi32.DuplicateTokenEx(_own_token(), 0, None, SECURITY_IMPERSONATION, TOKEN_PRIMARY,
                                      ctypes.byref(duplicate)), "复制进程令牌")
    sid = ctypes.c_void_p()
    _check(_advapi32.ConvertStringSidToSidW(LOW_INTEGRITY, ctypes.byref(sid)), "读取低完整性级别")
    label = _SidAndAttributes(sid, SE_GROUP_INTEGRITY)
    _check(_advapi32.SetTokenInformation(duplicate, TOKEN_INTEGRITY_LEVEL, ctypes.byref(label),
                                         ctypes.sizeof(label) + _advapi32.GetLengthSid(sid)), "降低完整性级别")
    return duplicate


def label(folder, user_sid: str) -> None:
    """Make `folder` (and what is in it) writable for low-integrity processes."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for arguments in (["/grant", f"*{user_sid}:(OI)(CI)F"], ["/setintegritylevel", "(OI)(CI)low"]):
        done = subprocess.run([_ICACLS, str(folder), *arguments, "/Q"], capture_output=True, check=False)
        if done.returncode != 0:
            raise ContainError(f"给 {folder} 设置写入权限失败：" + done.stdout.decode("mbcs", "replace").strip())


def _job():
    job = _check(_kernel32.CreateJobObjectW(None, None), "创建作业对象")
    limits = _ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    _check(_kernel32.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS, ctypes.byref(limits),
                                             ctypes.sizeof(limits)), "设置作业对象")
    return job


def run(command: list) -> int:
    """Start `command` at low integrity with this process's standard handles; its exit code."""
    handles = [_kernel32.GetStdHandle(number) for number in (-10, -11, -12)]
    for handle in handles:
        if handle:
            _kernel32.SetHandleInformation(handle, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT)
    info, process = _StartupInfo(), _ProcessInformation()
    info.cb = ctypes.sizeof(info)
    info.dwFlags = STARTF_USESTDHANDLES
    info.hStdInput, info.hStdOutput, info.hStdError = handles
    job = _job()
    _check(_advapi32.CreateProcessAsUserW(_low_token(), None, ctypes.create_unicode_buffer(subprocess.list2cmdline(command)),
                                          None, None, True, CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT, None, None,
                                          ctypes.byref(info), ctypes.byref(process)), f"以低完整性启动 {command[0]}")
    _check(_kernel32.AssignProcessToJobObject(job, process.hProcess), "把进程放进作业对象")
    _kernel32.ResumeThread(process.hThread)
    _kernel32.WaitForSingleObject(process.hProcess, INFINITE)
    code = wintypes.DWORD()
    _kernel32.GetExitCodeProcess(process.hProcess, ctypes.byref(code))
    return code.value


def main(argv: list) -> int:
    separator = argv.index("--")
    options, command = argv[:separator], argv[separator + 1:]
    writable = [options[i + 1] for i, part in enumerate(options) if part == "--writable"]
    temp = options[options.index("--temp") + 1]
    _declare()
    user = _user_sid()
    for folder in [*writable, temp]:
        label(folder, user)
    os.environ["TEMP"] = os.environ["TMP"] = temp
    return run(command)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ContainError as exc:
        print(f"文件保护没有生效，已停止运行：{exc}", file=sys.stderr)
        sys.exit(97)
