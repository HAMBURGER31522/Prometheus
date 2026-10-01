"""YouTube manual subtitles instead of transcription (PLAN 15.4.4, D-38)."""

from prometheus.ingest.platform_subtitles import pick_manual_subtitle
from prometheus.subtitle.vtt import parse_vtt

TRACK = [{"ext": "vtt", "url": "https://example.invalid/sub.vtt"}]


def _info(language, subtitles, automatic=None):
    return {"language": language, "subtitles": {key: TRACK for key in subtitles},
            "automatic_captions": {key: TRACK for key in (automatic or [])}}


def test_the_original_language_track_is_picked():
    assert pick_manual_subtitle("youtube", _info("en", ["de", "en"])) == "en"


def test_a_regional_language_matches_its_primary_code():
    assert pick_manual_subtitle("youtube", _info("en-US", ["en", "fr"])) == "en"


def test_without_a_language_the_video_is_transcribed():
    # yt-dlp often reports no language (3 of 4 checked videos, 2026-09-27): never guess.
    assert pick_manual_subtitle("youtube", _info(None, ["zh-CN", "en"])) is None


def test_automatic_captions_do_not_count():
    assert pick_manual_subtitle("youtube", _info("en", [], automatic=["en", "en-orig"])) is None


def test_live_chat_is_not_a_subtitle():
    assert pick_manual_subtitle("youtube", _info("en", ["live_chat"])) is None


def test_simplified_chinese_is_preferred():
    assert pick_manual_subtitle("youtube", _info("zh", ["zh-TW", "en", "zh-CN"])) == "zh-CN"
    assert pick_manual_subtitle("youtube", _info("zh-TW", ["zh-TW", "zh-Hans"])) == "zh-TW"


def test_bilibili_is_always_transcribed():
    assert pick_manual_subtitle("bilibili", _info("zh", ["zh-CN"])) is None


VTT = """WEBVTT
Kind: captions
Language: en

00:00:12.920 --> 00:00:17.136 align:start position:0%
What if I told you there was something
that you can do right now

00:00:17.160 --> 00:00:20.856
<i>that would</i> help &amp; heal

00:21.000 --> 00:22.000
(Laughter)

00:00:23.000 --> 00:00:24.000

"""


def test_vtt_cues_become_segments_in_seconds():
    assert parse_vtt(VTT) == [
        {"start": 12.92, "end": 17.136, "text": "What if I told you there was something that you can do right now"},
        {"start": 17.16, "end": 20.856, "text": "that would help & heal"},
        {"start": 21.0, "end": 22.0, "text": "(Laughter)"},
    ]
