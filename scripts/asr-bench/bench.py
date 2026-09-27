"""Run every engine on every sample, sampling VRAM with nvidia-smi (PLAN 15.4.3).

    python bench.py [--engines whisper,qwen3,funasr,bcut] [--samples zh,en] [--force]

Results go to acceptance-output/asr-bench/results/<engine>-<sample>.json (not committed).
"""

import argparse
import json
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "acceptance-output" / "asr-bench"
SAMPLES = OUT / "samples"


class VramSampler:
    """nvidia-smi memory.used every 200ms; peak minus the idle baseline."""

    def __init__(self):
        self.samples: list = []
        self._proc = None
        self._thread = None

    def _read(self):
        for line in self._proc.stdout:
            line = line.strip()
            if line.isdigit():
                self.samples.append(int(line))

    def start(self) -> None:
        self._proc = subprocess.Popen(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits", "-lms", "200"],
            stdout=subprocess.PIPE, text=True,
        )
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()
        time.sleep(1.5)

    def baseline(self) -> int:
        return int(statistics.median(self.samples[:6])) if self.samples else 0

    def stop(self) -> dict:
        self._proc.terminate()
        self._thread.join(timeout=5)
        base = self.baseline()
        peak = max(self.samples) if self.samples else 0
        return {"vram_baseline_mb": base, "vram_peak_mb": peak, "vram_used_mb": peak - base}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engines", default="whisper,qwen3,qwen3-seq,funasr,bcut")
    parser.add_argument("--samples", default="zh,en")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    (OUT / "results").mkdir(parents=True, exist_ok=True)
    for sample in args.samples.split(","):
        wav = SAMPLES / f"{sample}.wav"
        for engine in args.engines.split(","):
            out = OUT / "results" / f"{engine}-{sample}.json"
            if out.is_file() and not args.force:
                print(f"skip {out.name} (exists)", flush=True)
                continue
            sampler = VramSampler()
            sampler.start()
            started = time.perf_counter()
            proc = subprocess.run([sys.executable, str(Path(__file__).with_name("engines.py")),
                                   engine, str(wav), sample, str(out)],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            wall = time.perf_counter() - started
            vram = sampler.stop()
            if proc.returncode != 0:
                (OUT / "results" / f"{engine}-{sample}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
                print(f"FAIL {engine}-{sample} exit={proc.returncode}: {proc.stderr.strip()[-300:]}", flush=True)
                continue
            result = json.loads(out.read_text(encoding="utf-8"))
            result.update(vram, wall_s=wall)
            out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"ok {engine}-{sample}: load {result['load_s']:.1f}s run {result['run_s']:.1f}s "
                  f"vram +{vram['vram_used_mb']}MB segments {len(result['segments'])}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
