"""yt-dlp option building and error mapping (PLAN 8.4)."""


class CookiesRequired(RuntimeError):
    code = "YOUTUBE_COOKIES_REQUIRED"


def build_ytdlp_opts(platform: str, settings: dict, *, node_exe: str, media: str = "audio"):
    raise NotImplementedError


def download_error_code(error: Exception) -> str:
    raise NotImplementedError
