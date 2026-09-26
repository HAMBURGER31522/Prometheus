"""SRT/TXT beyond one hour and the zh t2s conversion (PLAN 8.5, D-20)."""

from prometheus.subtitle.convert import maybe_simplify
from prometheus.subtitle.format import to_srt, to_txt


def test_srt_beyond_one_hour():
    segments = [{"start": 3661.5, "end": 3663.0, "text": "超过一小时"}]
    srt = to_srt(segments)
    assert "1\n01:01:01,500 --> 01:01:03,000\n超过一小时\n" in srt


def test_txt_beyond_one_hour():
    segments = [{"start": 3661.5, "end": 3663.0, "text": "超过一小时"}]
    assert "[01:01:01] 超过一小时" in to_txt(segments)


def test_chinese_subtitles_are_simplified():
    segments = [
        {"start": 0.0, "end": 1.0, "text": "這個視頻講得很好"},
        {"start": 1.0, "end": 2.0, "text": "時間軸不變"},
    ]
    converted = maybe_simplify(segments, "zh")
    assert converted[0]["text"] == "这个视频讲得很好"
    assert converted[1]["text"] == "时间轴不变"
    assert converted[0]["start"] == 0.0
    assert converted[1]["end"] == 2.0


def test_non_chinese_subtitles_unchanged():
    segments = [{"start": 0.0, "end": 1.0, "text": "This video stays as-is"}]
    assert maybe_simplify(segments, "en") == segments


def test_already_simplified_chinese_is_stable():
    segments = [{"start": 0.0, "end": 1.0, "text": "本来就是简体"}]
    assert maybe_simplify(segments, "zh")[0]["text"] == "本来就是简体"
