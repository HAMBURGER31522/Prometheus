"""Vendor transcript stage (PLAN 8.3): canonical transcript via build_transcript."""

import argparse
from pathlib import Path

from video_report_agent.transcript import build_transcript as vendor_build_transcript


def build_transcript_md(work_dir, asr_path, metadata: dict) -> Path:
    """Write work/transcript.md in the exact vendor pipeline.py 188-194 format."""
    work_dir = Path(work_dir)
    args = argparse.Namespace(
        transcript_mode="asr-only", ocr_mode="off", ocr_backend="rapidocr",
        subtitle_file=None,
    )
    build, _artifacts, _status = vendor_build_transcript(
        args,
        source_path=work_dir / "media.mp4",
        artifact_root=work_dir,
        asr_path=Path(asr_path),
        source_duration_ms=round(float(metadata.get("duration_s", 0.0)) * 1000),
        manifest=metadata,
    )
    lines = [f"# {metadata['title']}", metadata["attribution"], ""]
    lines.extend(
        f"[{u.unit_id} | {u.start_ms / 1000:.3f}-{u.end_ms / 1000:.3f}s] {u.canonical_text}"
        for u in build.canonical_units
    )
    target = work_dir / "transcript.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target
