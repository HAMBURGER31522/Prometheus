"""Scoring for the ASR shoot-out (PLAN 15.4.3). Stub (red)."""


def subtitle_text(vtt: str, language: str) -> str:
    return ""


def score_zh(reference: str, hypothesis: str) -> dict:
    return {"cer": 1.0, "cer_raw": 1.0, "number_edits": 0}


def score_en(reference: str, hypothesis: str) -> dict:
    return {"wer": 1.0}


def punctuation_per_100(text: str) -> float:
    return -1.0
