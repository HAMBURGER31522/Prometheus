"""YouTube manual subtitles instead of transcription (PLAN 15.4.4, D-38).

Only the uploader's own track in the video's original language counts: automatic
captions and translations do not. yt-dlp often reports no language at all; then
nothing is picked and the video is transcribed as usual (never guess).
"""

from pathlib import Path

from prometheus.ingest.download import (
    IngestError,
    build_ytdlp_opts,
    download_error_code,
)
from yt_dlp import YoutubeDL

# Among Chinese variants of the same language, simplified first (subtitles are shown simplified).
_SIMPLIFIED = ("zh-Hans", "zh-CN", "zh-SG")


def _primary(code: str) -> str:
    return code.split("-")[0].lower()


def pick_manual_subtitle(platform: str, info: dict):
    """The manual subtitle language code to use, or None to transcribe."""
    language = info.get("language")
    if platform != "youtube" or not language:
        return None
    tracks = [key for key in (info.get("subtitles") or {}) if key != "live_chat"]
    if language in tracks:
        return language
    matching = [key for key in tracks if _primary(key) == _primary(language)]
    for preferred in _SIMPLIFIED:
        if preferred in matching:
            return preferred
    return matching[0] if matching else None


def download_subtitle(work: Path, row: dict, settings: dict, node_exe: str, language: str) -> Path:
    """Only the chosen track, as work/subtitle.<language>.vtt."""
    opts = build_ytdlp_opts(row["platform"], settings, node_exe=node_exe)
    opts.update({
        "skip_download": True, "writeinfojson": False,
        "writesubtitles": True, "writeautomaticsub": False,
        "subtitleslangs": [language], "subtitlesformat": "vtt",
        "outtmpl": str(Path(work) / "subtitle.%(ext)s"),
    })
    try:
        with YoutubeDL(opts) as ydl:
            ydl.extract_info(row["source_url"], download=True)
    except Exception as exc:
        raise IngestError(download_error_code(exc), str(exc)) from exc
    found = downloaded_subtitle(work)
    if found is None:
        raise IngestError("DOWNLOAD_FAILURE", f"字幕下载完成但找不到文件（{language}）")
    return found


def downloaded_subtitle(work: Path):
    """work/subtitle.<language>.vtt from download_subtitle, or None."""
    return next(iter(sorted(Path(work).glob("subtitle.*.vtt"))), None)
