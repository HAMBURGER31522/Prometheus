"""Subtitle paragraphs of 10–15 seconds (PLAN 15.4.10): whisper and 必剪 cut speech into
fragments (「对吧，」 on its own line); the subtitles are read as paragraphs instead."""

import random
from itertools import pairwise

from prometheus.subtitle import paragraphs
from prometheus.subtitle.paragraphs import group_segments


def _segments(rows):
    """[(start, end, text)] -> segments."""
    return [{"start": start, "end": end, "text": text} for start, end, text in rows]


def _ink(segments) -> str:
    """Every character except whitespace, in order: grouping may only add or drop spaces."""
    return "".join("".join(segment["text"].split()) for segment in segments)


def _spans(grouped):
    return [(paragraph["start"], paragraph["end"], paragraph["text"]) for paragraph in grouped]


def _assert_invariants(fine, grouped):
    assert _ink(grouped) == _ink(fine), "a character was lost or changed"
    assert all(paragraph["end"] - paragraph["start"] <= 15 for paragraph in grouped)
    assert all(paragraph["start"] <= paragraph["end"] for paragraph in grouped)
    assert all(a["end"] <= b["start"] for a, b in pairwise(grouped)), "times go backwards"
    assert all(set(paragraph) <= {"start", "end", "text", "zh"} for paragraph in grouped)


# --- where a paragraph ends --------------------------------------------------------------

def test_a_paragraph_ends_at_the_first_sentence_end_after_10_seconds():
    fine = _segments([
        (0.0, 2.0, "大家好，"), (2.0, 4.0, "今天聊聊"), (4.0, 6.0, "钱怎么流动。"),  # a full stop at 6 s is too early
        (6.0, 8.0, "对吧，"), (8.0, 10.5, "一个国家的钱"), (10.5, 12.0, "分成三份。"),
        (12.0, 14.0, "然后呢"), (14.0, 16.0, "我们接着看。"),
    ])
    assert _spans(group_segments(fine)) == [
        (0.0, 12.0, "大家好，今天聊聊钱怎么流动。对吧，一个国家的钱分成三份。"),
        (12.0, 16.0, "然后呢我们接着看。"),
    ]


def test_without_a_sentence_end_by_15_seconds_it_ends_at_the_last_comma():
    fine = _segments([
        (0.0, 3.0, "第一段话"), (3.0, 6.0, "说到这里，"), (6.0, 9.0, "还没说完"), (9.0, 12.0, "继续说，"),
        (12.0, 14.5, "还是没完"), (14.5, 17.0, "终于完了。"), (17.0, 19.0, "下一句。"),
    ])
    assert _spans(group_segments(fine)) == [
        (0.0, 12.0, "第一段话说到这里，还没说完继续说，"),
        (12.0, 19.0, "还是没完终于完了。下一句。"),
    ]


def test_without_any_punctuation_it_ends_at_the_last_boundary_within_15_seconds():
    fine = _segments([
        (0.0, 4.0, "so what we"), (4.0, 8.0, "want to do"), (8.0, 12.0, "is look at"),
        (12.0, 14.9, "the numbers"), (14.9, 18.0, "and then decide"), (18.0, 20.0, "what to do next"),
    ])
    assert _spans(group_segments(fine)) == [
        (0.0, 14.9, "so what we want to do is look at the numbers"),
        (14.9, 20.0, "and then decide what to do next"),
    ]


def test_a_paragraph_ends_early_when_the_next_segment_would_pass_15_seconds():
    fine = _segments([
        (0.0, 3.0, "开头一句"), (3.0, 6.0, "接着一句"), (6.0, 19.0, "这是一个十三秒长的分段。"), (19.0, 21.0, "结尾。"),
    ])
    assert _spans(group_segments(fine)) == [
        (0.0, 6.0, "开头一句接着一句"),
        (6.0, 19.0, "这是一个十三秒长的分段。"),
        (19.0, 21.0, "结尾。"),
    ]


def test_a_sentence_end_before_10_seconds_is_a_break_like_a_comma():
    # 「到 15 秒还没遇到句末，就在最后一个逗号类标点处结束」: a full stop is at least as good a break.
    fine = _segments([(0.0, 4.0, "first,"), (4.0, 8.0, "second."), (8.0, 13.0, "third"), (13.0, 17.0, "fourth.")])
    assert _spans(group_segments(fine)) == [(0.0, 8.0, "first, second."), (8.0, 17.0, "third fourth.")]


def test_the_end_of_the_transcript_stays_together_when_it_fits():
    fine = _segments([(0.0, 2.0, "好的，"), (2.0, 5.0, "我们开始吧")])
    assert _spans(group_segments(fine)) == [(0.0, 5.0, "好的，我们开始吧")]
    assert group_segments([{"start": 1.0, "end": 2.5, "text": "这是字幕"}]) == [
        {"start": 1.0, "end": 2.5, "text": "这是字幕"}]
    assert group_segments([]) == []


def test_a_sentence_end_inside_closing_quotes_counts():
    fine = _segments([(0.0, 5.0, "and then he said"), (5.0, 11.0, '"stop right there."'), (11.0, 13.0, "So we did")])
    assert _spans(group_segments(fine)) == [
        (0.0, 11.0, 'and then he said "stop right there."'),
        (11.0, 13.0, "So we did"),
    ]


# --- segments longer than 15 seconds ------------------------------------------------------

def test_a_long_segment_is_split_at_punctuation_with_times_by_character_count():
    # 6 + 9 + 15 characters over 30 seconds: one second per character.
    fine = _segments([(0.0, 30.0, "我们先看封面，封面上是三棵生命树，中间这棵是基督教卡巴拉的生命树。")])
    grouped = group_segments(fine)
    assert _spans(grouped) == [
        (0.0, 15.0, "我们先看封面，封面上是三棵生命树，"),
        (15.0, 30.0, "中间这棵是基督教卡巴拉的生命树。"),
    ]
    _assert_invariants(fine, grouped)


def test_a_long_segment_without_punctuation_is_split_evenly_by_characters():
    fine = _segments([(10.0, 40.0, "卡巴拉" * 15)])
    grouped = group_segments(fine)
    assert [(p["start"], p["end"], len(p["text"])) for p in grouped] == [
        (10.0, 20.0, 15), (20.0, 30.0, 15), (30.0, 40.0, 15)]
    _assert_invariants(fine, grouped)


def test_an_english_segment_is_never_cut_inside_a_word():
    text = "the rate went from 3.5 to 4.2 percent over the years and nobody in the room noticed it at all"
    fine = _segments([(0.0, 20.0, text)])
    grouped = group_segments(fine)
    assert len(grouped) == 2
    assert [word for paragraph in grouped for word in paragraph["text"].split()] == text.split()
    _assert_invariants(fine, grouped)


# --- joining ------------------------------------------------------------------------------

def test_english_is_joined_with_spaces_and_chinese_directly():
    english = _segments([(0.0, 2.6, " How could we"), (2.6, 4.0, " use AI"), (4.0, 5.0, " to learn better?")])
    assert _spans(group_segments(english)) == [(0.0, 5.0, "How could we use AI to learn better?")]
    mixed = _segments([(0.0, 1.0, "我们用"), (1.0, 2.0, "GPT"), (2.0, 3.0, "写代码，"), (3.0, 4.0, "AI Agent"),
                       (4.0, 5.0, "也行。")])
    assert _spans(group_segments(mixed)) == [(0.0, 5.0, "我们用GPT写代码，AI Agent也行。")]


def test_translations_are_joined_in_order():
    fine = [
        {"start": 0.0, "end": 2.0, "text": "Money moves", "zh": "钱在流动，"},
        {"start": 2.0, "end": 4.0, "text": "between pockets."},
        {"start": 4.0, "end": 6.0, "text": "Three of them.", "zh": "一共三个口袋。"},
    ]
    assert group_segments(fine) == [
        {"start": 0.0, "end": 6.0, "text": "Money moves between pockets. Three of them.", "zh": "钱在流动，一共三个口袋。"}]
    assert "zh" not in group_segments(_segments([(0.0, 2.0, "no translation")]))[0]


# --- invariants on generated transcripts -----------------------------------------------------

def _random_transcript(rng, english: bool):
    vocabulary = (["money", "country", "pocket", "the", "and", "3.5", "percent", "we", "go", "sitting"]
                  if english else list("我们今天聊一聊钱怎么流动国家企业政府家庭口袋"))
    marks = ["", "", "", ",", ".", "?", "…", ":"] if english else ["", "", "", "，", "。", "？", ",", "、", "；"]
    segments, clock = [], 0.0
    for _ in range(rng.randint(1, 80)):
        long = rng.random() < 0.1
        words = [rng.choice(vocabulary) + (rng.choice(marks) if long else "")
                 for _ in range(rng.randint(20, 60) if long else rng.randint(1, 8))]
        text = (" " if english else "").join(words) + rng.choice(marks)
        if english and rng.random() < 0.3:
            text = " " + text  # whisper's leading space
        start = round(clock + (rng.uniform(0, 3) if rng.random() < 0.2 else 0.0), 3)
        end = round(start + (rng.uniform(16, 50) if long else rng.uniform(0.2, 4.0)), 3)
        segments.append({"start": start, "end": end, "text": text})
        clock = end
    return segments


def test_nothing_is_lost_no_paragraph_passes_15_seconds_and_times_only_go_forward():
    rng = random.Random(20260927)
    for round_ in range(300):
        english = round_ % 2 == 0
        fine = _random_transcript(rng, english)
        grouped = group_segments(fine)
        _assert_invariants(fine, grouped)
        assert len(grouped) <= len(fine) + sum(int((s["end"] - s["start"]) // 15) + 20 for s in fine)
        if english:  # no word is ever cut in two
            assert ([word for p in grouped for word in p["text"].split()]
                    == [word for s in fine for word in s["text"].split()])


def test_short_fragments_become_fewer_longer_paragraphs():
    rng = random.Random(7)
    fine, clock = [], 0.0
    for _ in range(400):  # like the 104-minute sample: about 1.3 s and 8 characters each
        duration = rng.uniform(0.5, 2.2)
        fine.append({"start": round(clock, 3), "end": round(clock + duration, 3),
                     "text": "一段话" + rng.choice(["", "", "，", "。"])})
        clock += duration
    grouped = group_segments(fine)
    _assert_invariants(fine, grouped)
    durations = sorted(p["end"] - p["start"] for p in grouped)
    assert len(grouped) < len(fine) / 5
    assert durations[len(durations) // 2] >= 10


# --- the raw transcript uses the corrected version's boundaries ---------------------------------

def test_the_raw_transcript_is_grouped_with_the_corrected_boundaries():
    shown = _segments([(0.0, 2.0, "大家好，"), (2.0, 11.0, "今天聊聊钱怎么流动。"), (11.0, 13.0, "对吧，"),
                       (13.0, 16.0, "我们接着看")])
    raw = _segments([(0.0, 2.0, "大家好"), (2.0, 11.0, "今天聊聊钱怎么留动"), (11.0, 13.0, "对吧"),
                     (13.0, 16.0, "我们接着看")])
    grouped, raw_grouped = paragraphs.group_pair(shown, raw)
    assert _spans(grouped) == [(0.0, 11.0, "大家好，今天聊聊钱怎么流动。"), (11.0, 16.0, "对吧，我们接着看")]
    # On its own the unpunctuated raw text would be cut at 13 s instead.
    assert _spans(raw_grouped) == [(0.0, 11.0, "大家好今天聊聊钱怎么留动"), (11.0, 16.0, "对吧我们接着看")]


def test_a_long_segment_is_cut_at_the_same_place_in_both_versions():
    shown = _segments([(0.0, 30.0, "我们先看封面，封面上是三棵生命树，中间这棵是基督教卡巴拉的生命树。")])
    raw = _segments([(0.0, 30.0, "我们先看风面封面上是三颗生命树中间这棵是基督教卡巴拉的生命树")])
    grouped, raw_grouped = paragraphs.group_pair(shown, raw)
    assert [(p["start"], p["end"]) for p in raw_grouped] == [(p["start"], p["end"]) for p in grouped]
    assert [p["text"] for p in raw_grouped] == ["我们先看风面封面上是三颗生命树", "中间这棵是基督教卡巴拉的生命树"]


def test_translations_stay_with_the_corrected_version():
    shown = [{"start": 0.0, "end": 2.0, "text": "Hello there.", "zh": "你好。"},
             {"start": 2.0, "end": 4.0, "text": "How are you?", "zh": "你好吗？"}]
    raw = _segments([(0.0, 2.0, "hello there"), (2.0, 4.0, "how are you")])
    grouped, raw_grouped = paragraphs.group_pair(shown, raw)
    assert grouped == [{"start": 0.0, "end": 4.0, "text": "Hello there. How are you?", "zh": "你好。你好吗？"}]
    assert raw_grouped == [{"start": 0.0, "end": 4.0, "text": "hello there how are you"}]


def test_a_raw_transcript_that_does_not_match_is_grouped_on_its_own():
    shown = _segments([(0.0, 2.0, "大家好，"), (2.0, 11.0, "今天聊聊钱怎么流动。"), (11.0, 16.0, "对吧")])
    raw = _segments([(0.0, 4.0, "大家好"), (4.0, 8.0, "今天聊聊"), (8.0, 13.0, "钱怎么留动"), (13.0, 16.0, "对吧")])
    grouped, raw_grouped = paragraphs.group_pair(shown, raw)
    assert _spans(grouped) == [(0.0, 11.0, "大家好，今天聊聊钱怎么流动。"), (11.0, 16.0, "对吧")]
    assert raw_grouped == group_segments(raw)
    assert _spans(raw_grouped) == [(0.0, 13.0, "大家好今天聊聊钱怎么留动"), (13.0, 16.0, "对吧")]
