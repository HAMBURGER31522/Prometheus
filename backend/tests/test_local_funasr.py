"""FunASR ONNX output to subtitle segments (PLAN 15.4.4, D-39)."""

from prometheus.transcribe.local_funasr import attach_punctuation, build_segments


def _times(count, step=200, start=0):
    return [[start + i * step, start + (i + 1) * step] for i in range(count)]


def test_punctuation_attaches_to_the_token_before_it():
    tokens = ["这", "是", "b", "站", "每", "天"]
    assert attach_punctuation(tokens, "这是b站，每天。") == ["", "", "", "，", "", "。"]


def test_english_matches_without_case_and_joins_with_spaces():
    tokens = ["i", "am", "wonder", "woman"]
    assert attach_punctuation(tokens, "I am wonder woman.") == ["", "", "", "."]
    segments = build_segments(tokens, _times(4), "I am wonder woman.", offset_s=0)
    assert [s["text"] for s in segments] == ["i am wonder woman."]


def test_sentences_end_at_full_stops_with_times_from_their_characters():
    tokens = list("你好世界再见朋友")
    segments = build_segments(tokens, _times(8), "你好世界。再见朋友！", offset_s=10.0)
    assert [s["text"] for s in segments] == ["你好世界。", "再见朋友！"]
    assert segments[0]["start"] == 10.0 and segments[0]["end"] == 10.8
    assert segments[1]["start"] == 10.8 and segments[1]["end"] == 11.6


def test_long_sentences_split_again_at_commas():
    clause = "一二三四五六七八九十一二三四五六七八九十"  # 20 characters
    tokens = list(clause + clause)
    segments = build_segments(tokens, _times(40, step=100), clause + "，" + clause + "。", offset_s=0)
    assert [s["text"] for s in segments] == [clause + "，", clause + "。"]


def test_sentences_longer_than_eight_seconds_split_at_commas():
    tokens = list("慢慢说话慢慢说话")
    segments = build_segments(tokens, _times(8, step=1500), "慢慢说话，慢慢说话。", offset_s=0)
    assert [s["text"] for s in segments] == ["慢慢说话，", "慢慢说话。"]


def test_short_sentences_keep_their_commas_together():
    tokens = list("你好世界")
    segments = build_segments(tokens, _times(4), "你好，世界。", offset_s=0)
    assert [s["text"] for s in segments] == ["你好，世界。"]


def test_a_mismatched_punctuated_text_loses_no_characters():
    tokens = list("今天天气很好")
    segments = build_segments(tokens, _times(6), "今天气很好。", offset_s=0)
    assert "".join(s["text"] for s in segments).rstrip("。") == "今天天气很好"
