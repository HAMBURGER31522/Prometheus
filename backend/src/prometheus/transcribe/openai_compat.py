"""Custom cloud ASR (PLAN 15.4.9): any OpenAI-compatible /audio/transcriptions endpoint.

The 16 kHz mono mp3 goes up with response_format=verbose_json for timestamped segments.
Audio over 20 MB (the usual upload limit) is cut inside silences into chunks under the
limit, sent one after another, and the segments are shifted back onto the original
timeline. Anything that goes wrong raises ``CustomAsrUnavailable`` so the caller falls back
to local transcription, as with 必剪.
"""

import dataclasses
import re
import subprocess
from pathlib import Path

from prometheus.transcribe.language import guess_language

MAX_BYTES = 20 * 1024 * 1024
MARGIN = 0.95  # aim a little under the limit: the chunk's own headers and rounding
TIMEOUT_S = 600
FIELDS = {"response_format": "verbose_json", "timestamp_granularities[]": "segment"}
# verbose_json names the language ("english"); some servers send the code instead.
LANGUAGES = {"english": "en", "chinese": "zh", "japanese": "ja", "korean": "ko", "french": "fr",
             "german": "de", "spanish": "es", "russian": "ru", "italian": "it", "portuguese": "pt"}

_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_SILENCE = re.compile(r"silence_(start|end):\s*(-?\d+(?:\.\d+)?)")


class CustomAsrUnavailable(RuntimeError):
    code = "EXTERNAL_API_FAILURE"


def _post(url: str, *, api_key: str, fields: dict, file_path, timeout: float) -> dict:
    import requests

    with open(file_path, "rb") as audio:
        response = requests.post(url, headers={"Authorization": f"Bearer {api_key}"}, data=fields,
                                 files={"file": (Path(file_path).name, audio, "audio/mpeg")}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def build_probe_cmd(mp3) -> list:
    return ["ffmpeg", "-hide_banner", "-i", str(mp3), "-af", "silencedetect=noise=-35dB:d=0.4", "-f", "null", "-"]


def parse_probe(stderr: str) -> tuple:
    """(duration in seconds, [(silence start, silence end)]) from ffmpeg's silencedetect run."""
    match = _DURATION.search(stderr)
    duration = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3)) if match else 0.0
    silences, start = [], None
    for kind, value in _SILENCE.findall(stderr):
        if kind == "start":
            start = max(0.0, float(value))
        elif start is not None:
            silences.append((start, float(value)))
            start = None
    return duration, silences


def _probe(mp3) -> tuple:
    result = subprocess.run(build_probe_cmd(mp3), capture_output=True, check=False)
    duration, silences = parse_probe(result.stderr.decode("utf-8", "replace"))
    if result.returncode != 0 or duration <= 0:
        raise CustomAsrUnavailable("ffmpeg 读不出音频时长，无法切块上传")
    return duration, silences


def build_cut_cmd(mp3, start: float, end: float, target) -> list:
    return ["ffmpeg", "-y", "-hide_banner", "-i", str(mp3), "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
            "-c", "copy", str(target)]


def _cut(mp3, start: float, end: float, target: Path) -> Path:
    if subprocess.run(build_cut_cmd(mp3, start, end, target), capture_output=True, check=False).returncode != 0:
        raise CustomAsrUnavailable("ffmpeg 切块失败")
    return target


def plan_chunks(duration_s: float, size_bytes: int, silences: list, *, max_bytes: int = MAX_BYTES) -> list:
    """[(start, end)] covering the audio, each under ``max_bytes`` at the file's average rate,
    cut in the middle of the latest silence in the second half of each stretch."""
    span = max_bytes / (size_bytes / duration_s) * MARGIN
    chunks, start = [], 0.0
    while duration_s - start > span:
        limit = start + span
        middles = [(s + e) / 2 for s, e in silences if start + span / 2 < (s + e) / 2 <= limit]
        cut = max(middles) if middles else limit
        chunks.append((start, cut))
        start = cut
    chunks.append((start, duration_s))
    return chunks


def _language(value, texts: list) -> str:
    value = str(value or "").strip().lower()
    if value in LANGUAGES:
        return LANGUAGES[value]
    if re.fullmatch(r"[a-z]{2,3}", value):
        return value
    return guess_language(texts)


def _request(post, url: str, key: str, model: str, path) -> tuple:
    try:
        reply = post(url, api_key=key, fields={"model": model, **FIELDS}, file_path=path, timeout=TIMEOUT_S)
    except (OSError, ValueError) as exc:  # requests' errors are OSErrors, a bad body a ValueError
        raise CustomAsrUnavailable(f"自定义转写请求失败：{exc}") from exc
    items = reply.get("segments") if isinstance(reply, dict) else None
    if not isinstance(items, list):
        raise CustomAsrUnavailable("自定义转写没有返回带时间戳的分段（需要 verbose_json）")
    segments = [
        {"start": float(item["start"]), "end": float(item["end"]), "text": str(item.get("text") or "").strip()}
        for item in items
        if isinstance(item, dict) and isinstance(item.get("start"), (int, float)) and isinstance(item.get("end"), (int, float))
    ]
    return segments, reply.get("language")


def transcribe(mp3, config: dict, *, post=_post, probe=_probe, cut=_cut, max_bytes: int = MAX_BYTES) -> tuple:
    """(segments in seconds on the original timeline, language code)."""
    base = str(config.get("base_url") or "").strip().rstrip("/")
    key, model = str(config.get("api_key") or "").strip(), str(config.get("model") or "").strip()
    if not (base and key and model):
        raise CustomAsrUnavailable("自定义转写还没有填写接口地址、API Key 和模型名")
    url = f"{base}/audio/transcriptions"
    mp3 = Path(mp3)
    size = mp3.stat().st_size
    plan = [(0.0, None)]
    if size > max_bytes:
        duration, silences = probe(mp3)
        plan = plan_chunks(duration, size, silences, max_bytes=max_bytes)
    segments, reported = [], None
    for index, (start, end) in enumerate(plan):
        part = mp3 if end is None else cut(mp3, start, end, mp3.with_name(f"{mp3.stem}.part{index}.mp3"))
        try:
            found, language = _request(post, url, key, model, part)
        finally:
            if part != mp3:
                part.unlink(missing_ok=True)
        reported = reported or language
        segments += [{**segment, "start": segment["start"] + start, "end": segment["end"] + start} for segment in found]
    return segments, _language(reported, [segment["text"] for segment in segments])


def asr_run(segments: list, *, language: str, model: str, elapsed_ms: int):
    from prometheus.transcribe.local_whisper import build_asr_run

    run = build_asr_run({"segments": segments}, model=model, language=language, elapsed_ms=elapsed_ms,
                        engine="openai-compatible")
    return dataclasses.replace(run, backend="cloud", provider="custom")
