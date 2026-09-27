"""Run one ASR engine on one sample and write a JSON result (PLAN 15.4.3).

    python engines.py <engine> <audio.wav> <zh|en> <out.json>

Each call is its own process so the parent can sample VRAM per engine and the
GPU is empty again afterwards. Paths default to the layout described in
E:\\tools\\Prometheus-Desktop\\asr-bench\\使用说明.md.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

BENCH = Path(os.environ.get("ASR_BENCH_HOME", r"E:\tools\Prometheus-Desktop\asr-bench"))
MODELS = BENCH / "models"
ROOT = Path(__file__).resolve().parents[2]
APP_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
# A data dir whose .prometheus\models and runtime\cuda hold the app's whisper
# model and CUDA DLLs (see asr-bench\使用说明.md).
APP_DATA = Path(os.environ.get("ASR_BENCH_APP_DATA", ROOT / "acceptance-output" / "asr-bench" / "app-data"))
FFMPEG = os.environ.get("PROMETHEUS_FFMPEG", r"E:\tools\Prometheus-Desktop\ffmpeg\bin")
# FunASR downloads through ModelScope; keep its cache off C:.
os.environ["MODELSCOPE_CACHE"] = str(MODELS / "modelscope")


def _segments(items) -> list:
    return [{"start": round(float(s), 3), "end": round(float(e), 3), "text": t.strip()} for s, e, t in items]


def run_whisper(wav: str, language: str) -> dict:
    # The app's own worker in the app's venv: exactly what Prometheus runs today.
    started = time.perf_counter()
    raw_out = Path(wav).with_suffix(".whisper-asr.json")
    subprocess.run([str(APP_PYTHON), "-m", "prometheus.transcribe.local_whisper", wav, str(raw_out),
                    str(APP_DATA)], check=True)
    total = time.perf_counter() - started
    run = json.loads(raw_out.read_text(encoding="utf-8"))
    run_s = run["elapsed_ms"] / 1000
    return {"model": "faster-whisper large-v3-turbo (float16)", "detected_language": run["language"],
            "segments": _segments((s["start_ms"] / 1000, s["end_ms"] / 1000, s["text"]) for s in run["segments"]),
            "load_s": total - run_s, "run_s": run_s, "timestamp_unit": "segment",
            "note": "load_s = process start + model load + language detection"}


def run_qwen3(wav: str, language: str) -> dict:
    import torch
    from qwen_asr import Qwen3ASRModel

    started = time.perf_counter()
    model = Qwen3ASRModel.from_pretrained(
        str(MODELS / "Qwen3-ASR-1.7B"), dtype=torch.bfloat16, device_map="cuda:0",
        max_inference_batch_size=8, max_new_tokens=4096,
        forced_aligner=str(MODELS / "Qwen3-ForcedAligner-0.6B"),
        forced_aligner_kwargs={"dtype": torch.bfloat16, "device_map": "cuda:0"},
    )
    loaded = time.perf_counter()
    results = model.transcribe(audio=wav, language=None, return_time_stamps=True)
    result = results[0]
    units = [(u.start_time, u.end_time, u.text) for u in (result.time_stamps or [])]
    return {"model": "Qwen3-ASR-1.7B + Qwen3-ForcedAligner-0.6B (bf16)",
            "detected_language": result.language, "text": result.text,
            "segments": _segments(units), "load_s": loaded - started,
            "run_s": time.perf_counter() - loaded, "timestamp_unit": "word/char"}


def run_funasr(wav: str, language: str) -> dict:
    from funasr import AutoModel

    started = time.perf_counter()
    model = AutoModel(model="paraformer-zh", vad_model="fsmn-vad", punc_model="ct-punc",
                      hub="ms", device="cuda:0", disable_update=True)
    loaded = time.perf_counter()
    result = model.generate(input=wav, batch_size_s=300, sentence_timestamp=True)[0]
    sentences = result.get("sentence_info") or []
    return {"model": "FunASR paraformer-zh + fsmn-vad + ct-punc",
            "text": result.get("text", ""),
            "segments": _segments((s["start"] / 1000, s["end"] / 1000, s["text"]) for s in sentences),
            "load_s": loaded - started, "run_s": time.perf_counter() - loaded,
            "timestamp_unit": "sentence"}


BCUT = "https://member.bilibili.com/x/bcut/rubick-interface"
BCUT_HEADERS = {"User-Agent": "Bilibili/1.0.0 (https://www.bilibili.com)"}


def _bcut_data(response) -> dict:
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"bcut error {payload.get('code')}: {payload.get('message')}")
    return payload["data"]


def run_bcut(wav: str, language: str) -> dict:
    import requests

    started = time.perf_counter()
    mp3 = Path(wav).with_suffix(".bcut.mp3")
    subprocess.run([str(Path(FFMPEG) / "ffmpeg.exe"), "-loglevel", "error", "-y", "-i", wav,
                    "-ac", "1", "-ar", "16000", "-b:a", "48k", str(mp3)], check=True)
    data = mp3.read_bytes()
    session = requests.Session()
    session.headers.update(BCUT_HEADERS)
    grant = _bcut_data(session.post(f"{BCUT}/resource/create", json={
        "type": 2, "name": "audio.mp3", "size": len(data), "ResourceFileType": "mp3", "model_id": "8",
    }, timeout=30))
    size = grant["per_size"]
    etags = []
    for index, url in enumerate(grant["upload_urls"]):
        put = session.put(url, data=data[index * size:(index + 1) * size], timeout=120)
        put.raise_for_status()
        etags.append(put.headers.get("Etag") or "")
    done = _bcut_data(session.post(f"{BCUT}/resource/create/complete", json={
        "InBossKey": grant["in_boss_key"], "ResourceId": grant["resource_id"],
        "Etags": ",".join(tag for tag in etags if tag), "UploadId": grant["upload_id"], "model_id": "8",
    }, timeout=30))
    uploaded = time.perf_counter()
    task = _bcut_data(session.post(f"{BCUT}/task", json={
        "resource": done["download_url"], "model_id": "8",
    }, timeout=30))["task_id"]
    deadline = time.time() + 900
    while True:
        state = _bcut_data(session.get(f"{BCUT}/task/result",
                                       params={"model_id": 7, "task_id": task}, timeout=30))
        if state["state"] == 4:
            break
        if state["state"] == 3 or time.time() > deadline:
            raise RuntimeError(f"bcut task failed: state={state['state']}")
        time.sleep(2)
    utterances = json.loads(state["result"])["utterances"]
    return {"model": "必剪 (bcut, model_id 8)",
            "segments": _segments((u["start_time"] / 1000, u["end_time"] / 1000, u["transcript"])
                                  for u in utterances),
            "load_s": uploaded - started, "run_s": time.perf_counter() - uploaded,
            "timestamp_unit": "sentence", "note": "load_s = mp3 encode + upload"}


ENGINES = {"whisper": run_whisper, "qwen3": run_qwen3, "funasr": run_funasr, "bcut": run_bcut}


def main(argv: list) -> int:
    engine, wav, language, out = argv
    result = ENGINES[engine](wav, language)
    result.setdefault("text", "".join(s["text"] for s in result["segments"]) if language == "zh"
                      else " ".join(s["text"] for s in result["segments"]))
    result.update(engine=engine, sample_language=language)
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
