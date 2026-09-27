"""Custom cloud ASR (PLAN 15.4.9): any OpenAI-compatible /audio/transcriptions endpoint."""

MAX_BYTES = 20 * 1024 * 1024


class CustomAsrUnavailable(RuntimeError):
    code = "EXTERNAL_API_FAILURE"


def parse_probe(stderr: str) -> tuple:
    return 0.0, []


def plan_chunks(duration_s: float, size_bytes: int, silences: list, *, max_bytes: int = MAX_BYTES) -> list:
    return [(0.0, duration_s)]


def transcribe(mp3, config: dict, *, post=None, probe=None, cut=None, max_bytes: int = MAX_BYTES) -> tuple:
    return [], ""


def asr_run(segments: list, *, language: str, model: str, elapsed_ms: int):
    from prometheus.transcribe.local_whisper import build_asr_run

    return build_asr_run({"segments": segments}, model=model, language=language, elapsed_ms=elapsed_ms)
