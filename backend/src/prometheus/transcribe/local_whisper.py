"""faster-whisper worker helpers (PLAN 8.5)."""


class CudaUnavailable(RuntimeError):
    code = "CUDA_UNAVAILABLE"


def build_asr_run(raw_result: dict, *, model: str, language: str, elapsed_ms: int):
    raise NotImplementedError


def pick_device(has_cuda: bool):
    raise NotImplementedError


def assert_cuda_available(cuda_device_count: int) -> None:
    raise NotImplementedError


def build_transcribe_kwargs(language: str) -> dict:
    raise NotImplementedError
