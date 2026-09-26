"""faster-whisper worker helpers (PLAN 8.5).

The worker module doubles as a CLI: ``python -m prometheus.transcribe.local_whisper
<audio> <out.json> <data_dir>`` runs in a subprocess so cancellation can kill the
process tree and VRAM is freed on exit (D-19).
"""

import json
import sys
import time

from video_report_agent.asr import AsrRun, normalize_asr_segments

MODEL_ID = "large-v3-turbo"


class CudaUnavailable(RuntimeError):
    code = "CUDA_UNAVAILABLE"


def build_asr_run(raw_result: dict, *, model: str, language: str, elapsed_ms: int) -> AsrRun:
    normalized = normalize_asr_segments(raw_result.get("segments", []))
    return AsrRun(
        engine="faster-whisper",
        model=model,
        language=language,
        elapsed_ms=elapsed_ms,
        segments=normalized.segments,
        raw_result=raw_result,
        backend="local",
        provider="local",
        dropped_empty_raw_segment_ordinals=normalized.dropped_empty_raw_segment_ordinals,
        dropped_non_positive_raw_segment_ordinals=(
            normalized.dropped_non_positive_raw_segment_ordinals
        ),
        dropped_unrepresentable_raw_segment_ordinals=(
            normalized.dropped_unrepresentable_raw_segment_ordinals
        ),
    )


def pick_device(has_cuda: bool) -> tuple:
    return ("cuda", "float16") if has_cuda else ("cpu", "int8")


def assert_cuda_available(cuda_device_count: int) -> None:
    if cuda_device_count <= 0:
        raise CudaUnavailable("未检测到 NVIDIA GPU（CUDA 设备数为 0）。")


def build_transcribe_kwargs(language: str) -> dict:
    kwargs = {"language": language, "vad_filter": True}
    if language == "zh":
        kwargs["initial_prompt"] = "以下是普通话的句子。"
    return kwargs


def enable_cuda_dll_dirs(data_dir) -> None:
    """cuDNN 9 loads some DLLs on demand: PATH and add_dll_directory both (PLAN 8.5)."""
    import os

    from prometheus import paths

    bin_roots = sorted(str(p) for p in paths.cuda_dir(data_dir).glob("nvidia/*/bin"))
    for directory in bin_roots:
        os.add_dll_directory(directory)
        os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")


def _load_model(data_dir, device: str, compute_type: str):
    from faster_whisper import WhisperModel
    from prometheus import paths

    return WhisperModel(
        MODEL_ID, device=device, compute_type=compute_type,
        download_root=str(paths.models_dir(data_dir)),
    )


def run_worker(audio_path: str, out_path: str, data_dir) -> None:
    enable_cuda_dll_dirs(data_dir)
    import ctranslate2

    device, compute_type = pick_device(ctranslate2.get_cuda_device_count() > 0)
    print(f"asr backend=local device={device} model={MODEL_ID}", file=sys.stderr, flush=True)

    model = _load_model(data_dir, device, compute_type)
    language, _probability = model.detect_language(audio_path)
    kwargs = build_transcribe_kwargs(language)
    started = time.perf_counter()
    raw_segments, _info = model.transcribe(audio_path, **kwargs)
    raw_result = {"segments": [
        {"start": segment.start, "end": segment.end, "text": segment.text}
        for segment in raw_segments
    ]}
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    run = build_asr_run(raw_result, model=MODEL_ID, language=language, elapsed_ms=elapsed_ms)
    with open(out_path, "w", encoding="utf-8") as stream:
        json.dump(run.to_dict(), stream, ensure_ascii=False)


def main(argv: list | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Prometheus local ASR worker")
    parser.add_argument("audio")
    parser.add_argument("out")
    parser.add_argument("data_dir")
    args = parser.parse_args(argv)
    run_worker(args.audio, args.out, args.data_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
