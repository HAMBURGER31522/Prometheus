"""Subtitle correction after the report (PLAN 15.4.6, D-37). The model is faked."""

import json

import pytest
from prometheus.subtitle import fix


def _segments(texts, step=2.0):
    return [{"start": i * step, "end": (i + 1) * step, "text": text} for i, text in enumerate(texts)]


# --- the per-segment limit -------------------------------------------------------------

def test_a_homophone_fix_is_accepted():
    assert fix.accept("那么一点点管中亏报但是我希望", "那么一点点管中窥豹，但是我希望。")


def test_punctuation_only_changes_are_accepted():
    assert fix.accept("这是你打开B站每天可以看到的推荐视频", "这是你打开B站，每天可以看到的推荐视频。")


def test_a_rewrite_is_rejected():
    assert not fix.accept("我们发现很少有统计型的视频", "调查显示相关数据分析内容较为缺乏。")


def test_short_segments_may_change_two_characters():
    assert fix.accept("字目", "字幕")
    assert not fix.accept("字目", "完全不同")


def test_an_emptied_segment_is_rejected():
    assert not fix.accept("那只不过", "")


# --- replies -------------------------------------------------------------------------------

def test_the_reply_is_the_first_json_object_despite_noise():
    assert fix.parse_reply('好的：\n```json\n{"0": "你好。", "1": "世界。"}\n```') == {"0": "你好。", "1": "世界。"}


def test_a_reply_without_json_is_none():
    assert fix.parse_reply("抱歉，我无法完成") is None


# --- prompts ---------------------------------------------------------------------------------

def test_the_prompt_carries_rules_reference_and_segments():
    prompt = fix.build_prompt({"3": "管中亏报"}, "# 报告\n管中窥豹", human=False)
    assert "同音" in prompt and "标点" in prompt and "只输出 JSON" in prompt
    assert "管中窥豹" in prompt and '"3": "管中亏报"' in prompt


def test_human_subtitles_only_get_punctuation():
    assert "只补标点" in fix.build_prompt({"0": "你好"}, "", human=True)


def test_the_reference_is_capped():
    prompt = fix.build_prompt({"0": "你好"}, "字" * 20000, human=False)
    assert prompt.count("字") <= fix.MAX_REFERENCE + 200


# --- batches -------------------------------------------------------------------------------

def _echo(fixups=None, calls=None):
    """A fake model: echoes every segment with a full stop, applying ``fixups`` {old: new}."""
    def ask(prompt):
        if calls is not None:
            calls.append(prompt)
        batch = json.loads(prompt[prompt.index(fix.SEGMENTS_MARK) + len(fix.SEGMENTS_MARK):])
        return json.dumps({key: (fixups or {}).get(text, text) + "。" for key, text in batch.items()},
                          ensure_ascii=False)
    return ask


def test_segments_go_in_batches_of_at_most_120():
    calls = []
    segments = _segments([f"第{i}句话" for i in range(250)])
    fixed, stats = fix.fix_segments(segments, "", human=False, ask=_echo(calls=calls))
    assert len(calls) == 3
    assert [s["text"] for s in fixed] == [f"第{i}句话。" for i in range(250)]
    assert [(s["start"], s["end"]) for s in fixed] == [(s["start"], s["end"]) for s in segments]
    assert stats["changed"] == 250 and stats["failed_batches"] == 0


def _batch_sizes(calls):
    return [len(json.loads(call[call.index(fix.SEGMENTS_MARK) + len(fix.SEGMENTS_MARK):])) for call in calls]


def test_long_paragraphs_go_in_batches_of_about_2500_characters():
    # 「每次最多 120 段（约 2500 字）」: a 10–15 s paragraph (PLAN 15.4.10) holds far more than a fragment.
    calls = []
    fixed, stats = fix.fix_segments(_segments(["字" * 600] * 12), "", human=False, ask=_echo(calls=calls))
    assert _batch_sizes(calls) == [4, 4, 4]
    assert [s["text"] for s in fixed] == ["字" * 600 + "。"] * 12 and stats["failed_batches"] == 0


def test_translated_paragraphs_go_in_batches_of_about_1250_characters():
    calls = []
    _fixed, stats = fix.fix_segments(_segments(["word " * 80] * 10), "", human=False, ask=_translator(calls),
                                     translate=True)
    assert _batch_sizes(calls) == [3, 3, 3, 1]
    assert stats["translated"] == 10


def test_rejected_and_missing_segments_keep_their_text():
    segments = _segments(["管中亏报", "我们发现很少有统计型的视频", "那只不过"])

    def ask(prompt):
        return json.dumps({"0": "管中窥豹。", "1": "调查显示相关数据分析内容较为缺乏。"}, ensure_ascii=False)

    fixed, stats = fix.fix_segments(segments, "", human=False, ask=ask)
    assert [s["text"] for s in fixed] == ["管中窥豹。", "我们发现很少有统计型的视频", "那只不过"]
    assert stats["changed"] == 1 and stats["rejected"] == 2


def test_an_unreadable_batch_is_retried_once_then_kept():
    answers = iter(["不是 JSON", "还是不是"])
    segments = _segments(["你好", "世界"])
    fixed, stats = fix.fix_segments(segments, "", human=False, ask=lambda prompt: next(answers))
    assert [s["text"] for s in fixed] == ["你好", "世界"]
    assert stats["failed_batches"] == 1


def test_a_retry_that_answers_is_used():
    answers = iter(["不是 JSON", '{"0": "你好。"}'])
    fixed, stats = fix.fix_segments(_segments(["你好"]), "", human=False, ask=lambda prompt: next(answers))
    assert fixed[0]["text"] == "你好。" and stats["failed_batches"] == 0


# --- the item ------------------------------------------------------------------------------

@pytest.fixture
def item(tmp_path, monkeypatch):
    from prometheus import paths
    from prometheus.library import db
    from prometheus.library import items as items_store

    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    item_id = items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                      source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/",
                                      status="running")
    paths.segments_file(data_dir, item_id).write_text(
        json.dumps(_segments(["管中亏报", "字目这件事"]), ensure_ascii=False), encoding="utf-8")
    report = paths.report_file(data_dir, item_id)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("<html><body><h1>字幕调研</h1><p>管中窥豹，做字幕这件事。</p></body></html>",
                      encoding="utf-8")
    return data_dir, item_id


def _run(data_dir, item_id, ask, monkeypatch):
    from prometheus.library import items as items_store

    monkeypatch.setattr(fix, "_ask_model", lambda data_dir_, llm, *, node_exe, pi_cli: ask)
    return fix.fix_for_item(data_dir, item_id, items_store.get_item(data_dir, item_id),
                            {"provider": "deepseek", "model": "m"}, node_exe="node.exe", pi_cli="cli.js")


def test_the_item_keeps_the_raw_transcript_and_shows_the_fixed_one(item, monkeypatch):
    from prometheus import paths
    from prometheus.library import items as items_store

    data_dir, item_id = item
    assert _run(data_dir, item_id, _echo({"管中亏报": "管中窥豹", "字目这件事": "字幕这件事"}), monkeypatch) is True
    shown = json.loads(paths.segments_file(data_dir, item_id).read_text(encoding="utf-8"))
    raw = json.loads(paths.raw_segments_file(data_dir, item_id).read_text(encoding="utf-8"))
    assert [s["text"] for s in shown] == ["管中窥豹。", "字幕这件事。"]
    assert [s["text"] for s in raw] == ["管中亏报", "字目这件事"]
    assert items_store.get_item(data_dir, item_id).get("subtitle_status") == "ok"


def test_a_rerun_starts_from_the_raw_transcript(item, monkeypatch):
    from prometheus import paths

    data_dir, item_id = item
    _run(data_dir, item_id, _echo(), monkeypatch)
    seen = []
    _run(data_dir, item_id, _echo(calls=seen), monkeypatch)
    assert seen, "the second run must ask the model again"
    assert "管中亏报" in seen[0] and "管中亏报。" not in seen[0]
    shown = json.loads(paths.segments_file(data_dir, item_id).read_text(encoding="utf-8"))
    assert [s["text"] for s in shown] == ["管中亏报。", "字目这件事。"]


def test_a_model_error_leaves_the_subtitles_alone(item, monkeypatch):
    from prometheus import paths
    from prometheus.library import items as items_store

    data_dir, item_id = item

    def down(prompt):
        raise RuntimeError("502 Bad Gateway")

    assert _run(data_dir, item_id, down, monkeypatch) is False
    shown = json.loads(paths.segments_file(data_dir, item_id).read_text(encoding="utf-8"))
    assert [s["text"] for s in shown] == ["管中亏报", "字目这件事"]
    assert items_store.get_item(data_dir, item_id).get("subtitle_status") == "failed"


def test_the_stage_runs_between_finalize_and_mindmap():
    from prometheus.tasks.runner import STAGES

    assert "subtitle_fix" in STAGES
    assert STAGES.index("subtitle_fix") == STAGES.index("finalize") + 1
    assert STAGES.index("mindmap") == STAGES.index("subtitle_fix") + 1


def test_the_raw_transcript_survives_cleanup():
    from prometheus.tasks.cleanup import KEEP

    assert "segments.raw.json" in KEEP


def test_the_api_serves_the_raw_transcript_on_request(client):
    from conftest import BV_URL, wait_for_status
    from prometheus import paths

    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    wait_for_status(client, item_id, "done")
    data_dir = client.app.state.data_dir
    paths.raw_segments_file(data_dir, item_id).write_text(
        json.dumps(_segments(["原始识别"]), ensure_ascii=False), encoding="utf-8")
    raw = client.get(f"/api/items/{item_id}/subtitle", params={"variant": "raw"}).json()
    assert [s["text"] for s in raw] == ["原始识别"]
    shown = client.get(f"/api/items/{item_id}/subtitle").json()
    assert [s["text"] for s in shown] != ["原始识别"]


# --- 中外对照 (PLAN 15.4.9) ---------------------------------------------------------------------

def test_a_translation_must_be_chinese_and_about_the_same_size():
    assert fix.accept_translation("Money moves between three pockets.", "钱在三个口袋之间流动。")
    assert fix.accept_translation("Israel Regardie.", "以色列·雷加迪。")
    assert not fix.accept_translation("Hello there.", "")
    assert not fix.accept_translation("Hello there.", "Hello there.")
    assert not fix.accept_translation("Yes.", "是的。我们接下来还会讲很多很多其他相关的内容。")


def test_the_translating_prompt_asks_for_zh_in_the_same_reply():
    prompt = fix.build_prompt({"0": "hello"}, "", human=False, translate=True)
    assert "中文翻译" in prompt and '"zh"' in prompt
    assert "中文翻译" not in fix.build_prompt({"0": "你好"}, "", human=False)


def _translator(calls=None):
    """A fake model that corrects (adds a full stop) and translates every segment."""
    def ask(prompt):
        if calls is not None:
            calls.append(prompt)
        batch = json.loads(prompt[prompt.index(fix.SEGMENTS_MARK) + len(fix.SEGMENTS_MARK):])
        return json.dumps({key: {"text": text + ".", "zh": f"第{key}句的译文。"} for key, text in batch.items()},
                          ensure_ascii=False)
    return ask


def test_translated_segments_carry_zh_under_the_corrected_text():
    calls = []
    segments = _segments([f"sentence number {i}" for i in range(70)])
    fixed, stats = fix.fix_segments(segments, "", human=False, ask=_translator(calls), translate=True)
    assert len(calls) == 2, "the reply carries two texts per segment, so batches are smaller"
    assert fixed[0] == {"start": 0.0, "end": 2.0, "text": "sentence number 0.", "zh": "第0句的译文。"}
    assert stats["translated"] == 70


def test_a_bad_translation_is_dropped_and_the_text_still_corrected():
    def ask(prompt):
        return json.dumps({"0": {"text": "Hello there.", "zh": "Hello there."}, "1": "Goodbye."}, ensure_ascii=False)

    fixed, stats = fix.fix_segments(_segments(["hello there", "goodbye"]), "", human=False, ask=ask, translate=True)
    assert fixed[0]["text"] == "Hello there." and "zh" not in fixed[0]
    assert fixed[1]["text"] == "Goodbye." and "zh" not in fixed[1]
    assert stats["translated"] == 0


def test_only_a_non_chinese_transcript_is_translated(item, monkeypatch):
    from prometheus import paths

    data_dir, item_id = item
    asr = paths.work_dir(data_dir, item_id) / "asr.json"
    asr.write_text(json.dumps({"language": "en", "segments": []}), encoding="utf-8")
    seen = []
    assert _run(data_dir, item_id, _translator(seen), monkeypatch) is True
    assert "中文翻译" in seen[0]
    shown = json.loads(paths.segments_file(data_dir, item_id).read_text(encoding="utf-8"))
    assert [s.get("zh") for s in shown] == ["第0句的译文。", "第1句的译文。"]

    asr.write_text(json.dumps({"language": "zh", "segments": []}), encoding="utf-8")
    seen.clear()
    assert _run(data_dir, item_id, _echo(calls=seen), monkeypatch) is True
    assert seen and "中文翻译" not in seen[0]
    shown = json.loads(paths.segments_file(data_dir, item_id).read_text(encoding="utf-8"))
    assert not any("zh" in s for s in shown)


def test_a_translating_batch_without_any_translation_is_asked_again():
    # Live run 2026-09-27: one batch of an English video came back corrected but untranslated.
    answers = iter([
        json.dumps({"0": "Hello there.", "1": "Goodbye."}),
        json.dumps({"0": {"text": "Hello there.", "zh": "你好。"}, "1": {"text": "Goodbye.", "zh": "再见。"}},
                   ensure_ascii=False),
    ])
    fixed, stats = fix.fix_segments(_segments(["hello there", "goodbye"]), "", human=False,
                                    ask=lambda prompt: next(answers), translate=True)
    assert [s.get("zh") for s in fixed] == ["你好。", "再见。"]
    assert stats["translated"] == 2


def test_the_translating_prompt_repeats_the_format_after_the_reference():
    # Live run 2026-09-27: some batches came back corrected but untranslated, twice in a row.
    # The format line sits before a report of up to 12k characters; say it again near the end.
    prompt = fix.build_prompt({"0": "hello"}, "# 报告\n" + "正文" * 3000, human=False, translate=True)
    tail = prompt[prompt.index("参考材料（报告）："):prompt.index(fix.SEGMENTS_MARK)]
    assert '"zh"' in tail and "每一段都要有中文翻译" in tail
