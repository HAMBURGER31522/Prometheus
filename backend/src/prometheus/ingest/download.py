"""yt-dlp option building, download runner and error mapping (PLAN 8.4)."""

from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

FIGURES_VIDEO_FORMAT = "bv*[height<=480][ext=mp4]/bv*[height<=480]/wv*"
AUDIO_FORMAT = "bestaudio"


class CookiesRequired(RuntimeError):
    code = "YOUTUBE_COOKIES_REQUIRED"


def build_ytdlp_opts(platform: str, settings: dict, *, node_exe: str, media: str = "audio"):
    network = (settings or {}).get("network", {})
    opts: dict = {
        "writeinfojson": True,
        "format": AUDIO_FORMAT if media == "audio" else FIGURES_VIDEO_FORMAT,
    }
    proxy = (network.get("proxy") or "").strip()
    if proxy:
        opts["proxy"] = proxy
    if platform == "youtube":
        cookies_file = (network.get("youtube_cookies_file") or "").strip()
        if not cookies_file:
            # Fail before any request: YouTube would answer with a bot check anyway.
            raise CookiesRequired(
                "YouTube 需要 cookies.txt：请先在设置里导出 YouTube cookies 文件。"
            )
        opts["cookiefile"] = cookies_file
        opts["js_runtimes"] = {"node": {"path": node_exe}}
    return opts


def download_error_code(error: Exception) -> str:
    message = str(error)
    if "Sign in to confirm" in message and "bot" in message:
        return "YOUTUBE_COOKIES_REQUIRED"
    return "DOWNLOAD_FAILURE"


class IngestError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def download_stage(work_dir: Path, row: dict, settings: dict, node_exe: str, *, media: str):
    """Download into work/media.* (audio) or work/video.* (figures video); PLAN 8.3."""
    opts = build_ytdlp_opts(row["platform"], settings, node_exe=node_exe, media=media)
    stem = "media" if media == "audio" else "video"
    opts["outtmpl"] = str(Path(work_dir) / f"{stem}.%(ext)s")
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(row["source_url"], download=True)
            downloaded = Path(ydl.prepare_filename(info))
    except DownloadError as exc:
        raise IngestError(download_error_code(exc), str(exc)) from exc
    if not downloaded.is_file():
        raise IngestError("DOWNLOAD_FAILURE", f"下载完成但找不到文件：{downloaded}")
    return downloaded
