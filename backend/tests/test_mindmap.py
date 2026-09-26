"""Mindmap outline extraction, links and validation (PLAN 8.8, M6)."""

from pathlib import Path

from prometheus.report.mindmap import (
    build_mindmap_prompt,
    extract_outline,
    moment_link,
    validate_mindmap,
)


def load_example():

    example = Path("vendor/video-report-agent/docs/examples/report.html")
    return extract_outline(example.read_text(encoding="utf-8"))


def test_extract_outline_from_vendor_example():
    outline = load_example()
    assert outline["title"] == "削藩与分配：中国财政再平衡的逻辑与路径"
    assert 3 <= len(outline["sections"]) <= 9
    first = outline["sections"][0]
    assert "思想实验" in first["title"]
    assert first["start_label"] == "00:00"
    assert first["h3"], "example report has h3 sections"
    assert outline["intro"]


def test_moment_links_both_platforms():
    bilibili = moment_link("bilibili", "BV1xJYT6EEYc?p=3", 322.0)
    assert bilibili == "https://www.bilibili.com/video/BV1xJYT6EEYc/?p=3&t=322"
    youtube = moment_link("youtube", "jNQXAC9IVRw", 47.0)
    assert youtube == "https://www.youtube.com/watch?v=jNQXAC9IVRw&t=47s"


def test_validate_mindmap_accepts_good_map():
    text = """# 削藩与分配

## 口袋思想实验 [00:00](https://www.bilibili.com/video/BV1xJYT6EEYc/?p=1&t=0)

- 三个口袋
- 分封制的闭环

## 谁是藩 [02:26](https://www.bilibili.com/video/BV1xJYT6EEYc/?p=1&t=146)

- 制度性闭环

## 1994 分税制 [06:44](https://www.bilibili.com/video/BV1xJYT6EEYc/?p=1&t=404)

### 包干制

- 中央财政吃紧
"""
    errors = validate_mindmap(text, expect_title="削藩与分配")
    assert errors == []


def test_validate_mindmap_rejects_branch_count_and_missing_links():
    text = """# 标题

## 只有一个分支没有链接

- 内容
"""
    errors = validate_mindmap(text, expect_title="标题")
    assert any("一级分支数量" in e for e in errors)
    assert any("时间链接" in e for e in errors)


def test_validate_mindmap_rejects_long_nodes_and_depth():
    long_node = "超" * 41
    text = f"""# 标题

## 分支一 [00:00](https://www.bilibili.com/video/BV1xJYT6EEYc/?p=1&t=0)

- {long_node}

## 分支二 [00:30](https://www.bilibili.com/video/BV1xJYT6EEYc/?p=1&t=30)

##### 太深了
"""
    errors = validate_mindmap(text, expect_title="标题")
    assert any("40" in e for e in errors)
    assert any("####" in e for e in errors)


def test_prompt_carries_outline_and_rules():
    outline = load_example()
    prompt = build_mindmap_prompt(outline, "bilibili", "BV1xJYT6EEYc")
    assert "3-7" in prompt and "40" in prompt
    assert "削藩与分配" in prompt
    assert "https://www.bilibili.com/video/BV1xJYT6EEYc/?p=1&t=0" in prompt
