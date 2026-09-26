"""Link parsing into a normalized source (PLAN 8.4; full table in M3)."""

import re
from dataclasses import dataclass

BILIBILI_VIDEO_RE = re.compile(
    r"https?://(?:www\.)?bilibili\.com/video/(BV[0-9A-Za-z]+)/?(?:\?.*?)?$"
)
YOUTUBE_WATCH_RE = re.compile(
    r"https?://(?:www\.)?youtube\.com/watch\?(?:[^\s]*&)?v=(?P<id>[0-9A-Za-z_-]{11})"
)
YOUTUBE_SHORTS_RE = re.compile(
    r"https?://(?:www\.)?youtube\.com/shorts/(?P<id>[0-9A-Za-z_-]{11})"
)
YOUTUBE_SHORT_RE = re.compile(r"https?://youtu\.be/(?P<id>[0-9A-Za-z_-]{11})")
BARE_BV_RE = re.compile(r"BV[0-9A-Za-z]{10}")
URL_RE = re.compile(r"https?://[^\s\"'<>（）【】，]+")
P_PARAM_RE = re.compile(r"[?&]p=(\d+)")
B23_HOST_RE = re.compile(r"https?://b23\.tv/")

PLATFORMS = ("bilibili", "youtube")


class LinkUnsupported(ValueError):
    pass


@dataclass
class Source:
    platform: str
    video_id: str
    canonical_url: str
    page: int = 1


def resolve_redirect(url: str) -> str:
    """Follow one HTTP redirect chain (b23.tv short links only)."""
    import httpx

    response = httpx.head(url, follow_redirects=True, timeout=10)
    return str(response.url)


def parse_url(text: str) -> Source:
    match = URL_RE.search(text or "")
    if match:
        url = match.group(0)
        if B23_HOST_RE.match(url):
            return _parse_absolute(resolve_redirect(url))
        return _parse_absolute(url)
    bare = BARE_BV_RE.search(text or "")
    if bare:
        return Source(
            platform="bilibili", video_id=bare.group(0),
            canonical_url=f"https://www.bilibili.com/video/{bare.group(0)}/",
        )
    raise LinkUnsupported(f"unsupported link: {text!r}")


def _parse_absolute(url: str) -> Source:
    bilibili = BILIBILI_VIDEO_RE.match(url)
    if bilibili:
        page_match = P_PARAM_RE.search(url)
        page = int(page_match.group(1)) if page_match else 1
        video_id = bilibili.group(1)
        if page > 1:
            video_id = f"{video_id}?p={page}"
        canonical = f"https://www.bilibili.com/video/{bilibili.group(1)}/?p={page}"
        return Source(platform="bilibili", video_id=video_id, canonical_url=canonical,
                      page=page)
    watch = YOUTUBE_WATCH_RE.search(url)
    if watch and "list=" not in url:
        video_id = watch.group("id")
        return Source(
            platform="youtube", video_id=video_id,
            canonical_url=f"https://www.youtube.com/watch?v={video_id}",
        )
    shorts = YOUTUBE_SHORTS_RE.search(url)
    if shorts:
        video_id = shorts.group("id")
        return Source(
            platform="youtube", video_id=video_id,
            canonical_url=f"https://www.youtube.com/watch?v={video_id}",
        )
    short = YOUTUBE_SHORT_RE.match(url)
    if short:
        video_id = short.group("id")
        return Source(
            platform="youtube", video_id=video_id,
            canonical_url=f"https://www.youtube.com/watch?v={video_id}",
        )
    raise LinkUnsupported(f"unsupported link: {url!r}")
