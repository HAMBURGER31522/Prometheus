"""Scene-frame extraction and candidate filtering (PLAN 8.7)."""

import re
from pathlib import Path

SHOWINFO_PTS_RE = re.compile(r"pts_time:(\d+(?:\.\d+)?)")
MIN_INTERVAL_S = 20.0
PER_HOUR = 20
TOTAL_CAP = 80
TARGET_MIN = 5
FILL_EVERY_S = 300.0


def parse_showinfo(text: str) -> list:
    return [float(match) for match in SHOWINFO_PTS_RE.findall(text or "")]


def _label(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def filter_frames(candidates: list, *, duration_s: float) -> list:
    """Apply the PLAN 8.7 rules: interval, per-hour and total caps, even fill."""
    kept: list = []
    last = -MIN_INTERVAL_S
    hourly: dict = {}
    for seconds in sorted(candidates):
        if seconds - last < MIN_INTERVAL_S:
            continue
        if len(kept) >= TOTAL_CAP:
            break
        hour_bucket = int(seconds // 3600)
        if hourly.get(hour_bucket, 0) >= PER_HOUR:
            continue
        kept.append(seconds)
        last = seconds
        hourly[hour_bucket] = hourly.get(hour_bucket, 0) + 1

    if len(kept) < TARGET_MIN:
        fill = FILL_EVERY_S
        while len(kept) < TARGET_MIN and fill < duration_s:
            if all(abs(fill - existing) >= MIN_INTERVAL_S for existing in kept):
                kept.append(fill)
                kept.sort()
            fill += FILL_EVERY_S

    frames = []
    for seconds in kept:
        frames.append({
            "file": f"f_{int(seconds):06d}.jpg",
            "t": float(seconds),
            "label": _label(seconds),
        })
    return frames


def extract_frames(video_path: Path, work_dir: Path) -> Path:
    """ffmpeg scene-frame extraction + rules + frames.json (PLAN 8.7)."""
    import json
    import subprocess

    frames_dir = Path(work_dir) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", "select='gt(scene,0.3)',showinfo,scale=960:-2",
        "-fps_mode", "vfr", "-q:v", "4",
        str(frames_dir / "f_%06d.jpg"),
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    pts = parse_showinfo(result.stderr.decode("utf-8", "replace"))
    media_info = Path(work_dir) / "source.info.json"
    duration_s = 0.0
    if media_info.is_file():
        try:
            duration_s = float(json.loads(media_info.read_text(encoding="utf-8")).get("duration") or 0)
        except (ValueError, TypeError):
            duration_s = 0.0
    frames = filter_frames(pts, duration_s=duration_s)
    (frames_dir / "frames.json").write_text(
        json.dumps(frames, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return frames_dir / "frames.json"
