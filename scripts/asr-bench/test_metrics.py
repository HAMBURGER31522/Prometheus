"""Scoring rules for the ASR shoot-out (PLAN 15.4.3)."""

from metrics import punctuation_per_100, score_en, score_zh, subtitle_text

ZH_VTT = """WEBVTT
Kind: captions
Language: zh-CN

00:00:02.039 --> 00:00:02.840
這是你打開B站

00:00:02.840 --> 00:00:04.360
每天可以看到的
推荐视频
"""

EN_VTT = """WEBVTT
Kind: captions
Language: en

00:00:12.920 --> 00:00:17.136
What if I told you there was something
that you can do right now

00:00:17.160 --> 00:00:20.856
that would help.
"""


def test_subtitle_text_keeps_only_the_words():
    assert subtitle_text(ZH_VTT, "zh") == "這是你打開B站每天可以看到的推荐视频"
    assert subtitle_text(EN_VTT, "en") == (
        "What if I told you there was something that you can do right now that would help."
    )


def test_subtitle_text_drops_sound_annotations():
    vtt = EN_VTT.replace("that would help.", "that would help. (Laughter) [Music]")
    assert subtitle_text(vtt, "en").endswith("that would help.")
    assert subtitle_text(ZH_VTT.replace("推荐视频", "推荐视频（笑）"), "zh").endswith("推荐视频")


def test_chinese_ignores_script_punctuation_and_spaces():
    result = score_zh("這是你打開B站，每天！", "这是 你打开b站 每天")
    assert result["cer"] == 0


def test_chinese_counts_real_character_errors():
    result = score_zh("字幕很重要", "字母很重要")
    assert result["cer"] == 0.2


def test_chinese_number_spelling_is_counted_apart():
    result = score_zh("播放量可以增加7%以上", "播放量可以增加百分之七以上")
    assert result["cer"] == 0
    assert result["number_edits"] > 0


def test_english_ignores_case_and_punctuation():
    result = score_en("Don't stop, it's GOOD.", "dont stop its good")
    assert result["wer"] == 0


def test_english_counts_word_errors():
    result = score_en("the brain changes", "the rain changes")
    assert round(result["wer"], 3) == 0.333


def test_punctuation_density():
    assert punctuation_per_100("你好，世界。") == 50.0
    assert punctuation_per_100("你好世界") == 0.0
