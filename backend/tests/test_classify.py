"""Auto classification: parse, validate, retry, fallback (PLAN 8.6)."""


from prometheus.report.classify import (
    build_classify_prompt,
    classify_report,
    parse_category_response,
    validate_category,
)

EXISTING = ["科技", "历史", "生活"]


def test_parse_category_response():
    assert parse_category_response('{"category": "科技"}') == "科技"
    assert parse_category_response('前言\n{"category": "历史"}\n后记') == "历史"
    assert parse_category_response("不是 JSON") is None
    assert parse_category_response('{"name": "科技"}') is None


def test_validate_category_rules():
    assert validate_category("科技", EXISTING)
    assert validate_category("经济观察", EXISTING)  # 新分类：2-8 汉字
    assert not validate_category("其他", EXISTING)
    assert not validate_category("综合", EXISTING)
    assert not validate_category("杂项", EXISTING)
    assert not validate_category("科", EXISTING)  # 1 字
    assert not validate_category("九个字以上的分类名称超限", EXISTING)


def test_build_classify_prompt_contains_inputs():
    prompt = build_classify_prompt("标题", "导语", ["第一章", "第二章"], EXISTING)
    assert "科技" in prompt and "历史" in prompt
    assert "标题" in prompt and "导语" in prompt
    assert "第一章" in prompt


def test_classify_prefers_existing_and_falls_back(tmp_path):
    def one_shot_ok(work_dir, *, prompt, **kwargs):
        return '{"category": "历史"}'

    assert classify_report(
        tmp_path, "标题", "导语", ["h2"], EXISTING, one_shot=one_shot_ok,
    ) == "历史"

    bad_calls = []

    def one_shot_bad(work_dir, *, prompt, **kwargs):
        bad_calls.append(prompt)
        return "模型胡言乱语"

    assert classify_report(
        tmp_path, "标题", "导语", ["h2"], EXISTING, one_shot=one_shot_bad,
    ) == "未分类"
    assert len(bad_calls) == 2  # 重试一次

    state = {"n": 0}

    def one_shot_then_good(work_dir, *, prompt, **kwargs):
        state["n"] += 1
        return "坏输出" if state["n"] == 1 else '{"category": "经济观察"}'

    assert classify_report(
        tmp_path, "标题", "导语", ["h2"], EXISTING, one_shot=one_shot_then_good,
    ) == "经济观察"


def test_classify_rejects_forbidden_names(tmp_path):
    def one_shot_forbidden(work_dir, *, prompt, **kwargs):
        return '{"category": "杂项"}'

    assert classify_report(
        tmp_path, "标题", "导语", ["h2"], EXISTING, one_shot=one_shot_forbidden,
    ) == "未分类"
