"""必剪 cloud ASR (PLAN 15.4.4). Stub (R6 red)."""

API = "https://member.bilibili.com/x/bcut/rubick-interface"


class BcutUnavailable(RuntimeError):
    code = "EXTERNAL_API_FAILURE"


def transcribe(mp3, *, session=None, sleep=None, clock=None, timeout_s: float = 900.0) -> list:
    return []


def asr_run(segments: list, *, elapsed_ms: int):
    from prometheus.transcribe.local_whisper import build_asr_run

    return build_asr_run({"segments": segments}, model="", language="zh", elapsed_ms=elapsed_ms)
