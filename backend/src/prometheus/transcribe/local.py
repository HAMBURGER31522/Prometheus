"""Local ASR worker process management (PLAN 8.5, D-19)."""


class CudaUnavailable(RuntimeError):
    code = "CUDA_UNAVAILABLE"


def cuda_component_installed(data_dir) -> bool:
    raise NotImplementedError


def spawn_worker(command: list, *, out_path, log_path):
    raise NotImplementedError


def transcribe_local(data_dir, item_id: str, audio_path):
    raise NotImplementedError
