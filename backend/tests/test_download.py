"""yt-dlp option building and the YouTube cookies gate (PLAN 8.4)."""

import pytest
from prometheus.ingest.download import (
    CookiesRequired,
    build_ytdlp_opts,
    download_error_code,
)
from yt_dlp.utils import DownloadError

PROXY = "http://127.0.0.1:7897"


def test_youtube_without_cookies_fails_before_any_request():
    settings = {"network": {"proxy": PROXY, "youtube_cookies_file": ""}}
    with pytest.raises(CookiesRequired):
        build_ytdlp_opts("youtube", settings, node_exe="node.exe")


def test_youtube_opts_include_node_runtime_and_cookies(tmp_path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    settings = {"network": {"proxy": PROXY, "youtube_cookies_file": str(cookies)}}
    opts = build_ytdlp_opts("youtube", settings, node_exe="E:/rt/node.exe")
    assert opts["js_runtimes"] == {"node": {"path": "E:/rt/node.exe"}}
    assert opts["cookiefile"] == str(cookies)
    assert opts["proxy"] == PROXY
    assert opts["writeinfojson"] is True


def test_bilibili_opts_have_no_cookies():
    settings = {"network": {"proxy": PROXY, "youtube_cookies_file": "x.txt"}}
    opts = build_ytdlp_opts("bilibili", settings, node_exe="node.exe")
    assert "cookiefile" not in opts
    assert "js_runtimes" not in opts
    assert opts["proxy"] == PROXY
    assert opts["writeinfojson"] is True


def test_audio_and_figures_video_formats():
    settings = {"network": {"proxy": "", "youtube_cookies_file": ""}}
    audio = build_ytdlp_opts("bilibili", settings, node_exe="n", media="audio")
    assert audio["format"] == "bestaudio"
    video = build_ytdlp_opts("bilibili", settings, node_exe="n", media="video")
    assert video["format"] == "bv*[height<=480][ext=mp4]/bv*[height<=480]/wv*"


def test_sign_in_error_maps_to_cookies_required():
    error = DownloadError("ERROR: [youtube] jNQXAC9IVRw: Sign in to confirm you're not a bot")
    assert download_error_code(error) == "YOUTUBE_COOKIES_REQUIRED"


def test_generic_download_error_maps_to_download_failure():
    assert download_error_code(DownloadError("HTTP Error 412")) == "DOWNLOAD_FAILURE"
