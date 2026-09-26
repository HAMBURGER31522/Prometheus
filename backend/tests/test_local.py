"""Worker subprocess lifecycle and backend isolation (PLAN 8.5, D-19)."""

import json
import sys
import time
from pathlib import Path

import pytest

from prometheus.transcribe import local

FIXTURES = Path(__file__).parent / "fixtures"


def test_cancel_kills_worker_subprocess(tmp_path):
    log = tmp_path / "worker.log"
    worker = local.spawn_worker(
        [sys.executable, "-c", "import time; time.sleep(60)"], log_path=log,
    )
    time.sleep(0.5)
    assert worker.poll() is None
    worker.cancel()
    deadline = time.time() + 10
    while time.time() < deadline and worker.poll() is None:
        time.sleep(0.1)
    assert worker.poll() is not None


def test_asr_backend_env_does_not_affect_local_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ASR_BACKEND", "mlx")

    from video_report_agent import media_config

    calls = []
    monkeypatch.setattr(
        media_config, "resolve_media_config",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {},
    )

    data_dir = tmp_path / "data"
    (data_dir / "runtime" / "cuda" / "nvidia" / "cublas" / "bin").mkdir(parents=True)

    asr_payload = json.loads((FIXTURES / "asr.local.json").read_text(encoding="utf-8"))

    class FakeWorker:
        def __init__(self, out_path):
            self.out_path = out_path

        def run(self):
            self.out_path.write_text(
                json.dumps(asr_payload, ensure_ascii=False), encoding="utf-8",
            )
            return 0

        def cancel(self):
            return None

    captured = {}
    monkeypatch.setattr(
        local, "spawn_worker",
        lambda command, out_path, log_path: captured.update(command=command)
        or FakeWorker(out_path),
    )

    item_dir = data_dir / "items" / ("a" * 32)
    (item_dir / "work").mkdir(parents=True)
    (item_dir / "subtitle").mkdir(parents=True)
    audio = item_dir / "work" / "media.wav"
    audio.write_bytes(b"RIFF")

    asr_path = local.transcribe_local(data_dir, "a" * 32, audio)
    assert asr_path.is_file()
    assert json.loads(asr_path.read_text(encoding="utf-8"))["segments"]
    assert calls == []


def test_cuda_component_missing_fails_fast(monkeypatch, tmp_path):
    monkeypatch.setattr(local, "cuda_component_installed", lambda data_dir: False)
    with pytest.raises(local.CudaUnavailable) as error:
        local.transcribe_local(tmp_path, "a" * 32, tmp_path / "audio.wav")
    assert error.value.code == "CUDA_UNAVAILABLE"
