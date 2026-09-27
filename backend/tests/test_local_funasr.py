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


def test_fewer_timestamps_than_tokens_are_spread_over_the_tokens():
    # Real paraformer output: fillers such as 啊 (and "O K") can come without a timestamp.
    tokens = list("我们用必剪啊非常纯粹")
    times = _times(9)  # one short
    segments = build_segments(tokens, times, "我们用必剪啊，非常纯粹。", offset_s=0)
    assert "".join(s["text"] for s in segments) == "我们用必剪啊，非常纯粹。"
    assert segments[0]["start"] == 0 and segments[-1]["end"] == 1.8


def test_transcribe_array_punctuates_once_across_vad_spans():
    # A sentence cut by the VAD must not get a full stop at the cut (seen on the R5 sample).
    import numpy as np
    from prometheus.transcribe.local_funasr import transcribe_array

    audio = np.zeros(16000 * 10, dtype=np.float32)
    punctuated = []

    def vad(waveform):
        return [[[1000, 3000], [4000, 4500], [5000, 7000]]]

    answers = iter([
        {"preds": "我 们 分 析 做 字", "timestamp": _times(6, step=100)},
        {"preds": "", "timestamp": []},
        {"preds": "幕 这 件 事", "timestamp": _times(4, step=100)},
    ])

    def asr(piece):
        return [next(answers)]

    def punc(text):
        punctuated.append(text)
        return ("我们分析做字幕这件事。", [])

    segments = transcribe_array(audio, vad=vad, asr=asr, punc=punc)
    assert punctuated == ["我 们 分 析 做 字 幕 这 件 事"]
    assert [s["text"] for s in segments] == ["我们分析做字幕这件事。"]
    assert segments[0]["start"] == 1.0 and segments[0]["end"] == 5.4


def test_only_mandarin_goes_to_funasr():
    from prometheus.transcribe.local_funasr import choose_engine

    assert choose_engine("zh") == "funasr"
    assert choose_engine("en") == "whisper"
    assert choose_engine("yue") == "whisper"
    assert choose_engine("ja") == "whisper"
