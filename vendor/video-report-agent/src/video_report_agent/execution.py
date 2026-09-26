"""Enforce a wall-clock deadline for one pipeline and its local subprocesses."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .pipeline import write_json
from .retention import cleanup_cancelled_run
from .trace import RunTrace

RUN_TIMEOUT_SECONDS = 30 * 60

IS_WINDOWS = sys.platform == "win32"

# Captured at import time: the kill path must run the real taskkill even when
# tests patch subprocess.Popen to intercept worker spawns.
_REAL_POPen = subprocess.Popen


def spawn_worker(command: list[str], *, log, env: dict[str, str] | None) -> subprocess.Popen:
    # The worker and yt-dlp/FFmpeg/Pi/browser children share one process group
    # (POSIX) or console (Windows) so the tree can be stopped together.
    if IS_WINDOWS:
        return subprocess.Popen(
            command, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP, env=env,
        )
    return subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True, env=env)


def kill_process_tree(pid: int) -> None:
    if IS_WINDOWS:
        _REAL_POPen(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).wait()
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def generate(run: Path, *, timeout=RUN_TIMEOUT_SECONDS, env: dict[str, str] | None = None) -> dict:
    run = run.resolve()
    command = [
        sys.executable, "-c",
        "from pathlib import Path; import sys; "
        "from video_report_agent.pipeline import generate; generate(Path(sys.argv[1]))",
        str(run),
    ]
    with (run / "worker.log").open("ab") as log:
        process = spawn_worker(
            command, log=log, env={**os.environ, **env} if env is not None else None,
        )
        timed_out = False
        cancelled = False
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if (run / "cancel.requested").exists():
                    cancelled = True
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    process.wait(timeout=min(0.1, remaining))
                except subprocess.TimeoutExpired:
                    pass
        finally:
            # Kill before writing FAILED so a surviving worker cannot overwrite it.
            kill_process_tree(process.pid)
            process.wait()
    path = run / "status.json"
    status = json.loads(path.read_text(encoding="utf-8"))
    if cancelled:
        status.update(state="CANCELLED", stage="CANCELLED", finished_at=time.time())
        RunTrace(run).cancelled()
        write_json(path, status)
        cleanup_cancelled_run(run)
    elif timed_out or process.returncode or status.get("state") not in {"RENDERED", "FAILED"}:
        status.update(
            state="FAILED", stage="FAILED", finished_at=time.time(),
            error_category="EXECUTION_TIMEOUT" if timed_out else "EXECUTION_FAILURE",
            error=("任务执行超过 30 分钟，已停止本地处理。" if timed_out
                   else "任务进程异常结束，请查看 worker.log。"),
        )
        write_json(path, status)
    return status
