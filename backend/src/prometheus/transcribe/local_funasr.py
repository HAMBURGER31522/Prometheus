"""FunASR ONNX worker helpers (PLAN 15.4.4, D-39). Stub (R6 red)."""


def attach_punctuation(tokens: list, punctuated: str) -> list:
    return [""] * len(tokens)


def build_segments(tokens: list, times_ms: list, punctuated: str, *, offset_s: float) -> list:
    return []
