"""Local ASR worker process management (PLAN 8.5, D-19)."""

import subprocess
import sys
from pathlib import Path

from prometheus import paths

WORKER_MODULE = "prometheus.transcribe.local_whisper"


class CudaUnavailable(RuntimeError):
    code = "CUDA_UNAVAILABLE"


class AsrWorkerError(RuntimeError):
    code = "ASR_FAILURE"


def cuda_component_installed(data_dir) -> bool:
    cuda_root = paths.cuda_dir(data_dir)
    return cuda_root.is_dir() and any(True for _ in cuda_root.glob("nvidia/*/bin"))


def kill_process_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        return
    import os
    import signal

    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


class WorkerHandle:
    def __init__(self, process, out_path, log_path):
        self.process = process
        self.out_path = Path(out_path) if out_path else None
        self.log_path = Path(log_path)

    def run(self) -> int:
        return self.process.wait()

    def poll(self):
        return self.process.poll()

    def cancel(self) -> None:
        kill_process_tree(self.process.pid)


def spawn_worker(command: list, *, log_path, out_path=None) -> WorkerHandle:
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("ab")
    process = subprocess.Popen(command, stdout=log, stderr=log, **kwargs)
    return WorkerHandle(process, out_path, log_path)


def transcribe_local(data_dir, item_id: str, audio_path):
    """Run the whisper worker in a subprocess; return the asr.json path (D-19)."""
    if not cuda_component_installed(data_dir):
        raise CudaUnavailable("尚未安装本地转写组件，请先在设置里启用本地转写。")
    work = paths.work_dir(data_dir, item_id)
    asr_path = work / "asr.json"
    command = [
        sys.executable, "-m", WORKER_MODULE,
        str(audio_path), str(asr_path), str(data_dir),
    ]
    handle = spawn_worker(command, out_path=asr_path,
                          log_path=paths.logs_dir(data_dir) / "asr-worker.log")
    try:
        returncode = handle.run()
    except BaseException:
        handle.cancel()
        raise
    if returncode != 0 or not asr_path.is_file():
        raise AsrWorkerError(f"本地转写进程异常结束（exit {returncode}），请查看 asr-worker.log。")
    return asr_path
